"""app/similar.py (sound similarity from the AI's sound vectors) and where it is used: smooth transitions in mixes
(mixer.smooth), radio weighting, "More like this", similar bands and the classification of new bands.

The vectors are made up: every "scene" has its own direction, every song adds a little noise, and all songs share a
large common part (like real embeddings) – which the centering has to remove. No Essentia needed."""
from tests.python import env  # noqa: F401  (before app.*)

import copy
import json
import os
import random
import time
import unittest
from unittest import mock

from app import audio, classify, lastfm, mixer, ml, rules, similar
from app.rules import Library
from tests.python.factory import base_config, song

DIM = similar.DIM
_rnd = random.Random(11)
COMMON = [_rnd.gauss(0, 1) for _ in range(DIM)]
SCENES = {name: [_rnd.gauss(0, 1) for _ in range(DIM)] for name in ("metal", "kinder", "folk")}
_mtime = [1_800_000_000 * 10 ** 9]


def vector(scene, seed, noise=0.35, common=1.5):
    rnd = random.Random(seed)
    return [common * c + s + noise * rnd.gauss(0, 1) for c, s in zip(COMMON, SCENES[scene])]


def write_vectors(songs, version=similar.VERSION, dim=DIM):
    """songs: song id -> list of floats (encoded like the analysis process) or a stored text."""
    data = {"v": version, "dim": dim, "songs": {k: v if isinstance(v, str) else similar.encode(v) for k, v in songs.items()}}
    similar.STATE_FILE.write_text(json.dumps(data))
    _mtime[0] += 10 ** 9
    os.utime(similar.STATE_FILE, ns=(_mtime[0], _mtime[0]))


def reset():
    similar.STATE_FILE.unlink(missing_ok=True)
    similar._store.update(stamp=None, ids=frozenset(), rows={}, mean=None)
    similar._indexes.clear()
    ml.STATE_FILE.unlink(missing_ok=True)
    audio.STATE_FILE.unlink(missing_ok=True)
    ml._cache.update(stamp=None, songs={}, styles={}, labels={}, tempo={}, keys={}, instr={}, scores={}, themes={}, artists={})
    audio._cache.update(stamp=None, songs={})
    classify._memo.clear()


# bands of three scenes, 4 songs each – song id "<band>-<n>"
BANDS = {"Eisen": "metal", "Stahl": "metal", "Blech": "metal", "Kita": "kinder", "Sandkasten": "kinder",
         "Laterne": "kinder", "Harfe": "folk", "Dudel": "folk"}


def library(bands=BANDS, per_band=4, genres=()):
    return Library([song(f"{b}-{n}", artist=b, album=f"Album {b} {n // 2}", genres=genres)
                    for b in bands for n in range(per_band)])


def vectors_for(lib, skip=()):
    out = {}
    for k, s in enumerate(lib.songs):
        if s["id"] not in skip:
            out[s["id"]] = vector(BANDS[s["artist"]], k)
    return out


class SimilarTest(unittest.TestCase):
    def setUp(self):
        self.assertIn(env.ROOT, similar.STATE_FILE.parents)   # never the real data
        reset()
        self.addCleanup(reset)


# ---------------------------------------------------------------------------- File and decoding

class TestFile(SimilarTest):
    def test_encode_decode(self):
        text = similar.encode([0.5, -1.0] + [0.25] * (DIM - 2))
        vec = similar.decode(text)
        self.assertEqual(len(vec), DIM)
        self.assertEqual((vec[0], vec[1], vec[2]), (64, -127, 32))      # largest component ±127
        self.assertIsNone(similar.decode("kein base64!"))
        self.assertIsNone(similar.decode(similar.encode([1.0] * 10)))   # wrong length
        self.assertIsNone(similar.decode(similar.encode([0.0] * DIM)))  # no direction

    def test_without_file_or_of_another_version(self):
        lib = library()
        self.assertIsNone(similar.index(lib))
        self.assertEqual((similar.count(), similar.stored()), (0, frozenset()))
        write_vectors(vectors_for(lib), version=similar.VERSION + 1)   # other projection: not comparable
        self.assertIsNone(similar.index(lib))
        write_vectors(vectors_for(lib), dim=64)
        self.assertIsNone(similar.index(lib))
        write_vectors({**vectors_for(lib), "kaputt": "%%%"})
        self.assertEqual(similar.count(), 32)                     # the broken one is left out
        self.assertIn("kaputt", similar.stored())
        self.assertEqual(len(similar.index(lib)), 32)

    def test_index_is_cached_until_the_file_changes(self):
        lib = library()
        write_vectors(vectors_for(lib))
        idx = similar.index(lib)
        self.assertIs(similar.index(lib), idx)
        self.assertIsNot(similar.index(library()), idx)           # another song list
        write_vectors(vectors_for(lib, skip={"Eisen-0"}))
        fresh = similar.index(lib)
        self.assertIsNot(fresh, idx)
        self.assertFalse(fresh.has(0))
        self.assertIsNone(fresh.cos(0, 1))


