"""Analysis runs and caches under load: sound analysis (audio.py) tries a briefly unreadable file again and keeps an
earlier measurement when it fails, runs ffmpeg with lower priority; audio.json and ml.json are read only once by
parallel requests; a folder-watch run analyzes only the new songs; identical parallel requests are computed once
(web._memoized); the playlist cover cache; statistics of a music world without an icon. No network, no real data."""
from tests.python import env  # noqa: F401  (before app.*)

import copy
import json
import threading
import time
import unittest
from unittest import mock

from app import audio, config, images, ml, rules, stats, tasks
from app.rules import Library
from tests.python.factory import base_config, iso_days_ago, song
from tests.python.test_ml import RAW, FakeLib, values, write_json


def raw(**over):
    return {**RAW, **over}


class AudioRunTest(unittest.TestCase):
    def setUp(self):
        self.assertIn(env.ROOT, audio.STATE_FILE.parents)   # never the real data
        audio.STATE_FILE.unlink(missing_ok=True)
        audio._cache.update(stamp=None, songs={})
        self.addCleanup(audio.STATE_FILE.unlink, missing_ok=True)
        self.addCleanup(audio._cache.update, stamp=None, songs={})
        self.cfg = base_config()
        self.cfg["settings"]["analysis"]["workers"] = 1
        self.songs = [song(f"s{k}", created=iso_days_ago(k)) for k in range(3)]
        self.lib = FakeLib(self.songs, {s["id"]: f"Band/Album/{s['id']}.opus" for s in self.songs})
        self.logs = []

    def run_audio(self, analyse, **kw):
        with mock.patch.object(audio, "analyse_file", side_effect=analyse), mock.patch.object(audio, "RETRY_PAUSE", 0):
            return audio.run(self.cfg, self.lib, log=self.logs.append, **kw)

    def saved(self):
        return json.loads(audio.STATE_FILE.read_text())["songs"]

    def test_failed_file_keeps_its_earlier_measurement(self):
        # measured before under another path (due again), now not readable: the measurement stays
        write_json(audio.STATE_FILE, {"songs": {"s1": raw(path="Alt/s1.opus")}})
        calls = []

        def analyse(path, *a):
            calls.append(path.name)
            if path.name == "s1.opus":
                raise OSError("Permission denied")
            return raw()
        out = self.run_audio(analyse)
        self.assertEqual(out, {"analysed": 2, "errors": 1, "later": 0})
        self.assertEqual(calls.count("s1.opus"), audio.ATTEMPTS)          # tried again (NAS briefly unreadable)
        entry = self.saved()["s1"]
        self.assertNotIn("error", entry)
        self.assertEqual(entry["path"], "Alt/s1.opus")
        self.assertLessEqual(abs(entry["retry"] - time.time()), 60)
        self.assertIn("s1", audio.features())                              # still has its sound
        self.assertEqual([self.lib.songs[i]["id"] for _, i, _ in audio._todo(self.lib, self.saved(), "standard")], [])

    def test_unknown_song_that_fails_is_marked(self):
        out = self.run_audio(lambda path, *a: None if path.name == "s2.opus" else raw())
        self.assertEqual(out["errors"], 1)
        self.assertTrue(self.saved()["s2"]["error"])

    def test_too_long_is_not_tried_again(self):
        calls = []

        def analyse(path, *a):
            calls.append(path.name)
            raise audio._TooLong("measurement took too long")
        self.run_audio(analyse)
        self.assertEqual(sorted(calls), ["s0.opus", "s1.opus", "s2.opus"])

    def test_briefly_unreadable_file_works_the_second_time(self):
        seen = set()

        def analyse(path, *a):
            if path.name not in seen:
                seen.add(path.name)
                raise OSError("Permission denied")
            return raw()
        out = self.run_audio(analyse)
        self.assertEqual(out, {"analysed": 3, "errors": 0, "later": 0})

    def test_only_the_given_songs_and_the_backlog_count_stays(self):
        write_json(audio.STATE_FILE, {"songs": {}, "open": 40})
        calls = []
        out = self.run_audio(lambda path, *a: calls.append(path.name) or raw(), only={"s2"})
        self.assertEqual((out["analysed"], calls), (1, ["s2.opus"]))
        self.assertEqual(json.loads(audio.STATE_FILE.read_text())["open"], 40)

    def test_ffmpeg_runs_with_lower_priority(self):
        cmds = []

        class Proc:
            def __init__(self, cmd, **kw):
                cmds.append(cmd)

            def communicate(self, timeout=None):
                return "", ""
        with mock.patch.object(audio.subprocess, "Popen", Proc), mock.patch.object(audio, "_nice", return_value="/bin/nice"):
            audio._measure("x.opus")
        with mock.patch.object(audio.subprocess, "Popen", Proc), mock.patch.object(audio, "_nice", return_value=None):
            audio._measure("x.opus")
        self.assertEqual(cmds[0][:4], ["/bin/nice", "-n", str(audio.NICE), "ffmpeg"])
        self.assertEqual(cmds[1][0], "ffmpeg")


