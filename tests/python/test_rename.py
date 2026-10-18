"""NaviTool becomes Tuttiphon: existing installations keep running without changes – old environment variables
(NAVITOOL_PASSWORD in an old docker-compose.yaml), playlists with the old marker, the shared folder
.navitool/, old backups and an old interface that is still open (header X-NaviTool)."""
from tests.python import env  # noqa: F401  (before app.*)

import datetime as dt
import http.client
import json
import os
import socket
import threading
import unittest
from http.server import ThreadingHTTPServer
from unittest import mock

from app import auth, backup, config, instances, playlists
from tests.python.factory import base_config


class EnvironmentTest(unittest.TestCase):
    def setUp(self):
        env.reset_caches()
        config.ENV_FILE.unlink(missing_ok=True)
        self.addCleanup(config.ENV_FILE.unlink, missing_ok=True)
        self.addCleanup(env.reset_caches)

    def test_old_variable_names_still_count(self):
        with mock.patch.dict(os.environ, {"NAVITOOL_MODELS": "/alt"}):
            self.assertEqual(config.env_var("MODELS"), "/alt")
            with mock.patch.dict(os.environ, {"TUTTIPHON_MODELS": "/neu"}):
                self.assertEqual(config.env_var("MODELS"), "/neu")   # the new name wins
        with mock.patch.dict(os.environ, {"NAVITOOL_PASSWORD": "aus-der-alten-compose"}):
            env.reset_caches()
            self.assertEqual(config.load_env()["TUTTIPHON_PASSWORD"], "aus-der-alten-compose")
            self.assertTrue(auth.required())
            self.assertIn("TUTTIPHON_PASSWORD", config.environment())   # field counts as set by docker-compose

    def test_admin_password_and_its_old_names(self):
        for name in ("TUTTIPHON_ADMIN_PASSWORD", "TUTTIPHON_PASSWORD", "NAVITOOL_PASSWORD"):
            with mock.patch.dict(os.environ, {name: "aus-der-compose"}):
                env.reset_caches()
                self.assertEqual(config.admin_password(), "aus-der-compose", name)
                self.assertTrue(auth.required())
        with mock.patch.dict(os.environ, {"TUTTIPHON_ADMIN_PASSWORD": "neu-und-gut", "TUTTIPHON_PASSWORD": "alt-und-weg"}):
            env.reset_caches()
            self.assertEqual(config.admin_password(), "neu-und-gut")   # the new name wins
        config.ENV_FILE.write_text("TUTTIPHON_PASSWORD=altes-passwort\nNAVITOOL_PASSWORD=noch-aelter\n")
        env.reset_caches()
        self.assertEqual(config.admin_password(), "altes-passwort")
        config.save_env({"TUTTIPHON_ADMIN_PASSWORD": "neues-passwort"})
        text = config.ENV_FILE.read_text()
        self.assertEqual(text.strip(), "TUTTIPHON_ADMIN_PASSWORD=neues-passwort")   # no contradicting old lines
        env.reset_caches()
        self.assertEqual(config.admin_password(), "neues-passwort")

    def test_placeholders_are_no_administrator_password(self):
        from app import web
        for placeholder in config.PASSWORD_PLACEHOLDERS:
            for key in ("TUTTIPHON_ADMIN_PASSWORD", "TUTTIPHON_PASSWORD"):
                with self.assertRaises(ValueError):
                    web.api_env_save({key: placeholder})
        with self.assertRaises(ValueError):
            web.api_env_save({"TUTTIPHON_ADMIN_PASSWORD": "kurz"})

    def test_old_key_in_env_file_and_replacing_it(self):
        config.ENV_FILE.write_text("NAVITOOL_HOSTS=nas.local\nNAVITOOL_PASSWORD=altes-passwort\n")
        env.reset_caches()
        self.assertEqual(config.load_env()["TUTTIPHON_HOSTS"], "nas.local")
        config.save_env({"TUTTIPHON_PASSWORD": "neues-passwort"})
        text = config.ENV_FILE.read_text()
        self.assertIn("TUTTIPHON_ADMIN_PASSWORD=neues-passwort", text)   # saved under the newest name
        self.assertNotIn("NAVITOOL_PASSWORD", text)                  # no two contradicting lines
        self.assertIn("NAVITOOL_HOSTS=nas.local", text)                # everything else stays as it is


