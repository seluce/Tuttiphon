"""Configuration v7: vibes a migration added (v4 sound vibes, v5 “Good morning”) get their name in the server
language – also in installations that were migrated with the English names before. Names someone chose stay.
Temp folder only, no network."""
from tests.python import env  # noqa: F401  (before app.*)

import copy
import json
import unittest

from app import config


def names(cfg):
    return {s["id"]: s["name"] for s in cfg["stile"]}


class MigrationNamesTest(unittest.TestCase):
    def old(self, version, lang):
        cfg = copy.deepcopy(config.default_config())
        cfg["version"] = version
        if lang:
            cfg["settings"]["language"] = lang
        else:
            cfg["settings"].pop("language", None)
        return cfg

    def test_added_vibes_are_german_in_a_german_installation(self):
        cfg = self.old(4, None)   # before v6: no language yet – existing installations speak German
        cfg["stile"] = [s for s in cfg["stile"] if s["id"] != "klang-morgen"]
        cfg = config.migrate(cfg)
        self.assertEqual(cfg["settings"]["language"], "de")
        self.assertEqual(names(cfg)["klang-morgen"], "Guten Morgen")
        self.assertEqual(names(cfg)["klang-schlaf"], "Zum Einschlafen")
        self.assertEqual(cfg["version"], config.CONFIG_VERSION)

    def test_v6_with_english_default_names_gets_german_ones(self):
        cfg = self.old(6, "de")
        by_id = {s["id"]: s for s in cfg["stile"]}
        by_id["klang-ruhig"]["name"] = "Abends"          # chosen by someone – stays
        by_id["rock"]["name"] = "Rock & Punk (ours)"     # chosen by someone – stays
        cfg = config.migrate(cfg)
        got = names(cfg)
        self.assertEqual(got["klang-morgen"], "Guten Morgen")
        self.assertEqual(got["klang-power"], "Volle Power")
        self.assertEqual((got["klang-ruhig"], got["rock"]), ("Abends", "Rock & Punk (ours)"))
        self.assertEqual(cfg["version"], config.CONFIG_VERSION)

    def test_english_installation_keeps_english_names(self):
        cfg = config.migrate(self.old(6, "en"))
        self.assertEqual(names(cfg)["klang-morgen"], "Good morning")

    def test_current_version_is_not_touched(self):
        cfg = self.old(config.CONFIG_VERSION, "de")   # names in the current version: only a language switch renames
        self.assertEqual(names(config.migrate(cfg))["klang-morgen"], "Good morning")

    def test_load_config_migrates_the_file(self):
        before = config.CONFIG_FILE.read_text(encoding="utf-8") if config.CONFIG_FILE.exists() else None

        def restore():
            if before is None:
                config.CONFIG_FILE.unlink(missing_ok=True)
            else:
                config.CONFIG_FILE.write_text(before, encoding="utf-8")
            env.reset_caches()
        self.addCleanup(restore)
        config.CONFIG_FILE.write_text(json.dumps(self.old(6, "de"), ensure_ascii=False), encoding="utf-8")
        env.reset_caches()
        cfg = config.load_config()
        self.assertEqual(names(cfg)["klang-morgen"], "Guten Morgen")
        on_disk = json.loads(config.CONFIG_FILE.read_text(encoding="utf-8"))
        self.assertEqual((on_disk["version"], names(on_disk)["klang-morgen"]), (config.CONFIG_VERSION, "Guten Morgen"))
        self.assertTrue(list(config.BACKUP_DIR.glob("config_v6_*.json")))


if __name__ == "__main__":
    unittest.main()
