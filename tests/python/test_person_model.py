"""One person per Navidrome account, the family as an entry with an account of its own: the update of older
configurations (v13), setting up the family (POST /api/family) and the family's kid-safe mode in the plugin's answers."""
from tests.python import env  # noqa: F401  (before app.*)

import copy
import unittest
from unittest import mock

from app import auth, config, sonic, web
from app.navidrome import NavidromeError
from tests.python.factory import base_config


def old_config():
    """A v12 configuration as it was: the shared person "Familie" on Alex' account (the default person, visible to
    everyone), a child profile on Sam's account, a person without an account."""
    cfg = base_config()
    cfg["version"] = 12
    cfg["settings"].update(defaultPerson="familie", public=True)
    cfg["personen"] = [
        {"id": "familie", "name": "Familie", "user": "alex", "public": True, "prefix": "", "icon": "i:home",
         "likes": {"welten": ["kinder"], "stile": [], "artists": []}, "dislikes": {"artists": ["Band X"], "genres": []}},
        {"id": "alex", "name": "Alex", "user": "alex", "prefix": "Alex · ",
         "likes": {"welten": [], "stile": [], "artists": []}, "dislikes": {"artists": [], "genres": []}},
        {"id": "sam", "name": "Sam", "user": "Sam", "public": False, "prefix": "Sam · "},
        {"id": "lena", "name": "Lena", "user": "sam", "child": True, "prefix": "Lena · "},
        {"id": "oma", "name": "Oma", "user": "", "public": True, "prefix": "Oma · "},
    ]
    cfg["playlists"] = [
        {"id": "kids", "welt": "kinder", "stil": "*", "status": "aktiv"},                        # no person: Familie
        {"id": "car", "person": "familie", "welt": "*", "stil": "*", "type": "mix", "name": "Autofahrt",
         "together": ["alex", "sam"], "mix": {"every": "day"}},
        {"id": "f1", "person": "alex", "welt": "metal", "stil": "*"},
        {"id": "m1", "person": "lena", "welt": "kinder", "stil": "tanzen"},
        {"id": "o1", "person": "oma", "welt": "mittelalter", "stil": "*"},
    ]
    return cfg


def migrated(cfg, admin="root"):
    with mock.patch.object(config, "load_env", lambda: {"NAV_ADMIN_USER": admin}):
        return config.migrate(copy.deepcopy(cfg))


