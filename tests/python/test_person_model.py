"""One person per Navidrome account, the family as an entry with an account of its own: the rules, a configuration
from before 2.0 (not read), setting up the family (POST /api/family) and the family's kid-safe mode in the plugin's
answers."""
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
    """A configuration of a version before 2.0 is not read: Tuttiphon does not start, and the file stays as it is."""

    def tearDown(self):
        config.save_config(base_config())

    def test_not_read(self):
        cfg = without_family()
        cfg["version"] = 12
        text = json.dumps(cfg, ensure_ascii=False)
        config.CONFIG_FILE.write_text(text, encoding="utf-8")
        env.reset_caches()
        with self.assertRaises(config.ConfigOutdated) as cm:
            config.load_config()
        self.assertIn("before Tuttiphon 2.0", str(cm.exception))
        with self.assertRaises(SystemExit):
            web.serve("127.0.0.1", 0)
        self.assertEqual(config.CONFIG_FILE.read_text(encoding="utf-8"), text)   # untouched


class FamilySetupTest(unittest.TestCase):
    def setUp(self):
        cfg = without_family()
        cfg["settings"]["deezer"] = {**cfg["settings"].get("deezer", {}), "users": ["Jonas"]}
        config.save_config(cfg)
        self.addCleanup(config.save_config, base_config())
        self.created, self.saved, self.runs = [], {}, []

        self.env = {}

        class Api:
            def users(api):
                return [{"userName": "root", "isAdmin": True}, {"userName": "Taken"}, {"userName": "anna-lena"},
                        {"userName": "anna.lena"}, {"userName": "Jonas"}, {"userName": "Auto"}]

            def create_user(api, name, full, password):
                self.created.append((name, full, password))
                return "id-1"
        patches = [mock.patch.object(web.playlists, "native_api", lambda env: Api()),
                   mock.patch.object(web, "save_env", lambda values: self.saved.update(values)),
                   mock.patch.object(web.auth, "navidrome_users", lambda force=False: []),
                   mock.patch.object(web, "load_env", lambda: self.env),
                   mock.patch.object(web.RUNNER, "start", lambda steps, **opts: self.runs.append((steps, opts))),
                   mock.patch.object(web.auth, "note_password", lambda user, ok: None),
                   mock.patch.object(web, "Navidrome", Nav)]
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
        self.env["NAV_PASS_OMA_2"] = "pw-test"
        for body in ({"account": "root"}, {"account": "taken"}, {"account": "jonas"}, {"account": "a b"},
                     {"account": "anna.lena"}, {"account": "oma.2"}):   # the same password key as "anna-lena", "oma_2"
            with self.assertRaises(ValueError, msg=body):
                web.api_family(body)
        self.assertEqual(self.created, [])
        self.assertFalse(any(p.get("family") for p in config.load_config()["personen"]))

    def test_an_existing_account(self):
        for body, why in (({"account": "nobody"}, "not in Navidrome"),
                          ({"account": "jonas", "password": "pw-family"}, "Jonas' account"),
                          ({"account": "root", "password": "pw-family"}, "an administrator"),
                          ({"account": "anna-lena", "password": "pw-family"}, "the same password key as anna.lena"),
                          ({"account": "auto"}, "no password"),
                          ({"account": "auto", "password": "wrong"}, "a wrong password")):
            with self.assertRaises(ValueError, msg=why):
                web.api_family({**body, "existing": True})
        with mock.patch.object(web.auth, "current", lambda: {"user": "Auto", "role": "admin"}), \
                self.assertRaises(ValueError):                         # the account one is signed in with
            web.api_family({"account": "auto", "existing": True, "password": "pw-family"})
        self.assertEqual(self.saved, {})
        out = web.api_family({"name": "Wir", "account": "auto", "existing": True, "password": "pw-family"})
        self.assertEqual(out, {"person": "familie", "account": "Auto"})   # as Navidrome spells it, no password
        self.assertEqual(self.created, [])                             # the account stays as it is
        self.assertEqual(self.saved, {config.pass_key("Auto"): "pw-family"})
        cfg = config.load_config()
        family = next(p for p in cfg["personen"] if p.get("family"))
        self.assertEqual((family["user"], family["name"]), ("Auto", "Wir"))
        self.assertEqual(cfg["settings"]["deezer"]["users"], ["Jonas", "Auto"])
        self.assertEqual(self.runs, [(["deezer"], {"deezer_mode": "new"})])

    def test_an_existing_account_with_a_stored_password(self):
        self.env[config.pass_key("Auto")] = "pw-family"
        self.assertEqual(web.api_family({"account": "Auto", "existing": True})["account"], "Auto")
        self.assertEqual(self.saved, {})


