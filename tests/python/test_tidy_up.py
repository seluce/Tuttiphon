"""Version 0.7: fetching missing covers, tidying up playlists (season, unused, duplicate), good-morning and car-ride mix.
No network, no real data."""
from tests.python import env  # noqa: F401  (before app.*)

import datetime as dt
import unittest
from collections import Counter
from unittest import mock

from app import albumcover, config, mixer, rueckblick, rules, suggest
from app.rules import Library
from tests.python.factory import base_config, song


class SeasonTest(unittest.TestCase):
    def setUp(self):
        self.cfg = base_config()
        self.p = {"id": "x", "person": "familie", "welt": "kinder", "stil": "weihnachten", "status": "aktiv"}

    def test_resting_outside_season(self):
        self.assertEqual(rules.resting(self.cfg, self.p, dt.date(2026, 7, 1)), dt.date(2026, 11, 25))
        self.assertIsNone(rules.resting(self.cfg, self.p, dt.date(2026, 12, 24)))
        self.assertIsNone(rules.resting(self.cfg, {**self.p, "yearRound": True}, dt.date(2026, 7, 1)))
        self.assertIsNone(rules.resting(self.cfg, {**self.p, "stil": "jahreszeit"}, dt.date(2026, 7, 1)))
        self.cfg["settings"]["seasonRest"] = False
        self.assertIsNone(rules.resting(self.cfg, self.p, dt.date(2026, 7, 1)))

    def test_plan_skips_resting(self):
        from app import playlists
        self.cfg["playlists"] = [self.p, {"id": "y", "person": "familie", "welt": "kinder", "stil": "*", "status": "aktiv"}]
        lib = Library([song("s1", genres=["Children"])])
        with mock.patch.object(rules, "resting", side_effect=lambda cfg, p, today=None: dt.date(2026, 11, 25) if p["id"] == "x" else None):
            planned = [p["id"] for p, _, _ in playlists.plan(self.cfg, rules.BuildContext(lib))]
        self.assertEqual(planned, ["y"])


class TidyUpTest(unittest.TestCase):
    def setUp(self):
        self.cfg = base_config()
        self.lib = Library([song("a1", artist="Band A", genres=["Children"]), song("m1", artist="Spielleute", album="Mittelaltermarkt")])
        self.cfg["playlists"] = [
            {"id": "kids", "person": "familie", "welt": "kinder", "stil": "*", "status": "aktiv", "created": "2025-01-01", "minRating": 0},
            {"id": "mittel", "person": "familie", "welt": "mittelalter", "stil": "*", "status": "aktiv", "created": "2025-01-01", "minRating": 0},
        ]

    def test_unused_only_with_enough_history(self):
        with mock.patch.object(rueckblick, "last_snapshot", return_value={"since": "2025-01-01T00:00:00"}), \
                mock.patch.object(rueckblick, "plays_between", return_value=(Counter({"a1": 3}), {})):
            unused = suggest.unused_playlists(self.cfg, self.lib, today=dt.date(2026, 10, 13))
        self.assertEqual([p["id"] for p in unused], ["mittel"])
        with mock.patch.object(rueckblick, "last_snapshot", return_value={"since": "2026-10-01T00:00:00"}), \
                mock.patch.object(rueckblick, "plays_between", return_value=(Counter(), {})):
            self.assertEqual(suggest.unused_playlists(self.cfg, self.lib, today=dt.date(2026, 10, 13)), [])

    def test_duplicates(self):
        self.cfg["playlists"].append({**self.cfg["playlists"][0], "id": "kids2", "name": "Nochmal"})
        groups = suggest.duplicate_playlists(self.cfg)
        self.assertEqual([[p["id"] for p in g] for g in groups], [["kids", "kids2"]])


class MorningTest(unittest.TestCase):
    def test_rise_order(self):
        lib = Library([song(f"s{k}", artist=f"Band {k}") for k in range(4)])
        feats = {k: {"arousal": a} for k, a in enumerate((0.7, 0.2, 0.5, 0.3))}
        self.assertEqual(mixer.calm_down(lib, [0, 1, 2, 3], feats, rise=True), [1, 3, 2, 0])

class CoverTest(unittest.TestCase):
    def setUp(self):
        self.root = env.MUSIC
        folder = self.root / "Band" / "Ohne"
        folder.mkdir(parents=True, exist_ok=True)
        (self.root / "Band" / "Mit").mkdir(parents=True, exist_ok=True)
        (self.root / "Band" / "Mit" / "folder.jpg").write_bytes(b"x")
        songs = [song("o1", album="Ohne", album_id="al-o"), song("w1", album="Mit", album_id="al-w"),
                 song("n1", album="Neu", album_id="al-n")]
        self.lib = Library(songs)
        self.lib.path_loader = lambda: ({"o1": "Band/Ohne/o1.opus", "w1": "Band/Mit/w1.opus", "n1": "Band/Neu/n1.opus"}, {})

    def test_candidates(self):
        old = "2026-01-01T00:00:00Z"
        meta = [{"id": "al-o", "name": "Ohne", "albumArtist": "Band", "createdAt": old, "mbzAlbumId": "x"},
                {"id": "al-w", "name": "Mit", "albumArtist": "Band", "createdAt": old},                    # image in the folder
                {"id": "al-n", "name": "Neu", "albumArtist": "Band", "createdAt": dt.date.today().isoformat()},   # give Lidarr time
                {"id": "al-x", "name": "Hat", "albumArtist": "Band", "createdAt": old, "imageHash": "abc"}]
        got = albumcover.candidates(self.lib, self.root, meta)
        self.assertEqual([a["id"] for a in got], ["al-o"])
        self.assertEqual(albumcover.candidates(self.lib, self.root, meta, {"al-o": {"t": 9e12}}), [])   # only just tried

    def test_image_check(self):
        self.assertIsNone(albumcover._image(b"\xff\xd8\xff" + b"0" * 100))   # too small
        self.assertIsNone(albumcover._image(b"<html>" + b"0" * 20000))       # not an image


if __name__ == "__main__":
    unittest.main()