class MigrationTest(unittest.TestCase):
    def test_one_person_per_account(self):
        out = migrated(old_config())
        config.validate_config(out)
        persons = {p["id"]: p for p in out["personen"]}
        self.assertEqual(set(persons), {"alex", "sam", "oma"})          # Familie and Lena merged
        self.assertEqual(persons["oma"]["user"], "root")                   # without an account: the administrator's
        self.assertFalse(any("public" in p or p.get("family") for p in out["personen"]))
        self.assertNotIn("defaultPerson", out["settings"])
        self.assertNotIn("public", out["settings"])
        owner = {p["id"]: p["person"] for p in out["playlists"]}
        self.assertEqual(owner, {"kids": "alex", "car": "alex", "f1": "alex", "m1": "sam", "o1": "oma"})
        by_id = {p["id"]: p for p in out["playlists"]}
        self.assertEqual(by_id["kids"]["name"], "Kinder · All Sorts")   # the name it has in Navidrome now stays –
        self.assertNotIn("name", by_id["f1"])                              # not “Alex · …” (server language here: en)
        self.assertNotIn("together", by_id["car"])                   # only the family has “What everyone likes”

    def test_what_is_left_to_review(self):
        st = migrated(old_config())["settings"]
        self.assertEqual(st["familySetup"]["name"], "Familie")
        self.assertEqual(st["familySetup"]["dislikes"], {"artists": ["Band X"], "genres": []})
        self.assertEqual(st["familySetup"]["playlists"], ["kids", "car"])
        self.assertEqual(st["familySetup"]["together"], {"car": ["alex", "sam"]})
        self.assertEqual(st["mergedPersons"], [{"name": "Lena", "into": "sam", "child": True, "playlists": ["m1"]}])

    def test_the_former_family_playlists_stay_for_everyone_until_the_family_is_set_up(self):
        from app import rules
        cfg = migrated(old_config())
        kids = next(p for p in cfg["playlists"] if p["id"] == "kids")      # Familie's – now Alex'
        mine = next(p for p in cfg["playlists"] if p["id"] == "f1")
        self.assertTrue(rules.build_nsp(cfg, kids)["public"])               # nobody loses it in Symfonium meanwhile
        self.assertFalse(rules.build_nsp(cfg, mine)["public"])
        sam = {"user": "Sam", "role": "user", "own": ["sam"], "local": False}
        self.assertTrue(auth.visible_playlist(kids, cfg, sam))
        self.assertFalse(auth.visible_playlist(mine, cfg, sam))
        cfg["settings"].pop("familySetup")                                   # set up (or done with)
        self.assertFalse(rules.build_nsp(cfg, kids)["public"])

    def test_a_default_person_alone_on_its_account_stays_a_person(self):
        cfg = old_config()
        cfg["personen"] = [cfg["personen"][0], cfg["personen"][2]]
        cfg["personen"][0]["user"] = "familie"
        cfg["playlists"] = [cfg["playlists"][0]]
        out = migrated(cfg)
        config.validate_config(out)
        self.assertEqual([p["id"] for p in out["personen"]], ["familie", "sam"])
        self.assertFalse(out["personen"][0].get("family"))   # never by itself: that needs an account of its own
        self.assertEqual(out["settings"]["familySetup"]["person"], "familie")

    def test_an_old_new_installation(self):
        cfg = copy.deepcopy(old_config())
        cfg["personen"] = [{"id": "familie", "name": "Family", "user": "", "public": True, "prefix": ""}]
        cfg["playlists"] = []
        out = migrated(cfg)
        self.assertEqual(out["personen"], [])
        config.validate_config(out)

    def test_the_rules(self):
        cfg = base_config()
        for change in (lambda c: c["personen"][2].update(user=""),
                       lambda c: c["personen"][2].update(user="JONAS"),                    # the account twice
                       lambda c: c["personen"][2].update(family=True),                     # two families
                       lambda c: c["playlists"].append({"id": "x", "welt": "*", "stil": "80er"}),   # nobody's
                       lambda c: c["settings"].update(familyEdit="alle")):
            bad = copy.deepcopy(cfg)
            change(bad)
            with self.assertRaises(ValueError):
                config.validate_config(bad)


class FamilySetupTest(unittest.TestCase):
    def setUp(self):
        self.cfg = migrated(old_config())
        config.save_config(self.cfg)
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

    def test_set_up_with_the_playlists_chosen(self):
        out = web.api_family({"name": "Familie", "playlists": ["car", "f1"]})
        self.assertEqual((out["person"], out["account"]), ("familie", "familie"))
        self.assertEqual(self.created[0][:2], ("familie", "Familie"))
        self.assertEqual(self.saved, {config.pass_key("familie"): out["password"]})
        cfg = config.load_config()
        family = next(p for p in cfg["personen"] if p.get("family"))
        self.assertEqual((family["user"], family["clean"], family["dislikes"]["artists"]), ("familie", True, ["Band X"]))
        owner = {p["id"]: p["person"] for p in cfg["playlists"]}
        self.assertEqual((owner["car"], owner["kids"], owner["f1"]), ("familie", "alex", "alex"))   # chosen ones
        self.assertEqual(next(p for p in cfg["playlists"] if p["id"] == "car")["together"], ["alex", "sam"])
        self.assertNotIn("familySetup", cfg["settings"])
        self.assertEqual(self.runs, [(["deezer", "playlists", "scan"], {"deezer_mode": "new"})])   # its stars, the move
        with self.assertRaises(ValueError):
            web.api_family({})                                       # only one family

    def test_account_names(self):
        for body in ({"account": "root"}, {"account": "Taken"}, {"account": "alex"}, {"account": "a b"}):
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
