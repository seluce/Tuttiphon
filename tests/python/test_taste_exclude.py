"""Music worlds a person keeps out of their taste (person.tasteExclude) – e.g. the children's music a parent plays for
the kids: those songs count neither as liked nor as disliked, the family's playlists still take them into account, the
morning habit ignores them, and "To review" offers it when a separate world makes up a big part of what is played."""
from tests.python import env  # noqa: F401  (before app.*)

import copy
import datetime as dt
import unittest
from unittest import mock

from app import auth, config, listenclock, mixer, rules, suggest, taste
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

    def test_with_and_without_the_exclusion(self):
        jonas = {"id": "jonas", "user": "Jonas", "tasteExclude": ["kinder"]}
        without = {"id": "jonas", "user": "Jonas"}
        with mock.patch.object(taste, "_person_lib", lambda cfg, base, user: base):
            mine = taste.for_person(self.cfg, self.lib, jonas, TODAY)
            ours = taste.for_person(self.cfg, self.lib, without, TODAY)
        self.assertNotIn("kinder", dict(mine["welten"]))
        self.assertIn("kinder", dict(ours["welten"]))
        self.assertFalse({a for a, _s in mine["artists"]} & {"Band A", "Band B"})
        self.assertEqual(taste.excluded(jonas), ("kinder",))
        self.assertEqual(taste.excluded({"tasteExclude": ["b", "a", "a", 5]}), ("a", "b"))


    def test_child_share_counts_each_song_once_without_audio_plays(self):
        self.cfg["welten"].append({"id": "hoerspiel", "name": "Hörspiele", "artists": ["Band A"], "separate": True,
                                   "scene": "hoerspiel"})   # half of the children's songs are "audio plays" too
        with mock.patch.object(taste, "_person_lib", lambda cfg, base, user: base):
            prof = taste.profile(self.cfg, self.lib, "Jonas", TODAY)
        shares = dict(prof["welten"])
        self.assertGreater(shares["hoerspiel"], 0)
        self.assertAlmostEqual(prof["childShare"], shares["kinder"], places=3)   # not kinder + hoerspiel

    def test_family_mix_takes_each_member_with_their_exclusion(self):
        self.cfg["personen"][1]["tasteExclude"] = ["kinder"]
        p = {"id": "fm", "person": "familie", "welt": "*", "stil": "*", "type": "mix", "together": ["jonas", "oma"],
             "mix": {"every": "week"}}
        seen = []
        with mock.patch.object(taste, "for_person", lambda cfg, base, person, today=None: seen.append(person["id"])), \
                mock.patch.object(mixer, "person_lib", lambda cfg, playlist, base: base):
            mixer.pick(self.cfg, self.lib, p, rules.build_nsp(self.cfg, p, rules.BuildContext(self.lib, TODAY)), TODAY)
        self.assertEqual(seen, ["familie", "jonas", "oma"])   # the family's own account and every member – each as
        #                                                        for_person() sees them (Jonas with his exclusion)

    def test_family_suggestions_keep_the_children_music(self):
        self.cfg["personen"][1]["tasteExclude"] = ["kinder"]
        self.cfg["personen"][1]["likes"]["welten"] = []   # only from listening

        def profile(cfg, base, user, today=None, exclude=()):
            plays_kids = (user or "").lower() == "jonas" and "kinder" not in exclude   # only the parent's account
            welten = [["metal", 0.4]] + ([["kinder", 0.4]] if plays_kids else [])
            return {"enough": True, "welten": welten, "artists": [], "childShare": 0.0}
        with mock.patch.object(taste, "profile", profile), mock.patch.object(taste, "_person_lib", lambda cfg, base, user: base), \
                mock.patch("app.listenclock.morning_of", lambda *a, **k: None):
            out = suggest.suggestions(self.cfg, self.lib, today=TODAY)
        family = next(x for x in out if x["playlist"].get("together") and x["playlist"].get("name") != "Car ride")
        self.assertIn("kinder", family["playlist"]["welt"])   # the parent's account plays it for the family


class FavoriteWorldTest(unittest.TestCase):
    def test_a_left_out_world_is_no_favorite_for_suggestions(self):
        cfg = base_config()
        cfg["personen"][1]["likes"]["welten"] = ["kinder"]   # once taken over from listening …

        def worlds():
            with mock.patch.object(taste, "profile", lambda *a, **k: None), \
                    mock.patch("app.rueckblick.plays_between", lambda user, start, end: ({}, {})):
                out = suggest.suggestions(cfg, library(), today=TODAY, only_person="jonas")
            return {w for x in out if x.get("playlist") for w in rules.welt_ids(x["playlist"])}
        self.assertIn("kinder", worlds())
        cfg["personen"][1]["tasteExclude"] = ["kinder"]      # … then kept out of the taste
        self.assertNotIn("kinder", worlds())                 # not even “for the season”


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
        self.assertFalse(any(k.startswith("taste-world|familie") for k in keys))   # never for the family
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
