"""The year in music (#/jahr): plays per weekday from the counted days, the time of day kept for the whole year
(listenclock.keep_hours – the moments themselves go after 120 days) and the message in the first week of December.
Temp folders, no network."""
from tests.python import env  # noqa: F401  (before app.*)

import datetime as dt
import json
import shutil
import unittest
from unittest import mock

from app import listenclock, notify, rueckblick, web
from app.rules import Library
from tests.python.factory import base_config, song

NOW = dt.datetime(2026, 10, 20, 12, 0)
USER = "year-test"
MOMENTS = [(dt.datetime(2026, 10, 18, 7, 5), "a"), (dt.datetime(2026, 10, 18, 7, 40), "b"),
           (dt.datetime(2026, 10, 19, 20, 0), "c"), (dt.datetime(2026, 10, 20, 9, 0), "d")]   # the last one today


class HoursTest(unittest.TestCase):
    def setUp(self):
        shutil.rmtree(rueckblick._dir(USER), ignore_errors=True)
        self.addCleanup(shutil.rmtree, rueckblick._dir(USER), ignore_errors=True)

    def test_finished_days_are_counted_once(self):
        with mock.patch.object(listenclock, "moments", return_value=MOMENTS):
            listenclock.keep_hours(USER, [], NOW)
            listenclock.keep_hours(USER, [], NOW)                      # the next day's run: nothing twice
            hours = listenclock.year_hours(USER, 2026, [], NOW)
        days, kept = listenclock._hours_kept(USER, 2026)
        self.assertEqual(days, {"2026-10-18", "2026-10-19"})
        self.assertEqual((kept[7], kept[20], kept[9]), (2, 1, 0))      # today is not finished yet …
        self.assertEqual((hours[7], hours[20], hours[9]), (2, 1, 1))   # … but counts in the recap

    def test_the_hours_stay_when_the_moments_are_gone(self):
        with mock.patch.object(listenclock, "moments", return_value=MOMENTS):
            listenclock.keep_hours(USER, [], NOW)
        with mock.patch.object(listenclock, "moments", return_value=[]):
            hours = listenclock.year_hours(USER, 2026, [], NOW + dt.timedelta(days=200))
        self.assertEqual((hours[7], hours[20], sum(hours)), (2, 1, 3))
        self.assertEqual(sum(listenclock.year_hours(USER, 2025, [], NOW)), 0)

    def test_a_damaged_file_starts_over(self):
        path = listenclock._hours_file(USER, 2026)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('{"days": "x", "hours": [1, 2]}')
        self.assertEqual(listenclock._hours_kept(USER, 2026), (set(), [0] * 24))
        with mock.patch.object(listenclock, "moments", return_value=MOMENTS):
            listenclock.keep_hours(USER, [], NOW)
        self.assertEqual(sum(json.loads(path.read_text())["hours"]), 3)


class WeekdaysTest(unittest.TestCase):
    def setUp(self):
        folder = rueckblick._dir(USER)
        shutil.rmtree(folder, ignore_errors=True)
        self.addCleanup(shutil.rmtree, folder, ignore_errors=True)
        folder.mkdir(parents=True)
        (folder / "2025-10-19.json").write_text(json.dumps({"s1": 3}))   # a Sunday
        (folder / "2025-10-20.json").write_text(json.dumps({"s1": 2}))   # a Monday
        self.lib = Library([song("s1", artist="Band A")])

    def test_plays_per_weekday_and_hours_of_the_year(self):
        cfg = base_config()
        out = rueckblick.summary(cfg, self.lib, USER, "jahr", 2025)
        self.assertEqual(out["weekdays"], [2, 0, 0, 0, 0, 0, 3])
        person = {"id": "x", "user": USER}
        with mock.patch.object(listenclock, "moments", return_value=[]):
            got = web._recap(cfg, self.lib, [], person, "jahr", 2025)
        self.assertEqual((len(got["hours"]), got["person"]), (24, "x"))
        self.assertNotIn("hours", web._recap(cfg, self.lib, [], person, "woche", None))


class YearMessageTest(unittest.TestCase):
    def setUp(self):
        notify.SENT_FILE.unlink(missing_ok=True)
        self.addCleanup(notify.SENT_FILE.unlink, missing_ok=True)
        self.cfg = base_config()
        self.cfg["settings"]["notify"] = {"enabled": True,
                                          "events": {"favorites": False, "review": False, "weekly": False}}
        next(p for p in self.cfg["personen"] if p["id"] == "jonas")["push"] = "jonas-topic"
        self.sent = []

    def run_on(self, day, plays=True):
        played = ({}, {"2026-11-02": 5} if plays else {})
        with mock.patch.object(notify, "send", side_effect=lambda topic, title, text, tags, path, cfg:
                               self.sent.append((topic, title, path)) or True), \
                mock.patch.object(rueckblick, "plays_between", return_value=played):
            return notify.for_persons(self.cfg, Library([]), today=day)

    def test_first_week_of_december_once(self):
        self.assertEqual(self.run_on(dt.date(2026, 12, 2)), 1)
        self.assertEqual(self.run_on(dt.date(2026, 12, 3)), 0)          # once a year
        self.assertEqual([(topic, path) for topic, _title, path in self.sent], [("jonas-topic", "#/jahr")])
        self.assertIn("2026", self.sent[0][1])

    def test_not_outside_the_first_week_or_without_plays(self):
        self.assertEqual(self.run_on(dt.date(2026, 11, 30)), 0)
        self.assertEqual(self.run_on(dt.date(2026, 12, 9)), 0)          # set up later in December
        self.assertEqual(self.run_on(dt.date(2026, 12, 2), plays=False), 0)
        self.cfg["settings"]["notify"]["events"]["year"] = False
        self.assertEqual(self.run_on(dt.date(2026, 12, 2)), 0)
        self.assertEqual(self.sent, [])


if __name__ == "__main__":
    unittest.main()
