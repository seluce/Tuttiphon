"""Themes of the AI sound analysis (MTG-Jamendo mood/theme model, "t" per song in state/ml.json): which ones count,
sound filters, validation, the catalog, search words, the search's theme group and the combined search – with the
precedence of music worlds and vibes over the AI's guess – and Christmas songs that a theme filter may contain.
No Essentia needed: the results are written into temp files."""
from tests.python import env  # noqa: F401  (before app.*)

import json
import os
import unittest
from unittest import mock

from app import audio, classify, config, lastfm, ml, rules, similar
from app.rules import ALL, BuildContext, Library
from tests.python.factory import base_config, song

RAW = {"v": audio.VERSION, "depth": "standard", "bpm": 120.0, "beat": 0.7, "loud": -10.0, "dyn": 12.0,
       "cent": 1800, "flat": 0.2, "flux": 60.0, "path": "x"}
_mtime = [1_900_000_000 * 10 ** 9]


def write_json(path, data):
    """Write the file with a modification time never used before – the caches see every change."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")
    _mtime[0] += 10 ** 9
    os.utime(path, ns=(_mtime[0], _mtime[0]))


def reset():
    for path in (ml.STATE_FILE, audio.STATE_FILE, similar.STATE_FILE):
        path.unlink(missing_ok=True)
    ml._cache.update(stamp=None, songs={}, styles={}, labels={}, tempo={}, keys={}, instr={}, scores={}, themes={},
                     artists={})
    audio._cache.update(stamp=None, songs={})
    classify._memo.clear()


# songs: id -> (title, album, genres, themes of the AI)
SONGS = {
    "xmas-1": ("Stille Nacht", "Weihnachtslieder", ["Christmas"], {"christmas": 0.41, "love": 0.12}),
    "xmas-2": ("Schneeflocke", "Winter", [], {"christmas": 0.25, "calm": 0.3}),
    "film-1": ("Theme", "Score", [], {"film": 0.22, "epic": 0.31, "dark": 0.04}),
    "film-2": ("Battle", "Score", [], {"epic": 0.16, "film": 0.05}),              # film too weak
    "love-1": ("Herz", "Pop", [], {"love": 0.27, "happy": 0.5, "romantic": 0.02}),
    "kids-1": ("Hüpfen", "Kinderlieder", [], {"children": 0.05, "happy": 0.4}),   # children: not offered
    "none-1": ("Ohne", "X", [], {}),
}


def library():
    return Library([song(sid, title=title, album=album, genres=genres, artist="Band", duration=200, rating=4)
                    for sid, (title, album, genres, _t) in SONGS.items()])


class ThemeTest(unittest.TestCase):
    def setUp(self):
        for path in (ml.STATE_FILE, audio.STATE_FILE):
            self.assertIn(env.ROOT, path.parents)   # never the real data
        reset()
        self.addCleanup(reset)
        patcher = mock.patch.object(lastfm, "artist", return_value=None)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.lib = library()
        write_json(audio.STATE_FILE, {"songs": {sid: RAW for sid in SONGS}})
        write_json(ml.STATE_FILE, {"v": ml.VERSION, "songs": {
            sid: {"v": ml.VERSION, "path": "x", "m": {"happy": 0.5}, **({"t": t} if t else {})}
            for sid, (_a, _b, _c, t) in SONGS.items() if sid != "none-1"}})


# ---------------------------------------------------------------------------- Which themes count

class TestThemes(ThemeTest):
    def test_only_offered_themes_from_their_strength(self):
        th = ml.themes()
        self.assertEqual(th["xmas-1"], {"christmas": 0.41})                 # love 0.12 < 0.2
        self.assertEqual(th["film-1"], {"film": 0.22, "epic": 0.31})         # dark 0.04 < 0.1
        self.assertEqual(th["film-2"], {"epic": 0.16})
        self.assertNotIn("kids-1", th)                                       # children is not offered
        self.assertNotIn("none-1", th)
        self.assertEqual(set(ml.THEMES), set(ml.THEME_PRESENT))             # a threshold for every theme
        for left_out in ("calm", "happy", "party", "relaxing", "sad", "energetic", "children", "background"):
            self.assertNotIn(left_out, ml.THEMES)                           # moods and listening vibes exist already

    def test_song_features_and_sound_filters(self):
        feats = classify.song_features(self.lib)
        idx = {s["id"]: i for i, s in enumerate(self.lib.songs)}
        self.assertEqual(feats[idx["film-1"]]["themes"], {"film": 0.22, "epic": 0.31})
        self.assertNotIn("themes", feats[idx["kids-1"]])

        def matching(sound):
            return sorted(s["id"] for i, s in enumerate(self.lib.songs) if audio.matches(feats.get(i), sound))
        self.assertEqual(matching({"themes": ["christmas"]}), ["xmas-1", "xmas-2"])
        self.assertEqual(matching({"themes": ["film", "love"]}), ["film-1", "love-1"])      # at least one
        self.assertEqual(matching({"themes": ["epic"], "moods": ["ruhig"]}), [])              # and the mood as well
        self.assertEqual(matching({"themes": ["epic"], "bpm": [100, 140]}), ["film-1", "film-2"])
        self.assertEqual(matching({"themes": ["space"]}), [])

    def test_validation(self):
        cfg = base_config()
        cfg["stile"].append({"id": "episch", "name": "Episch", "sound": {"themes": ["epic", "film"]}})
        config.validate_config(cfg)
        for bad in (["children"], ["weihnachten"], "epic", [1]):
            cfg["stile"][-1]["sound"] = {"themes": bad}
            with self.assertRaises(ValueError, msg=bad):
                config.validate_config(cfg)

    def test_all_times_everything_with_a_theme(self):
        cfg = base_config()
        mix = {"id": "neu", "person": "familie", "welt": ALL, "stil": ALL, "type": "mix",
               "mix": {"size": 40, "perArtist": 3, "every": "week"}}
        config.validate_config({**cfg, "playlists": [{**mix, "sound": {"themes": ["film"]}}]})   # a theme narrows enough
        for plain in ({}, {"sound": {"moods": ["ruhig"]}}):
            with self.assertRaises(ValueError):                              # “All × Everything” without it: no
                config.validate_config({**cfg, "playlists": [{**mix, **plain}]})

    def test_catalog(self):
        cat = ml.theme_catalog(self.lib)
        self.assertTrue(cat["available"])
        counts = {x["id"]: x["songs"] for x in cat["themes"]}
        self.assertEqual(len(counts), len(ml.THEMES))
        self.assertEqual((counts["christmas"], counts["epic"], counts["film"], counts["space"]), (2, 2, 1, 0))
        both = ml.sound_catalog(self.lib)
        self.assertEqual(set(both), {"available", "instruments", "themes", "themesAvailable"})
        self.assertEqual(len(both["instruments"]), 40)
        self.assertFalse(both["available"])                                  # no instruments in this test
        self.assertTrue(both["themesAvailable"])

    def test_song_window_and_stats(self):
        info = ml.song_info("film-1")
        self.assertEqual([x["id"] for x in info["themes"]], ["epic", "film"])   # strongest first
        self.assertEqual(info["themes"][1]["label"], "film music")
        self.assertNotIn("themes", ml.song_info("kids-1"))
        self.assertIn(["epic", 2], ml.stats()["themes"])

    def test_search_words(self):
        for word, theme in (("weihnachtsmusik", "christmas"), ("weihnachtlich", "christmas"), ("christmas", "christmas"),
                            ("xmas", "christmas"), ("filmmusik", "film"), ("soundtrack", "film"), ("filme", "film"),
                            ("filmisches", "film"), ("episch", "epic"), ("epische", "epic"), ("epic", "epic"), ("düster", "dark"),
                            ("dark", "dark"), ("liebeslieder", "love"), ("lovesongs", "love"), ("romantisch", "romantic"),
                            ("balladen", "ballad"), ("sommerlich", "summer"), ("summer", "summer"),
                            ("weltraum", "space"), ("weihn", "christmas")):
            self.assertEqual(ml.theme_word(word), [theme], word)
        for word in ("darkwave", "filmriss", "kinderlieder", "lieber", "lovely", "ruhige", "klavier"):
            self.assertIsNone(ml.theme_word(word), word)
        self.assertEqual([(x["id"], x["count"]) for x in ml.search_themes("Weihnachten", self.lib)], [("christmas", 2)])
        self.assertEqual([x["id"] for x in ml.search_themes("epische filmmusik", self.lib)], ["epic", "film"])
        self.assertEqual(ml.search_themes("film music", self.lib)[0]["ids"], ["film"])   # two words, one theme
        self.assertEqual(ml.search_themes("weltraum", self.lib), [])         # no songs: left out
        self.assertEqual(ml.search_themes("ep", self.lib), [])

    @env.german
    def test_german_labels(self):
        self.assertEqual(ml.search_themes("Filmmusik", self.lib)[0]["label"], "Filmmusik")
        self.assertEqual(ml.song_info("xmas-1")["themes"][0]["label"], "Weihnachten")
        cfg = base_config()
        p = {"id": "x", "welt": ALL, "stil": ALL, "type": "mix", "sound": {"themes": ["epic", "dark"]}}
        line = next(x for x in rules.summary(cfg, p, BuildContext(self.lib)) if x.startswith("Klang"))
        self.assertIn("episch, düster", line)


# ---------------------------------------------------------------------------- Christmas songs in a theme filter

class TestThemeAndHiddenContent(ThemeTest):
    def test_a_christmas_theme_may_contain_the_christmas_songs(self):
        cfg = base_config()   # the vibe “Weihnachten” hides its songs from every other playlist (excludeElsewhere)
        ctx = BuildContext(self.lib)
        film = {"id": "x", "person": "familie", "welt": ALL, "stil": ALL, "type": "mix", "sound": {"themes": ["film"]}}
        self.assertEqual(rules.shown_vibes(cfg, film), set())
        self.assertNotIn(0, self.lib.match(rules.build_nsp(cfg, film, ctx)))   # “Stille Nacht” is hidden
        self.assertEqual(rules.shown_vibes(cfg, {**film, "stil": "tanzen"}, rules._find(cfg["stile"], "tanzen")), {"tanzen"})
        xmas = {**film, "sound": {"themes": ["christmas"]}}
        self.assertEqual(rules.shown_vibes(cfg, xmas), {"weihnachten"})
        nsp = rules.build_nsp(cfg, xmas, ctx)
        self.assertNotIn({"notContains": {"album": "Weihnacht"}}, nsp["all"])
        self.assertEqual(sorted(self.lib.songs[i]["id"] for i in rules.apply_sound(cfg, self.lib, xmas, self.lib.match(nsp))),
                         ["xmas-1", "xmas-2"])
        self.assertFalse(any(x.startswith("Hidden") and "Weihnachten" in x for x in rules.summary(cfg, xmas, ctx)))
        self.assertTrue(any(x.startswith("Hidden") and "Weihnachten" in x for x in rules.summary(cfg, film, ctx)))


# ---------------------------------------------------------------------------- Search

class TestSearch(ThemeTest):
    ADMIN = {"user": "niklas", "role": "admin", "own": [], "persons": [], "local": False}
    JONAS = {"user": "Jonas", "role": "user", "own": ["jonas"], "persons": ["jonas"], "local": False}

    def setUp(self):
        super().setUp()
        from app import auth, web
        self.web, self.auth = web, auth
        env.reset_caches()
        self.cfg = base_config()
        config.save_config(self.cfg)
        patcher = mock.patch.object(web.CACHE, "get", return_value=self.lib)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.addCleanup(auth.set_current, {"user": None, "role": "none", "own": [], "persons": [], "local": False})
        auth.set_current(self.ADMIN)

    def combos(self, q, cfg=None):
        with mock.patch.object(rules, "count", return_value=50):
            return self.web._search_combos(q, cfg or self.cfg, self.lib)

    def test_catalog_endpoints(self):
        routes = self.web.Handler.GET_ROUTES
        for path in ("/api/sound/catalog", "/api/instruments"):
            self.assertIn(path, routes)
            self.assertNotIn(path, self.web.Handler.ADMIN_ONLY)          # labels and counts for everyone
        old = routes["/api/instruments"]({})                              # the older name still has its fields
        self.assertEqual(len(old["instruments"]), 40)
        self.assertIn("available", old)
        cat = routes["/api/sound/catalog"]({})
        self.assertEqual({x["id"]: x["songs"] for x in cat["themes"]}["christmas"], 2)

    def test_theme_group(self):
        out = self.web.api_search({"q": "episch"})
        self.assertEqual([(x["id"], x["count"]) for x in out["themes"]], [("epic", 2)])
        self.assertNotIn("stil", out["themes"][0])
        self.assertEqual(self.web.api_search({"q": "x"})["themes"], [])
        self.assertEqual(self.web.api_search({"q": "kla"})["themes"], [])

    def test_a_vibe_stands_for_its_theme(self):
        with mock.patch.object(rules, "count", return_value=123):
            hit = self.web.api_search({"q": "weihnachten"})["themes"][0]
        self.assertEqual((hit["id"], hit["stil"], hit["stilName"], hit["count"]), ("christmas", "weihnachten", "Weihnachten", 123))
        english = base_config()
        next(x for x in english["stile"] if x["id"] == "weihnachten")["name"] = "Christmas"
        config.save_config(english)
        hit = self.web.api_search({"q": "weihnachtsmusik"})["themes"][0]
        self.assertEqual(hit["stil"], "weihnachten")                        # linked by id (ml.THEME_VIBES)
        sommer = self.web._theme_vibe(self.cfg, "summer", ["sommerlich"])
        self.assertEqual(sommer["id"], "sommer")                            # by name
        without = base_config()
        without["stile"] = [x for x in without["stile"] if x["id"] != "weihnachten"]
        config.save_config(without)
        self.assertNotIn("stil", self.web.api_search({"q": "weihnachten"})["themes"][0])

    def test_a_music_world_wins(self):
        cfg = base_config()
        cfg["welten"].append({"id": "film", "name": "Filmmusik", "artists": ["Band"]})
        config.save_config(cfg)
        self.assertEqual(self.web.api_search({"q": "filmmusik"})["themes"], [])   # the interface lists the world
        out = self.combos("ruhige filmmusik", cfg)
        self.assertEqual(out[0]["playlist"]["welt"], "film")
        self.assertEqual(out[0]["playlist"]["sound"], {"moods": ["ruhig"]})       # the word went to the world

    def test_combined_search_with_a_theme(self):
        self.auth.set_current(self.JONAS)
        dark = self.combos("düstere mittelalter")
        self.assertEqual(dark[0]["title"], "Mittelalter · dark")
        self.assertEqual((dark[0]["playlist"]["welt"], dark[0]["playlist"]["sound"]), ("mittelalter", {"themes": ["dark"]}))
        calm = self.combos("ruhige epische filmmusik")
        self.assertEqual(calm[0]["playlist"]["sound"], {"moods": ["ruhig"], "themes": ["epic"]})   # the first theme
        self.assertEqual(calm[0]["playlist"]["welt"], ALL)
        config.validate_config({**self.cfg, "playlists": [{**calm[0]["playlist"], "id": "neu"}]})   # no world needed
        self.assertEqual(self.combos("episch"), [])                          # one kind alone is no combination
        self.assertEqual(self.combos("epische filmmusik"), [])               # two themes are still one kind

    def test_christmas_goes_to_the_vibe(self):
        out = self.combos("ruhige weihnachtsmusik")                          # the vibe “Weihnachten” takes the word
        self.assertEqual(out[0]["playlist"]["stil"], "weihnachten")
        self.assertEqual(out[0]["playlist"]["sound"], {"moods": ["ruhig"]})
        english = base_config()
        next(x for x in english["stile"] if x["id"] == "weihnachten")["name"] = "Christmas"
        out = self.combos("ruhige weihnachtsmusik", english)                 # linked by id
        self.assertEqual((out[0]["playlist"]["stil"], out[0]["playlist"]["sound"]), ("weihnachten", {"moods": ["ruhig"]}))
        without = base_config()
        without["stile"] = [x for x in without["stile"] if x["id"] != "weihnachten"]
        out = self.combos("ruhige weihnachtsmusik", without)                 # without the vibe: the AI's theme
        self.assertEqual(out[0]["title"], "calm & gentle · Christmas")
        self.assertEqual((out[0]["playlist"]["stil"], out[0]["playlist"]["sound"]),
                         (ALL, {"moods": ["ruhig"], "themes": ["christmas"]}))


if __name__ == "__main__":
    unittest.main()
