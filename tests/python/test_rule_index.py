"""app/rules.py: rules evaluated from the value index (instead of song by song) and song lists sharing their caches
(the default list and the account lists, stats.songs_for) – the results must be exactly those of the song-by-song
evaluation. Also the caches that follow the shared key (classify, ml, similar)."""
from tests.python import env  # noqa: F401  (before app.*)

import gc
import random
import unittest
import weakref
from unittest import mock

from app import classify, ml, rules, similar, stats
from app.rules import Library, _scan
from tests.python.factory import ARTISTS, GENRES, WORDS, iso_days_ago, random_songs, song

FIELDS = ("artist", "albumartist", "genre", "album", "title", "filepath", "year", "duration", "rating", "loved",
          "playcount", "lastplayed", "dateadded", "missing")
TEXT_OPS = ("contains", "notContains", "startsWith", "endsWith")


def edge_songs():
    """Random library plus the awkward cases: case and diacritics, several artists (also the same one twice), no album,
    no genre, numbers of different types, average ratings."""
    songs = random_songs(260, seed=4)
    songs += [
        song("e1", title="Über den Wolken", artists=["Die Ärzte-Neu", "die ärzte-neu"], album_artist="Die Ärzte-Neu",
             genres=["Rock", "rock", "Hörspiel-Genre"], year=1999, duration=200.0, rating=3, avg=2.5),
        song("e2", title="über den wolken", artist="Solo Sänger", genres=[], year=None, duration=59, avg=4.5),
        song("e3", title="Lied", artists=["Band A", "Band A"], album_artist="Band A", duration=60.5, plays=3,
             played=iso_days_ago(2), created=iso_days_ago(1)),
        song("e4", title="ÄÖÜ", artist="ÄÖÜ", genres=["Ä"], year=2026, duration=0),
        song("e5", title="", artist="", genres=[""], album="", year=1980),
    ]
    songs[-1]["album"] = ""
    noalbum = song("e6", title="Ohne Album", artist="Band D")
    noalbum.pop("album")
    songs.append(noalbum)
    return songs


def values_for(songs, field, rnd):
    """Values a rule might ask for: taken from the library (exact, other case, parts) and a few odd ones."""
    pick = rnd.choice(songs)
    text = {"artist": (pick.get("artists") or [{"name": pick.get("artist", "")}])[0]["name"],
            "albumartist": (pick.get("albumArtists") or [{"name": ""}])[0]["name"],
            "genre": (pick.get("genres") or [{"name": rnd.choice(GENRES)}])[0]["name"],
            "album": pick.get("album") or rnd.choice(WORDS), "title": pick.get("title") or "",
            "filepath": pick.get("path") or ""}.get(field)
    if text is not None:
        a = rnd.randrange(max(1, len(text)))
        part = text[a:a + rnd.randint(1, 4)]
        return [text, text.lower(), text.upper(), part, part.swapcase(), "ä", "Ä", "", rnd.choice(ARTISTS), 5, None]
    if field in ("year", "duration", "rating", "playcount"):
        return [0, 1, 3, 45, 60, 59.5, 1980, 1999, 2026, "1999", True, None, "9"]
    if field in ("lastplayed", "dateadded"):
        return [1, 30, 400, "2025", iso_days_ago(1)[:7], None]
    return [True, False, "true", None, 0, 1]


def rules_for(field, value):
    out = [{op: {field: value}} for op in TEXT_OPS + ("is", "isNot", "gt", "lt")]
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        out += [{"inTheRange": {field: [value, value + 10]}}, {"inTheLast": {field: value}},
                {"notInTheLast": {field: value}}]
    return out


def scanned(lib, rule):
    """The song-by-song evaluation (as before the value index) -> bit mask or the exception type."""
    ((op, body),) = rule.items()
    ((field, value),) = body.items()
    try:
        return _scan(lib._predicate(op, field.lower(), value), lib._field(field.lower()))
    except Exception as e:   # noqa: BLE001 – the same error has to come from the index
        return type(e)


def indexed(lib, rule):
    try:
        return lib._bits(rule)
    except Exception as e:   # noqa: BLE001
        return type(e)


