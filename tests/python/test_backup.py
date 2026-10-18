"""app/backup.py: backup as ZIP – content, permissions, cleanup, names."""
from tests.python import env  # noqa: F401  (before app.*)

import datetime as dt
import os
import shutil
import stat
import time
import unittest
import zipfile
from unittest import mock

from app import backup, config


class BackupTest(unittest.TestCase):
    def setUp(self):
        env.reset_caches()
        self.folder = env.ROOT / "sicherungen-test"
        shutil.rmtree(self.folder, ignore_errors=True)
        self.addCleanup(shutil.rmtree, self.folder, True)
        self.cfg = config.load_config()
        self.cfg["settings"]["backup"] = {"enabled": True, "keep": 14, "dir": str(self.folder)}

    def fake(self, *days):
        self.folder.mkdir(parents=True, exist_ok=True)
        names = [f"{backup.PREFIX}{d}_120000.zip" for d in days]
        for n in names:
            (self.folder / n).write_bytes(b"PK")
        return names

    def names(self):
        return sorted(p.name for p in self.folder.iterdir())


class TestCreate(BackupTest):
    def setUp(self):
        super().setUp()
        made = []

        def put(path, text="x"):
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text)
            made.append(path)
        put(config.ENV_FILE, "NAV_URL=http://test.invalid\n")
        put(config.STATE_DIR / "test-lyrics.json", "{}")
        put(config.STATE_DIR / "test-sub" / "werte.json", "[]")
        put(config.STATE_DIR / "cache" / "img" / "ab" / "bild.png")
        put(config.STATE_DIR / "task.lock", "")
        put(config.STATE_DIR / "instance-pc_test.json", "{}")
        put(config.STATE_DIR / "install_id", "0123456789abcdef\n")
        put(config.STATE_DIR / ".versteckt")
        put(config.STATE_DIR / "halb.json.123.tmp")
        put(config.BACKUP_DIR / "config_v1_test.json", "{}")
        self.sessions_existed = (config.STATE_DIR / "sessions.json").exists()
        if not self.sessions_existed:
            put(config.STATE_DIR / "sessions.json", "{}")

        def cleanup():
            for p in made:
                p.unlink(missing_ok=True)
            shutil.rmtree(config.STATE_DIR / "test-sub", ignore_errors=True)
        self.addCleanup(cleanup)

    def test_content_and_permissions(self):
        log = []
        info = backup.create(self.cfg, log=log.append)
        path = self.folder / info["name"]
        self.assertRegex(info["name"], backup.NAME)
        self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)   # contains credentials
        with zipfile.ZipFile(path) as z:
            names = set(z.namelist())
            self.assertEqual(z.read("config.json"), config.CONFIG_FILE.read_bytes())
            self.assertEqual(z.read(".env"), b"NAV_URL=http://test.invalid\n")
        self.assertEqual(info["files"], len(names))
        self.assertLessEqual({"config.json", ".env", "state/test-lyrics.json", "state/test-sub/werte.json",
                              "backup/config_v1_test.json"}, names)
        for skipped in ("state/cache/img/ab/bild.png", "state/sessions.json", "state/task.lock",
                        "state/instance-pc_test.json", "state/install_id", "state/.versteckt", "state/halb.json.123.tmp"):
            self.assertNotIn(skipped, names)
        self.assertFalse(any(n.startswith(("logs/", "sicherungen")) for n in names))
        self.assertEqual([p.name for p in self.folder.iterdir()], [info["name"]])   # no temporary file left
        self.assertTrue(log and info["name"] in log[-1])

    def test_backup_folder_inside_the_data_folder_does_not_nest(self):
        # e.g. BACKUP_DIR=/config/backup in docker-compose.yaml: the folder of the playlist originals
        made = [config.BACKUP_DIR / "2026-01-01_120000_Lieder.nsp", config.BACKUP_DIR / "notiz.txt",
                config.BACKUP_DIR / "navitool-sicherung-2025-01-01_120000 (1).zip"]
        for p in made:
            p.write_text("x")
            self.addCleanup(p.unlink, missing_ok=True)
        self.cfg["settings"]["backup"]["dir"] = ""

        def ours():
            return sorted(p for p in config.BACKUP_DIR.iterdir() if backup.NAME.match(p.name))
        self.addCleanup(lambda: [p.unlink() for p in ours()])
        with mock.patch.dict(os.environ, {"BACKUP_DIR": str(config.BACKUP_DIR)}):
            self.assertEqual(backup.folder(self.cfg), config.BACKUP_DIR)
            first = backup.create(self.cfg, log=lambda *_: None)
            time.sleep(1.05)   # the name has the time to the second
            second = backup.create(self.cfg, log=lambda *_: None)
        self.assertEqual(len(ours()), 2)
        self.assertEqual(first["files"], second["files"])
        with zipfile.ZipFile(config.BACKUP_DIR / second["name"]) as z:
            names = z.namelist()
        self.assertFalse(any(n.endswith(".zip") for n in names), names)   # never earlier backups
        self.assertIn("backup/2026-01-01_120000_Lieder.nsp", names)
        self.assertIn("backup/config_v1_test.json", names)
        self.assertNotIn("backup/notiz.txt", names)   # backup/ holds only playlist originals and old configurations
        inner = config.STATE_DIR / "sicherungen"   # a folder inside state/: nothing from it
        inner.mkdir()
        self.addCleanup(shutil.rmtree, inner, True)
        (inner / "kopie.bin").write_bytes(b"x" * 1000)
        with mock.patch.dict(os.environ, {"BACKUP_DIR": str(inner)}):
            third = backup.create(self.cfg, log=lambda *_: None)
        with zipfile.ZipFile(inner / third["name"]) as z:
            self.assertFalse([n for n in z.namelist() if n.startswith("state/sicherungen")])

    def test_backup_folder_in_state_or_backup_is_refused(self):
        for bad in (str(config.STATE_DIR / "sicherungen"), str(config.BACKUP_DIR), str(config.STATE_DIR)):
            self.cfg["settings"]["backup"]["dir"] = bad
            with self.assertRaises(ValueError, msg=bad):
                config.validate_config(self.cfg)
        for good in (str(self.folder), "Sicherungen", str(config.DATA_DIR / "sicherungen")):
            self.cfg["settings"]["backup"]["dir"] = good
            config.validate_config(self.cfg)
        self.cfg["settings"]["backup"]["dir"] = str(config.BACKUP_DIR)   # saved before the check: other saves still work
        with mock.patch.dict(config._cfg_cache, {"cfg": self.cfg}):
            config.validate_config(self.cfg)

    def test_create_prunes_old_backups(self):
        self.cfg["settings"]["backup"]["keep"] = 2
        self.fake("2026-01-01", "2026-01-02", "2026-01-03")
        info = backup.create(self.cfg, log=lambda *_: None)
        self.assertEqual(self.names(), sorted([f"{backup.PREFIX}2026-01-03_120000.zip", info["name"]]))


