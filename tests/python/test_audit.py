"""Regression tests for findings from the audit of 2026-10-12 (one test per fixed bug)."""
from tests.python import env  # noqa: F401  (before app.*)

import copy
import json
import unittest
from unittest import mock

from app import classify, deezer, mixer, rules
from app.rules import BuildContext, Library
from tests.python.factory import base_config, song


class FakeNav:
    def __init__(self):
        self.set = []

    def set_rating(self, sid, stars):
        self.set.append((sid, stars))


class TestDeezerManual(unittest.TestCase):
    def apply(self, prev, current):
        nav = FakeNav()
        result = {"processed": 0, "found": 0, "notFound": 0, "kept": 0, "set": 0}
        entries = {"s1": prev}
        deezer._apply({"id": "s1", "artist": "A", "title": "T"}, 1, entries, {"niklas": (nav, {"s1": current})},
                      "full", False, False, result, lambda *_: None, thresholds=[0, 10, 20, 30, 40])
        return nav.set, result

    def test_star_tuttiphon_never_set_counts_as_by_hand(self):
        # entry without "u" for this account: a differing star was set by hand and stays
        changed, result = self.apply({}, 5)
        self.assertEqual((changed, result["kept"]), ([], 1))

    def test_star_tuttiphon_set_is_updated(self):
        changed, _ = self.apply({"r": 900, "s": 3, "t": 1, "u": {"niklas": 3}}, 3)
        self.assertEqual(changed, [("s1", 1)])


class TestHits(unittest.TestCase):
    def test_hits_without_any_stars_are_not_everything(self):
        lib = Library([song(f"s{k}", artist="Band A") for k in range(40)])
        cfg = base_config()
        threshold = rules.hits_threshold(cfg, [], BuildContext(lib), floor=0)
        self.assertGreaterEqual(threshold, 1)
        self.assertEqual(lib.ids({"all": [{"any": [{"gt": {"rating": threshold - 1}}, {"is": {"loved": True}}]}]}), frozenset())


class TestCalmDown(unittest.TestCase):
    def test_never_the_same_band_twice_in_a_row_when_avoidable(self):
        # many calm songs by one band at the front: the search must not give up after 6 slots
        songs = [song(f"a{k}", artist="Band A") for k in range(10)] + [song(f"b{k}", artist="Band B") for k in range(9)]
        lib = Library(songs)
        feats = {i: {"arousal": 0.9 if lib.songs[i]["artist"] == "Band A" else 0.1} for i in range(len(songs))}
        out = mixer.calm_down(lib, list(range(len(songs))), feats)
        artists = [lib.songs[i]["artist"] for i in out]
        self.assertFalse(any(a == b for a, b in zip(artists, artists[1:])), artists)


class TestSettingsKeyCosmetics(unittest.TestCase):
    def test_renaming_a_world_keeps_the_mix(self):
        cfg = base_config()
        p = {"id": "m", "type": "mix", "welt": "kinder", "stil": "tanzen", "person": "jonas"}
        before = mixer.settings_key(cfg, p)
        cfg2 = copy.deepcopy(cfg)
        cfg2["welten"][0].update(name="Ganz anders", icon="i:star")
        next(s for s in cfg2["stile"] if s["id"] == "tanzen").update(name="Hüpfen")
        self.assertEqual(before, mixer.settings_key(cfg2, p))


class TestAutoAssignOnce(unittest.TestCase):
    def test_removed_band_does_not_come_back(self):
        classify.AUTO_FILE.unlink(missing_ok=True)
        self.addCleanup(classify.AUTO_FILE.unlink, missing_ok=True)
        cfg = base_config()
        wid = cfg["welten"][0]["id"]
        guess = [{"artist": "Neue Band", "welt": wid, "score": 0.95, "why": "x", "songs": 5}]
        with mock.patch.object(classify, "suggestions", return_value=guess):
            first = classify.auto_assign(cfg, None, 0.7, log=lambda *_: None)
            classify.remember(first)                          # the configuration is saved
            cfg["welten"][0]["artists"].remove("Neue Band")   # removed again by hand
            second = classify.auto_assign(cfg, None, 0.7, log=lambda *_: None)
        self.assertEqual((len(first), len(second)), (1, 0))
        self.assertNotIn("Neue Band", cfg["welten"][0]["artists"])
        logged = json.loads(classify.AUTO_FILE.read_text())
        self.assertEqual(list(logged), ["neue band"])
        self.assertEqual((logged["neue band"]["name"], logged["neue band"]["welt"]), ("Neue Band", wid))

    def test_new_only_skips_old_bands(self):
        from app.rules import Library
        from tests.python.factory import iso_days_ago
        classify.AUTO_FILE.unlink(missing_ok=True)
        self.addCleanup(classify.AUTO_FILE.unlink, missing_ok=True)
        cfg = base_config()
        wid = cfg["welten"][0]["id"]
        lib = Library([song("n1", artist="Neu", created=iso_days_ago(3)), song("o1", artist="Alt", created=iso_days_ago(400))])
        guess = [{"artist": a, "welt": wid, "score": 0.95, "why": "x", "songs": 5} for a in ("Neu", "Alt")]
        with mock.patch.object(classify, "suggestions", return_value=guess):
            made = classify.auto_assign(cfg, lib, 0.7, log=lambda *_: None, new_only=True)
        self.assertEqual([m["artist"] for m in made], ["Neu"])


