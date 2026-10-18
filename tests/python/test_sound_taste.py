"""app/soundtaste.py: the sound taste per account – a few sound prototypes from what the account plays (AI sound
vectors, similar.py) – and where it is used: taste.matcher() (mix weighting, "Your sound"), suggestions, the
"From your listening" card.

The vectors are made up as in test_similar: every scene has its own direction, every song a little noise, all share
a large common part. The account's song list, the recap and the sound features are replaced – no network, no real
data."""
from tests.python import env  # noqa: F401  (before app.*)

import copy
import datetime as dt
import json
import os
import random
import time
import unittest
from collections import Counter
from unittest import mock

from app import classify, feedback, mixer, rueckblick, rules, similar, soundtaste, stats, taste
from app.rules import Library
from tests.python.factory import base_config, song

TODAY = dt.date(2026, 10, 17)
DIM = similar.DIM
_rnd = random.Random(5)
COMMON = [_rnd.gauss(0, 1) for _ in range(DIM)]
SCENES = {name: [_rnd.gauss(0, 1) for _ in range(DIM)] for name in ("kinder", "metal", "folk", "pop")}
_mtime = [1_900_000_000 * 10 ** 9]


def vector(mix, seed, noise=0.35):
    """mix: scene -> share (e.g. {"metal": 0.4, "folk": 0.6})."""
    rnd = random.Random(seed)
    return [1.5 * c + sum(w * SCENES[sc][d] for sc, w in mix.items()) + noise * rnd.gauss(0, 1)
            for d, c in enumerate(COMMON)]


def write_vectors(vectors):
    data = {"v": similar.VERSION, "dim": DIM, "songs": {k: similar.encode(v) for k, v in vectors.items()}}
    similar.STATE_FILE.write_text(json.dumps(data))
    _mtime[0] += 10 ** 9
    os.utime(similar.STATE_FILE, ns=(_mtime[0], _mtime[0]))


def reset():
    similar.STATE_FILE.unlink(missing_ok=True)
    similar._store.update(stamp=None, ids=frozenset(), rows={}, mean=None, pos=None)
    similar._indexes.clear()
    soundtaste._memo.clear()
    taste._memo.clear()
    feedback._cache.clear()


# scene per band, 10 songs each: song id "<band>-<n>"
BANDS = {"Kita": "kinder", "Sandkasten": "kinder", "Laterne": "kinder", "Eisen": "metal", "Stahl": "metal",
         "Blech": "metal", "Harfe": "folk", "Dudel": "folk", "Schlager": "pop"}


def library(user="Jonas", played=None, extra=()):
    """played: band -> (songs played, plays each) – the songs 0 … n−1 of the band; the others stay unplayed."""
    played = played or {}
    songs = []
    for band in BANDS:
        n, plays = played.get(band, (0, 0))
        for k in range(10):
            songs.append(song(f"{band}-{k}", artist=band, album=f"{band} {k // 5}", plays=plays if k < n else 0))
    songs += list(extra)
    return Library(songs, ratings_exact=True, user=user)


def vectors_for(lib, mixed=()):
    out = {s["id"]: vector({BANDS[s["artist"]]: 1.0}, k) for k, s in enumerate(lib.songs) if s["artist"] in BANDS}
    for k, (sid, mix) in enumerate(mixed):
        out[sid] = vector(mix, 1000 + k)
    return out


FAMILY = {"Kita": (6, 8), "Sandkasten": (6, 8), "Laterne": (6, 8), "Eisen": (6, 3), "Stahl": (6, 3), "Blech": (6, 3)}


class SoundTasteTest(unittest.TestCase):
    def setUp(self):
        self.assertIn(env.ROOT, similar.STATE_FILE.parents)   # never the real data
        env.reset_caches()
        reset()
        self.addCleanup(reset)
        self.libs = {"jonas": library("Jonas", FAMILY)}
        self.recent = {}
        patches = [
            mock.patch.object(stats, "songs_for", side_effect=lambda user, base: self.libs[user.lower()]),
            mock.patch.object(rueckblick, "plays_between", side_effect=lambda user, *a: (Counter(self.recent.get(user.lower(), {})), {})),
            mock.patch.object(classify, "song_features", return_value={}),
        ]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)

    def taste_of(self, user="Jonas"):
        lib = self.libs[user.lower()]
        return soundtaste.of(lib, user, TODAY, lambda: taste.song_scores(lib, user, TODAY))

    def ids(self, lib, *bands, unplayed=True):
        return [i for i, s in enumerate(lib.songs) if s["artist"] in bands and (not unplayed or not s.get("playCount"))]


