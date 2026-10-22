"""One person per Navidrome account, the family as an entry with an account of its own: the rules, an older
configuration (v12 – nothing is converted), setting up the family (POST /api/family) and the family's kid-safe mode in
the plugin's answers."""
from tests.python import env  # noqa: F401  (before app.*)

import copy
import json
import unittest
from unittest import mock

from app import config, sonic, web
from app.navidrome import NavidromeError
from tests.python.factory import base_config


def without_family():
    cfg = base_config()
    cfg["personen"] = [p for p in cfg["personen"] if not p.get("family")]
    return cfg


class RulesTest(unittest.TestCase):
    def test_the_rules(self):
        cfg = base_config()
        for change in (lambda c: c["personen"][2].update(user=""),
                       lambda c: c["personen"][2].update(user="JONAS"),                    # the account twice
                       lambda c: c["personen"][2].update(family=True),                     # two families
                       lambda c: c["playlists"].append({"id": "x", "welt": "*", "stil": "80er"}),   # nobody's
                       lambda c: c["playlists"].append({"id": "y", "person": "oma", "welt": "*", "stil": "*",
                                                        "together": ["jonas", "oma"]}),     # only the family's
                       lambda c: c["settings"].update(familyEdit="alle")):
            bad = copy.deepcopy(cfg)
            change(bad)
            with self.assertRaises(ValueError):
                config.validate_config(bad)


class OlderConfigTest(unittest.TestCase):
    """An older configuration is not converted: what fits loads (the settings that are gone are removed), what does
    not fit stops the start – and the file stays as it was."""

    def tearDown(self):
        config.save_config(base_config())

    def write(self, cfg):
        text = json.dumps(cfg, ensure_ascii=False)
        config.CONFIG_FILE.write_text(text, encoding="utf-8")
        env.reset_caches()
        return text

    def test_it_fits(self):
        cfg = without_family()
        cfg["version"] = 12
        cfg["settings"].update(defaultPerson="jonas", public=True)
        cfg["personen"][0]["public"] = True
        self.write(cfg)
        out = config.load_config()
        self.assertEqual(out["version"], config.CONFIG_VERSION)
        self.assertFalse({"defaultPerson", "public"} & set(out["settings"]))
        self.assertNotIn("public", out["personen"][0])
        self.assertEqual([p["id"] for p in out["personen"]], ["jonas", "niklas", "oma"])

    def test_it_does_not_fit(self):
        cfg = without_family()
        cfg["version"] = 12
        cfg["personen"].append({"id": "familie", "name": "Familie", "user": "jonas", "prefix": ""})   # an account twice
        text = self.write(cfg)
        backups = set(config.BACKUP_DIR.glob("config_v*.json"))
        with self.assertRaises(config.ConfigOutdated) as cm:
            config.load_config()
        self.assertIn("earlier version", str(cm.exception))
        with self.assertRaises(SystemExit):
            web.serve("127.0.0.1", 0)
        self.assertEqual(config.CONFIG_FILE.read_text(encoding="utf-8"), text)   # untouched
        self.assertEqual(set(config.BACKUP_DIR.glob("config_v*.json")), backups)   # no backup per attempt either