class TestHousekeeping(BackupTest):
    def test_prune_keeps_the_newest(self):
        names = self.fake("2025-12-31", "2026-01-05", "2026-01-01", "2026-02-01", "2026-01-10")
        (self.folder / "eigene-datei.zip").write_bytes(b"")
        self.cfg["settings"]["backup"]["keep"] = 3
        backup.prune(self.cfg)
        self.assertEqual(self.names(), sorted([names[1], names[3], names[4], "eigene-datei.zip"]))
        self.assertEqual([x["name"] for x in backup.items(self.cfg)], [names[3], names[4], names[1]])

    def test_keep_at_least_one(self):
        self.fake("2026-01-01", "2026-01-02")
        self.cfg["settings"]["backup"]["keep"] = 0   # invalid/empty -> default, never delete everything
        backup.prune(self.cfg)
        self.assertEqual(len(self.names()), 2)

    def test_path_of_accepts_only_existing_backup_names(self):
        (name,) = self.fake("2026-03-04")
        self.assertEqual(backup.path_of(name, self.cfg), self.folder / name)
        for bad in ("../config.json", f"../{name}", f"{name}/../../x", "x.zip", "tuttiphon-sicherung-2026-03-04.zip",
                    f"{backup.PREFIX}2026-03-05_120000.zip", "", None):
            with self.assertRaises(ValueError, msg=bad):
                backup.path_of(bad, self.cfg)

    def test_done_today(self):
        self.assertFalse(backup.done_today(self.cfg))
        yesterday = dt.date.today() - dt.timedelta(days=1)
        self.fake(yesterday.isoformat())
        self.assertFalse(backup.done_today(self.cfg))
        self.fake(dt.date.today().isoformat())
        self.assertTrue(backup.done_today(self.cfg))

    def test_folder(self):
        st = self.cfg["settings"]["backup"]
        st["dir"] = ""
        self.assertEqual(backup.folder(self.cfg), config.DATA_DIR / "sicherungen")
        st["dir"] = "Sicherungen/Tuttiphon"
        self.assertEqual(backup.folder(self.cfg), env.BASE / "Sicherungen" / "Tuttiphon")
        st["dir"] = str(self.folder)
        self.assertEqual(backup.folder(self.cfg), self.folder)


if __name__ == "__main__":
    unittest.main()
