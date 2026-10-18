"""Tuttiphon's own names: environment variables TUTTIPHON_*, the playlist marker, the shared folder .tuttiphon/,
backup file names and the header of the interface."""
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

    def test_own_variables(self):
        with mock.patch.dict(os.environ, {"TUTTIPHON_MODELS": "/modelle"}):
            self.assertEqual(config.env_var("MODELS"), "/modelle")
        self.assertEqual(config.env_var("MODELS", "/standard"), "/standard")

    def test_admin_password_from_the_environment_or_the_env_file(self):
        with mock.patch.dict(os.environ, {"TUTTIPHON_ADMIN_PASSWORD": "aus-der-compose"}):
            env.reset_caches()
            self.assertEqual(config.admin_password(), "aus-der-compose")
            self.assertTrue(auth.required())
            self.assertIn("TUTTIPHON_ADMIN_PASSWORD", config.environment())   # field counts as set by docker-compose
        config.save_env({"TUTTIPHON_ADMIN_PASSWORD": "aus-der-datei"})
        env.reset_caches()
        self.assertEqual(config.admin_password(), "aus-der-datei")
        self.assertEqual(config.ENV_FILE.read_text().strip(), "TUTTIPHON_ADMIN_PASSWORD=aus-der-datei")

    def test_placeholders_are_no_administrator_password(self):
        from app import web
        for placeholder in config.PASSWORD_PLACEHOLDERS:
            with self.assertRaises(ValueError):
                web.api_env_save({"TUTTIPHON_ADMIN_PASSWORD": placeholder})
        with self.assertRaises(ValueError):
            web.api_env_save({"TUTTIPHON_ADMIN_PASSWORD": "kurz"})


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

    def test_marker_means_ours(self):
        nsp = self.write("Auto – Neu.nsp", json.dumps({"name": "Neu", "comment": "Tuttiphon: Kinder × Rock", "all": []}))
        mix = self.write("Mix – Neu.m3u", "#EXTM3U\n#PLAYLIST:Neu\n# Tuttiphon Weekly Mix\n")
        hand = self.write("Handgemacht.nsp", json.dumps({"name": "Hand", "comment": "von Hand", "all": []}))
        self.assertTrue(playlists._has_marker(nsp) and playlists._has_marker(mix))
        self.assertFalse(playlists._has_marker(hand))
        self.assertEqual([x["file"] for x in playlists.handmade(base_config())], ["Handgemacht.nsp"])


class SharedFolderTest(unittest.TestCase):
    def test_hidden_folder_in_the_playlist_folder(self):
        instances._state["dir"] = None
        self.addCleanup(instances._state.update, dir=None)
        with mock.patch.dict(os.environ):
            del os.environ["TUTTIPHON_SHARED_DIR"]
            folder = instances.shared_dir()
        self.assertEqual(folder, playlists.playlist_dir(config.load_config()) / ".tuttiphon")


class BackupTest(unittest.TestCase):
    def test_backups_are_listed_counted_and_downloadable(self):
        cfg = base_config()
        cfg["settings"]["backup"] = {"dir": str(env.ROOT / "sicherungen-namen"), "keep": 2}
        target = backup.folder(cfg)
        target.mkdir(parents=True, exist_ok=True)
        today = dt.date.today()
        names = ["tuttiphon-sicherung-2026-03-01_020000.zip", "tuttiphon-sicherung-2026-03-02_020000.zip",
                 f"tuttiphon-sicherung-{today:%Y-%m-%d}_020000.zip", "andere-sicherung-2026-03-03_020000.zip"]
        for name in names:
            (target / name).write_bytes(b"PK")
        self.assertEqual([x["name"] for x in backup.items(cfg)], names[2::-1])   # by date, newest first, only ours
        self.assertTrue(backup.path_of(names[1], cfg).is_file())
        self.assertTrue(backup.done_today(cfg))
        backup.prune(cfg)
        self.assertEqual(sorted(p.name for p in target.iterdir()), sorted(names[1:]))   # a foreign file stays


def _loopback(address, *args, **kwargs):
    """Only for this test: connections to 127.0.0.1 (otherwise the test environment blocks every network)."""
    if address[0] != "127.0.0.1":
        raise env.NetworkBlocked("only 127.0.0.1")
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(10)
    env._real_connect(s, address)
    return s


class HeaderTest(unittest.TestCase):
    def test_interface_header_required(self):
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
        self.assertEqual(post({"X-Tuttiphon": "0"}), 403)
        self.assertEqual(post({"X-Tuttiphon": "1"}), 404)            # passes the check, path unknown


if __name__ == "__main__":
    unittest.main()