# ---------------------------------------------------------------------------- Similarity

class TestIndex(SimilarTest):
    def setUp(self):
        super().setUp()
        self.lib = library()
        write_vectors(vectors_for(self.lib))
        self.idx = similar.index(self.lib)
        self.scene = [BANDS[s["artist"]] for s in self.lib.songs]

    def test_centering_removes_what_all_songs_share(self):
        raw = [vector(BANDS[s["artist"]], k) for k, s in enumerate(self.lib.songs)]

        def plain(a, b):
            return sum(x * y for x, y in zip(a, b)) / (sum(x * x for x in a) * sum(y * y for y in b)) ** 0.5
        n = len(raw)
        same = [self.idx.cos(i, j) for i in range(n) for j in range(i + 1, n) if self.scene[i] == self.scene[j]]
        other = [self.idx.cos(i, j) for i in range(n) for j in range(i + 1, n) if self.scene[i] != self.scene[j]]
        self.assertGreater(min(plain(raw[i], raw[j]) for i in range(n) for j in range(n)), 0.5)   # all look alike
        self.assertGreater(min(same), 0.5)
        self.assertLess(max(other), 0.1)
        self.assertAlmostEqual(self.idx.cos(3, 3), 1.0, places=3)
        self.assertAlmostEqual(self.idx.cos(3, 20), self.idx.cos(20, 3), places=9)

    def test_neighbors(self):
        best = self.idx.neighbors(0, 11)
        self.assertEqual(len(best), 11)
        self.assertNotIn(0, [j for j, _sc in best])
        self.assertEqual({self.scene[j] for j, _sc in best}, {"metal"})   # the other 11 metal songs
        self.assertEqual([sc for _j, sc in best], sorted((sc for _j, sc in best), reverse=True))
        self.assertIs(self.idx.neighbors(0, 11), best)                     # cached
        within = self.idx.neighbors(0, 5, within={1, 13, 20, 999})
        self.assertEqual([j for j, _sc in within][0], 1)
        self.assertEqual({j for j, _sc in within}, {1, 13, 20})

    def test_closeness_and_centered_vectors_agree_with_cos(self):
        u = self.idx.centered(5)
        self.assertAlmostEqual(sum(x * x for x in u), 1.0, places=6)
        self.assertAlmostEqual(self.idx.closeness(9, u), self.idx.cos(9, 5), places=6)
        self.assertIsNone(self.idx.closeness(9, None))

    def test_bands_that_sound_alike(self):
        cents = self.idx.centroids()
        self.assertEqual(set(cents), set(BANDS))
        self.assertEqual(cents["Eisen"][1], 4)
        names = [a for a, _sc in self.idx.similar_artists("Eisen", 3)]
        self.assertEqual(set(names[:2]), {"Stahl", "Blech"})
        self.assertGreater(dict(self.idx.similar_artists("Eisen", 3))["Stahl"], 0.8)
        self.assertEqual(self.idx.similar_artists("Unbekannt"), [])
        world = similar.mean_unit([cents["Kita"][0], cents["Sandkasten"][0]])
        self.assertGreater(similar.cosine(cents["Laterne"][0], world), 0.8)
        self.assertLess(similar.cosine(cents["Eisen"][0], world), 0.2)

    def test_a_band_needs_two_songs(self):
        lib = Library(self.lib.songs + [song("solo-0", artist="Solo")])
        write_vectors({**vectors_for(self.lib), "solo-0": vector("folk", 99)})
        idx = similar.index(lib)
        self.assertNotIn("Solo", idx.centroids())
        self.assertTrue(idx.has(len(lib.songs) - 1))

    def test_25000_songs_in_well_under_a_second(self):
        rnd = random.Random(3)
        songs = [song(f"g{k}", artist=f"Band {k % 2000}") for k in range(25000)]
        dirs = [[rnd.gauss(0, 1) for _ in range(DIM)] for _ in range(50)]
        write_vectors({s["id"]: [c + d + 0.8 * rnd.gauss(0, 1) for c, d in zip(COMMON, dirs[k % 50])]
                       for k, s in enumerate(songs)})
        lib = Library(songs)
        started = time.perf_counter()
        idx = similar.index(lib)
        best = idx.neighbors(7, 20)
        took = time.perf_counter() - started
        self.assertLess(took, 2.0)        # loading included; on the development PC ≈ 0.3 s, neighbors alone ≈ 0.08 s
        self.assertEqual(len(best), 20)
        self.assertTrue(all(j % 50 == 7 for j, _sc in best))
        started = time.perf_counter()
        idx.neighbors(8, 20)
        self.assertLess(time.perf_counter() - started, 1.0)


