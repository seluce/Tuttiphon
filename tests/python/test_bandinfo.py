"""Band knowledge (app/bandinfo.py): similar bands and tags from ListenBrainz/MusicBrainz and Deezer – free and without
a key – merged with what Last.fm delivered; Last.fm only with a key that it still accepts. Temp folders, the services
are answered by a fake (no network)."""
from tests.python import env  # noqa: F401  (before app.*)

import json
import threading
import unittest
import urllib.parse
from unittest import mock

from app import bandinfo, lastfm

NIGHTWISH = "00a9f935-ba93-4fc8-a33a-993abe9c936b"
ROLF = "60a2a697-21d8-4a32-bdd4-53aaf0f13943"


class Services:
    """Answers of MusicBrainz, ListenBrainz and Deezer by URL – and which URLs were asked."""

    def __init__(self):
        self.asked = []
        self.broken = set()   # hosts that fail

    def __call__(self, url, pace, attempts=3):
        self.asked.append(url)
        parts = urllib.parse.urlsplit(url)
        q = dict(urllib.parse.parse_qsl(parts.query))
        if parts.netloc in self.broken:
            raise bandinfo.BandError("HTTP 503")
        if parts.netloc == "musicbrainz.org":
            hits = {'artist:"Rolf Zuckowski"': [{"id": "other", "name": "Rolf Zuckowski und seine Freunde", "score": "100"},
                                                {"id": ROLF, "name": "Rolf Zuckowski", "score": "100"}],
                    'artist:"Nobody"': [{"id": "x", "name": "Nobody Else", "score": "100"}]}
            return {"artists": hits.get(q["query"], [])}
        if parts.path.startswith("/similar-artists"):
            return {NIGHTWISH: [{"name": "Within Temptation", "artist_mbid": "wt", "score": 3000},
                                {"name": "Epica", "artist_mbid": "ep", "score": 1500}],
                    ROLF: [{"name": "Simone Sommerland", "artist_mbid": "ss", "score": 100}]}.get(q["artist_mbids"], [])
        if parts.path.startswith("/1/metadata/artist"):
            tags = {NIGHTWISH: [{"tag": "symphonic metal", "count": 30}, {"tag": "Metal", "count": 6},
                                {"tag": "boring", "count": -2}]}.get(q["artist_mbids"], [])
            return [{"artist_mbid": q["artist_mbids"], "tag": {"artist": tags}}]
        if parts.path == "/search/artist":
            return {"data": {"Nightwish": [{"id": 1, "name": "NIGHTWISH", "nb_fan": 10}, {"id": 2, "name": "Nightwish", "nb_fan": 900},
                                           {"id": 3, "name": "Nightwish Tribute", "nb_fan": 5000}],
                             "Rolf Zuckowski": [{"id": 7, "name": "Rolf Zuckowski", "nb_fan": 60}]}.get(q["q"], [])}
        if parts.path.endswith("/related"):
            rel = {"2": ["Epica", "Tarja"], "7": ["Detlev Jöcker"]}.get(parts.path.split("/")[2], [])
            return {"data": [{"name": n} for n in rel], "total": len(rel)}
        raise AssertionError(url)