# ---------------------------------------------------------------------------- Many songs at once (similar.Batch)

class TestBatch(SoundTasteTest):
    def test_closeness_and_sums_agree_with_the_index(self):
        lib = self.libs["jonas"]
        write_vectors(vectors_for(lib))
        idx = similar.index(lib)
        sids, b = similar.batch([s["id"] for s in lib.songs[:40]] + ["unknown"])
        self.assertEqual(len(sids), 40)                       # without a vector: left out
        u = idx.centered(3)
        for j, c in enumerate(b.closeness(u)):
            self.assertAlmostEqual(c, idx.cos(j, 3), places=3)
        weights = [1 + (j % 3) for j in range(40)]
        groups = [j % 2 for j in range(40)]
        sums = b.sums(weights, groups, 2)
        for g in (0, 1):
            direct = [sum(weights[j] * idx.centered(j)[d] for j in range(40) if groups[j] == g) for d in range(DIM)]
            self.assertLess(max(abs(x - y) for x, y in zip(sums[g], direct)), 1e-3)
        everything = similar.batch()[1]
        self.assertEqual(everything.positions[lib.songs[5]["id"]], 5)
        self.assertIsNone(b.positions)

    def test_without_vectors(self):
        self.assertIsNone(similar.batch())
        self.assertIsNone(similar.batch(["a", "b"]))


# ---------------------------------------------------------------------------- Prototypes and scores

class TestPrototypes(SoundTasteTest):
    def setUp(self):
        super().setUp()
        write_vectors(vectors_for(self.libs["jonas"]))

    def test_two_kinds_of_music_give_two_prototypes(self):
        st = self.taste_of()
        self.assertEqual(len(st.like), 2)
        self.assertEqual(st.songs, 36)
        self.assertAlmostEqual(st.coverage, 1.0)
        self.assertAlmostEqual(st.share, soundtaste.SHARE)
        idx = similar.index(self.libs["jonas"])
        lib = self.libs["jonas"]
        for vec, share, n, typ in st.like:
            scenes = {BANDS[lib.songs[i]["artist"]] for i, _sc in sorted(
                ((i, idx.closeness(i, vec)) for i in range(len(lib.songs))), key=lambda x: -x[1])[:18]}
            self.assertEqual(len(scenes), 1)                  # each prototype is one kind of music
            self.assertEqual(n, 18)
            self.assertGreater(typ, 0.5)
        self.assertGreater(st.like[0][1], st.like[1][1])      # children's songs are played more: biggest first
        self.assertAlmostEqual(st.like[0][1] + st.like[1][1], 1.0, places=3)

    def test_scores_rank_what_sounds_like_both(self):
        st = self.taste_of()
        lib = self.libs["jonas"]
        score = st.for_lib(lib)
        kinder = [score[i] for i in self.ids(lib, "Kita", "Sandkasten", "Laterne")]
        metal = [score[i] for i in self.ids(lib, "Eisen", "Stahl", "Blech")]
        other = [score[i] for i in self.ids(lib, "Harfe", "Dudel", "Schlager")]
        # not one average: the less played metal is just as much "your sound" as the children's songs
        self.assertGreater(min(kinder + metal), 0.7)
        self.assertLess(max(other), 0.3)
        self.assertEqual(st.score(lib.songs[0]["id"]), score[0])
        self.assertIsNone(st.score("unknown"))

    def test_one_kind_of_music_one_prototype(self):
        self.libs["jonas"] = library("Jonas", {"Kita": (8, 5), "Sandkasten": (8, 5), "Laterne": (8, 5),
                                               "Harfe": (2, 1)})
        write_vectors(vectors_for(self.libs["jonas"]))
        st = self.taste_of()
        self.assertEqual(len(st.like), 1)                     # 4 folk songs: too few for their own prototype
        self.assertEqual(st.like[0][2], 26)

    def test_deterministic_and_cached_per_day(self):
        a = self.taste_of()
        self.assertIs(self.taste_of(), a)                     # cached per account and day
        soundtaste._memo.clear()
        b = self.taste_of()
        self.assertIsNot(a, b)
        self.assertEqual([list(p[0]) for p in a.like], [list(p[0]) for p in b.like])
        write_vectors(vectors_for(self.libs["jonas"]))       # new state of the sound vectors: computed again
        self.assertIsNot(self.taste_of(), b)

    def test_too_few_songs_with_a_vector(self):
        lib = self.libs["jonas"]
        write_vectors({s["id"]: v for s, v in zip(lib.songs, vectors_for(lib).values()) if s["artist"] == "Kita"})
        self.assertIsNone(self.taste_of())                    # 6 liked songs with a vector
        write_vectors({s["id"]: v for s, v in zip(lib.songs, vectors_for(lib).values()) if s["artist"] in ("Kita", "Sandkasten", "Laterne")})
        st = self.taste_of()
        self.assertEqual((st.songs, len(st.like)), (18, 1))
        self.assertLess(st.coverage, 0.85)                    # metal is played too, but has no vector yet
        self.assertAlmostEqual(st.share, soundtaste.SHARE * min(1.0, st.coverage / soundtaste.FULL_COVERAGE))

    def test_prototypes_on_their_own(self):
        lib = self.libs["jonas"]
        sids, b = similar.batch([s["id"] for s in lib.songs if BANDS[s["artist"]] in ("kinder", "metal", "folk")])
        weights = [1.0] * len(sids)
        protos = soundtaste.prototypes(b, weights, 4)
        self.assertEqual(len(protos), 3)                      # four allowed, three kinds of music
        self.assertEqual(sorted(p[2] for p in protos), [20, 30, 30])
        self.assertEqual(len(soundtaste.prototypes(b, weights, 1)), 1)