class TestIndexMatchesScan(unittest.TestCase):
    def test_every_operator_on_every_field(self):
        songs = edge_songs()
        rnd = random.Random(8)
        checked = 0
        for exact in (True, False):
            lib, ref = Library(songs, ratings_exact=exact), Library(songs, ratings_exact=exact)
            for field in FIELDS:
                for _ in range(4):
                    for value in values_for(songs, field, rnd):
                        for rule in rules_for(field, value):
                            self.assertEqual(indexed(lib, rule), scanned(ref, rule), rule)
                            checked += 1
        self.assertGreater(checked, 5000)

    def test_case_diacritics_and_several_artists(self):
        lib = Library(edge_songs())

        def ids(rule):
            return {lib.songs[i]["id"] for i in lib.ids(rule)}
        self.assertEqual(ids({"is": {"artist": "Die Ärzte-Neu"}}), {"e1"})
        self.assertEqual(ids({"is": {"artist": "die ärzte-neu"}}), {"e1"})           # its second artist
        self.assertEqual(ids({"is": {"artist": "DIE ÄRZTE-NEU"}}), set())            # "is" is exact
        self.assertIn("e1", ids({"contains": {"artist": "ÄRZTE-N"}}))                   # contains ignores case
        self.assertEqual(ids({"contains": {"title": "ÜBER"}}), {"e1", "e2"})
        self.assertNotIn("e1", ids({"isNot": {"artist": "die ärzte-neu"}}))          # NOT EXISTS
        self.assertIn("e2", ids({"notContains": {"genre": "rock"}}))                  # no genre: passes
        self.assertNotIn("e6", ids({"notContains": {"album": "x"}}))                  # no album: NULL
        self.assertIn("e5", ids({"is": {"album": ""}}))
        self.assertEqual(ids({"is": {"year": 1999}}), ids({"is": {"year": 1999.0}}))   # 1999 == 1999.0, as before
        self.assertIn("e3", ids({"gt": {"duration": 60}}))                            # 60.5

    def test_mask_helpers(self):
        for n in (0, 1, 7, 8, 9, 100, 1000):
            rnd = random.Random(n)
            for share in (0.0, 0.01, 0.5, 1.0):
                idx = [i for i in range(n) if rnd.random() < share]
                groups = [i if k % 2 else [i] for k, i in enumerate(idx)]   # numbers and lists, as in the index
                bits = rules._mask(groups, n)
                self.assertEqual(bits, sum(1 << i for i in idx))
                self.assertEqual(rules._indices(bits), frozenset(idx))


class TestSharedCaches(unittest.TestCase):
    def setUp(self):
        self.base = Library(random_songs(200, seed=5))
        rnd = random.Random(6)
        mine = []
        for s in self.base.songs:   # another account: other stars and plays for some songs
            s = dict(s)
            if rnd.random() < 0.4:
                s["userRating"] = rnd.randint(1, 5)
                s["playCount"] = rnd.choice([0, 2, 9])
                s.pop("starred", None)
            mine.append(s)
        self.songs = stats.overlay(self.base, mine)
        self.acct = Library(self.songs)
        self.acct.share_with(self.base)
        self.fresh = Library(self.songs)   # the same account list without shared caches
        self.rules = [
            {"any": [{"is": {"artist": a}} for a in ARTISTS[:4]] + [{"is": {"albumartist": a}} for a in ARTISTS[:4]]},
            {"all": [{"contains": {"genre": "rock"}}, {"notContains": {"title": "live"}}, {"gt": {"duration": 45}}]},
            {"all": [{"is": {"artist": "Band A"}}, {"gt": {"rating": 2}}]},
            {"any": [{"gt": {"rating": 3}}, {"is": {"loved": True}}]},
            {"inTheLast": {"dateadded": 100}}, {"notInTheLast": {"lastplayed": 30}}, {"is": {"playcount": 0}},
            {"contains": {"filepath": "band"}},
        ]

    def test_results_are_those_of_the_account(self):
        for rule in self.rules:   # the default list first: its results land in the shared cache
            self.base.ids(rule)
        for rule in self.rules:
            self.assertEqual(self.acct.ids(rule), self.fresh.ids(rule), rule)
            self.assertEqual(self.base.ids(rule), Library(self.base.songs).ids(rule), rule)

    def test_only_account_independent_results_are_shared(self):
        world, mixed, account, date = self.rules[0], self.rules[2], self.rules[3], self.rules[4]
        for rule in (world, mixed, account, date):
            self.base.ids(rule)
        self.acct.ids(world)
        self.assertEqual(self.acct._cache, {})                         # found in the cache of the default list
        self.acct.ids(mixed)
        self.acct.ids(account)
        self.acct.ids(date)
        key = rules.json.dumps
        own = set(self.acct._cache)
        self.assertIn(key(mixed, sort_keys=True, ensure_ascii=False), own)    # rating: per account
        self.assertIn(key(account, sort_keys=True, ensure_ascii=False), own)
        self.assertIn(key(date, sort_keys=True, ensure_ascii=False), own)     # depends on today: per list
        self.assertNotIn(key(world, sort_keys=True, ensure_ascii=False), own)

    def test_songs_key(self):
        self.assertEqual(self.acct.songs_key(), self.base.songs_key())
        self.assertNotEqual(self.fresh.songs_key(), self.base.songs_key())
        self.assertEqual(ml.songs_key(self.acct), ml.songs_key(self.base))
        other = Library(self.base.songs[:-1])
        other.share_with(self.base)                                    # not the same songs: nothing shared
        self.assertNotEqual(other.songs_key(), self.base.songs_key())

    def test_songs_for_shares_only_with_the_same_songs_in_the_same_order(self):
        class Nav:
            order = None

            def __init__(self, url, user, pw):
                pass

            def iter_songs(self):
                return iter(Nav.order)
        stats._cache.clear()
        self.addCleanup(stats._cache.clear)
        with mock.patch.object(stats, "Navidrome", Nav), mock.patch.object(stats, "load_env", return_value={"NAV_URL": "x"}), \
             mock.patch.object(stats, "user_password", return_value="pw"):
            Nav.order = [dict(s) for s in self.base.songs]
            same = stats.songs_for("jonas", self.base)
            self.assertEqual(same.songs_key(), self.base.songs_key())
            stats._cache.clear()
            Nav.order = [dict(s) for s in reversed(self.base.songs)]
            other = stats.songs_for("jonas", self.base)
            self.assertNotEqual(other.songs_key(), self.base.songs_key())
            rule = self.rules[0]
            self.assertEqual({other.songs[i]["id"] for i in other.ids(rule)},
                             {self.base.songs[i]["id"] for i in self.base.ids(rule)})


