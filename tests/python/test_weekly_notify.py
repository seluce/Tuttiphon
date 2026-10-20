"""The weekly "New for you this week" notification: on Monday per person with "Discovered for you" or "Album of the
week", from the selections written for this week, once per week; configuration v12 turns the event on."""
from tests.python import env  # noqa: F401  (before app.*)

import copy
import datetime as dt
import unittest
from unittest import mock

from app import config, mixer, notify
from app.rules import Library
from tests.python.factory import base_config, song

MONDAY = dt.date(2026, 10, 19)


class WeeklyTest(unittest.TestCase):
    def setUp(self):
        self.cfg = base_config()
        self.cfg["settings"]["notify"] = {"enabled": True, "events": {}}
        self.cfg["playlists"] = [
            {"id": "disc", "person": "jonas", "welt": "*", "stil": "*", "type": "mix", "unheard": True, "name": "Entdeckt für Jonas",
             "mix": {"every": "week"}},
            {"id": "alb", "person": "jonas", "welt": "*", "stil": "*", "type": "mix", "album": True, "name": "Album der Woche für Jonas",
             "mix": {"every": "week"}}]
        self.lib = Library([song(f"d{k}") for k in range(30)] + [song(f"a{k}", artist="Gruppe Z", album="Platte Z") for k in range(9)])
        self.state = {"disc": {"day": MONDAY.isoformat(), "ids": [f"d{k}" for k in range(30)]},
                      "alb": {"day": MONDAY.isoformat(), "ids": [f"a{k}" for k in range(9)]}}
        self.sent = []
        for p in (mock.patch.object(mixer, "_load_state", lambda: self.state),
                  mock.patch.object(notify, "deliver", lambda title, text, *a, **k: self.sent.append((title, text, k)) or True),
                  mock.patch.object(notify, "once", lambda key, go: key not in self.keys and (self.keys.add(key) or go()))):
            p.start()
            self.addCleanup(p.stop)
        self.keys = set()

    def run_on(self, day):
        with mock.patch.object(mixer, "mix_day", lambda now=None: day):
            return notify._weekly(self.cfg, self.lib, self.cfg["personen"][1], None, day)

    @env.german
    def test_monday_once_with_both(self):
        self.assertEqual(self.run_on(MONDAY), 1)
        title, text, kw = self.sent[0]
        self.assertEqual(title, "Neu für dich diese Woche")
        self.assertEqual(text, "Entdeckt für Jonas: 30 Songs, die du noch nie gehört hast · Album der Woche: Gruppe Z – Platte Z")
        self.assertEqual(kw["accounts"], ["Jonas"])
        self.assertEqual(self.run_on(MONDAY + dt.timedelta(days=1)), 0)   # the same week: not again

    def test_not_mid_week_and_not_before_it_is_written(self):
        self.assertEqual(self.run_on(MONDAY + dt.timedelta(days=2)), 0)
        self.state["disc"]["day"] = self.state["alb"]["day"] = (MONDAY - dt.timedelta(days=7)).isoformat()
        self.assertEqual(self.run_on(MONDAY), 0)
        self.assertEqual(self.sent, [])

    def test_migration_turns_the_event_on(self):
        old = copy.deepcopy(base_config())
        old["version"] = 11
        old["settings"]["notify"] = {"enabled": True, "events": {"favorites": False}}
        new = config.migrate(old)
        self.assertEqual(new["version"], config.CONFIG_VERSION)
        self.assertEqual(new["settings"]["notify"]["events"], {"favorites": False, "weekly": True})


if __name__ == "__main__":
    unittest.main()