class TestWatchRetry(unittest.TestCase):
    def test_files_stay_new_when_the_run_cannot_start(self):
        import time
        from app import config, watch
        root = config.paths()["music"]
        new = root / "Neue Band" / "Album" / "01 Lied.opus"
        new.parent.mkdir(parents=True, exist_ok=True)
        new.write_text("x")
        old = time.time() - 600
        self.addCleanup(lambda: (new.unlink(missing_ok=True), watch.STATE_FILE.unlink(missing_ok=True),
                                 watch.FILES_FILE.unlink(missing_ok=True)))
        watch.FILES_FILE.write_text(json.dumps({"v": 2, "dirs": {}}))
        watch._save({"last": old - 60, "checked": 0})

        class Busy:
            started = []

            def running(self):
                return False

            def start(self, steps, **kw):
                if not self.started:
                    self.started.append(False)
                    raise RuntimeError("läuft schon")
                self.started.append(True)
        cfg = copy.deepcopy(config.load_config())
        cfg["settings"]["watch"] = {"enabled": True, "interval": 0}
        runner = Busy()
        # SETTLE < 0: the file just created counts as finished right away (ctime cannot be turned back in the test)
        with mock.patch.object(watch, "load_config", return_value=cfg), mock.patch.object(watch, "SETTLE", -30):
            self.assertIsNone(watch.check(runner))          # another run: remember nothing
            self.assertEqual(json.loads(watch.FILES_FILE.read_text()), {"v": 2, "dirs": {}})
            self.assertEqual(watch.check(runner), 1)          # found again and started next time
        self.assertIn("Neue Band/Album/01 Lied.opus", watch._known())


class TestArchiveOtherVolume(unittest.TestCase):
    """Archive on another volume (UGREEN: music on volume2, archive on the HDD pool volume1)."""

    def setUp(self):
        import errno
        import os
        from app import opus
        self.opus, self.errno = opus, errno
        self.dir = env.ROOT / "archiv-test"
        (self.dir / "musik").mkdir(parents=True, exist_ok=True)
        (self.dir / "archiv").mkdir(parents=True, exist_ok=True)
        self.addCleanup(__import__("shutil").rmtree, self.dir, True)
        self.src = self.dir / "musik" / "01 Lied.flac"
        self.src.write_bytes(b"x" * 5000)
        self.dst = self.dir / "archiv" / "01 Lied.flac"

        def cross_device(a, b):
            raise OSError(errno.EXDEV, "Invalid cross-device link")
        self.rename = mock.patch.object(os, "rename", side_effect=cross_device)

    def test_copies_then_deletes(self):
        with self.rename:
            self.opus.move_to_archive(self.src, self.dst)
        self.assertFalse(self.src.exists())
        self.assertEqual(self.dst.read_bytes(), b"x" * 5000)
        self.assertEqual([f.name for f in self.dst.parent.iterdir()], ["01 Lied.flac"])   # no temporary file

    def test_failed_copy_keeps_the_original_and_leaves_nothing(self):
        with self.rename, mock.patch("shutil.copyfileobj", side_effect=OSError(28, "No space left on device")):
            with self.assertRaises(OSError):
                self.opus.move_to_archive(self.src, self.dst)
        self.assertTrue(self.src.exists())
        self.assertEqual(list(self.dst.parent.iterdir()), [])


