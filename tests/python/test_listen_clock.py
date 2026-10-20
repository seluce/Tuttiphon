"""Listening clock (listenclock.py) and "Good morning" from it: sessions from the last plays, the morning habit
(enough mornings over enough weeks), moments kept by the snapshots, the suggestion only with the habit, the mix in the
sound of the mornings."""
from tests.python import env  # noqa: F401  (before app.*)

import copy
import datetime as dt
import unittest
from unittest import mock

from app import config, listenclock, mixer, rueckblick, rules, suggest, taste
from app.rules import Library
from tests.python.factory import base_config, random_songs, song

NOW = dt.datetime(2026, 10, 20, 12, 0)   # a Tuesday


def iso(local):
    """Local time -> Navidrome's "played" (UTC, Z)."""
    return local.astimezone(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def mornings(days, start=(6, 40), songs_per=8, weekdays_only=True, prefix="m"):
    """Songs played in the morning on the last `days` (week)days, one new song every 4 minutes."""
    out, d, n = [], NOW.date(), 0
    while n < days:
        d -= dt.timedelta(days=1)
        if weekdays_only and d.weekday() >= 5:
            continue
        n += 1
        t = dt.datetime.combine(d, dt.time(*start))
        for k in range(songs_per):
            out.append(song(f"{prefix}{n}-{k}", plays=1, played=iso(t + dt.timedelta(minutes=4 * k))))
    return out


class ClockTest(unittest.TestCase):
    def setUp(self):
        listenclock._memo.clear()
        self.user = "clock-test"
        listenclock._file(self.user).unlink(missing_ok=True)
        self.addCleanup(listenclock._file(self.user).unlink, missing_ok=True)

    def test_local_time_and_sessions(self):
        t = dt.datetime(2026, 10, 19, 6, 40)
        self.assertEqual(listenclock.local_time(iso(t)), t)
        self.assertIsNone(listenclock.local_time("gestern"))
        moms = [(t, "a"), (t + dt.timedelta(minutes=4), "b"), (t + dt.timedelta(minutes=50), "c")]
        sess = listenclock.sessions(moms)
        self.assertEqual([len(s["songs"]) for s in sess], [2, 1])   # 46 minutes apart: a new session
        self.assertEqual(sess[0]["minutes"], 4 + listenclock.SONG_MINUTES)

    def test_morning_habit(self):
        info = listenclock.morning(self.user, mornings(10), NOW)
        self.assertEqual((info["days"], info["at"], info["weekdays"]), (10, "6:40", True))
        self.assertEqual(info["minutes"], 30)   # 7 × 4 minutes + one song, rounded to 5
        self.assertEqual(len(info["songs"]), 80)

    def test_no_habit_without_enough_mornings(self):
        self.assertIsNone(listenclock.morning(self.user, mornings(4), NOW))                       # too few mornings
        self.assertIsNone(listenclock.morning(self.user, mornings(10, songs_per=1), NOW))         # single songs only
        self.assertIsNone(listenclock.morning(self.user, mornings(10, start=(13, 0)), NOW))      # lunchtime
        dense = [s for s in mornings(14, weekdays_only=False) if s["id"].split("-")[0] in {f"m{i}" for i in range(1, 8)}]
        self.assertIsNone(listenclock.morning(self.user, dense, NOW))   # 7 mornings, but within two weeks only

    def test_length_has_limits(self):
        self.assertEqual(listenclock.morning(self.user, mornings(10, songs_per=40), NOW)["minutes"], listenclock.MINUTES[1])

    def test_recorded_moments_outlive_a_newer_play(self):
        songs = mornings(10)
        listenclock.record(self.user, songs, {s["id"] for s in songs}, NOW)
        evening = [{**s, "played": iso(NOW.replace(hour=21))} for s in songs]   # all played again in the evening
        self.assertIsNotNone(listenclock.morning(self.user, evening, NOW))      # the mornings stay known
        self.assertIsNone(listenclock.morning("someone-else", evening, NOW))

    def test_snapshot_records_moments(self):
        user = "clock-snapshot"
        self.addCleanup(lambda: [p.unlink() for p in rueckblick._dir(user).glob("*")])
        first = [song("s1", plays=1, played=iso(NOW - dt.timedelta(days=1)))]
        rueckblick.snapshot(user, first, NOW - dt.timedelta(hours=2))   # the very first: only the baseline
        again = [song("s1", plays=2, played=iso(NOW - dt.timedelta(hours=1)))]
        rueckblick.snapshot(user, again, NOW)
        self.assertEqual([sid for sid, _iso in listenclock._stored(user)], ["s1"])


def with_profiles(*users):
    """taste.profile: enough listening for these accounts (as with a stored password)."""
    return mock.patch.object(taste, "profile", lambda cfg, base, user, today=None, exclude=():
                             {"enough": True, "welten": [], "artists": []} if user in users else None)


class SuggestionTest(unittest.TestCase):
    INFO = {"days": 9, "weeks": 4, "at": "6:45", "minutes": 25, "weekdays": True, "songs": {}}

    def setUp(self):
        self.cfg = base_config()
        self.cfg["stile"].append(copy.deepcopy(next(s for s in config.default_config()["stile"] if s["id"] == "klang-morgen")))
        self.lib = Library(random_songs(1200))
        # sound vibes match everything here (the test songs have no sound analysis)
        p = mock.patch.object(rules, "apply_sound", lambda cfg, lib, playlist, ids: ids)
        p.start()
        self.addCleanup(p.stop)

    def keys(self, info, users=("Jonas",), person="jonas"):
        with with_profiles(*users), mock.patch("app.listenclock.morning_of", lambda cfg, base, user, today=None, exclude=(): info):
            return {s["key"]: s for s in suggest.suggestions(self.cfg, self.lib, today=NOW.date(), only_person=person)}

    @env.german
    def test_good_morning_only_with_the_habit(self):
        got = self.keys(self.INFO)
        s = next(v for k, v in got.items() if "daytime:morning" in k)
        self.assertEqual((s["title"], s["playlist"]["name"]), ("Guten Morgen, Jonas", "Guten Morgen, Jonas"))
        self.assertEqual(s["playlist"]["mix"]["minutes"], 25)
        self.assertIn("werktags gegen 6:45 Uhr", s["why"])
        self.assertEqual(s["because"], "Aus dem Hören")
        self.assertFalse(any("klang-morgen" in k for k in got))   # no "Good morning · world" with listening data
        self.assertFalse(any("daytime" in k for k in self.keys(None)))

    def test_without_listening_data_as_before(self):
        got = self.keys(None, users=())
        self.assertTrue(any(k.startswith("jonas|kinder|klang-morgen") for k in got))
        self.assertFalse(any("daytime" in k for k in got))

    def test_one_person_per_account(self):
        self.cfg["personen"].append({"id": "jonas-familie", "name": "Familie Jonas", "user": "Jonas", "prefix": "",
                                     "likes": {"welten": ["kinder"], "stile": [], "artists": []},
                                     "dislikes": {"artists": [], "genres": []}})
        with with_profiles("Jonas"), mock.patch("app.listenclock.morning_of", lambda *a, **k: self.INFO):
            out = suggest.suggestions(self.cfg, self.lib, today=NOW.date())
        self.assertEqual([s["person"] for s in out if "daytime" in s["key"]], ["jonas"])

    def test_valid_configuration(self):
        p = {"id": "m", "person": "jonas", "welt": "*", "stil": "*", "type": "mix", "daytime": "morning",
             "mix": {"size": 40, "minutes": 25, "every": "day"}}
        cfg = base_config()
        cfg["playlists"] = [p]
        config.validate_config(cfg)   # "All × Everything" is fine for the morning from the clock
        for bad in ({**p, "daytime": "evening"}, {**p, "type": None}):
            cfg["playlists"] = [bad]
            with self.assertRaises(ValueError):
                config.validate_config(cfg)


class MixTest(unittest.TestCase):
    def test_sound_of_the_mornings_weighs(self):
        lib = Library([song(f"s{i}") for i in range(3)])

        class Taste:
            def for_lib(self, plib):
                return [1.0, 0.0, None]
        cfg = base_config()
        playlist = {"person": "jonas", "welt": "*", "stil": "*", "type": "mix", "daytime": "morning"}
        adjust = {"s1": 2.0}
        with mock.patch("app.listenclock.morning_taste", lambda *a, **k: Taste()):
            mixer.morning_sound(cfg, lib, lib, [0, 1, 2], playlist, NOW.date(), adjust)
        self.assertAlmostEqual(adjust["s0"], 1.4 ** mixer.MORNING_POWER)
        self.assertAlmostEqual(adjust["s1"], 2.0 * 0.6 ** mixer.MORNING_POWER)
        self.assertNotIn("s2", adjust)   # no sound vector: unchanged
        plain = {**playlist}
        del plain["daytime"]
        self.assertNotEqual(mixer.settings_key(cfg, playlist), mixer.settings_key(cfg, plain))
        self.assertIn("|daytime:morning", suggest.key_of(playlist))


if __name__ == "__main__":
    unittest.main()
