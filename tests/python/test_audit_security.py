"""Findings of the 0.7 security audit: preview only for own persons, family mix only with consent, child protection
can only be switched off by the administrator, lyrics only from real files, safe temporary files."""
from tests.python import env  # noqa: F401  (before app.*)

import copy
import os
import unittest

from app import auth, config, liedtext, rules
from app.rules import Library
from tests.python.factory import base_config, song

JONAS = {"user": "Jonas", "role": "user", "own": "jonas", "persons": ["jonas"], "local": False}


class PreviewTest(unittest.TestCase):
    def setUp(self):
        env.reset_caches()
        self.cfg = base_config()
        config.save_config(self.cfg)
        auth.set_current(JONAS)
        self.addCleanup(auth.set_current, {"user": None, "role": "none", "own": None, "persons": [], "local": False})

    def test_preview_only_for_own_person(self):
        from app import web
        with self.assertRaises(PermissionError):
            web._guard_preview({"person": "niklas", "welt": "*", "stil": "*", "type": "mix", "review": {"period": "month"}}, self.cfg)
        body = {"person": "jonas", "welt": "kinder", "stil": "*", "type": "mix", "rules": [{"is": {"loved": True}}],
                "sampleSize": 99999, "mix": {"size": 99999}}
        web._guard_preview(body, self.cfg)
        self.assertNotIn("rules", body)
        self.assertEqual((body["sampleSize"], body["mix"]["size"]), (100, 500))
        family = {"person": "familie", "welt": "kinder", "stil": "*"}
        web._guard_preview(family, self.cfg)                       # the family's: everyone may create them …
        self.cfg["settings"]["familyEdit"] = "admins"
        config.save_config(self.cfg)
        with self.assertRaises(PermissionError):                   # … unless only administrators may
            web._guard_preview(family, self.cfg)

    def test_preview_config_keeps_account_from_server(self):
        from app import web
        sent = copy.deepcopy(self.cfg)
        jonas = next(p for p in sent["personen"] if p["id"] == "jonas")
        jonas.update(user="niklas", likes={"welten": ["metal"], "stile": [], "artists": []})
        cfg = web._preview_config(sent)
        mine = next(p for p in cfg["personen"] if p["id"] == "jonas")
        self.assertEqual(mine["user"], "Jonas")                      # account from the server
        self.assertEqual(mine["likes"]["welten"], ["metal"])        # likes from the interface
        oma = next(p for p in cfg["personen"] if p["id"] == "oma")
        self.assertNotIn("likes", oma)


class FamilyMixTest(unittest.TestCase):
    def test_what_everyone_likes_only_for_the_family(self):
        cfg = base_config()
        p = {"id": "t", "person": "familie", "welt": "kinder", "stil": "*", "type": "mix",
             "together": ["jonas", "oma", "niklas", "familie"]}
        self.assertEqual([x["id"] for x in rules.together_of(cfg, p)], ["jonas", "niklas", "oma"])   # never the family
        self.assertEqual(rules.together_of(cfg, {**p, "person": "jonas"}), [])   # a person's playlist: no family mix
        cfg["playlists"] = [{**p, "person": "jonas"}]
        with self.assertRaises(ValueError):
            config.validate_config(cfg)


class KidSafeTest(unittest.TestCase):
    def test_user_cannot_switch_off(self):
        cfg = base_config()
        cfg["personen"][1]["clean"] = True
        incoming = copy.deepcopy(cfg)
        incoming["personen"][1]["clean"] = False
        out = auth.merge_user_changes(cfg, incoming, JONAS)
        self.assertTrue(out["personen"][1]["clean"])
        cfg["personen"][1]["clean"] = False
        incoming["personen"][1]["clean"] = True
        self.assertTrue(auth.merge_user_changes(cfg, incoming, JONAS)["personen"][1]["clean"])


class FilesTest(unittest.TestCase):
    def setUp(self):
        liedtext.DB_FILE.unlink(missing_ok=True)
        liedtext._derb_cache.update(stamp=None, ids=frozenset())
        self.addCleanup(liedtext.DB_FILE.unlink, missing_ok=True)

    def test_lyrics_ignore_symlinks_and_huge_files(self):
        folder = env.MUSIC / "Sicher" / "Album"
        folder.mkdir(parents=True, exist_ok=True)
        secret = env.ROOT / "geheim.txt"
        secret.write_text("NAV_ADMIN_PASS=geheim und noch mehr Text", encoding="utf-8")
        (folder / "a.lrc").unlink(missing_ok=True)
        os.symlink(secret, folder / "a.lrc")
        (folder / "b.txt").write_text("x " * (liedtext.MAX_BYTES // 2 + 10), encoding="utf-8")
        (folder / "c.txt").write_text("Ein ganz normaler Liedtext über den Mond", encoding="utf-8")
        lib = Library([song("a"), song("b"), song("c")])
        lib.path_loader = lambda: ({x: f"Sicher/Album/{x}.opus" for x in "abc"}, {})
        liedtext.update(lib, base_config())
        self.assertEqual(liedtext.search("admin pass"), [])
        self.assertEqual([h["song"] for h in liedtext.search("normaler liedtext")], ["c"])
        self.assertEqual(liedtext.status()["songs"], 1)

    def test_write_atomic_never_follows_links(self):
        target = env.ROOT / "ziel.txt"
        target.write_text("bleibt", encoding="utf-8")
        dst = env.ROOT / "neu.txt"
        config.write_atomic(dst, "inhalt")
        self.assertEqual(dst.read_text(encoding="utf-8"), "inhalt")
        self.assertEqual(target.read_text(encoding="utf-8"), "bleibt")
        self.assertEqual([p.name for p in env.ROOT.glob(".neu.txt.*")], [])   # no temporary file left


if __name__ == "__main__":
    unittest.main()
