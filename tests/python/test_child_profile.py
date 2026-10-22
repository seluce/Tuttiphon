"""Child profile (person.child, set only by the administrator): children's music belongs to "all" for this person
(audio plays stay out), kid-safe mode is on, no hint to keep it out of the taste – and "To review" asks the
administrator when an account plays mostly separate music worlds."""
from tests.python import env  # noqa: F401  (before app.*)

import copy
import datetime as dt
import unittest
from unittest import mock

from app import auth, config, mixer, rules, suggest, taste
from app.rules import BuildContext, Library, build_nsp
from tests.python.factory import base_config, song

TODAY = dt.date(2026, 10, 20)
JONAS = {"user": "Jonas", "role": "user", "own": ["jonas"], "local": False}


def setup():
    cfg = base_config()
    cfg["welten"].append({"id": "hoerspiel", "name": "Hörspiele", "artists": ["Erzähler"], "genres": ["Audio Drama"],
                          "separate": True, "scene": "hoerspiel"})
    lib = Library([song(f"k{n}", artist="Band A", genres=("Children",), rating=4) for n in range(5)]
                  + [song(f"h{n}", artist="Erzähler", genres=("Audio Drama",), rating=4) for n in range(5)]
                  + [song(f"r{n}", artist="Gruppe", genres=("Rock",), rating=4) for n in range(5)])
    return cfg, lib


def all_songs(cfg, lib, person):
    p = {"id": "x", "person": person, "welt": "*", "stil": "*"}
    nsp = build_nsp(cfg, p, BuildContext(lib, TODAY))
    return {lib.songs[i]["id"][0] for i in lib.ids({"all": nsp["all"]})}


class AllTest(unittest.TestCase):
    def test_children_music_belongs_to_all_on_a_child_profile(self):
        cfg, lib = setup()
        self.assertEqual(all_songs(cfg, lib, "jonas"), {"r"})                 # a parent: without the separate worlds
        cfg["personen"][1]["child"] = True
        self.assertEqual(all_songs(cfg, lib, "jonas"), {"r", "k"})            # a child: with children's music …
        self.assertEqual(rules.child_worlds(cfg, cfg["personen"][1]), {"kinder"})   # … but never the audio plays
        self.assertEqual(all_songs(cfg, lib, "oma"), {"r"})                   # everyone else as before

    @env.german
    def test_description_and_mix_fingerprint(self):
        cfg, _lib = setup()
        p = {"id": "x", "person": "jonas", "welt": "*", "stil": "*", "type": "mix", "unheard": True, "mix": {"every": "week"}}
        self.assertIn("ohne Kinder, Hörspiele", "\n".join(rules.summary(cfg, p)))
        before = mixer.settings_key(cfg, p)
        cfg["personen"][1]["child"] = True
        text = "\n".join(rules.summary(cfg, p))
        self.assertIn("ohne Hörspiele", text)
        self.assertNotIn("Kinder,", text)
        self.assertNotEqual(mixer.settings_key(cfg, p), before)   # the mix is picked anew right away


