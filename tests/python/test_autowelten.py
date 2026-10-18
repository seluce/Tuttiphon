"""app/autowelten.py: music worlds emerge by themselves from genres, Last.fm tags, language and decade.
Without network and without real data – Last.fm, taste and lyrics language are replaced or empty."""
from tests.python import env  # noqa: F401  (before app.*)

import json
import unittest
from unittest import mock

from app import autowelten, config, lastfm, rules, taste
from app.rules import Library, BuildContext
from tests.python.factory import base_config, song


def band(name, n, genres=(), year=2010, titles="Lied", album=None):
    return [song(f"{name}-{k}", f"{titles} {k}", artist=name, album=album or f"{name} Album", genres=list(genres), year=year)
            for k in range(n)]


def library():
    songs = []
    for name in ("Euro A", "Euro B", "Euro C", "Euro D"):
        songs += band(name, 20, ["Eurodance", "Pop"], 1995)
    for name in ("Rap Eins", "Rap Zwei"):
        songs += band(name, 15, ["Hip Hop"], 2015, titles="Ich bin nicht der und die")
    for name in ("Rapper One", "Rapper Two"):
        songs += band(name, 15, ["Hip Hop"], 2015, titles="I love you and the night")
    for name in ("Synth 1", "Synth 2", "Synth 3", "Synth 4", "Synth 5"):
        songs += band(name, 20, ["Synth-Pop"], 1984)
    songs += band("Kelly", 3, ["Pop"], 2018)
    return Library(songs)


class AutoWorldsTest(unittest.TestCase):
    def setUp(self):
        env.reset_caches()
        autowelten._memo.clear()
        lastfm._mem.update(stamp=None, data=None)
        lastfm.STATE_FILE.write_text(json.dumps({"artists": {
            "Kelly": {"tags": [["80s", 100], ["pop", 80]]},
        }}))
        self.addCleanup(lastfm.STATE_FILE.unlink, missing_ok=True)
        p = mock.patch.object(taste, "profile", return_value=None)
        p.start()
        self.addCleanup(p.stop)
        self.lib = library()

    def test_profiles_language_and_era(self):
        prof = autowelten.profiles(self.lib)
        self.assertEqual(prof["Rap Eins"]["lang"], "de")
        self.assertEqual(prof["Rapper One"]["lang"], "en")
        self.assertEqual(prof["Euro A"]["era"], 1995)
        self.assertEqual(prof["Kelly"]["decades"], {1980})

    def test_assign_uses_language_and_decades(self):
        a = autowelten.assign(self.lib)
        self.assertEqual(a["primary"]["Euro A"][0], "eurodance")
        self.assertEqual(a["primary"]["Rap Eins"][0], "deutschrap")
        self.assertEqual(a["primary"]["Rapper One"][0], "hiphop")
        self.assertIn("Synth 1", a["members"]["achtziger"])
        self.assertIn("Kelly", a["members"]["achtziger"])        # Last.fm says 80s, even if the years are recent
        self.assertNotIn("Euro A", a["members"].get("achtziger", []))

    def test_candidates_and_sync(self):
        cfg = base_config()
        config.save_config(cfg)
        found = {c["scene"]["id"]: c for c in autowelten.candidates(cfg, self.lib)}
        self.assertIn("eurodance", found)
        self.assertIn("achtziger", found)
        self.assertNotIn("deutschrap", found)     # too few: 2 bands, and nobody listens to them much
        made = autowelten.sync(self.lib)
        self.assertEqual({m["id"] for m in made}, {"eurodance", "achtziger"})
        cfg = config.load_config()
        w = next(x for x in cfg["welten"] if x["id"] == "eurodance")
        self.assertTrue(w["autoScene"] and w["auto"])
        self.assertEqual(set(rules.welt_artists(w, BuildContext(self.lib))), {"Euro A", "Euro B", "Euro C", "Euro D"})
        self.assertEqual(autowelten.sync(self.lib), [])   # already there

    def test_dismissed_and_switched_off(self):
        cfg = base_config()
        cfg["dismissed"] = ["scene|eurodance"]
        cfg["settings"]["welten"] = {"auto": False}
        config.save_config(cfg)
        self.assertEqual(autowelten.sync(self.lib), [])
        cfg["settings"]["welten"] = {"auto": True}
        config.save_config(cfg)
        self.assertEqual({m["id"] for m in autowelten.sync(self.lib)}, {"achtziger"})

    def test_existing_world_with_same_bands_is_not_duplicated(self):
        cfg = base_config()
        cfg["welten"].append({"id": "dance", "name": "Dance", "artists": ["Euro A", "Euro B", "Euro C"]})
        config.save_config(cfg)
        self.assertNotIn("eurodance", {c["scene"]["id"] for c in autowelten.candidates(cfg, self.lib)})

    def test_heard_lowers_the_bar(self):
        cfg = base_config()
        with mock.patch.object(autowelten, "_heard_shares", return_value={"Jonas": {"Rap Eins": 0.3, "Rap Zwei": 0.1}}):
            found = {c["scene"]["id"]: c for c in autowelten.candidates(cfg, self.lib)}
        self.assertEqual(found["deutschrap"]["heard"], ["Jonas"])


if __name__ == "__main__":
    unittest.main()
