"""Deezer stars with ListenBrainz as the second source: songs Deezer does not find get their stars from the number of
ListenBrainz listeners, while Deezer does not answer only songs without a Deezer rank do – the others stay as they
are, nothing is removed. Temp folders; Deezer, MusicBrainz, ListenBrainz and Navidrome are fakes (no network)."""
from tests.python import env  # noqa: F401  (before app.*)

import io
import json
import unittest
import urllib.error
from unittest import mock

from app import config, deezer
from tests.python.factory import base_config

M_LB = "11111111-1111-4111-8111-111111111111"     # ListenBrainz has listeners for it
M_NONE = "22222222-2222-4222-8222-222222222222"   # ListenBrainz knows it, without listeners
SONGS = [{"id": sid, "title": sid, "artist": "Band", "artists": [{"name": "Band"}], "albumArtists": [{"name": "Band"}]}
         for sid in ("dz", "lbonly", "none", "nombid")]
MBIDS = {"lbonly": M_LB, "none": M_NONE}


class FakeNav:
    ratings = {}
    calls = []

    def __init__(self, *a, **k):
        pass

    def all_songs(self):
        return [{**s, "userRating": self.ratings.get(s["id"], 0)} for s in SONGS]

    def set_rating(self, sid, stars):
        FakeNav.calls.append((sid, stars))


class FakeNative:
    def _request(self, method, path):
        return {"mbzRecordingID": MBIDS.get(path.rsplit("/", 1)[-1], "")}


class StarsWithListenBrainzTest(unittest.TestCase):
    def setUp(self):
        deezer.STATE_FILE.unlink(missing_ok=True)
        self.addCleanup(deezer.STATE_FILE.unlink, missing_ok=True)
        FakeNav.ratings, FakeNav.calls = {}, []
        self.cfg = base_config()
        self.cfg["settings"]["deezer"] = {"users": ["anna"]}
        self.env = {"NAV_URL": "http://nav.test", "NAV_ADMIN_USER": "admin", "NAV_ADMIN_PASS": "x",
                    config.pass_key("anna"): "x"}
        self.deezer_ranks = {"dz": 700000}
        self.deezer_down = False
        self.lb_down = False
        self.lb_asked = []
        for p in (mock.patch.object(deezer, "Navidrome", FakeNav),
                  mock.patch("app.navidrome.native_session", return_value=FakeNative()),
                  mock.patch.object(deezer.DeezerClient, "best_rank", side_effect=self.best_rank),
                  mock.patch.object(deezer.DeezerClient, "rank_by_isrc", return_value=None),
                  mock.patch.object(deezer.MusicBrainz, "isrcs", return_value=[]),
                  mock.patch.object(deezer.ListenBrainz, "_post", side_effect=self.lb_post)):
            p.start()
            self.addCleanup(p.stop)
        self.lines = []

    def best_rank(self, song):
        if self.deezer_down:
            raise ConnectionError("Deezer does not respond (tried several times)")
        return self.deezer_ranks.get(song["id"])

    def lb_post(self, ids):
        self.lb_asked.append(list(ids))
        if self.lb_down:
            raise ConnectionError("ListenBrainz does not respond (tried several times)")
        return [{"recording_mbid": M_LB, "total_user_count": 500}, {"recording_mbid": M_NONE, "total_user_count": None}]

    def rate(self, mode="new"):
        return deezer.run(self.env, mode=mode, log=lambda x: self.lines.append(str(x)), cfg=self.cfg)

    def entries(self):
        return json.loads(deezer.STATE_FILE.read_text())["songs"]

    def test_songs_deezer_does_not_find(self):
        res = self.rate()
        e = self.entries()
        self.assertEqual((e["dz"]["r"], e["dz"].get("src")), (700000, None))
        rank = deezer.listeners_to_rank(500)
        self.assertEqual((e["lbonly"]["r"], e["lbonly"]["src"], e["lbonly"]["s"]),
                         (rank, "lb", deezer.rank_to_stars(rank)))
        self.assertIsNone(e["none"]["r"])                       # no listeners: not found, as before
        self.assertIsNone(e["nombid"]["r"])                     # without a MusicBrainz ID ListenBrainz can't help
        self.assertEqual(self.lb_asked, [[M_LB, M_NONE]])       # one request for the whole portion
        self.assertEqual((res["found"], res["lb"], res["notFound"]), (2, 1, 2))
        self.assertTrue(any("neither on Deezer nor on ListenBrainz" in x for x in self.lines))
        self.assertTrue(any("of them from ListenBrainz" in x for x in self.lines))
        self.assertEqual(deezer.stats()["listenbrainz"], 1)
        self.assertEqual(deezer.rank_histogram()["listenbrainz"], 1)

    def test_turned_off(self):
        self.cfg["settings"]["deezer"]["listenbrainz"] = False
        self.rate()
        self.assertIsNone(self.entries()["lbonly"]["r"])
        self.assertEqual(self.lb_asked, [])
        self.assertTrue(any("not found on Deezer" in x for x in self.lines))

    def test_deezer_does_not_answer(self):
        deezer.save_state({"version": 1, "songs": {"dz": {"r": 700000, "s": 4, "t": 5, "u": {"anna": 4}}}})
        FakeNav.ratings = {"dz": 4}
        self.deezer_down = True
        res = self.rate("full")
        e = self.entries()
        self.assertEqual(e["dz"], {"r": 700000, "s": 4, "t": 5, "u": {"anna": 4}})   # Deezer's rank stays untouched
        self.assertEqual(e["lbonly"]["src"], "lb")
        self.assertNotIn("none", e)                              # nobody could say anything: comes again next time
        self.assertNotIn("nombid", e)
        self.assertEqual(res["skipped"], 3)
        self.assertNotIn(("dz", 0), FakeNav.calls)               # no star removed
        self.assertIn("full", json.loads(deezer.STATE_FILE.read_text()))   # the full check isn't over yet
        self.assertEqual(sum("Deezer does not answer" in x for x in self.lines), 1)

    def test_deezer_does_not_answer_without_listenbrainz(self):
        self.cfg["settings"]["deezer"]["listenbrainz"] = False
        self.deezer_down = True
        with self.assertRaises(ConnectionError):
            self.rate()

    def test_listenbrainz_does_not_answer(self):
        rank = deezer.listeners_to_rank(500)
        deezer.save_state({"version": 1, "songs": {"lbonly": {"r": rank, "s": 3, "t": 5, "u": {"anna": 3}, "src": "lb"}}})
        FakeNav.ratings = {"lbonly": 3}
        self.lb_down = True
        res = self.rate("full")
        e = self.entries()
        self.assertEqual(e["lbonly"]["src"], "lb")               # rated by ListenBrainz before: stays
        self.assertEqual(e["lbonly"]["t"], 5)
        self.assertIsNone(e["none"]["r"])                        # never had anything: not found, as without ListenBrainz
        self.assertNotIn(("lbonly", 0), FakeNav.calls)
        self.assertEqual(res["skipped"], 1)
        self.assertEqual(sum("ListenBrainz does not answer" in x for x in self.lines), 1)

    def test_deezer_finds_it_again(self):
        deezer.save_state({"version": 1, "songs": {"lbonly": {"r": 5000, "s": 0, "t": 5, "u": {}, "src": "lb"}}})
        self.deezer_ranks["lbonly"] = 400000
        self.rate("refresh")
        self.assertNotIn("src", self.entries()["lbonly"])        # Deezer's rank replaces the stand-in

    def test_recalc_keeps_the_source(self):
        deezer.save_state({"version": 1, "songs": {"lbonly": {"r": 650000, "s": 3, "t": 5, "u": {}, "src": "lb"}}})
        self.rate("recalc")
        e = self.entries()["lbonly"]
        self.assertEqual((e["s"], e["src"]), (4, "lb"))
        self.assertEqual(self.lb_asked, [])