class Nav:
    """Navidrome for a password check: only "pw-family" works."""
    def __init__(self, url, user, password):
        self.password = password

    def ping(self):
        if self.password != "pw-family":
            raise NavidromeError("Wrong username or password", code=40)
        return {}


class SuggestionKeyTest(unittest.TestCase):
    """What counts as "already there": formats made from an account's own listening are never shared with the family,
    one-per-person formats do not depend on their worlds, two mixes of the same worlds differ by their flavor."""

    def test_keys(self):
        from app import suggest
        morning = {"person": "jonas", "welt": ["kinder"], "stil": "*", "type": "mix", "daytime": "morning"}
        self.assertEqual(suggest.key_of(morning), suggest.key_of({**morning, "welt": ["kinder", "metal"]}))
        daily = {"person": "jonas", "welt": ["kinder", "metal"], "stil": "*", "type": "mix", "mix": {"flavor": "ausgewogen"}}
        self.assertNotEqual(suggest.key_of(daily), suggest.key_of({**daily, "mix": {"flavor": "entdecken"}}))
        unheard = {"person": "familie", "welt": "*", "stil": "*", "type": "mix", "unheard": True}
        self.assertNotEqual(suggest._content_key(unheard), suggest._content_key({**unheard, "person": "jonas"}))
        plain = {"person": "familie", "welt": "kinder", "stil": "80er"}
        self.assertEqual(suggest._content_key(plain), suggest._content_key({**plain, "person": "jonas"}))

    def test_a_deleted_vibe_newly_added(self):
        from app import suggest
        from app.library import Library
        from tests.python.factory import random_songs
        cfg = base_config()
        cfg["stile"] = [s for s in cfg["stile"] if s["id"] != "neu"]
        cfg["personen"][1]["likes"]["welten"] = ["kinder", "metal"]
        out = suggest.suggestions(cfg, Library(random_songs(800, seed=4)), only_person="jonas")   # no KeyError
        self.assertFalse(any((x.get("playlist") or {}).get("stil") == "neu" for x in out))


class TogetherConsentTest(unittest.TestCase):
    """“What everyone likes” takes the members' taste and 1-star songs: a user only adds or removes themselves, and the
    preview takes the members as saved."""

    def setUp(self):
        from app import auth
        self.cfg = base_config()
        self.cfg["playlists"] = [{"id": "alle", "person": "familie", "welt": "*", "stil": "*", "type": "mix",
                                  "together": ["niklas", "oma"]}]
        self.jonas = {"user": "Jonas", "role": "user", "own": "jonas", "persons": ["jonas"], "local": False}
        self.auth = auth

    def merged(self, together, pid="alle"):
        incoming = copy.deepcopy(self.cfg)
        pl = next((x for x in incoming["playlists"] if x["id"] == pid), None)
        if pl is None:
            pl = {"id": pid, "person": "familie", "welt": "*", "stil": "*", "type": "mix"}
            incoming["playlists"].append(pl)
        pl["together"] = together
        out = self.auth.merge_user_changes(self.cfg, incoming, self.jonas)
        return next(x for x in out["playlists"] if x["id"] == pid).get("together")

    def test_only_themselves(self):
        self.assertEqual(self.merged(["niklas", "oma", "jonas"]), ["niklas", "oma", "jonas"])
        self.assertEqual(self.merged(["jonas"]), ["niklas", "oma", "jonas"])     # others stay, only themselves added …
        self.assertEqual(self.merged([]), ["niklas", "oma"])                     # … or removed
        self.assertIsNone(self.merged(["niklas", "oma"], pid="neu"))             # a new one: not with other people

    def test_preview_takes_the_saved_members(self):
        body = {"id": "alle", "person": "familie", "together": ["jonas", "oma"]}
        with mock.patch.object(web.auth, "current", return_value=self.jonas), \
                mock.patch.object(web, "load_config", return_value=self.cfg):
            web._guard_preview(body, self.cfg)
            self.assertEqual(body["together"], ["niklas", "oma"])
            other = {"person": "familie", "together": ["niklas", "oma"]}         # not saved: no members
            web._guard_preview(other, self.cfg)
            self.assertNotIn("together", other)


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
