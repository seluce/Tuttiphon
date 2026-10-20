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
    def hints(self, cfg, welten, **kw):
        prof = {"enough": True, "welten": welten, "artists": []}
        with mock.patch.object(taste, "profile", lambda *a, **k: prof):
            return suggest.taste_hints(cfg, Library([]), **kw)

    @env.german
    def test_mostly_separate_worlds_ask_the_administrator(self):
        cfg, _lib = setup()
        mostly = [["kinder", 0.4], ["hoerspiel", 0.25], ["metal", 0.2]]
        got = {x[0]: x for x in self.hints(cfg, mostly)}
        hint = got["child|jonas"]
        self.assertEqual(hint[2], "Ist Jonas ein Kind?")
        self.assertIn("65 %", hint[3])
        self.assertIn("„Kinder“", hint[3])
        self.assertEqual([a["do"] for a in hint[4]], ["childProfile", "goto"])
        self.assertFalse(any(k.startswith("taste-world|jonas") for k in got))   # not both
        self.assertEqual(self.hints(cfg, mostly, only_persons={"jonas"}), [])   # the child itself is never told
        cfg["personen"][1]["child"] = True
        self.assertFalse(any("jonas" in x[0] for x in self.hints(cfg, mostly)))  # a child profile: nothing at all
        cfg["personen"][1]["child"] = False
        part = self.hints(cfg, [["kinder", 0.3], ["metal", 0.5]], only_persons={"jonas"})
        self.assertEqual([x[0] for x in part], ["taste-world|jonas|kinder"])   # a parent: as before


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

    def test_only_the_administrator_sets_it(self):
        cfg = base_config()
        incoming = copy.deepcopy(cfg)
        incoming["personen"][1]["child"] = True
        self.assertNotIn("child", auth.merge_user_changes(cfg, incoming, JONAS)["personen"][1])
        cfg["personen"][1].update(child=True, clean=True)
        incoming = copy.deepcopy(cfg)
        incoming["personen"][1]["child"] = False
        self.assertTrue(auth.merge_user_changes(cfg, incoming, JONAS)["personen"][1]["child"])
        incoming["personen"].append({"id": "jonas-2", "name": "Noch ich", "user": "Jonas"})   # a second own profile
        fresh = auth.merge_user_changes(cfg, incoming, JONAS)["personen"][-1]
        self.assertEqual((fresh["id"], fresh.get("child"), fresh.get("clean")), ("jonas-2", True, True))


if __name__ == "__main__":
    unittest.main()