class ListenBrainzClientTest(unittest.TestCase):
    def test_listeners_to_rank(self):
        self.assertIsNone(deezer.listeners_to_rank(0))
        self.assertIsNone(deezer.listeners_to_rank(None))
        ranks = [deezer.listeners_to_rank(n) for n in (1, 3, 10, 50, 100, 1000, 10000, 10 ** 6)]
        self.assertEqual(ranks, sorted(ranks))                   # more listeners, never a lower rank
        self.assertLess(ranks[0], ranks[-1])
        self.assertLessEqual(ranks[-1], 1000000)
        self.assertEqual(deezer.listeners_to_rank(10 ** 6), deezer.LB_ANCHORS[-1][1])

    def test_batches_and_filters(self):
        ids = [f"{k:08x}-0000-4000-8000-000000000000" for k in range(1500)] + ["not-an-id", ""]
        asked = []

        def post(batch):
            asked.append(len(batch))
            return [{"recording_mbid": batch[0], "total_user_count": 7}, {"recording_mbid": batch[1], "total_user_count": 0},
                    {"recording_mbid": "elsewhere", "total_user_count": 9}, "junk"]
        with mock.patch.object(deezer.ListenBrainz, "_post", side_effect=post):
            got = deezer.ListenBrainz().listeners(ids + ids[:3])
        self.assertEqual(asked, [1000, 500])
        self.assertEqual(got, {ids[0]: 7, ids[1000]: 7})

    def test_retries_and_gives_up(self):
        busy = urllib.error.HTTPError(deezer.LB_API, 503, "busy", {}, io.BytesIO(b""))
        answer = mock.MagicMock()
        answer.__enter__.return_value.read.return_value = json.dumps([{"recording_mbid": M_LB, "total_user_count": 3}]).encode()
        answer.__enter__.return_value.headers = {}
        with mock.patch("urllib.request.urlopen", side_effect=[busy, answer]), mock.patch("time.sleep"):
            self.assertEqual(deezer.ListenBrainz().listeners([M_LB]), {M_LB: 3})
        with mock.patch("urllib.request.urlopen", side_effect=busy), mock.patch("time.sleep"), \
                self.assertRaises(ConnectionError):
            deezer.ListenBrainz().listeners([M_LB])
        refused = urllib.error.HTTPError(deezer.LB_API, 400, "bad", {}, io.BytesIO(b""))
        with mock.patch("urllib.request.urlopen", side_effect=refused):
            self.assertEqual(deezer.ListenBrainz().listeners([M_LB]), {})


if __name__ == "__main__":
    unittest.main()