# ---------------------------------------------------------------------------- Mixes: smooth transitions

class TestSmooth(SimilarTest):
    def setUp(self):
        super().setUp()
        # 12 bands, one song each, three scenes – chosen alternating between the scenes
        self.bands = {f"{scene}-{k}": scene for scene in ("metal", "kinder", "folk") for k in range(4)}
        self.lib = Library([song(f"s-{b}", artist=b, album=f"Album {b}") for b in self.bands])
        write_vectors({s["id"]: vector(self.bands[s["artist"]], k) for k, s in enumerate(self.lib.songs)})
        self.chosen = [0, 4, 8, 1, 5, 9, 2, 6, 10, 3, 7, 11]

    def scenes(self, order):
        return [self.bands[self.lib._main_artist(self.lib.songs[i])] for i in order]

    def test_similar_songs_follow_each_other(self):
        order = mixer.smooth(self.lib, self.chosen)
        self.assertEqual(sorted(order), sorted(self.chosen))
        self.assertEqual(order[0], self.chosen[0])                      # starts with the first pick
        changes = sum(1 for a, b in zip(self.scenes(order), self.scenes(order)[1:]) if a != b)
        self.assertEqual(changes, 2)                                    # three blocks instead of 11 changes
        self.assertEqual(mixer.smooth(self.lib, self.chosen), order)    # deterministic

    def test_never_the_same_band_twice_in_a_row(self):
        lib = library(per_band=3)
        write_vectors(vectors_for(lib))
        rnd = random.Random(5)
        for _ in range(30):
            chosen = rnd.sample(range(len(lib.songs)), rnd.randint(4, len(lib.songs)))
            order = mixer.smooth(lib, chosen)
            names = [lib._main_artist(lib.songs[i]) for i in order]
            self.assertEqual(sorted(order), sorted(chosen))
            most = max(names.count(n) for n in names)
            allowed = max(0, 2 * most - len(names) - 1)                 # like spread(): only what cannot be avoided
            self.assertEqual(sum(1 for a, b in zip(names, names[1:]) if a == b), allowed, names)

    def test_one_band_dominates(self):
        lib = Library([song(f"a{k}", artist="Viel") for k in range(5)] + [song(f"b{k}", artist=f"B{k}") for k in range(4)])
        write_vectors({s["id"]: vector("metal" if s["artist"] == "Viel" else "folk", k) for k, s in enumerate(lib.songs)})
        order = mixer.smooth(lib, list(range(9)))
        names = [lib._main_artist(lib.songs[i]) for i in order]
        self.assertFalse(any(a == b for a, b in zip(names, names[1:])), names)   # V B V B V B V B V

    def test_keys_and_tempo_without_vectors(self):
        lib = Library([song(f"k{k}", artist=f"Band {k}") for k in range(6)])
        feats = {0: {"camelot": "8A", "bpm": 120, "energy": 0.5}, 1: {"camelot": "2B", "bpm": 120, "energy": 0.5},
                 2: {"camelot": "9A", "bpm": 121, "energy": 0.5}, 3: {"camelot": "3B", "bpm": 120, "energy": 0.5},
                 4: {"camelot": "10A", "bpm": 119, "energy": 0.5}, 5: {"camelot": "8A", "bpm": 60, "energy": 0.5}}
        with mock.patch("app.classify.song_features", return_value=feats):
            order = mixer.smooth(lib, list(range(6)))
        self.assertEqual(order[:3], [0, 2, 4])                         # 8A → 9A → 10A: neighbours on the wheel
        self.assertEqual(set(order[3:5]), {1, 3})                      # 2B and 3B belong together

    def test_falls_back_without_sound_or_key(self):
        reset()
        self.assertIsNone(mixer.smooth(self.lib, self.chosen))
        p = {"id": "m", "type": "mix", "welt": "*", "stil": "*", "mix": {"size": 12, "perArtist": 1, "perAlbum": 0}}
        pool = frozenset(range(len(self.lib.songs)))
        plain = mixer.select(self.lib, pool, p)
        self.assertEqual(mixer.select(self.lib, pool, p, arrange=mixer.smooth), plain)   # as before
        write_vectors({s["id"]: vector(self.bands[s["artist"]], k) for k, s in enumerate(self.lib.songs) if k < 5})
        self.assertIsNone(mixer.smooth(self.lib, self.chosen))           # fewer than half have a vector
        self.assertIsNone(mixer.smooth(self.lib, [0, 1]))

    def test_transition_cost(self):
        idx = similar.index(self.lib)
        near = mixer.transition_cost((0, {}), (1, {}), idx)
        far = mixer.transition_cost((0, {}), (4, {}), idx)
        self.assertLess(near, far)
        self.assertAlmostEqual(mixer.transition_cost((0, {}), (1, {})), 0.5)   # nothing known: neutral
        self.assertEqual(mixer._tempo_gap(120, 120), 0)
        self.assertEqual(mixer._tempo_gap(100, 130), 1)
        self.assertAlmostEqual(mixer._tempo_gap(60, 120), 0.4)              # double tempo: fairly close

    def test_pick_uses_it_unless_an_arc_decides(self):
        cfg = base_config()
        cfg["settings"]["mixLearn"] = False
        cfg["stile"].append({"id": "schlaf", "name": "Schlaf", "sound": {"moods": ["schlaf"]}})
        p = {"id": "m", "type": "mix", "person": "familie", "welt": "*", "stil": "*", "minRating": 0,
             "mix": {"size": 12, "perArtist": 1, "perAlbum": 0}}
        for settings, playlist, expected in (({}, p, mixer.smooth), ({"smoothTransitions": False}, p, None),
                                             ({}, {**p, "stil": "schlaf"}, None)):
            c = copy.deepcopy(cfg)
            c["settings"].update(settings)
            with mock.patch.object(mixer, "select", wraps=mixer.select) as sel, \
                 mock.patch.object(rules, "apply_sound", side_effect=lambda cfg, lib, pl, ids: ids):
                mixer.pick(c, self.lib, playlist, {"all": []})
            self.assertIs(sel.call_args.kwargs["arrange"], expected, (settings, playlist.get("stil")))

    def test_radio_prefers_songs_that_sound_like_the_seed(self):
        lib = library()
        write_vectors(vectors_for(lib, skip={"Dudel-0"}))
        adjust = {lib.songs[0]["id"]: 2.0}
        mixer.radio_sound(lib, range(len(lib.songs)), ["Eisen", "Unbekannt"], adjust)
        by_id = {s["id"]: adjust.get(s["id"]) for s in lib.songs}
        self.assertGreater(by_id["Stahl-1"], 1.2)
        self.assertLess(by_id["Kita-1"], 0.8)
        self.assertGreater(by_id["Eisen-0"], 2.4)                        # multiplied into what is there
        self.assertIsNone(by_id["Dudel-0"])                              # without a vector: unchanged
        before = dict(adjust)
        mixer.radio_sound(lib, range(len(lib.songs)), ["Unbekannt"], adjust)
        self.assertEqual(adjust, before)