class ReadOnceTest(unittest.TestCase):
    """Parallel requests after a save of the run: the large files are parsed once, not once per request."""

    def setUp(self):
        for path in (audio.STATE_FILE, ml.STATE_FILE):
            self.assertIn(env.ROOT, path.parents)
            self.addCleanup(path.unlink, missing_ok=True)
        self.addCleanup(audio._cache.update, stamp=None, songs={})
        self.addCleanup(ml._refresh)

    def parallel(self, module, read):
        calls = []
        real = module.load

        def slow():
            calls.append(1)
            time.sleep(0.2)
            return real()
        with mock.patch.object(module, "load", side_effect=slow):
            threads = [threading.Thread(target=read) for _ in range(4)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()
        return len(calls)

    def test_audio_json(self):
        write_json(audio.STATE_FILE, {"songs": {"a": raw()}})
        self.assertEqual(self.parallel(audio, audio.features), 1)
        self.assertIn("a", audio.features())

    def test_ml_json(self):
        write_json(ml.STATE_FILE, {"v": ml.VERSION, "songs": {"a": {"v": ml.VERSION, "path": "x", "m": values()}}})
        self.assertEqual(self.parallel(ml, ml.features), 1)
        self.assertIn("a", ml.features())
        ml.STATE_FILE.unlink()
        self.assertEqual((ml.features(), ml.themes(), ml.scores()), ({}, {}, {}))   # gone: everything empty again


class WatchRunTest(unittest.TestCase):
    def setUp(self):
        self.cfg = base_config()
        self.root = config.paths(self.cfg)["music"]
        self.songs = [song("neu1", artist="Neue Band", path="x"), song("neu2", artist="Neue Band", path="y"),
                      song("alt", artist="Alte Band", path="z")]
        self.lib = Library(self.songs)
        real = {"neu1": "Neue Band/Album/01 Lied.opus", "neu2": "Neue Band/Album/02 Lied.m4a", "alt": "Alt/01.opus"}
        self.lib.path_loader = lambda: (real, set())

    def test_new_song_ids_follow_the_conversion(self):
        files = [self.root / "Neue Band/Album/01 Lied.flac", self.root / "Neue Band/Album/02 Lied.flac",
                 env.ROOT / "anderswo/03.flac"]
        self.assertEqual(tasks.new_song_ids(self.cfg, self.lib, [str(f) for f in files]), {"neu1", "neu2"})
        self.assertEqual(tasks.new_song_ids(self.cfg, self.lib, []), set())

    def analyse(self, **opts):
        calls = {}

        def rec(name):
            def f(*a, **kw):
                calls[name] = kw
                return {}
            return f
        from app import classify, fingerprint, lastfm, lautstaerke
        runner = tasks.TaskRunner()
        with mock.patch.object(tasks.CACHE, "get", return_value=self.lib), \
             mock.patch.object(tasks, "load_config", return_value=self.cfg), \
             mock.patch.object(tasks, "update_config", side_effect=lambda fn: fn(copy.deepcopy(self.cfg))), \
             mock.patch.object(lastfm, "api_key", return_value="k"), \
             mock.patch.object(lastfm, "refresh", side_effect=lambda names, **kw: calls.update(lastfm=names) or {}), \
             mock.patch.object(audio, "run", side_effect=rec("audio")), mock.patch.object(ml, "run", side_effect=rec("ml")), \
             mock.patch.object(lautstaerke, "settings", return_value={"enabled": True}), \
             mock.patch.object(lautstaerke, "run", side_effect=rec("loudness")), \
             mock.patch.object(fingerprint, "enabled", return_value=True), \
             mock.patch.object(fingerprint, "run", side_effect=rec("fingerprints")), \
             mock.patch.object(classify, "suggestions", return_value=[]), \
             mock.patch.object(classify, "auto_assign", return_value=[]), \
             mock.patch.object(tasks.TaskRunner, "_autowelten"):
            runner._step_analyse({"summary": {}}, **opts)
        return calls

    def test_folder_watch_analyzes_only_the_new_songs(self):
        calls = self.analyse(new_files=[str(self.root / "Neue Band/Album/01 Lied.flac")])
        self.assertEqual(calls["lastfm"], ["Neue Band"])
        self.assertEqual(calls["audio"]["only"], {"neu1"})
        self.assertEqual(calls["ml"]["only"], {"neu1"})
        self.assertEqual(calls["loudness"]["budget"], tasks.WATCH_BUDGET)
        self.assertEqual(calls["fingerprints"]["budget"], tasks.WATCH_BUDGET)

    def test_regular_run_analyzes_everything(self):
        calls = self.analyse()
        self.assertEqual(set(calls["lastfm"]), {"Neue Band", "Alte Band"})
        self.assertIsNone(calls["audio"]["only"])
        self.assertIsNone(calls["ml"]["only"])
        self.assertIsNone(calls["loudness"]["budget"])
        self.assertIsNone(calls["fingerprints"]["budget"])

    def test_watch_hands_over_the_new_files(self):
        from app import watch
        new = self.root / "Neue Band" / "Album" / "01 Lied.opus"
        new.parent.mkdir(parents=True, exist_ok=True)
        new.write_text("x")
        self.addCleanup(lambda: (new.unlink(missing_ok=True), watch.STATE_FILE.unlink(missing_ok=True),
                                 watch.FILES_FILE.unlink(missing_ok=True)))
        watch.FILES_FILE.write_text("[]")
        watch._save({"last": time.time() - 700, "checked": 0})
        got = {}

        class Runner:
            def running(self):
                return False

            def start(self, steps, **kw):
                got.update(steps=steps, **kw)
        cfg = copy.deepcopy(self.cfg)
        cfg["settings"]["watch"] = {"enabled": True, "interval": 0}
        with mock.patch.object(watch, "load_config", return_value=cfg), mock.patch.object(watch, "SETTLE", -30):
            self.assertEqual(watch.check(Runner()), 1)
        self.assertEqual(got["new_files"], [str(new)])
        self.assertIn("analyse", got["steps"])


class MemoizedTest(unittest.TestCase):
    def setUp(self):
        from app import web
        self.web = web
        web._memo.clear()
        self.addCleanup(web._memo.clear)

    def test_parallel_identical_requests_compute_once(self):
        calls, out = [], []

        def build():
            calls.append(1)
            time.sleep(0.3)
            return {"n": len(calls)}
        threads = [threading.Thread(target=lambda: out.append(self.web._memoized("perf-test", build))) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(len(calls), 1)
        self.assertEqual(out, [{"n": 1}] * 5)
        self.assertEqual(self.web._inflight, {})

    def test_after_an_error_the_next_request_computes(self):
        calls = []

        def build():
            calls.append(1)
            if len(calls) == 1:
                time.sleep(0.2)
                raise RuntimeError("Navidrome briefly gone")
            return "ok"
        errors, out = [], []

        def first():
            try:
                self.web._memoized("perf-test-error", build)
            except RuntimeError as e:
                errors.append(e)
        t = threading.Thread(target=first)
        t.start()
        time.sleep(0.05)
        out.append(self.web._memoized("perf-test-error", build))   # waits for the first, then computes itself
        t.join()
        self.assertEqual((len(errors), out, len(calls)), (1, ["ok"], 2))
        self.assertEqual(self.web._inflight, {})


class SmallFixesTest(unittest.TestCase):
    def test_statistics_of_a_world_without_icon(self):
        cfg = base_config()
        cfg["welten"][0].pop("icon", None)
        lib = Library([song("a", artist="Band A", plays=3), song("b", artist="Band B")])
        out = stats.compute(cfg, lib)
        self.assertIn(cfg["welten"][0]["id"], [w["id"] for w in out["welten"]])

    def test_live_cover_cache_under_parallel_requests(self):
        calls = []

        class Client:
            def cover_art(self, cover_id, size):
                calls.append(cover_id)
                return b"img", "image/png"
        images._live.clear()
        self.addCleanup(images._live.clear)
        with mock.patch.object(images, "_client", return_value=Client()):
            threads = [threading.Thread(target=images.live_image, args=(f"pl-{k % 7}abc", 300, k // 7))
                       for k in range(70)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()
            self.assertEqual(images.live_image("pl-1abc", 300, 9), (b"img", "image/png"))
            n = len(calls)
            self.assertEqual(images.live_image("pl-1abc", 300, 9), (b"img", "image/png"))   # from memory
            self.assertEqual(len(calls), n)
        self.assertEqual(len({k[:2] for k in images._live}), len(images._live))   # one version per cover


if __name__ == "__main__":
    unittest.main()
