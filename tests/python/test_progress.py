"""Progress of a run (app/progress.py, TaskRunner.status): the part at work with how many of how many and the time
still to go, the step at work and how long the finished ones took – what "Progress" shows at a glance. Temp folders,
no network."""
from tests.python import env  # noqa: F401  (before app.*)

import threading
import time
import unittest
from unittest import mock

from app import notify, progress, tasks
from app.tasks import TaskRunner


class ProgressTest(unittest.TestCase):
    def setUp(self):
        progress.clear()
        self.addCleanup(progress.clear)

    def test_part_and_time_left(self):
        self.assertIsNone(progress.get())
        progress.at(5)                                   # no part: nothing to report
        self.assertIsNone(progress.get())
        with mock.patch("time.time", return_value=1000.0):
            progress.part("audio", 100)
        progress.at(10)
        early = progress.get(now=1010.0)                 # too early for a remaining time
        self.assertEqual((early["part"], early["done"], early["total"], early["left"]), ("audio", 10, 100, None))
        later = progress.get(now=1060.0)                 # 10 songs in 60 s: 90 more take 540 s
        self.assertEqual((later["elapsed"], later["left"]), (60, 540))

    def test_the_night_ends_it_earlier(self):
        with mock.patch("time.time", return_value=1000.0):
            progress.part("ml", 1000, until=1300.0)
        progress.at(10)
        got = progress.get(now=1100.0)
        self.assertEqual((got["left"], got["until"]), (200, 1300))   # the pace says 9,900 s – but it stops at 1300

    def test_without_a_total(self):
        progress.part("scan")
        progress.at(1234)
        self.assertEqual(progress.get()["done"], 1234)
        self.assertIsNone(progress.get()["left"])
        progress.part("playlists")
        progress.at(0, 12)                               # the total once it is known
        self.assertEqual(progress.get()["total"], 12)


class RunnerStatusTest(unittest.TestCase):
    def test_step_at_work_and_durations(self):
        runner = TaskRunner()
        runner.name = "Test"
        inside, release = threading.Event(), threading.Event()

        def cover(ctx, **_):
            progress.part("cover", 4)
            progress.at(1)
            inside.set()
            release.wait(5)
            return True

        with mock.patch.object(runner, "_step_cover", cover), \
                mock.patch.object(runner, "_step_deezer", lambda ctx, **_: True), \
                mock.patch.object(runner, "_langzeit", lambda opts: None), \
                mock.patch.object(notify, "after_run", lambda entry: None):
            runner.started_at = time.time()
            runner.thread = threading.Thread(target=runner._run_locked, args=(["cover", "deezer"], {}), daemon=True)
            runner.thread.start()
            self.assertTrue(inside.wait(5))
            st = runner.status()
            self.assertEqual((st["running"], st["pos"], st["durations"]), (True, 0, [None, None]))
            self.assertEqual((st["progress"]["part"], st["progress"]["done"], st["progress"]["total"]), ("cover", 1, 4))
            self.assertIsInstance(st["elapsed"], int)
            release.set()
            runner.thread.join(5)
        st = runner.status()
        self.assertFalse(st["running"])
        self.assertEqual((st["pos"], st["progress"], st["elapsed"]), (None, None, None))
        self.assertTrue(all(isinstance(x, int) for x in st["durations"]))
        self.assertIsNone(progress.get())                # cleared at the end of the run
        self.assertEqual(st["results"], {"cover": "ok", "deezer": "ok"})


if __name__ == "__main__":
    unittest.main()
