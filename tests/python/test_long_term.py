"""Long term: lean song list (shared entries, other accounts as an overlay), reloading the song list in the background,
long-term maintenance (trash, vanished songs, old marks, compacting the lyrics index). No network, no real data."""
from tests.python import env  # noqa: F401  (before app.*)

import datetime as dt
import json
import threading
import time
import unittest
from unittest import mock

from app import config, deezer, feedback, langzeit, library, liedtext, navidrome, playlists, stats
from app.rules import Library
from tests.python.factory import base_config, song

TODAY = dt.date(2026, 10, 13)


class SongListTest(unittest.TestCase):
    def test_slim_shares_repeated_entries(self):
        raw = {"id": "1", "title": "A", "album": "Alb", "artist": "Band", "type": "music", "size": 1, "comment": "",
               "artists": [{"id": "ar1", "name": "Band", "extra": 1}], "genres": [{"name": "Rock"}]}
        a = navidrome._slim(raw)
        b = navidrome._slim({**raw, "id": "2", "artists": [{"id": "ar1", "name": "Band"}], "genres": [{"name": "Rock"}]})
        self.assertNotIn("type", a)
        self.assertNotIn("size", a)
        self.assertEqual(a["artists"], [{"id": "ar1", "name": "Band"}])
        self.assertIs(a["artists"], b["artists"])
        self.assertIs(a["genres"], b["genres"])

    def test_overlay_shares_unchanged_songs(self):
        base = Library([song("a", rating=5, plays=3), song("b", rating=4), song("c")])
        mine = [{**base.songs[0]}, {**base.songs[1], "userRating": 1, "starred": "2026-01-01"},
                {k: v for k, v in base.songs[2].items()}, song("neu")]
        mine[2].pop("playCount", None)
        out = stats.overlay(base, mine)
        self.assertIs(out[0], base.songs[0])                       # unchanged: the same entry
        self.assertEqual((out[1]["userRating"], out[1]["starred"]), (1, "2026-01-01"))
        self.assertEqual(base.songs[1]["userRating"], 4)            # the default list stays untouched
        self.assertIs(out[1]["genres"], base.songs[1]["genres"])    # the rest is shared
        self.assertNotIn("playCount", out[2])                       # not played in this account
        self.assertEqual(out[3]["id"], "neu")


class BackgroundReloadTest(unittest.TestCase):
    def test_stale_list_is_served_while_reloading(self):
        cache = library.LibraryCache()
        first, second = Library([song("a")]), Library([song("a"), song("b")])
        gate = threading.Event()

        def slow():
            gate.wait(2)
            return second, None
        with mock.patch.object(library, "_load", return_value=(first, None)):
            self.assertIs(cache.get(), first)
        cache._at = time.time() - library.MAX_AGE - 1                  # expired
        with mock.patch.object(library, "_load", side_effect=slow):
            self.assertIs(cache.get(), first)                          # the previous one right away
            gate.set()
            for _ in range(100):
                if cache._lib is second:
                    break
                time.sleep(0.01)
        self.assertIs(cache.get(), second)
        cache.invalidate()                                             # after a scan: wait for the fresh one
        with mock.patch.object(library, "_load", return_value=(first, None)):
            self.assertIs(cache.get(), first)