class BandKnowledgeTest(unittest.TestCase):
    def setUp(self):
        for f in (bandinfo.STATE_FILE, lastfm.STATE_FILE):
            f.unlink(missing_ok=True)
            self.addCleanup(f.unlink, missing_ok=True)
        bandinfo._mem.update(stamp=None, data=None)
        lastfm._mem.update(stamp=None, data=None)
        self.services = Services()
        for p in (mock.patch.object(bandinfo, "_get", self.services),
                  mock.patch.object(bandinfo, "navidrome_ids", return_value={"Nightwish": NIGHTWISH})):
            p.start()
            self.addCleanup(p.stop)
        self.lines = []

    def refresh(self, names, use=bandinfo.SOURCES, **kw):
        return bandinfo.refresh(names, list(use), log=self.lines.append, **kw)

    def test_both_sources_without_a_key(self):
        res = self.refresh(["Nightwish", "Rolf Zuckowski"])
        self.assertEqual(res, {"artists": 2, "later": 0})
        nw = bandinfo.artist("Nightwish")
        self.assertEqual(nw["tags"], [["symphonic metal", 100], ["metal", 20]])      # like Last.fm: the top tag 100
        self.assertEqual(nw["similar"][0], ["Epica", 1.0])                           # Deezer's first – the strongest
        self.assertEqual(dict(nw["similar"])["Within Temptation"], bandinfo.LB_WEIGHT)
        self.assertEqual(dict(nw["similar"])["Tarja"], 1 - bandinfo.DZ_STEP)
        # the MusicBrainz ID from Navidrome: no search; Rolf Zuckowski by his exact name
        searched = [u for u in self.services.asked if "musicbrainz.org" in u]
        self.assertEqual(len(searched), 1)
        self.assertIn("Rolf", searched[0])
        stored = bandinfo.load()["artists"]
        self.assertEqual((stored["Rolf Zuckowski"]["mbid"], stored["Nightwish"]["dz"]), (ROLF, 2))   # the most fans
        self.assertEqual(stored["Rolf Zuckowski"]["src"], ["listenbrainz", "deezer"])
        self.assertEqual([s for s, _m in bandinfo.artist("Rolf Zuckowski")["similar"]], ["Detlev Jöcker", "Simone Sommerland"])

    def test_nothing_twice_and_a_source_turned_on_later(self):
        self.refresh(["Nightwish"], use=["listenbrainz"])
        self.assertNotIn("dz", bandinfo.load()["artists"]["Nightwish"])
        self.services.asked.clear()
        self.assertEqual(self.refresh(["Nightwish"], use=["listenbrainz"])["artists"], 0)
        self.assertEqual(self.services.asked, [])
        self.assertEqual(self.refresh(["Nightwish"])["artists"], 1)   # Deezer turned on: the band is due again
        self.assertEqual(bandinfo.load()["artists"]["Nightwish"]["dz"], 2)

    def test_no_band_by_another_name(self):
        self.refresh(["Nobody"])
        self.assertEqual(bandinfo.artist("Nobody"), {"tags": [], "similar": []})   # asked: known, but nothing there
        self.assertIsNone(bandinfo.artist("Never asked"))

    def test_a_failing_source_keeps_its_data_and_gives_up(self):
        self.refresh(["Nightwish"])
        self.services.broken.add("api.deezer.com")
        names = ["Nightwish"] + [f"Band {k}" for k in range(8)]
        self.refresh(names, everything=True)
        nw = bandinfo.load()["artists"]["Nightwish"]
        self.assertEqual(nw["src"], ["listenbrainz"])                    # due again in the next run …
        self.assertEqual([s for s, _m in nw["deezer"]], ["Epica", "Tarja"])   # … and Deezer's similar bands stay
        deezer = [u for u in self.services.asked if "deezer" in u]
        self.assertEqual(len(deezer), 2 + bandinfo.GIVE_UP)              # given up after GIVE_UP failures
        self.assertTrue(any("Deezer" in str(x) for x in self.lines))

    def test_merged_with_lastfm(self):
        lastfm.STATE_FILE.write_text(json.dumps({"artists": {
            "Nightwish": {"t": 1, "tags": [["female vocalists", 100], ["symphonic metal", 60]],
                          "similar": [["Epica", 0.5], ["Delain", 0.9]]},
            "Only Lastfm": {"t": 1, "tags": [["pop", 100]], "similar": []}}}))
        self.refresh(["Nightwish"])
        nw = bandinfo.artist("Nightwish")
        self.assertEqual(dict(nw["tags"]), {"symphonic metal": 100, "female vocalists": 100, "metal": 20})
        self.assertEqual([s for s, _m in nw["similar"]], ["Epica", "Tarja", "Delain", "Within Temptation"])   # the strongest value
        self.assertEqual(bandinfo.artist("Only Lastfm")["tags"], [["pop", 100]])
        before = bandinfo.stamp()
        lastfm.STATE_FILE.write_text(json.dumps({"artists": {}}))
        self.assertNotEqual(bandinfo.stamp(), before)
        self.assertNotIn("female vocalists", dict(bandinfo.artist("Nightwish")["tags"]))
        st = bandinfo.stats()
        self.assertEqual((st["artists"], st["listenbrainz"], st["deezer"]), (1, 1, 1))

    def test_stop_and_time_limit(self):
        stop = threading.Event()
        stop.set()
        self.assertEqual(self.refresh(["Nightwish"], stop=stop)["artists"], 0)
        with mock.patch("time.time", side_effect=[1000.0, 1000.0] + [99999.0] * 20):
            res = self.refresh(["Nightwish", "Rolf Zuckowski"], budget=1)
        self.assertEqual(res, {"artists": 0, "later": 2})

    def test_names_and_settings(self):
        self.assertEqual(bandinfo._key("The Beatles"), bandinfo._key("beatles"))
        self.assertEqual(bandinfo._key("Simon & Garfunkel"), bandinfo._key("Simon and Garfunkel"))
        self.assertEqual(bandinfo._key("Die Ärzte"), bandinfo._key("Die Arzte"))
        self.assertNotEqual(bandinfo._key("Theodor"), bandinfo._key("odor"))
        self.assertEqual(bandinfo.sources({}), ["listenbrainz", "deezer"])
        self.assertEqual(bandinfo.sources({"deezerSimilar": False}), ["listenbrainz"])
        self.assertEqual(self.refresh(["Nightwish"], use=[]), {"artists": 0, "later": 0})


class LastfmKeyTest(unittest.TestCase):
    def setUp(self):
        lastfm.STATE_FILE.unlink(missing_ok=True)
        self.addCleanup(lastfm.STATE_FILE.unlink, missing_ok=True)
        lastfm._mem.update(stamp=None, data=None)
        p = mock.patch.object(lastfm, "api_key", return_value="free-key")
        p.start()
        self.addCleanup(p.stop)

    def test_a_rejected_key_is_shown(self):
        with mock.patch.object(lastfm.Client, "call", side_effect=lastfm.LastfmError("invalid", bad_key=True)):
            with self.assertRaises(lastfm.LastfmError):
                lastfm.refresh(["Nightwish"], log=lambda *_: None)
        self.assertTrue(lastfm.stats()["rejected"])
        with mock.patch.object(lastfm, "api_key", return_value="pro-key"):   # another key: not rejected (yet)
            self.assertFalse(lastfm.stats()["rejected"])

    def test_errors_in_a_row_end_the_run(self):
        with mock.patch.object(lastfm.Client, "call", side_effect=lastfm.LastfmError("Last.fm: 403")) as call:
            res = lastfm.refresh([f"Band {k}" for k in range(20)], log=lambda *_: None)
        self.assertEqual(call.call_count, lastfm.GIVE_UP)
        self.assertEqual(res, {"artists": 0, "later": 20 - lastfm.GIVE_UP})


if __name__ == "__main__":
    unittest.main()
