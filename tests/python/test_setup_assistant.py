"""The setup assistant on the first start: a new installation starts with `settings.setup.done` false and conversion
off. Temp folder only, no network."""
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


if __name__ == "__main__":
    unittest.main()
