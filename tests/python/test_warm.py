"""The warm-up watcher (web.warm_loop()): the pages the app asks for first are prepared again as soon as the
configuration, the song list or the day changed – not during a run, once after it; a song list a run threw away is
loaded again right away; after Navidrome could not be reached it waits before the next try. Temp folders, no
network."""
from tests.python import env  # noqa: F401  (before app.*)

import contextlib
import datetime as dt
import io
import threading
import time
import types
import unittest
from unittest import mock

from app import auth, config, suggest, web
from app.library import Library
from tests.python.factory import base_config, random_songs

PAGES = ("api_library", "api_playlists", "api_inbox", "api_suggestions", "_warm_learning", "_sync_welten")


class WatcherTest(unittest.TestCase):
    def setUp(self):
        config.save_config(base_config())
        self.lib = Library(random_songs(40))
        self.loads = []
        self.calls = {name: mock.MagicMock() for name in PAGES}
        for p in [mock.patch.object(web, name, m) for name, m in self.calls.items()] + [
                mock.patch.object(web.CACHE, "get", side_effect=self.get),
                mock.patch.object(web, "_warmed", {"stamp": None, "failed": 0.0})]:
            p.start()
            self.addCleanup(p.stop)
        web.CACHE._at = 1000.0
        self.addCleanup(setattr, web.CACHE, "_at", 0.0)

    def get(self, force=False):
        if not web.CACHE._at:   # thrown away by a run: loaded again
            self.loads.append(time.time())
            web.CACHE._at = time.time()
        return self.lib

    def warmed(self):
        """How often the pages were prepared since the last call."""
        n = self.calls["api_suggestions"].call_count
        for m in self.calls.values():
            m.reset_mock()
        return n

    def test_prepares_once_per_change(self):
        web._warm_check()
        self.assertEqual(self.warmed(), 1)
        web._warm_check()
        web._warm_check()
        self.assertEqual(self.warmed(), 0)              # nothing changed: nothing to do
        web.CACHE._at = 2000.0                          # the song list was refreshed
        web._warm_check()
        self.assertEqual(self.warmed(), 1)
        time.sleep(0.01)
        config.save_config(base_config())               # the server changed the configuration itself
        web._warm_check()
        self.assertEqual(self.warmed(), 1)
        tomorrow = types.SimpleNamespace(date=types.SimpleNamespace(today=lambda: dt.date.today() + dt.timedelta(days=1)))
        with mock.patch.object(web, "dt", tomorrow):    # midnight
            web._warm_check()
        self.assertEqual(self.warmed(), 1)

    def test_every_page_is_prepared(self):
        web._warm_check()
        for name, m in self.calls.items():
            self.assertEqual(m.call_count, 1, name)

    def test_not_during_a_run_once_after_it(self):
        web._warm_check()
        self.warmed()
        with mock.patch.object(web.RUNNER, "running", return_value=True):
            web.CACHE._at = 0.0                         # the run threw the song list away …
            web._warm_check()
            self.assertEqual((self.warmed(), self.loads), (0, []))
        web._warm_check()                               # … over: loaded again and prepared at once
        self.assertEqual((self.warmed(), len(self.loads)), (1, 1))
        web._warm_check()
        self.assertEqual(self.warmed(), 0)

    def test_waits_after_navidrome_was_away(self):
        with mock.patch.object(web.CACHE, "get", side_effect=web.NavidromeError("offline")):
            web.CACHE._at = 0.0
            web._warm_check()
            self.assertEqual(self.warmed(), 0)
        web._warm_check()                               # tried just now: not again yet
        self.assertEqual(self.warmed(), 0)
        web._warmed["failed"] -= web.WARM_RETRY
        web._warm_check()
        self.assertEqual(self.warmed(), 1)

    def test_one_warm_up_at_a_time(self):
        self.assertTrue(web._warming.acquire(blocking=False))
        try:
            web._warm_now()                             # another one is going on: left to the watcher
        finally:
            web._warming.release()
        self.assertEqual(self.warmed(), 0)
        self.assertIsNone(web._warmed["stamp"])
        web._warm_check()
        self.assertEqual(self.warmed(), 1)

    def test_a_change_while_preparing_is_noticed(self):
        saved = []

        def save_meanwhile():   # the first time: someone saves while the pages are being prepared
            if not saved:
                time.sleep(0.01)
                config.save_config(base_config())
                saved.append(True)
        self.calls["api_playlists"].side_effect = save_meanwhile
        web._warm_check()
        self.assertEqual(self.warmed(), 1)
        web._warm_check()                               # the pages after it saw the new state – once more
        self.assertEqual(self.warmed(), 1)
        web._warm_check()
        self.assertEqual(self.warmed(), 0)


class PreparedPagesTest(unittest.TestCase):
    """What the watcher prepared is what the page gets – not computed a second time."""

    def test_suggestions_come_from_the_warm_up(self):
        config.save_config(base_config())
        lib = Library(random_songs(60))
        web._memo.clear()
        self.addCleanup(web._memo.clear)
        auth.set_current({"user": "niklas", "role": "admin", "own": "niklas", "persons": [], "local": False})
        self.addCleanup(auth.set_current, {"user": None, "role": "none", "own": None, "persons": [], "local": False})
        real = suggest.suggestions
        with mock.patch.object(web.CACHE, "get", lambda force=False: lib), \
                mock.patch.object(web.playlists, "native_api", side_effect=web.NavidromeError("offline")), \
                mock.patch.object(web, "_warmed", {"stamp": None, "failed": 0.0}), \
                mock.patch.object(web.suggest, "suggestions", side_effect=real) as computed, \
                contextlib.redirect_stdout(io.StringIO()):
            web.CACHE._at = 1000.0
            self.addCleanup(setattr, web.CACHE, "_at", 0.0)
            done = threading.Event()
            threading.Thread(target=lambda: (web._warm_check(), done.set()), daemon=True).start()
            self.assertTrue(done.wait(30))
            self.assertEqual(computed.call_count, 1)
            web.api_suggestions()
            self.assertEqual(computed.call_count, 1)    # the page: from the warm-up


if __name__ == "__main__":
    unittest.main()
