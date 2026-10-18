"""app/mixer.py: only stable properties of select()/spread()/settings_key() – no exact weights
(the weighting of the mixes is still changing)."""
from tests.python import env  # noqa: F401  (before app.*)

import copy
import datetime as dt
import random
import unittest
from collections import Counter

from app import mixer
from app.rules import Library
from tests.python.factory import base_config, iso_days_ago, song

DAY = dt.date(2026, 10, 14)   # a Wednesday


def big_library(artists=30, albums=3, per_album=5, seed=5):
    rnd = random.Random(seed)
    songs = []
    for a in range(artists):
        for b in range(albums):
            for t in range(per_album):
                sid = f"a{a:02d}-b{b}-t{t}"
                songs.append(song(sid, title=f"Lied {t}", artist=f"Band {a:02d}", album=f"Album {a}-{b}",
                                  album_id=f"al-{a}-{b}", rating=rnd.choice([None, 1, 2, 3, 4, 5]),
                                  starred=rnd.random() < 0.15, plays=rnd.choice([0, 0, 3, 12]),
                                  played=iso_days_ago(rnd.randint(1, 300)) if rnd.random() < 0.6 else None))
    return Library(songs)


def mix(pid="mix1", **opts):
    return {"id": pid, "type": "mix", "welt": "*", "stil": "tanzen",
            "mix": {"size": 40, "perArtist": 3, "perAlbum": 2, "every": "day", **opts}}