class PlaylistMarkerTest(unittest.TestCase):
    def setUp(self):
        self.dir = playlists.playlist_dir(base_config())
        self.dir.mkdir(parents=True, exist_ok=True)
        self.files = []

    def tearDown(self):
        for f in self.files:
            f.unlink(missing_ok=True)

    def write(self, name, text):
        f = self.dir / name
        f.write_text(text)
        self.files.append(f)
        return f

    def test_old_and_new_marker_mean_ours(self):
        old = self.write("Auto – Alt.nsp", json.dumps({"name": "Alt", "comment": "NaviTool: Kinder × Rock", "all": []}))
        new = self.write("Auto – Neu.nsp", json.dumps({"name": "Neu", "comment": "Tuttiphon: Kinder × Rock", "all": []}))
        mix = self.write("Mix – Alt.m3u", "#EXTM3U\n#PLAYLIST:Alt\n# NaviTool Weekly Mix – automatisch erzeugt\n")
        hand = self.write("Handgemacht.nsp", json.dumps({"name": "Hand", "comment": "von Hand", "all": []}))
        self.assertTrue(all(playlists._has_marker(f) for f in (old, new, mix)))
        self.assertFalse(playlists._has_marker(hand))
        self.assertEqual([x["file"] for x in playlists.handmade(base_config())], ["Handgemacht.nsp"])
        self.assertTrue(config.MARKER == "Tuttiphon")                 # new files get the new name


class SharedFolderTest(unittest.TestCase):
    def test_keeps_old_folder_while_only_it_exists(self):
        parent = env.ROOT / "ordnertest"
        (parent / ".navitool").mkdir(parents=True, exist_ok=True)
        self.assertEqual(instances._named(parent).name, ".navitool")
        (parent / ".tuttiphon").mkdir()
        self.assertEqual(instances._named(parent).name, ".tuttiphon")
        self.assertEqual(instances._named(env.ROOT / "leer").name, ".tuttiphon")


class BackupTest(unittest.TestCase):
    def test_old_backups_are_listed_counted_and_downloadable(self):
        cfg = base_config()
        cfg["settings"]["backup"] = {"dir": str(env.ROOT / "sicherungen"), "keep": 2}
        target = backup.folder(cfg)
        target.mkdir(parents=True, exist_ok=True)
        today = dt.date.today()
        for name in ("navitool-sicherung-2026-03-01_020000.zip", "navitool-sicherung-2026-03-02_020000.zip",
                     f"tuttiphon-sicherung-{today:%Y-%m-%d}_020000.zip"):
            (target / name).write_bytes(b"PK")
        names = [x["name"] for x in backup.items(cfg)]
        self.assertEqual(names[0], f"tuttiphon-sicherung-{today:%Y-%m-%d}_020000.zip")   # by date, newest first
        self.assertTrue(backup.path_of("navitool-sicherung-2026-03-02_020000.zip", cfg).is_file())
        self.assertTrue(backup.done_today(cfg))
        backup.prune(cfg)
        self.assertEqual(sorted(p.name for p in target.iterdir()),
                         ["navitool-sicherung-2026-03-02_020000.zip", f"tuttiphon-sicherung-{today:%Y-%m-%d}_020000.zip"])


def _loopback(address, *args, **kwargs):
    """Only for this test: connections to 127.0.0.1 (otherwise the test environment blocks every network)."""
    if address[0] != "127.0.0.1":
        raise env.NetworkBlocked("only 127.0.0.1")
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(10)
    env._real_connect(s, address)
    return s


class HeaderTest(unittest.TestCase):
    def test_old_ui_header_still_accepted(self):
        from app import web
        env.reset_caches()
        server = ThreadingHTTPServer(("127.0.0.1", 0), web.Handler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)

        def post(headers):
            with mock.patch("socket.create_connection", _loopback):
                c = http.client.HTTPConnection("127.0.0.1", server.server_address[1], timeout=10)
                c.request("POST", "/api/gibt-es-nicht", body="{}", headers={"Content-Type": "application/json", **headers})
                status = c.getresponse().status
                c.close()
            return status
        self.assertEqual(post({}), 403)                              # without header: rejected
        self.assertEqual(post({"X-Tuttiphon": "1"}), 404)            # passes the check, path unknown
        self.assertEqual(post({"X-NaviTool": "1"}), 404)             # old interface as well


if __name__ == "__main__":
    unittest.main()
