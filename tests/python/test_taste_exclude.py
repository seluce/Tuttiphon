"""Music worlds a person keeps out of their taste (person.tasteExclude) – e.g. the children's music on a parent's
account: those songs count neither as liked nor as disliked, the family person on the same account keeps them, the
morning habit ignores them, and "To review" offers it when a separate world makes up a big part of what is played."""
from tests.python import env  # noqa: F401  (before app.*)

import copy
import datetime as dt
import unittest
from unittest import mock

from app import auth, config, listenclock, suggest, taste
from app.rules import Library
from tests.python.factory import base_config, song

TODAY = dt.date(2026, 10, 20)


def library():
    kids = [song(f"k{n}", artist="Band A" if n % 2 else "Band B", album=f"Kinder {n % 4}", genres=("Children",),
                 rating=3, plays=5) for n in range(30)]
    own = [song(f"r{n}", artist=f"Gruppe {n % 6}", album=f"Rock {n % 6}", genres=("Rock",), rating=3, plays=2)
           for n in range(30)]
    return Library(kids + own)


class ScoresTest(unittest.TestCase):
    def setUp(self):
        self.cfg = base_config()
        self.lib = library()
        p = mock.patch("app.rueckblick.plays_between", lambda user, start, end: ({}, {}))
        p.start()
        self.addCleanup(p.stop)
        taste._memo.clear()
        taste._excl_memo.clear()

    def test_songs_of_left_out_worlds_do_not_count(self):
        both = taste.song_scores(self.lib, "jonas", TODAY)
        own = taste.song_scores(self.lib, "jonas", TODAY, self.cfg, ("kinder",))
        kids = {i for i, s in enumerate(self.lib.songs) if s["id"].startswith("k")}
        self.assertTrue(kids & set(both))
        self.assertFalse(kids & set(own))
        self.assertEqual(set(own), set(both) - kids)

    def test_profile_per_person_on_the_same_account(self):
        jonas = {"id": "jonas", "user": "Jonas", "tasteExclude": ["kinder"]}
        family = {"id": "familie", "user": "Jonas"}
        with mock.patch.object(taste, "_person_lib", lambda cfg, base, user: base):
            mine = taste.for_person(self.cfg, self.lib, jonas, TODAY)
            ours = taste.for_person(self.cfg, self.lib, family, TODAY)
        self.assertNotIn("kinder", dict(mine["welten"]))
        self.assertIn("kinder", dict(ours["welten"]))
        self.assertFalse({a for a, _s in mine["artists"]} & {"Band A", "Band B"})
        self.assertEqual(taste.excluded(jonas), ("kinder",))
        self.assertEqual(taste.excluded({"tasteExclude": ["b", "a", "a", 5]}), ("a", "b"))


class MorningTest(unittest.TestCase):
    def test_left_out_songs_do_not_make_a_morning(self):
        now = dt.datetime(2026, 10, 20, 12, 0)
        songs, d, n = [], now.date(), 0
        while n < 8:
            d -= dt.timedelta(days=1)
            if d.weekday() >= 5:
                continue
            n += 1
            for k in range(6):
                t = dt.datetime.combine(d, dt.time(7, 0)) + dt.timedelta(minutes=4 * k)
                songs.append(song(f"k{n}-{k}", plays=1, played=t.astimezone(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")))
        user = "taste-exclude-test"
        self.assertIsNotNone(listenclock.morning(user, songs, now))
        self.assertIsNone(listenclock.morning(user, songs, now, skip=frozenset(s["id"] for s in songs)))


class HintTest(unittest.TestCase):
    def hints(self, cfg, share):
        prof = {"enough": True, "welten": [["kinder", share], ["metal", 0.3]], "artists": []}
        with mock.patch.object(taste, "profile", lambda *a, **k: prof):
            return suggest.taste_hints(cfg, Library([]))

    @env.german
    def test_hint_for_a_separate_world_that_shapes_the_taste(self):
        cfg = base_config()
        got = self.hints(cfg, 0.45)
        keys = [x[0] for x in got]
        self.assertIn("taste-world|jonas|kinder", keys)
        self.assertFalse(any(k.startswith("taste-world|familie") for k in keys))   # never for the shared person
        self.assertFalse(any(k.endswith("|metal") for k in keys))                  # only separate worlds
        hint = next(x for x in got if x[0] == "taste-world|jonas|kinder")
        self.assertEqual(hint[2], "„Kinder“ zählt zum Geschmack von Jonas")
        self.assertIn("45 %", hint[3])
        self.assertEqual(hint[4][0]["href"], "#/person/jonas")
        self.assertEqual(self.hints(cfg, 0.1), [])
        cfg["personen"][1]["tasteExclude"] = ["kinder"]
        self.assertFalse(any(x[0] == "taste-world|jonas|kinder" for x in self.hints(cfg, 0.45)))


class ConfigTest(unittest.TestCase):
    def test_validation_and_users_may_set_it(self):
        cfg = base_config()
        cfg["personen"][1]["tasteExclude"] = ["kinder", "gibt-es-nicht"]   # unknown ids are ignored, not refused
        config.validate_config(cfg)
        for bad in ("kinder", [5], ["x" * 101]):
            broken = copy.deepcopy(cfg)
            broken["personen"][1]["tasteExclude"] = bad
            with self.assertRaises(ValueError):
                config.validate_config(broken)
        self.assertIn("tasteExclude", auth.PERSON_FIELDS)


if __name__ == "__main__":
    unittest.main()
