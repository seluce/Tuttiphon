"""“You might still be missing”: suggestions from Last.fm that are already in the library – under a slightly different
spelling or as part of a credit – are left out. Temp data, Last.fm mocked, no network."""
from tests.python import env  # noqa: F401  (before app.*)

import unittest
from unittest import mock

from app import classify, lastfm
from app.rules import Library
from tests.python.factory import song


def library():
    return Library([
        song("s1", artist="Rolf Zuckowski und seine Freunde"),
        song("s2", artist="Simone Sommerland, Karsten Glück & die Kita-Frösche"),
        song("s3", artist="Detlev Jöcker", album="Hits", album_artists=["Various Artists"]),   # only on a compilation
        song("s4", artist="Die Ärzte"),
        song("s5", title="Duett", artists=["Volker Rosin", "Gast Sängerin"], album_artists=["Volker Rosin"]),
    ])


class ArtistPartsTest(unittest.TestCase):
    def test_parts(self):
        self.assertEqual(classify.artist_parts("Simone Sommerland, Karsten Glück & die Kita-Frösche"),
                         ["simone sommerland", "karsten gluck", "kita frosche"])
        self.assertEqual(classify.artist_parts("The Beatles feat. Billy Preston"), ["beatles", "billy preston"])
        self.assertEqual(classify.artist_parts("Mumford and Sons"), classify.artist_parts("Mumford & Sons"))
        self.assertEqual(classify.artist_parts("Guns N’ Roses"), classify.artist_parts("guns n' roses"))
        self.assertEqual(classify.artist_parts("Defeater"), ["defeater"])   # "feat" only as its own word
        self.assertEqual(classify.artist_parts(""), [])

    def test_in_library(self):
        known = classify.library_artist_parts(library())
        for name in ("Rolf Zuckowski", "Simone Sommerland, Karsten Glück, Die Kita-Frösche", "Die Kita-Frösche",
                     "Detlev Jöcker", "detlev jocker", "Ärzte", "Gast Sängerin", "Volker Rosin & Gast Sängerin"):
            self.assertTrue(classify.in_library(name, known), name)
        for name in ("Rolf Zuckowski & Nena", "Nena", "Kita", "", "Various Artists"):
            self.assertFalse(classify.in_library(name, known), name)


class MissingArtistsTest(unittest.TestCase):
    def test_present_bands_are_not_suggested(self):
        similar = {"Rolf Zuckowski und seine Freunde": {"similar": [
            ["Rolf Zuckowski", 0.9], ["Simone Sommerland, Karsten Glück, Die Kita-Frösche", 0.8], ["Detlev Jöcker", 0.7],
            ["Nena", 0.6], ["Fredrik Vahle", 0.5], ["Weit weg", 0.1]]}}
        with mock.patch.object(lastfm, "artist", side_effect=lambda name: similar.get(name)):
            got = classify.missing_artists(["Rolf Zuckowski und seine Freunde", "Unbekannt"], library())
        self.assertEqual([m["artist"] for m in got], ["Nena", "Fredrik Vahle"])
        self.assertEqual(got[0]["because"], ["Rolf Zuckowski und seine Freunde"])


if __name__ == "__main__":
    unittest.main()
