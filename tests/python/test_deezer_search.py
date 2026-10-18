"""Deezer stars, version 2: hits only from the right band, fallback via the ISRC, wrong stars removed again,
top songs per band, refreshing in batches. Without network – Deezer and Navidrome are mocked."""
from tests.python import env  # noqa: F401  (before app.*)

import unittest
from unittest import mock

from app import deezer


def track(title, artist, album_artist=None, sid="x"):
    return {"id": sid, "title": title, "artist": artist, "artists": [{"name": a} for a in artist.split(", ")],
            "albumArtists": [{"name": album_artist or artist}]}


def hit(artist, title, rank, short=None):
    return {"artist": {"name": artist}, "title": title, "title_short": short or title, "rank": rank}


class MatchingTest(unittest.TestCase):
    def test_only_the_right_band_and_title(self):
        bellini = track("Vem Vem Vem", "Bellini")
        self.assertTrue(deezer.matches(bellini, hit("Bellini", "Vem Vem Vem", 2811)))
        self.assertFalse(deezer.matches(bellini, hit("Bassjackers", "Samba De Janeiro (Dimitri Vegas Edit)", 542822)))
        self.assertFalse(deezer.matches(track("Bored", "Pentatonix"), hit("Pentatonix", "Bohemian Rhapsody", 431207)))

    def test_tolerates_spelling(self):
        kita = track("Wer will fleißige Handwerker seh'n", "Simone Sommerland, Karsten Glück, die Kita-Frösche",
                     album_artist="Simone Sommerland, Karsten Glück & die Kita-Frösche")
        self.assertTrue(deezer.matches(kita, hit("Simone Sommerland", "Wer will fleißige Handwerker sehn", 166884)))
        self.assertTrue(deezer.matches(track("Lappi (Remastered)", "Nightwish"), hit("Nightwish", "Lappi - Remastered 2004", 1)))
        self.assertTrue(deezer.matches(track("Hello feat. X", "Band"), hit("Band", "Hello", 1)))

    def test_best_rank_takes_the_best_matching_hit(self):
        c = deezer.DeezerClient()
        hits = [hit("Pentatonix", "Bohemian Rhapsody", 431207), hit("Pentatonix", "Bored", 67789),
                hit("Pentatonix", "Bored (Live)", 12000, short="Bored")]
        with mock.patch.object(c, "_get", return_value=hits) as get:
            self.assertEqual(c.best_rank(track("Bored", "Pentatonix")), 67789)
        self.assertIn('artist:"Pentatonix"', get.call_args_list[0][0][0])
        with mock.patch.object(c, "_get", return_value=[hit("Jemand", "Anders", 999999)]):
            self.assertIsNone(c.best_rank(track("Bored", "Pentatonix")))


class TopSongsTest(unittest.TestCase):
    def test_top_songs_of_a_band_get_one_star_more(self):
        ranks = {"barbie": 800000, "robot": 790000, "good": 700000, "man": 650000, "aquarius": 620000, "jones": 610000}
        songs = [track(t, "Aqua", sid=t) for t in ranks] + [track("barbie", "Aqua", sid="barbie-single")]
        entries = {sid: {"r": r} for sid, r in ranks.items()} | {"barbie-single": {"r": 795000}}
        top = deezer.top_songs(songs, entries)
        self.assertEqual(top, {"barbie", "barbie-single", "robot", "good"})        # same title counts as one song
        self.assertEqual(deezer._stars(800000, None, True), 5)
        # already 5 stars at the top or only one song on the level: nothing to do
        entries = {sid: {"r": 900000 if sid == "barbie" else 300000} for sid in ranks}
        self.assertEqual(deezer.top_songs(songs[:6], entries), set())


class ApplyTest(unittest.TestCase):
    def test_wrongly_matched_star_is_removed_but_manual_stays(self):
        nav = mock.Mock()
        users = {"niklas": (nav, {"a": 4, "b": 5})}
        entries = {"a": {"r": 700000, "s": 4, "u": {"niklas": 4}}, "b": {"r": 700000, "s": 4, "u": {"niklas": 4}}}
        result = {"processed": 0, "found": 0, "notFound": 0, "set": 0, "kept": 0, "cleared": 0, "isrc": 0, "top": 0}
        for sid in ("a", "b"):
            deezer._apply(track("Song", "Band", sid=sid), None, entries, users, "refresh", False, False, result, lambda *_: None)
        nav.set_rating.assert_called_once_with("a", 0)       # someone set b to 5 by hand – stays
        self.assertEqual((result["cleared"], entries["a"]["v"], entries["a"]["r"]), (1, 2, None))

    def test_isrc_is_remembered(self):
        users = {"niklas": (mock.Mock(), {})}
        entries = {}
        result = {"processed": 0, "found": 0, "notFound": 0, "set": 0, "kept": 0, "cleared": 0, "isrc": 0, "top": 0}
        deezer._apply(track("Song", "Band", sid="a"), 300000, entries, users, "new", False, False, result, lambda *_: None,
                      isrc="DEABC1234567")
        self.assertEqual((entries["a"]["i"], result["isrc"]), ("DEABC1234567", 1))

    def test_refresh_order(self):
        songs = [track("x", "B", sid=s) for s in ("alt-neu", "alt-alt", "v2")]
        entries = {"alt-neu": {"t": 200}, "alt-alt": {"t": 100}, "v2": {"t": 1, "v": 2}}
        self.assertEqual([s["id"] for s in deezer.refresh_order(songs, entries)], ["alt-alt", "alt-neu", "v2"])


if __name__ == "__main__":
    unittest.main()