class TestCachesPerSongList(unittest.TestCase):
    """classify.song_features, ml.artist_styles and similar.index keep one entry per song list – the default list and
    the account lists used one after another no longer push each other out (that was a new computation each time)."""

    def setUp(self):
        from tests.python.test_similar import BANDS, library, reset, vectors_for, write_vectors
        reset()
        self.addCleanup(reset)
        self.libs = [library() for _ in range(6)]   # more than the old caches held (1, 1 and 5)
        write_vectors(vectors_for(self.libs[0]))
        self.bands = BANDS

    def test_entries_survive_other_lists(self):
        first = {id(lib): (classify.song_features(lib), ml.artist_styles(lib), similar.index(lib)) for lib in self.libs}
        for lib in self.libs:   # alternately: every list finds its own results
            again = (classify.song_features(lib), ml.artist_styles(lib), similar.index(lib))
            for a, b in zip(first[id(lib)], again):
                self.assertIs(a, b)

    def test_index_keeps_no_song_list(self):
        lib = Library([dict(s) for s in self.libs[0].songs])
        idx = similar.index(lib)
        self.assertIsNotNone(idx)
        cents = idx.centroids()
        self.assertEqual(set(cents), set(self.bands))
        ref = weakref.ref(lib)
        del lib
        gc.collect()
        self.assertIsNone(ref())                 # the cached index does not keep it alive
        self.assertIs(idx.centroids(), cents)

    def test_entries_of_song_lists_that_are_gone_are_dropped(self):
        # e.g. the song list is reloaded every 15 minutes: the results of the old one must not pile up
        old = Library([dict(s) for s in self.libs[0].songs])
        key = ml.songs_key(old)
        classify.song_features(old), ml.artist_styles(old), similar.index(old)
        self.assertTrue(any(k[1] == key for k in classify._memo))
        del old
        gc.collect()
        self.assertTrue(ml.gone(key))
        new = Library([dict(s) for s in self.libs[0].songs])
        classify.song_features(new), ml.artist_styles(new), similar.index(new)
        self.assertFalse(any(k[1] == key for k in classify._memo))
        self.assertNotIn(key, ml._cache["artists"])
        self.assertFalse(any(k[0] == key for k in similar._indexes))
        self.assertFalse(ml.gone(ml.songs_key(new)))


class TestSoundFilterMemo(unittest.TestCase):
    def test_same_songs_as_testing_each_one(self):
        from app import audio
        from tests.python.test_ml import RAW, write_json
        self.addCleanup(audio.STATE_FILE.unlink, missing_ok=True)
        self.addCleanup(audio._cache.update, stamp=None, songs={})
        classify._memo.clear()
        songs = random_songs(120, seed=9)
        rnd = random.Random(3)
        write_json(audio.STATE_FILE, {"songs": {s["id"]: {**RAW, "bpm": rnd.uniform(60, 180), "loud": rnd.uniform(-20, -5),
                                                           "flux": rnd.uniform(10, 120)}
                                                for s in songs if rnd.random() < 0.8}})
        lib = Library(songs)
        feats = classify.song_features(lib)
        cfg = {"stile": [{"id": "x", "sound": {"bpm": [90, 140], "energy": [0.3, 1]}}]}
        playlist = {"stil": "x"}
        ids = lib.ids({"contains": {"genre": "o"}})
        expected = frozenset(i for i in ids if audio.matches(feats.get(i), cfg["stile"][0]["sound"]))
        self.assertTrue(expected)
        self.assertEqual(rules.apply_sound(cfg, lib, playlist, ids), expected)
        with mock.patch.object(audio, "matches", side_effect=AssertionError("not again")):
            self.assertEqual(rules.apply_sound(cfg, lib, playlist, ids), expected)          # from the memo
            self.assertEqual(rules.apply_sound(cfg, lib, playlist, frozenset()), frozenset())
        self.assertIs(rules.apply_sound({"stile": []}, lib, {"stil": "*"}, ids), ids)        # no filter


if __name__ == "__main__":
    unittest.main()