# ---------------------------------------------------------------------------- Radio, "More like this", artist window

class TestUses(SimilarTest):
    def setUp(self):
        super().setUp()
        self.lib = library()
        patcher = mock.patch.object(lastfm, "artist", return_value=None)   # without Last.fm data
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_radio_takes_bands_that_sound_alike(self):
        self.assertEqual(classify.radio_artists(["Eisen"], self.lib), ["Eisen"])
        write_vectors(vectors_for(self.lib))
        bands = classify.radio_artists(["Eisen"], self.lib)
        self.assertEqual(bands[0], "Eisen")
        self.assertEqual(set(bands[1:]), {"Stahl", "Blech"})

    def test_more_like_this(self):
        pool = set(range(len(self.lib.songs))) - {0}
        before = classify.rank_like(self.lib, 0, pool, random.Random(1))
        self.assertEqual(sorted(before), sorted(pool))
        write_vectors(vectors_for(self.lib, skip={"Stahl-3"}))
        ranked = classify.rank_like(self.lib, 0, pool, random.Random(1))
        metal = {i for i, s in enumerate(self.lib.songs) if BANDS[s["artist"]] == "metal" and s["id"] != "Stahl-3"} - {0}
        self.assertEqual(set(ranked[:len(metal)]), metal)
        self.assertGreater(ranked.index(self.lib.index_of()["Stahl-3"]), len(metal) - 1)   # no vector: later

    def test_artist_window_sounds_like(self):
        self.assertEqual(classify.artist_profile("Kita", self.lib)["soundsLike"], [])
        write_vectors(vectors_for(self.lib))
        like = classify.artist_profile("Kita", self.lib)["soundsLike"]
        self.assertEqual({a for a, _sc in like}, {"Sandkasten", "Laterne"})
        self.assertTrue(all(sc >= classify.SOUNDS_LIKE_MIN for _a, sc in like))