class TestSelect(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        env.reset_caches()
        cls.lib = big_library()
        cls.pool = frozenset(range(len(cls.lib.songs)))

    def artist(self, i):
        return self.lib._main_artist(self.lib.songs[i])

    def album(self, i):
        return self.lib.songs[i]["albumId"]

    def test_size_and_unique_songs_from_pool(self):
        pool = frozenset(i for i in self.pool if i % 3)   # only part of the library matches
        order = mixer.select(self.lib, pool, mix(), today=DAY)
        self.assertEqual(len(order), 40)
        self.assertEqual(len(set(order)), 40)
        self.assertLessEqual(set(order), pool)

    def test_caps_per_artist_and_album(self):
        for per_artist, per_album in ((3, 2), (1, 1), (2, 1)):
            order = mixer.select(self.lib, self.pool, mix(perArtist=per_artist, perAlbum=per_album, size=25), today=DAY)
            self.assertEqual(len(order), 25)
            self.assertLessEqual(max(Counter(map(self.artist, order)).values()), per_artist)
            self.assertLessEqual(max(Counter(map(self.album, order)).values()), per_album)

    def test_caps_limit_a_small_pool(self):
        pool = frozenset(i for i in self.pool if self.artist(i) in ("Band 00", "Band 01"))   # 2 bands, 15 songs each
        order = mixer.select(self.lib, pool, mix(perArtist=3, perAlbum=2, size=40), today=DAY)
        self.assertEqual(len(order), 6)
        self.assertEqual(Counter(map(self.artist, order)), {"Band 00": 3, "Band 01": 3})

    def test_zero_means_no_limit(self):
        pool = frozenset(i for i in self.pool if self.artist(i) in ("Band 00", "Band 01"))
        order = mixer.select(self.lib, pool, mix(perArtist=0, perAlbum=0, size=20), today=DAY)
        self.assertEqual(len(order), 20)
        self.assertGreater(max(Counter(map(self.artist, order)).values()), 3)

    def test_deterministic_for_same_day_and_playlist(self):
        a = mixer.select(self.lib, self.pool, mix(), today=DAY)
        b = mixer.select(self.lib, sorted(self.pool, reverse=True), mix(), today=DAY)   # pool order is irrelevant
        self.assertEqual(a, b)

    def test_changes_with_day_and_playlist(self):
        a = mixer.select(self.lib, self.pool, mix(), today=DAY)
        self.assertNotEqual(set(a), set(mixer.select(self.lib, self.pool, mix(), today=DAY + dt.timedelta(days=1))))
        self.assertNotEqual(set(a), set(mixer.select(self.lib, self.pool, mix("mix2"), today=DAY)))

    def test_weekly_mix_stays_the_same_within_the_week(self):
        p = mix(every="week")
        wed = mixer.select(self.lib, self.pool, p, today=DAY)
        self.assertEqual(wed, mixer.select(self.lib, self.pool, p, today=DAY - dt.timedelta(days=2)))   # Monday
        self.assertEqual(wed, mixer.select(self.lib, self.pool, p, today=DAY + dt.timedelta(days=4)))   # Sunday
        self.assertNotEqual(set(wed), set(mixer.select(self.lib, self.pool, p, today=DAY + dt.timedelta(days=5))))

    def test_same_band_not_back_to_back(self):
        for day in range(10):
            order = mixer.select(self.lib, self.pool, mix(), today=DAY + dt.timedelta(days=day))
            artists = [self.artist(i) for i in order]
            self.assertFalse(any(x == y for x, y in zip(artists, artists[1:])), artists)

    def test_sampler_counts_the_track_artist(self):
        songs = [song(f"va{k}", artist=f"Interpret {k % 4}", album_artist="Various Artists", album="Sampler",
                      album_id="al-va") for k in range(16)]
        lib = Library(songs)
        order = mixer.select(lib, frozenset(range(16)), mix(perArtist=1, perAlbum=0, size=10), today=DAY)
        self.assertEqual(sorted(lib._main_artist(lib.songs[i]) for i in order),
                         ["Interpret 0", "Interpret 1", "Interpret 2", "Interpret 3"])


def adjacent_pairs(names):
    return sum(1 for x, y in zip(names, names[1:]) if x == y)


class TestSpread(unittest.TestCase):
    def lib_for(self, artists):
        return Library([song(f"s{k}", artist=a, album=f"Album {a}") for k, a in enumerate(artists)])

    def test_permutation_with_as_few_neighbours_as_possible(self):
        rnd = random.Random(42)
        for _ in range(300):
            names = [rnd.choice("ABCDE"[:rnd.randint(1, 5)]) for _ in range(rnd.randint(1, 25))]
            lib = self.lib_for(names)
            chosen = list(range(len(names)))
            rnd.shuffle(chosen)
            out = mixer.spread(lib, chosen)
            self.assertEqual(sorted(out), sorted(chosen))
            got = [names[i] for i in out]
            most = max(Counter(names).values())
            # more songs of one band than all others together (+1) cannot be separated – otherwise no neighbours
            self.assertEqual(adjacent_pairs(got), max(0, 2 * most - len(names) - 1), (names, got))

    def test_keeps_order_within_a_band(self):
        names = list("AABBBCAACB")
        lib = self.lib_for(names)
        chosen = [9, 3, 0, 7, 2, 5, 1, 8, 4, 6]
        out = mixer.spread(lib, chosen)
        for band in "ABC":
            self.assertEqual([i for i in out if names[i] == band], [i for i in chosen if names[i] == band])

    def test_empty(self):
        self.assertEqual(mixer.spread(self.lib_for([]), []), [])


class TestSettingsKey(unittest.TestCase):
    def setUp(self):
        self.cfg = base_config()
        self.p = {"id": "m", "type": "mix", "welt": "kinder", "stil": "tanzen", "person": "jonas",
                  "mix": {"size": 30, "perArtist": 2}}
        self.key = mixer.settings_key(self.cfg, self.p)

    def other(self, cfg=None, **changes):
        return mixer.settings_key(cfg or self.cfg, {**copy.deepcopy(self.p), **changes})

    def test_stable(self):
        self.assertEqual(self.key, mixer.settings_key(copy.deepcopy(self.cfg), copy.deepcopy(self.p)))
        self.assertRegex(self.key, r"^[0-9a-f]{16}$")

    def test_ignores_name_cover_status_and_unset_extras(self):
        self.assertEqual(self.key, self.other(name="Mein Mix", cover={"style": "x"}, status="pausiert",
                                              created="2020-01-01", radio=None, sound=None, minDuration=None))

    def test_changes_with_radio_and_sound(self):
        radio = self.other(radio={"seed": ["Band A"]})
        self.assertNotEqual(self.key, radio)
        self.assertNotEqual(radio, self.other(radio={"seed": ["Band B"]}))
        self.assertNotEqual(radio, self.other(radio={"seed": ["Band A"], "bands": 10}))
        sound = self.other(sound={"moods": ["ruhig"]})
        self.assertNotEqual(self.key, sound)
        self.assertNotEqual(sound, self.other(sound={"moods": ["froh"]}))

    def test_changes_with_what_decides_the_selection(self):
        self.assertNotEqual(self.key, self.other(mix={"size": 31, "perArtist": 2}))
        self.assertNotEqual(self.key, self.other(person="niklas"))
        self.assertNotEqual(self.key, self.other(excludeArtists=["Band A"]))
        cfg = copy.deepcopy(self.cfg)
        cfg["welten"][0]["artists"].append("Band C")            # the playlist's own world
        self.assertNotEqual(self.key, self.other(cfg))
        cfg = copy.deepcopy(self.cfg)
        cfg["personen"][1]["dislikes"]["artists"].append("Band C")   # the person's no-gos
        self.assertNotEqual(self.key, self.other(cfg))
        cfg = copy.deepcopy(self.cfg)
        cfg["settings"]["minDuration"] = 60
        self.assertNotEqual(self.key, self.other(cfg))

    def test_unrelated_config_changes_keep_the_key(self):
        cfg = copy.deepcopy(self.cfg)
        cfg["welten"][1]["artists"].append("Band C")            # another world
        cfg["personen"][0]["dislikes"]["artists"].append("Band C")   # another person
        cfg["settings"]["autoApply"] = not cfg["settings"]["autoApply"]
        self.assertEqual(self.key, self.other(cfg))


if __name__ == "__main__":
    unittest.main()
