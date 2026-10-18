"""Configuration v10: the setup assistant on the first start. A new installation starts with `settings.setup.done`
false and conversion off; an existing installation counts as set up and keeps converting as before (the migration
writes the earlier effective value). Temp folder only, no network."""
from tests.python import env  # noqa: F401  (before app.*)

import copy
import json
import unittest

from app import config


class SetupDefaultsTest(unittest.TestCase):
    def test_template(self):
        d = config.default_config()
        self.assertEqual(d["version"], config.CONFIG_VERSION)
        self.assertEqual(d["settings"]["setup"], {"done": False})
        self.assertIs(d["settings"]["opus"]["enabled"], False)   # nothing is converted before someone chose it
        # unchanged defaults (checked for the assistant: they add files or only read, nothing is moved or deleted)
        self.assertIs(d["settings"]["lyrics"]["fetch"], True)
        self.assertIs(d["settings"]["analysis"]["enabled"], True)
        self.assertIs(d["settings"]["deezer"]["overwriteManual"], False)
        self.assertIs(d["settings"]["watch"]["enabled"], False)
        config.validate_config(copy.deepcopy(d))

    def test_new_installation_starts_with_the_assistant(self):
        before = config.CONFIG_FILE.read_text(encoding="utf-8") if config.CONFIG_FILE.exists() else None

        def restore():
            if before is None:
                config.CONFIG_FILE.unlink(missing_ok=True)
            else:
                config.CONFIG_FILE.write_text(before, encoding="utf-8")
            env.reset_caches()
        self.addCleanup(restore)
        config.CONFIG_FILE.unlink(missing_ok=True)
        env.reset_caches()
        cfg = config.load_config()   # no config.json yet: written from the template, not migrated
        self.assertEqual(cfg["settings"]["setup"], {"done": False})
        self.assertIs(cfg["settings"]["opus"]["enabled"], False)

    def test_validation(self):
        cfg = copy.deepcopy(config.default_config())
        for good in ({"done": True, "at": "2026-10-17"}, {"done": False}, {}):
            cfg["settings"]["setup"] = good
            config.validate_config(cfg)
        for bad in ("yes", {"done": "yes"}, {"done": True, "at": "17.10.2026"}):
            cfg["settings"]["setup"] = bad
            with self.assertRaises(ValueError):
                config.validate_config(cfg)


class SetupMigrationTest(unittest.TestCase):
    def old(self, version=9):
        """A configuration as an existing installation has it – before the setup assistant."""
        cfg = copy.deepcopy(config.default_config())
        cfg["version"] = version
        cfg["settings"].pop("setup", None)
        cfg["settings"]["opus"]["enabled"] = True   # the template up to v9
        return cfg

    def test_existing_installation_counts_as_set_up(self):
        cfg = config.migrate(self.old())
        self.assertEqual(cfg["version"], config.CONFIG_VERSION)
        self.assertIs(cfg["settings"]["setup"]["done"], True)
        self.assertNotIn("at", cfg["settings"]["setup"])   # marked by the migration, the assistant never ran
        config.validate_config(cfg)

    def test_conversion_keeps_its_earlier_value(self):
        cfg = self.old()
        del cfg["settings"]["opus"]["enabled"]   # never saved explicitly: the earlier default (on) applied
        self.assertIs(config.migrate(cfg)["settings"]["opus"]["enabled"], True)
        cfg = self.old()
        cfg["settings"]["opus"]["enabled"] = False   # turned off by hand – stays off
        self.assertIs(config.migrate(cfg)["settings"]["opus"]["enabled"], False)
        cfg = self.old()
        del cfg["settings"]["opus"]   # no section at all
        self.assertIs(config.migrate(cfg)["settings"]["opus"]["enabled"], True)

    def test_owner_keeps_its_earlier_value(self):
        # until 0.17.0 new files got 1000:10 by default; new installations no longer chown (empty)
        cfg = self.old(version=10)
        del cfg["settings"]["opus"]["owner"]   # never saved explicitly: the earlier default applied
        self.assertEqual(config.migrate(cfg)["settings"]["opus"]["owner"], "1000:10")
        cfg = self.old(version=10)
        cfg["settings"]["opus"]["owner"] = "1000:100"   # chosen by hand – stays
        self.assertEqual(config.migrate(cfg)["settings"]["opus"]["owner"], "1000:100")
        cfg = self.old(version=10)
        cfg["settings"]["opus"]["owner"] = ""   # emptied by hand – stays empty
        self.assertEqual(config.migrate(cfg)["settings"]["opus"]["owner"], "")
        self.assertEqual(config.default_config()["settings"]["opus"]["owner"], "")   # new installations

    def test_very_old_configuration(self):
        cfg = self.old(version=5)
        del cfg["settings"]["opus"]["enabled"]
        cfg = config.migrate(cfg)
        self.assertEqual((cfg["settings"]["setup"]["done"], cfg["settings"]["opus"]["enabled"]), (True, True))

    def test_current_version_is_left_alone(self):
        cfg = copy.deepcopy(config.default_config())   # a new installation: the assistant is still to come
        cfg = config.migrate(cfg)
        self.assertEqual(cfg["settings"]["setup"], {"done": False})
        self.assertIs(cfg["settings"]["opus"]["enabled"], False)

    def test_load_config_migrates_the_file(self):
        before = config.CONFIG_FILE.read_text(encoding="utf-8") if config.CONFIG_FILE.exists() else None

        def restore():
            if before is None:
                config.CONFIG_FILE.unlink(missing_ok=True)
            else:
                config.CONFIG_FILE.write_text(before, encoding="utf-8")
            env.reset_caches()
        self.addCleanup(restore)
        old = self.old()
        del old["settings"]["opus"]["enabled"]
        config.CONFIG_FILE.write_text(json.dumps(old, ensure_ascii=False), encoding="utf-8")
        env.reset_caches()
        cfg = config.load_config()
        self.assertIs(cfg["settings"]["setup"]["done"], True)
        self.assertIs(cfg["settings"]["opus"]["enabled"], True)   # _fill() must not bring the new default (off)
        on_disk = json.loads(config.CONFIG_FILE.read_text(encoding="utf-8"))
        self.assertEqual((on_disk["version"], on_disk["settings"]["setup"]["done"], on_disk["settings"]["opus"]["enabled"]),
                         (config.CONFIG_VERSION, True, True))


if __name__ == "__main__":
    unittest.main()
