"""“Discovered for you” (only songs the account has never played, by taste, weekly) and how much of each mix is
listened to (feedback.usage(): finished editions from the mix history against the recap counters)."""
from tests.python import env  # noqa: F401  (before app.*)

import datetime as dt
import unittest
from unittest import mock

from app import config, feedback, mixer, rueckblick, rules, suggest, taste
from app.rules import Library
from tests.python.factory import base_config, song

TODAY = dt.date(2026, 10, 20)   # a Tuesday


class DiscoverTest(unittest.TestCase):
    def setUp(self):
        self.cfg = base_config()
        self.cfg["settings"]["allMinRating"] = 0   # the whole library, whatever the stars
        # 40 bands, every third song was played on this account
        self.lib = Library([song(f"s{k}", artist=f"Gruppe {k % 40}", album=f"Album {k % 80}", genres=("Pop",), rating=4,
                                 plays=2 if k % 3 == 0 else 0) for k in range(400)])

    def test_pick_takes_only_never_played_songs(self):
        p = {"id": "d", "person": "jonas", "welt": "*", "stil": "*", "type": "mix", "unheard": True,
             "mix": {"size": 30, "perArtist": 2, "perAlbum": 1, "every": "week"}}
        config.validate_config({**self.cfg, "playlists": [p]})   # “All × Everything” is fine here
        with mock.patch.object(mixer, "person_lib", lambda cfg, playlist, base: base), \
                mock.patch.object(taste, "profile", lambda *a, **k: None):
            order, pool = mixer.pick(self.cfg, self.lib, p, {"all": []}, TODAY)
        self.assertTrue(order)
        self.assertFalse(any(self.lib.songs[i].get("playCount") for i in order))
        self.assertEqual(pool, 266)   # the never played two thirds
        self.assertIn("|unheard", suggest.key_of(p))
        for bad in ({**p, "unheard": "ja"}, {**p, "type": None}):
            with self.assertRaises(ValueError):
                config.validate_config({**self.cfg, "playlists": [bad]})

    def suggestions(self, played_all=False):
        if played_all:
            for s in self.lib.songs:
                s["playCount"] = 1
        with mock.patch.object(taste, "profile", lambda cfg, base, user, today=None:
                               {"enough": True, "welten": [], "artists": []} if user == "Jonas" else None), \
                mock.patch.object(taste, "_person_lib", lambda cfg, base, user: base), \
                mock.patch("app.listenclock.morning_of", lambda *a, **k: None):
            return suggest.suggestions(self.cfg, self.lib, today=TODAY, only_person="jonas")

    @env.german
    def test_suggested_once_per_account_with_enough_unheard_songs(self):
        s = next(x for x in self.suggestions() if x["playlist"].get("unheard"))
        self.assertEqual((s["title"], s["playlist"]["name"]), ("Entdeckt für Jonas", "Entdeckt für Jonas"))
        self.assertEqual(s["playlist"]["mix"], {"size": 30, "perArtist": 2, "perAlbum": 1, "every": "week"})
        self.assertLess(s["count"], len(self.lib.songs))   # counted from the never played songs only
        self.assertIn("jeden Montag neu", s["why"])
        self.assertFalse(any(x["playlist"].get("unheard") for x in self.suggestions(played_all=True)))


class UsageTest(unittest.TestCase):
    def history(self, entries):
        return mock.patch.object(feedback, "_cached", lambda path, default, convert=None, extra=None: entries)

    def counted(self, plays):
        snap = {"since": "2026-09-01T05:30:00", "at": "2026-10-20T05:30:00"}
        return (mock.patch.object(rueckblick, "last_snapshot", lambda user: snap),
                mock.patch.object(rueckblick, "plays_between", lambda user, start, end:
                                  ({sid: 1 for sid, day in plays if start <= day <= end}, {})))

    def run_usage(self, entries, plays):
        a, b = self.counted(plays)
        with self.history(entries), a, b:
            return feedback.usage(None, TODAY)

    def test_editions_heard_and_songs_played(self):
        weeks = [{"day": d, "every": "week", "user": "jonas", "ids": [f"{d}-{k}" for k in range(10)]}
                 for d in ("2026-09-28", "2026-10-05", "2026-10-12", "2026-10-19")]   # the last one still runs
        plays = [(f"2026-10-05-{k}", dt.date(2026, 10, 7)) for k in range(4)] + [("2026-10-12-1", dt.date(2026, 10, 13))]
        u = self.run_usage({"mix": weeks}, plays)["mix"]
        self.assertEqual((u["periods"], u["heard"], u["songs"], u["played"], u["days"]), (3, 1, 30, 5, 21))
        self.assertEqual((u["every"], u["last"]), ("week", "2026-10-05"))

    def test_not_counted_yet(self):
        late = {"mix": [{"day": "2026-10-19", "every": "day", "user": "jonas", "ids": ["a"]}]}
        a, _b = self.counted([])
        snap = {"since": "2026-10-20T05:30:00", "at": "2026-10-20T05:30:00"}   # counting started after it
        with self.history(late), mock.patch.object(rueckblick, "last_snapshot", lambda user: snap):
            self.assertEqual(feedback.usage(None, TODAY), {})

    @env.german
    def test_tidy_up_hint_for_a_mix_nobody_plays(self):
        cfg = base_config()
        cfg["playlists"] = [{"id": "mix", "person": "jonas", "welt": "kinder", "stil": "*", "type": "mix",
                             "mix": {"every": "day"}}]
        days = [{"day": (TODAY - dt.timedelta(days=d)).isoformat(), "every": "day", "user": "jonas", "ids": ["a", "b"]}
                for d in range(1, 13)]
        a, b = self.counted([])
        with self.history({"mix": days}), a, b, mock.patch.object(suggest, "unused_playlists", lambda *x, **k: []):
            items = suggest.playlist_tidy_items(cfg, Library([song("a"), song("b")]))
        hint = next(x for x in items if x[0] == "unheard-mix|mix")
        self.assertIn("Aus den letzten 12 Ausgaben lief kein einziger Song", hint[3])
        self.assertEqual([x["do"] for x in hint[4]], ["pause", "goto"])
        a, b = self.counted([("a", TODAY - dt.timedelta(days=3))])   # one song played: no hint
        with self.history({"mix": days}), a, b, mock.patch.object(suggest, "unused_playlists", lambda *x, **k: []):
            self.assertFalse(any(x[0].startswith("unheard-mix") for x in suggest.playlist_tidy_items(cfg, Library([]))))


if __name__ == "__main__":
    unittest.main()