# ---------------------------------------------------------------------------- Dislikes

class TestDislikes(SoundTasteTest):
    def setUp(self):
        super().setUp()
        # songs that sound partly like metal and mostly like folk – and folk songs rated 1 star by hand
        mixed = [song(f"mix-{k}", artist="Mischung", album="Mischung") for k in range(6)]
        self.libs["jonas"] = library("Jonas", FAMILY, extra=mixed)
        self.mixed = [(s["id"], {"metal": 0.4, "folk": 0.6}) for s in mixed]
        write_vectors(vectors_for(self.libs["jonas"], self.mixed))

    def test_dislikes_of(self):
        lib = self.libs["jonas"]
        by_id = {s["id"]: s for s in lib.songs}
        by_id["Harfe-0"]["userRating"] = 1                    # by hand (the Deezer rating never set it)
        by_id["Harfe-1"]["userRating"] = 2
        feedback.DEEZER_STATE.write_text(json.dumps({"songs": {"Harfe-1": {"r": 1, "s": 3, "t": 1, "u": {"Jonas": 3}},
                                                               "Harfe-2": {"r": 1, "s": 2, "t": 1, "u": {"Jonas": 2}}}}))
        self.addCleanup(feedback.DEEZER_STATE.unlink, missing_ok=True)
        by_id["Harfe-2"]["userRating"] = 2                    # 2 stars – but set by the Deezer rating
        skipped = {"Dudel-0": feedback.SKIP_FACTOR ** 3, "Dudel-1": feedback.SKIP_FACTOR, "Kita-0": feedback.SKIP_FACTOR ** 4}
        by_id["Kita-0"]["starred"] = "2026-01-01T00:00:00Z"   # a favorite is never "disliked"
        with mock.patch.object(feedback, "factors", return_value=skipped):
            out = soundtaste.dislikes_of(lib, "Jonas", TODAY)
        self.assertEqual(out["Harfe-0"], 3.0)
        self.assertEqual(out["Harfe-1"], 1.5)
        self.assertAlmostEqual(out["Dudel-0"], 2.0)           # skipped three times: 3 − 1
        self.assertEqual(set(out), {"Harfe-0", "Harfe-1", "Dudel-0"})

    def test_what_sounds_like_the_dislikes_comes_less(self):
        lib = self.libs["jonas"]
        before = self.taste_of()
        self.assertEqual(before.dislike, [])
        for s in lib.songs:
            if s["artist"] in ("Harfe", "Dudel") and int(s["id"][-1]) < 4:
                s["userRating"] = 1                           # 1 star by hand
        soundtaste._memo.clear()
        after = self.taste_of()
        self.assertEqual(len(after.dislike), 1)
        mixed = [i for i, s in enumerate(lib.songs) if s["artist"] == "Mischung"]
        b, a = before.for_lib(lib), after.for_lib(lib)
        self.assertGreater(min(b[i] for i in mixed), 0.2)
        for i in mixed:
            self.assertLess(a[i], b[i] - 0.05)                # sounds more like the dislikes than like the likes
        self.assertLess(sum(a[i] for i in mixed), 0.6 * sum(b[i] for i in mixed))
        for i in self.ids(lib, "Kita", "Eisen"):              # what sounds like the likes stays
            self.assertAlmostEqual(a[i], b[i], places=6)
        folk = self.ids(lib, "Harfe", "Dudel")
        self.assertTrue(all(a[i] == 0 for i in folk))


