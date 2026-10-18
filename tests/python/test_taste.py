"""app/taste.py: taste per account from plays, favourites and the account's own stars.

The account's song list (stats.songs_for), the recap (rueckblick.plays_between) and the sound features
(classify.song_features) are replaced – no network access, no real data."""
from tests.python import env  # noqa: F401  (before app.*)

import datetime as dt
import json
import unittest
from collections import Counter
from unittest import mock

from app import classify, feedback, rueckblick, stats, taste
from app.rules import Library
from tests.python.factory import base_config, song

TODAY = dt.date(2026, 10, 13)


def library():
    songs = []
    for k in range(12):
        songs.append(song(f"a{k}", artist="Band A", genres=["Children"], plays=8, starred=k < 3, rating=3))
    for k in range(6):
        songs.append(song(f"m{k}", artist="Spielleute", plays=2, rating=3))
    for k in range(10):
        songs.append(song(f"x{k}", artist="Band X", plays=0, rating=5))   # 5 stars – but set by Deezer
    songs.append(song("hass", artist="Band Y", rating=1))               # 1 star by hand
    return Library(songs, ratings_exact=True, user="Jonas")


class TasteTest(unittest.TestCase):
    def setUp(self):
        env.reset_caches()
        taste._memo.clear()
        feedback._cache.clear()
        self.lib = library()
        deezer = {"songs": {f"x{k}": {"r": 900000, "s": 5, "t": 1, "u": {"Jonas": 5}} for k in range(10)}}
        deezer["songs"].update({f"a{k}": {"r": 1000, "s": 3, "t": 1, "u": {"Jonas": 3}} for k in range(12)})
        deezer["songs"]["hass"] = {"r": 500000, "s": 4, "t": 1, "u": {"Jonas": 4}}
        feedback.DEEZER_STATE.write_text(json.dumps(deezer))
        self.addCleanup(feedback.DEEZER_STATE.unlink, missing_ok=True)
        self.recent = Counter({"m0": 4, "m1": 3})
        patches = [
            mock.patch.object(stats, "songs_for", return_value=self.lib),
            mock.patch.object(rueckblick, "plays_between", side_effect=lambda *a: (self.recent, {})),
            mock.patch.object(classify, "song_features", return_value={}),
        ]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)

    def test_scores_ignore_deezer_stars_and_count_hand_dislikes(self):
        scores = taste.song_scores(self.lib, "Jonas", TODAY)
        ids = {s["id"]: i for i, s in enumerate(self.lib.songs)}
        self.assertNotIn(ids["x0"], scores)                 # 5 stars from Deezer, never heard: no signal
        self.assertLess(scores[ids["hass"]], 0)              # 1 star by hand
        self.assertGreater(scores[ids["a0"]], scores[ids["a5"]])   # favourite counts
        self.assertGreater(scores[ids["m0"]], scores[ids["m5"]])   # recently heard counts most

    def test_profile_finds_favourite_bands_and_worlds(self):
        prof = taste.profile(base_config(), self.lib, "Jonas", TODAY)
        self.assertTrue(prof["enough"])
        self.assertEqual(prof["artists"][0][0], "Band A")
        worlds = dict(prof["welten"])
        self.assertGreater(worlds["kinder"], worlds.get("mittelalter", 0))
        self.assertIn("mittelalter", worlds)
        self.assertNotIn("Band X", [a for a, _ in prof["artists"]])
        self.assertEqual(prof["basis"]["rated"], 1)   # only the one star by hand – Deezer set the others
        self.assertEqual(prof["basis"]["favorites"], 3)

    def test_too_little_listening_gives_no_profile(self):
        quiet = Library([song(f"q{k}", artist="Band A") for k in range(30)], ratings_exact=True, user="Jonas")
        self.recent.clear()
        with mock.patch.object(stats, "songs_for", return_value=quiet):
            prof = taste.profile(base_config(), quiet, "Jonas", TODAY)
        self.assertFalse(prof["enough"])
        self.assertIsNone(taste.matcher(prof, quiet))

    def test_no_password_no_profile(self):
        with mock.patch.object(stats, "songs_for", side_effect=ValueError("no password")):
            self.assertIsNone(taste.profile(base_config(), self.lib, "Jonas", TODAY))
        self.assertIsNone(taste.profile(base_config(), self.lib, "", TODAY))

    def test_matcher_prefers_the_usual_sound(self):
        feats = {i: {"energy": 0.8, "arousal": 0.8, "valence": 0.7, "dance": 0.7} for i in range(12)}   # Band A
        feats.update({i: {"energy": 0.1, "arousal": 0.1, "valence": 0.2, "dance": 0.1} for i in range(12, 28)})
        with mock.patch.object(classify, "song_features", return_value=feats):
            prof = taste.profile(base_config(), self.lib, "Jonas", TODAY)
            sim = taste.matcher(prof, self.lib)
        self.assertGreater(sim(0), sim(20))
        self.assertGreater(taste.factor(sim(0)), 1.0)
        self.assertLess(taste.factor(sim(20)), 1.0)

    def test_summary_for_the_page(self):
        prof = taste.profile(base_config(), self.lib, "Jonas", TODAY)
        out = taste.summary(base_config(), prof, self.lib)
        self.assertTrue(out["available"] and out["enough"])
        self.assertEqual(out["artists"][0]["name"], "Band A")
        self.assertEqual(out["welten"][0]["name"], "Kinder")
        self.assertEqual(taste.summary(base_config(), None, self.lib), {"available": False})


if __name__ == "__main__":
    unittest.main()