@env.german   # checks the German output of existing installations
class LongTermMaintenanceTest(unittest.TestCase):
    def setUp(self):
        env.reset_caches()
        self.cfg = base_config()
        config.save_config(self.cfg)
        for path in (langzeit.STATE_FILE, deezer.STATE_FILE):
            path.unlink(missing_ok=True)
            self.addCleanup(path.unlink, missing_ok=True)
        feedback.FEEDBACK_DIR.mkdir(parents=True, exist_ok=True)
        self.fb = feedback.FEEDBACK_DIR / "test.json"
        self.addCleanup(self.fb.unlink, missing_ok=True)
        self.lib = Library([song(f"s{k}") for k in range(10)])

    def test_trash_expires_after_30_days(self):
        folder = playlists.playlist_dir(self.cfg)
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "noch-da.nsp").write_text("{}")
        self.addCleanup((folder / "noch-da.nsp").unlink, missing_ok=True)
        base = {"person": "familie", "welt": "kinder", "stil": "*", "status": "papierkorb"}
        self.cfg["playlists"] = [{**base, "id": "alt", "deletedAt": "2026-09-01", "file": "weg.nsp"},
                                 {**base, "id": "frisch", "deletedAt": "2026-10-01"},
                                 {**base, "id": "datei", "deletedAt": "2026-09-01", "file": "noch-da.nsp"},
                                 {**base, "id": "ohne"},
                                 {**base, "id": "aktiv", "status": "aktiv"}]
        config.save_config(self.cfg)
        names = langzeit.expire_trash(TODAY)
        self.assertEqual(len(names), 1)
        left = {p["id"]: p for p in config.load_config()["playlists"]}
        self.assertEqual(sorted(left), ["aktiv", "datei", "frisch", "ohne"])
        self.assertEqual(left["ohne"]["deletedAt"], TODAY.isoformat())   # counts from today

    def test_missing_songs_are_forgotten_after_30_days(self):
        deezer.save_state({"version": 1, "songs": {"s1": {"r": 1}, "alt": {"r": 2}}})
        self.fb.write_text(json.dumps({"alt": {"s": ["2026-10-01"], "p": 0}, "s2": {"s": [], "p": 1}}))
        langzeit.run(self.lib, log=lambda *_: None, today=TODAY)
        self.assertIn("alt", deezer.load_state()["songs"])                 # only remembered at first
        self.assertIn("alt", json.loads(langzeit.STATE_FILE.read_text())["missing"])
        out = langzeit.run(self.lib, log=lambda *_: None, today=TODAY + dt.timedelta(days=31))
        self.assertEqual(out["songs"], 1)
        self.assertEqual(set(deezer.load_state()["songs"]), {"s1"})
        self.assertEqual(set(json.loads(self.fb.read_text())), {"s2"})

    def test_nothing_forgotten_when_library_is_suspiciously_small(self):
        deezer.save_state({"version": 1, "songs": {f"s{k}": {} for k in range(10)}})
        langzeit.run(self.lib, log=lambda *_: None, today=TODAY)
        small = Library([song("s0")])                                  # music folder not mounted
        logs = []
        for days in (7, 14, 21, 28, 35, 42):
            langzeit.run(small, log=logs.append, today=TODAY + dt.timedelta(days=days))
        self.assertEqual(len(deezer.load_state()["songs"]), 10)
        self.assertTrue(any("kleiner als sonst" in x for x in logs))

    def test_old_skip_marks_fade_out(self):
        self.fb.write_text(json.dumps({"s1": {"s": ["2023-01-01", "2026-01-01"], "p": 0},
                                       "s2": {"s": ["2022-05-01"], "p": 0}}))
        self.assertEqual(langzeit._age_marks(TODAY), 2)
        self.assertEqual(json.loads(self.fb.read_text()), {"s1": {"s": ["2026-01-01"], "p": 0}})

    def test_weekly_only(self):
        self.assertIsNotNone(langzeit.run(self.lib, log=lambda *_: None, today=TODAY))
        self.assertIsNone(langzeit.run(self.lib, log=lambda *_: None, today=TODAY + dt.timedelta(days=3)))
        self.assertFalse(langzeit.due(TODAY + dt.timedelta(days=3)))
        self.assertTrue(langzeit.due(TODAY + dt.timedelta(days=7)))


class HiddenTest(unittest.TestCase):
    def setUp(self):
        env.reset_caches()

    def test_suggestions_come_back_after_half_a_year(self):
        cfg = base_config()
        cfg["dismissed"] = ["alt", "neu", "scene|achtziger", "ohne"]
        cfg["dismissedAt"] = {"alt": "2026-01-01", "neu": "2026-10-01", "scene|achtziger": "2025-01-01"}
        cfg["accounts"] = {"jonas": {"role": "user", "dismissed": ["k1", "k2"], "dismissedAt": {"k1": "2026-02-01", "k2": "2026-09-01"}}}
        config.save_config(cfg)
        self.assertEqual(langzeit.expire_dismissed(TODAY), 2)
        fresh = config.load_config()
        self.assertEqual(fresh["dismissed"], ["neu", "scene|achtziger", "ohne"])   # music worlds stay hidden
        self.assertEqual(fresh["dismissedAt"]["ohne"], dt.date.today().isoformat())   # without a date: counts from saving
        self.assertEqual(fresh["accounts"]["jonas"]["dismissed"], ["k2"])
        self.assertEqual(langzeit.expire_dismissed(TODAY), 0)

    def test_save_stamps_new_dismissals(self):
        current = base_config()
        current["dismissed"], current["dismissedAt"] = ["a"], {"a": "2026-05-01"}
        incoming = {**base_config(), "dismissed": ["a", "b"], "dismissedAt": {"a": "2020-01-01"}}
        out = config.merge_server_fields(incoming, current)
        self.assertEqual(out["dismissedAt"], {"a": "2026-05-01", "b": dt.date.today().isoformat()})   # from the server, not from the interface


class CompactTest(unittest.TestCase):
    def setUp(self):
        liedtext.DB_FILE.unlink(missing_ok=True)
        self.addCleanup(liedtext.DB_FILE.unlink, missing_ok=True)

    def test_compact(self):
        folder = env.MUSIC / "Dicht" / "Album"
        folder.mkdir(parents=True, exist_ok=True)
        lib = Library([song(f"d{k}") for k in range(40)])
        for k in range(40):
            (folder / f"d{k}.txt").write_text(f"Zeile {k} " + "Wort " * 400, encoding="utf-8")
        lib.path_loader = lambda: ({f"d{k}": f"Dicht/Album/d{k}.opus" for k in range(40)}, {})
        liedtext.update(lib, base_config())
        for k in range(40):
            (folder / f"d{k}.txt").unlink()
        lib = Library([song(f"d{k}") for k in range(40)])
        lib.path_loader = lambda: ({f"d{k}": f"Dicht/Album/d{k}.opus" for k in range(40)}, {})
        liedtext.update(lib, base_config())
        before, after = liedtext.compact()
        self.assertLess(after, before)
        self.assertEqual(liedtext.status()["songs"], 0)


if __name__ == "__main__":
    unittest.main()