class FamilySetupTest(unittest.TestCase):
    def setUp(self):
        cfg = without_family()
        cfg["settings"]["deezer"] = {**cfg["settings"].get("deezer", {}), "users": ["Jonas"]}
        config.save_config(cfg)
        self.addCleanup(config.save_config, base_config())
        self.created, self.saved, self.runs = [], {}, []

        class Api:
            def create_user(api, name, full, password):
                if name.lower() in ("root", "taken"):
                    raise NavidromeError('HTTP 400: {"errors":{"userName":"ra.validation.unique"}}')
                self.created.append((name, full, password))
                return "id-1"
        patches = [mock.patch.object(web.playlists, "native_api", lambda env: Api()),
                   mock.patch.object(web, "save_env", lambda values: self.saved.update(values)),
                   mock.patch.object(web.auth, "navidrome_users", lambda force=False: []),
                   mock.patch.object(web, "load_env", lambda: {}),
                   mock.patch.object(web.RUNNER, "start", lambda steps, **opts: self.runs.append((steps, opts)))]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)

    def test_set_up(self):
        out = web.api_family({"name": "Familie"})
        self.assertEqual((out["person"], out["account"]), ("familie", "familie"))
        self.assertEqual(self.created[0][:2], ("familie", "Familie"))
        self.assertEqual(self.saved, {config.pass_key("familie"): out["password"]})
        cfg = config.load_config()
        family = next(p for p in cfg["personen"] if p.get("family"))
        self.assertEqual((family["id"], family["user"], family["clean"]), ("familie", "familie", True))
        self.assertEqual(cfg["settings"]["deezer"]["users"], ["Jonas", "familie"])   # its stars too
        self.assertEqual(self.runs, [(["deezer"], {"deezer_mode": "new"})])
        with self.assertRaises(ValueError):
            web.api_family({})                                       # only one family

    def test_account_names(self):
        for body in ({"account": "root"}, {"account": "Taken"}, {"account": "jonas"}, {"account": "a b"}):
            with self.assertRaises(ValueError, msg=body):
                web.api_family(body)
        self.assertEqual(self.created, [])
        self.assertFalse(any(p.get("family") for p in config.load_config()["personen"]))


class DeezerCatchUpTest(unittest.TestCase):
    def test_a_new_account_gets_the_stars_of_songs_rated_before(self):
        from app import deezer

        class Nav:
            def __init__(self):
                self.set = []

            def set_rating(self, sid, stars):
                self.set.append((sid, stars))
        old, fam = Nav(), Nav()
        entries = {"a": {"r": 1, "s": 5, "u": {"alex": 5}}, "b": {"r": 9, "s": 2, "u": {"alex": 2}},
                   "c": {"r": None, "s": None}, "d": {"r": 5, "s": 3, "u": {"alex": 3}}}
        state = {"songs": entries, "caughtUp": ["alex"]}
        users = {"alex": (old, {"a": 5, "b": 0, "d": 3}), "familie": (fam, {"d": 1})}   # d: 1 star by hand there
        result = {"set": 0, "kept": 0, "stopped": False}
        songs = [{"id": x, "artist": "A", "title": x} for x in "abcd"]
        deezer._catch_up(songs, {"a"}, entries, state, users, False, False, result, lambda *a: None, None)
        self.assertEqual(fam.set, [("b", 2)])            # a: rated in this run already, c: no stars, d: by hand
        self.assertEqual(old.set, [])                     # a known account: untouched (b was cleared by hand there)
        self.assertEqual((result["set"], result["kept"]), (1, 1))
        self.assertEqual(state["caughtUp"], ["alex", "familie"])
        deezer._catch_up(songs, set(), entries, state, users, False, False, result, lambda *a: None, None)
        self.assertEqual(fam.set, [("b", 2)])             # done once


class PluginKidSafeTest(unittest.TestCase):
    def test_the_family_s_kid_safe_mode_only_for_its_answers(self):
        cfg = base_config()
        cfg["personen"][0]["clean"] = True                     # the family: kid-safe (its default)
        self.assertFalse(next(p for p in sonic._view(cfg, ("niklas", False))[0]["personen"] if p["id"] == "niklas").get("clean"))
        self.assertTrue(next(p for p in sonic._view(cfg)[0]["personen"] if p["id"] == "familie").get("clean"))
        cfg["personen"][1]["child"] = True                     # a child profile: everyone's answers, as before
        self.assertTrue(next(p for p in sonic._view(cfg, ("niklas", False))[0]["personen"] if p["id"] == "niklas").get("clean"))


if __name__ == "__main__":
    unittest.main()