# ---------------------------------------------------------------------------- Where it is used

class TestUses(SoundTasteTest):
    def setUp(self):
        super().setUp()
        self.cfg = base_config()
        self.lib = self.libs["jonas"]

    def test_without_vectors_everything_as_before(self):
        prof = taste.profile(self.cfg, self.lib, "Jonas", TODAY)
        self.assertTrue(prof["enough"])
        self.assertNotIn("soundTaste", prof)
        sim = taste.matcher(prof, self.lib)
        self.assertEqual(sim(0), 0.5)                         # nothing known about the sound: neutral as before
        self.assertFalse(taste.summary(self.cfg, prof, self.lib)["sound"])

    def test_matcher_blends_the_sound_taste(self):
        write_vectors(vectors_for(self.lib))
        prof = taste.profile(self.cfg, self.lib, "Jonas", TODAY)
        self.assertIsInstance(prof["soundTaste"], soundtaste.SoundTaste)
        self.assertTrue(taste.summary(self.cfg, prof, self.lib)["sound"])
        sim = taste.matcher(prof, self.lib)
        kinder, metal = self.ids(self.lib, "Kita"), self.ids(self.lib, "Eisen")
        folk = self.ids(self.lib, "Harfe")
        self.assertGreater(min(sim(i) for i in kinder + metal), 0.7)    # 0.5 · 0.5 (no features) + 0.5 · score
        self.assertLess(max(sim(i) for i in folk), 0.4)
        strong = taste.matcher(prof, self.lib, sound=taste.FLAVOR_SOUND)
        self.assertGreater(min(strong(i) for i in kinder), min(sim(i) for i in kinder))
        self.assertLess(max(strong(i) for i in folk), max(sim(i) for i in folk))
        self.assertGreater(taste.factor(sim(kinder[0])), 1.15)
        self.assertLess(taste.factor(sim(folk[0])), 0.95)

    def test_accounts_stay_apart(self):
        self.libs["mia"] = library("Mia", {"Harfe": (8, 6), "Dudel": (8, 6), "Schlager": (4, 2)})
        write_vectors(vectors_for(self.lib))
        jonas, mia = self.taste_of("Jonas"), self.taste_of("Mia")
        self.assertIs(self.taste_of("jonas"), jonas)          # one account, whatever the spelling
        j, m = jonas.for_lib(self.lib), mia.for_lib(self.lib)
        harfe, kita = self.ids(self.lib, "Harfe", unplayed=False), self.ids(self.lib, "Kita", unplayed=False)
        self.assertGreater(min(m[i] for i in harfe), max(j[i] for i in harfe) + 0.5)
        self.assertGreater(min(j[i] for i in kita), max(m[i] for i in kita) + 0.5)
        # mixes: each person's taste from their own account (a person sharing the account gets the same)
        cfg = copy.deepcopy(self.cfg)
        cfg["personen"].append({"id": "mia", "name": "Mia", "user": "Mia", "public": False, "prefix": ""})
        cfg["personen"].append({"id": "jonas2", "name": "Jonas zu zweit", "user": "jonas", "public": False, "prefix": ""})
        seen = []
        real = taste.matcher

        def spy(prof, plib, sound=1.0):
            seen.append((prof or {}).get("user"))
            return real(prof, plib, sound)
        for pid in ("mia", "jonas", "jonas2"):
            p = {"id": f"m-{pid}", "type": "mix", "person": pid, "welt": "*", "stil": "*", "minRating": 0,
                 "mix": {"size": 10, "perArtist": 2, "perAlbum": 0, "flavor": "geschmack"}}
            with mock.patch.object(taste, "matcher", side_effect=spy), \
                 mock.patch.object(rules, "apply_sound", side_effect=lambda cfg, lib, pl, ids: ids):
                mixer.pick(cfg, self.lib, p, {"all": []}, today=TODAY)
        self.assertEqual([u.lower() for u in seen], ["mia", "jonas", "jonas"])

    def test_your_sound_mix_prefers_the_sound(self):
        write_vectors(vectors_for(self.lib))
        p = {"id": "sound", "type": "mix", "person": "jonas", "welt": "*", "stil": "*", "minRating": 0,
             "mix": {"size": 20, "perArtist": 3, "perAlbum": 0, "flavor": "geschmack", "avoidRecent": 0}}
        with mock.patch.object(rules, "apply_sound", side_effect=lambda cfg, lib, pl, ids: ids):
            order, _pool = mixer.pick(self.cfg, self.lib, p, {"all": []}, today=TODAY)
        scenes = Counter(BANDS[self.lib.songs[i]["artist"]] for i in order)
        self.assertGreaterEqual(scenes["kinder"] + scenes["metal"], 16)

    def test_suggestions_move_up_what_sounds_like_the_person(self):
        write_vectors(vectors_for(self.lib))
        st = taste.profile(self.cfg, self.lib, "Jonas", TODAY)["soundTaste"]
        near = st.bonus(self.lib, self.ids(self.lib, "Kita", "Eisen", unplayed=False))
        far = st.bonus(self.lib, self.ids(self.lib, "Harfe", "Dudel", "Schlager", unplayed=False))
        self.assertGreater(near, 0.1)
        self.assertLess(far, -0.1)
        self.assertLessEqual(max(abs(near), abs(far)), soundtaste.SUGGEST_MAX)
        self.assertEqual(st.bonus(self.lib, self.ids(self.lib, "Kita")[:3]), 0.0)   # too few songs