class HintTest(unittest.TestCase):
    def hints(self, cfg, welten, child_share=0.0, **kw):
        prof = {"enough": True, "welten": welten, "artists": [], "childShare": child_share}
        with mock.patch.object(taste, "profile", lambda *a, **k: prof):
            return suggest.taste_hints(cfg, Library([]), **kw)

    @env.german
    def test_mostly_children_music_asks_the_administrator(self):
        cfg, _lib = setup()
        mostly = [["kinder", 0.45], ["hoerspiel", 0.3], ["metal", 0.2]]
        got = {x[0]: x for x in self.hints(cfg, mostly, 0.55)}
        hint = got["child|jonas"]
        self.assertEqual(hint[2], "Ist Jonas ein Kind?")
        self.assertIn("55 %", hint[3])   # each song once, without the audio plays
        self.assertIn("„Kinder“", hint[3])
        self.assertEqual([a["do"] for a in hint[4]], ["childProfile", "goto"])
        self.assertFalse(any(k.startswith("taste-world|jonas") for k in got))   # not both
        self.assertEqual(self.hints(cfg, mostly, 0.55, only_persons={"jonas"}), [])   # the account itself: no hint
        cfg["personen"][1]["child"] = True
        self.assertFalse(any("jonas" in x[0] for x in self.hints(cfg, mostly, 0.55)))  # a child profile: nothing at all

    def test_a_parent_and_audiobooks(self):
        cfg, _lib = setup()
        part = self.hints(cfg, [["kinder", 0.3], ["metal", 0.5]], 0.3, only_persons={"jonas"})
        self.assertEqual([x[0] for x in part], ["taste-world|jonas|kinder"])   # a parent: the taste hint
        self.assertEqual([a["do"] for a in part[0][4]], ["goto"])
        admin = {x[0]: x for x in self.hints(cfg, [["kinder", 0.3], ["metal", 0.5]], 0.3)}
        self.assertEqual([a["do"] for a in admin["taste-world|jonas|kinder"][4]], ["goto", "childProfile"])   # or a child
        books = {x[0]: x for x in self.hints(cfg, [["hoerspiel", 0.6], ["metal", 0.4]], 0.0)}
        self.assertNotIn("child|jonas", books)                                    # audio books do not make a child
        self.assertEqual([a["do"] for a in books["taste-world|jonas|hoerspiel"][4]], ["goto"])
        cfg["personen"][1]["tasteExclude"] = ["kinder"]                           # decided: a parent
        self.assertFalse(any(k == "child|jonas" for k, *_r in self.hints(cfg, [["kinder", 0.7]], 0.7)))


class SettingTest(unittest.TestCase):
    def test_validation_and_kid_safe_mode(self):
        cfg = base_config()
        cfg["personen"][1]["child"] = True
        config.validate_config(cfg)
        self.assertTrue(config.normalize_persons(copy.deepcopy(cfg))["personen"][1]["clean"])
        bad = copy.deepcopy(cfg)
        bad["personen"][1]["child"] = "ja"
        with self.assertRaises(ValueError):
            config.validate_config(bad)

    def test_kid_safe_mode_and_old_exclusions(self):
        cfg = base_config()
        cfg["personen"][1].update(child=True, tasteExclude=["kinder", "weg"])
        out = config.normalize_persons(copy.deepcopy(cfg))
        self.assertTrue(out["personen"][1]["clean"])                       # a child profile is always kid-safe
        self.assertNotIn("clean", out["personen"][3])                      # others stay as they are
        family = copy.deepcopy(cfg)
        family["personen"][0]["child"] = True
        with self.assertRaises(ValueError):
            config.validate_config(family)                                 # the family is never a child profile
        self.assertEqual(out["personen"][1]["tasteExclude"], ["kinder"])   # worlds that no longer exist go
        self.assertEqual(taste.excluded(cfg["personen"][1]), ())            # a child: children's music is its taste

    def test_preview_keeps_kid_safe_mode(self):
        from app import web
        cfg = base_config()
        cfg["personen"][1].update(child=True, clean=True)
        sent = copy.deepcopy(cfg)
        sent["personen"][1].update(child=False, clean=False)   # what a child's browser might send
        with mock.patch.object(web.auth, "current", lambda: JONAS), mock.patch.object(web, "load_config", lambda: copy.deepcopy(cfg)):
            out = web._preview_config(sent)
        jonas = next(p for p in out["personen"] if p["id"] == "jonas")
        self.assertEqual((jonas["clean"], jonas["child"]), (True, True))

    def test_only_the_administrator_sets_it(self):
        cfg = base_config()
        incoming = copy.deepcopy(cfg)
        incoming["personen"][1]["child"] = True
        self.assertNotIn("child", auth.merge_user_changes(cfg, incoming, JONAS)["personen"][1])
        cfg["personen"][1].update(child=True, clean=True)
        incoming = copy.deepcopy(cfg)
        incoming["personen"][1]["child"] = False
        self.assertTrue(auth.merge_user_changes(cfg, incoming, JONAS)["personen"][1]["child"])


if __name__ == "__main__":
    unittest.main()