@env.german   # checks the German output of existing installations
class TestPauseForApply(unittest.TestCase):
    """A long analysis pauses briefly for applying to Navidrome and then continues with the same parameters."""

    def run_chain(self, steps):
        import threading
        import time
        from app import tasks
        order, started, calls = [], threading.Event(), {"analyse": 0}

        def analyse(runner, ctx, **kw):
            calls["analyse"] += 1
            order.append(("analyse", kw.get("night_until")))
            started.set()
            if calls["analyse"] == 1:
                while not runner.stop.wait(0.01):   # runs until stopped
                    pass
            return True

        def step(name):
            return lambda runner, ctx, **kw: order.append(name) or True
        with mock.patch.object(tasks.TaskRunner, "_step_analyse", analyse), \
             mock.patch.object(tasks.TaskRunner, "_step_playlists", step("playlists")), \
             mock.patch.object(tasks.TaskRunner, "_step_scan", step("scan")):
            runner = tasks.TaskRunner()
            runner.start(steps, name="Klanganalyse (nachts)", night_until=123)
            self.assertTrue(started.wait(3))
            paused = runner.pause_for(["playlists", "scan"], name="Automatisch übernommen")
            if not paused:
                runner.cancel()
            end = time.time() + 5
            while time.time() < end and (runner.running() or (paused and len(order) < 4)):
                time.sleep(0.05)
        return paused, order, runner

    def test_analysis_pauses_and_resumes(self):
        paused, order, runner = self.run_chain(["analyse"])
        self.assertTrue(paused)
        self.assertEqual(order, [("analyse", 123), "playlists", "scan", ("analyse", 123)])
        self.assertEqual(runner.name, "Klanganalyse (nachts) (fortgesetzt)")

    def test_second_scan_counts_as_open_step(self):
        # folder watch: scan occurs twice – during the run the position counts, not the name
        from app import tasks
        runner = tasks.TaskRunner()
        runner.steps, runner._pos = ["scan", "analyse", "playlists", "scan", "deezer"], 3
        with mock.patch.object(tasks.TaskRunner, "running", return_value=True):
            self.assertFalse(runner.can_pause())   # "scan" cannot be paused
            runner._pos = 4
            self.assertTrue(runner.can_pause())    # only "deezer" left

    def test_run_that_writes_playlists_itself_is_not_paused(self):
        paused, order, _ = self.run_chain(["analyse", "playlists"])
        self.assertFalse(paused)


@env.german   # checks the German output of existing installations
class TestComboSearch(unittest.TestCase):
    """Combo search: music world, mood and direction from an input like "ruhige Kinderlieder"."""

    def combos(self, q):
        from app import auth, web
        cfg = base_config()
        cfg["stile"].append({"id": "ruhig-chill", "name": "Ruhig & Chill", "genres": ["Chill"]})
        auth.set_current({"user": "Jonas", "role": "user", "own": "jonas", "persons": ["jonas"], "local": False})
        with mock.patch.object(web.rules, "count", return_value=50):
            return web._search_combos(q, cfg, Library([song("s1")]))

    def test_world_and_mood(self):
        out = self.combos("ruhige kinderlieder")
        self.assertEqual([c["title"] for c in out], ["Kinder · ruhig & sanft"])
        p = out[0]["playlist"]
        self.assertEqual((p["welt"], p["stil"], p["type"], p["sound"], p["person"]), ("kinder", "*", "mix", {"moods": ["ruhig"]}, "jonas"))

    def test_one_word_is_not_a_combo(self):
        self.assertEqual(self.combos("ruhig"), [])        # "ruhig" is a mood, not also "Ruhig & Chill"
        self.assertEqual(self.combos("kinder"), [])

    def test_two_word_mood(self):
        self.assertEqual([c["title"] for c in self.combos("gute laune kinder")], ["Kinder · fröhlich"])

    def test_world_and_direction(self):
        self.assertEqual([c["title"] for c in self.combos("kinder tanzen")], ["Kinder · tanzbar"])
        self.assertEqual([c["title"] for c in self.combos("weihnachten kinder")], ["Kinder · Weihnachten"])


class TestComboSearchEnglish(unittest.TestCase):
    """The same combo search with English words (English interface): "calm kinder", "kinder without vocals"."""

    def combos(self, q):
        from app import auth, web
        cfg = base_config()
        auth.set_current({"user": "Jonas", "role": "user", "own": "jonas", "persons": ["jonas"], "local": False})
        with mock.patch.object(web.rules, "count", return_value=50):
            return web._search_combos(q, cfg, Library([song("s1")]))

    def test_english_mood_words(self):
        for q, mood in (("calm kinder", "ruhig"), ("kinder sleep", "schlaf"), ("good mood kinder", "froh"),
                        ("kinder without vocals", "instrumental"), ("dance kinder", "tanzbar")):
            out = self.combos(q)
            self.assertEqual([c["playlist"]["sound"] for c in out], [{"moods": [mood]}], q)
        self.assertEqual([c["title"] for c in self.combos("calm kinder")], ["Kinder · calm & gentle"])


if __name__ == "__main__":
    unittest.main()