# ---------------------------------------------------------------------------- Time on a NAS

class TestTime(SoundTasteTest):
    def test_25000_songs_and_2000_played(self):
        rnd = random.Random(9)
        dirs = [[rnd.gauss(0, 1) for _ in range(DIM)] for _ in range(50)]
        songs, vectors = [], {}
        for k in range(25000):
            sid = f"g{k}"
            # 2,000 played songs from two "kinds of music" (scenes 0–9 and 25–29), recently and before
            played = k < 2000
            scene = (k % 10 if k % 3 else 25 + k % 5) if played else k % 50
            songs.append(song(sid, artist=f"Band {k % 2000}", plays=1 + k % 7 if played else 0,
                              starred=played and k % 17 == 0))
            vectors[sid] = [c + d + 0.8 * rnd.gauss(0, 1) for c, d in zip(COMMON, dirs[scene])]
        self.libs["jonas"] = lib = Library(songs, ratings_exact=True, user="Jonas")
        self.recent["jonas"] = {f"g{k}": 1 + k % 3 for k in range(0, 2000, 2)}
        write_vectors(vectors)
        similar.count()                                       # loading the file is not part of it
        started = time.perf_counter()
        st = self.taste_of()
        built = time.perf_counter() - started
        started = time.perf_counter()
        score = st.for_lib(lib)
        scored = time.perf_counter() - started
        # on the development PC (Ryzen 5 5600H) about 0.1 s + 0.06 s – an Intel N100 needs about twice as long
        self.assertLess(built + scored, 2.0, (built, scored))
        self.assertTrue(2 <= len(st.like) <= soundtaste.LIKE_K)
        self.assertEqual(len(score), 25000)
        liked = [score[k] for k in range(2000, 25000) if k % 50 < 10]
        other = [score[k] for k in range(2000, 25000) if 10 <= k % 50 < 25]
        self.assertGreater(sum(liked) / len(liked), sum(other) / len(other) + 0.4)


if __name__ == "__main__":
    unittest.main()