# ---------------------------------------------------------------------------- Classification

class TestClassification(SimilarTest):
    def setUp(self):
        super().setUp()
        self.cfg = base_config()
        self.cfg["welten"] = [{"id": "kinder", "name": "Kinder", "artists": ["Kita", "Sandkasten"]},
                              {"id": "metal", "name": "Metal", "artists": ["Eisen", "Stahl"]}]
        self.lib = library(bands={**{b: s for b, s in BANDS.items() if s != "folk"}}, genres=["Rock"])
        patcher = mock.patch.object(lastfm, "artist", return_value=None)
        patcher.start()
        self.addCleanup(patcher.stop)

    def best(self, artist):
        return next(x for x in classify.suggestions(self.cfg, self.lib) if x["artist"] == artist)

    def test_without_vectors_as_before(self):
        blech = self.best("Blech")   # same genres everywhere: a tie, the first world wins
        self.assertEqual((blech["welt"], blech["score"]), ("kinder", 0.85))
        self.assertNotIn("sounds similar", blech["why"])

    def test_sound_decides_between_equal_worlds(self):
        write_vectors(vectors_for(self.lib))
        blech, laterne = self.best("Blech"), self.best("Laterne")
        self.assertEqual(blech["welt"], "metal")
        self.assertEqual(laterne["welt"], "kinder")
        self.assertAlmostEqual(blech["score"], round(0.85 * 0.85 + 0.15, 2))
        self.assertIn("sounds similar", blech["why"])

    def test_too_few_analyzed_songs_do_not_count(self):
        write_vectors(vectors_for(self.lib, skip={"Blech-0", "Blech-1"}))   # only 2 of 4 songs
        self.assertEqual(self.best("Blech")["score"], 0.85)

    def test_score_mapping(self):
        u = similar.unit([1.0] + [0.0] * (DIM - 1))
        self.assertIsNone(classify.sound_score(None, u))
        self.assertEqual(classify.sound_score(u, u), 1.0)
        self.assertEqual(classify.sound_score(u, similar.unit([-1.0] + [0.0] * (DIM - 1))), 0.0)


# ---------------------------------------------------------------------------- Endpoints

class TestEndpoints(SimilarTest):
    ADMIN = {"user": "niklas", "role": "admin", "own": None, "persons": [], "local": False}
    JONAS = {"user": "Jonas", "role": "user", "own": "jonas", "persons": ["jonas"], "local": False}

    def setUp(self):
        super().setUp()
        from app import auth, config, images, web
        self.web, self.auth = web, auth
        env.reset_caches()
        config.save_config(base_config())
        self.lib = library()
        write_vectors(vectors_for(self.lib))
        ml.STATE_FILE.write_text(json.dumps({"v": ml.VERSION, "songs": {
            "Kita-0": {"v": ml.VERSION, "path": "x", "m": {"happy": 0.5}, "k": "C major", "ks": 0.8, "b": 100.0, "bc": 1.0,
                       "i": {"piano": 0.7, "voice": 0.15}},
            "Kita-1": {"v": ml.VERSION, "path": "x", "m": {"happy": 0.5}, "i": {"guitar": 0.4}}}}))
        raw = {"v": audio.VERSION, "depth": "standard", "bpm": 120.0, "beat": 0.7, "loud": -10.0, "dyn": 12.0,
               "cent": 1800, "flat": 0.2, "flux": 60.0, "path": "x"}
        audio.STATE_FILE.write_text(json.dumps({"songs": {s["id"]: raw for s in self.lib.songs}}))
        for patcher in (mock.patch.object(web.CACHE, "get", return_value=self.lib),
                        mock.patch.object(lastfm, "artist", return_value=None),
                        mock.patch.object(images, "artist_info", return_value={}),
                        mock.patch.object(web, "_structured_lyrics", return_value=(None, None))):
            patcher.start()
            self.addCleanup(patcher.stop)
        self.addCleanup(auth.set_current, {"user": None, "role": "none", "own": None, "persons": [], "local": False})
        auth.set_current(self.ADMIN)

    def test_song_window_has_key_tempo_and_instruments(self):
        d = self.web.api_song({"id": "Kita-0"})
        self.assertEqual((d["bpm"], d["bpmSource"], d["key"], d["camelot"]), (100, "ai", "C major", "8B"))
        self.assertEqual([x["id"] for x in d["instruments"]], ["piano", "voice"])
        plain = self.web.api_song({"id": "Eisen-0"})
        self.assertEqual(plain["bpmSource"], "measured")
        self.assertNotIn("key", plain)

    def test_artist_window_sounds_like(self):
        d = self.web.api_artist({"name": "Eisen"})
        self.assertEqual({x["name"] for x in d["soundsLike"]}, {"Stahl", "Blech"})
        self.assertEqual(set(d["soundsLike"][0]), {"name", "id", "score"})

    def test_more_like_this_by_sound(self):
        self.auth.set_current(self.JONAS)
        with mock.patch("app.classify.radio_artists", return_value=list(BANDS)):
            d = self.web.api_song_more({"id": "Eisen-0"})
        bands = [s["artist"] for s in d["songs"]]
        self.assertEqual(len(bands), 17)                      # 3 of the band itself + 2 of every other band
        metal = [b for b in bands if BANDS[b] == "metal"]
        self.assertEqual(len(metal), 7)

    def test_instrument_catalog_and_search(self):
        cat = self.web.Handler.GET_ROUTES["/api/sound/catalog"]({})
        self.assertEqual({x["id"]: x["songs"] for x in cat["instruments"]}["piano"], 1)
        out = self.web.api_search({"q": "piano"})
        self.assertEqual([(x["id"], x["count"]) for x in out["instruments"]], [("piano", 1)])
        self.assertEqual(self.web.api_search({"q": "x"})["instruments"], [])

    def test_combined_search_with_an_instrument(self):
        self.auth.set_current(self.JONAS)
        cfg = base_config()
        with mock.patch.object(rules, "count", return_value=50):
            out = self.web._search_combos("ruhige klaviermusik", cfg, self.lib)
            kinder = self.web._search_combos("kinder e-gitarre", cfg, self.lib)
            alone = self.web._search_combos("klavier", cfg, self.lib)
        self.assertEqual([c["title"] for c in out], ["calm & gentle · piano"])
        self.assertEqual(out[0]["playlist"]["sound"], {"moods": ["ruhig"], "instruments": ["piano"]})
        self.assertEqual(kinder[0]["playlist"]["sound"], {"instruments": ["electricguitar"]})
        self.assertEqual(kinder[0]["playlist"]["welt"], "kinder")
        self.assertEqual(alone, [])                           # one kind alone is no combination
        from app import config
        config.validate_config({**cfg, "playlists": [{**out[0]["playlist"], "id": "neu"}]})   # instrument: no world needed
        with self.assertRaises(ValueError):                   # a mood alone still is not enough for everything
            config.validate_config({**cfg, "playlists": [{**out[0]["playlist"], "id": "neu", "sound": {"moods": ["ruhig"]}}]})


if __name__ == "__main__":
    unittest.main()
