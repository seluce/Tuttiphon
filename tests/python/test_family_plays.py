"""A family mix heard on a person's own account (listen._runs()): at least three songs in a row in the order of one of
its editions belong to the family – they teach the family's mixes, taste, listening clock and episodes, not the
person's. What the person plays in another order (an album, a playlist of their own) stays theirs. The recap keeps
everything. Temp folders, no network."""
from tests.python import env  # noqa: F401  (before app.*)

import datetime as dt
import shutil
import time
import unittest
from unittest import mock

from app import config, feedback, listen, rueckblick
from tests.python.factory import base_config

T0 = time.mktime(dt.datetime(2026, 10, 20, 8, 0).timetuple())   # Tuesday 08:00 local time
DAY = dt.date(2026, 10, 20)
MIX = ["m1", "m2", "m3", "m4", "m5", "m6"]   # the family's daily mix of that day, in its order


class FamilyPlaysTest(unittest.TestCase):
    def setUp(self):
        self.cfg = base_config()   # the family (account "familie") and Jonas (account "Jonas")
        config.save_config(self.cfg)
        self.addCleanup(config.save_config, base_config())
        self.clean()
        self.addCleanup(self.clean)
        feedback.record("famix", "familie", "day", DAY, MIX)

    def clean(self):
        feedback.HISTORY.unlink(missing_ok=True)
        for user in ("Jonas", "familie"):
            shutil.rmtree(rueckblick._dir(user), ignore_errors=True)
        listen._summary_days.clear()
        listen._fam["key"] = None
        listen._seen["pruned"].clear()
        feedback._live_memo.clear()
        feedback._factors_memo.clear()

    def play(self, user, ids, start=0, skip=()):
        """Songs one after another on one player – a skipped one gives way after 5 seconds."""
        t = start
        for sid in ids:
            listen.record(user, "report", sid, position=1, state="playing", player="phone", cfg=self.cfg, now=T0 + t)
            if sid in skip:
                t += 5
                continue
            listen.record(user, "report", sid, position=150, state="playing", player="phone", cfg=self.cfg,
                          now=T0 + t + 150)
            listen.record(user, "play", sid, t=T0 + t, cfg=self.cfg, now=T0 + t + 160)
            t += 200
        return t

    def test_the_family_s_mix_on_a_person_s_account(self):
        end = self.play("Jonas", ["m1", "m2", "m3", "m4"], skip={"m2"})
        self.play("Jonas", ["own1", "own2", "own3"], start=end + 600)        # something of their own afterwards
        self.assertEqual(listen.summary("Jonas", DAY, DAY), ({}, {"own1": 1, "own2": 1, "own3": 1}))
        self.assertEqual(listen.family_summary(DAY, DAY), ({"m2": [DAY.isoformat()]}, {"m1": 1, "m3": 1, "m4": 1}))
        self.assertLess(feedback.factors("familie", DAY).get("m2", 1), 1)     # the family's mix learns …
        self.assertNotIn("m2", feedback.factors("Jonas", DAY))               # … Jonas' mixes do not
        self.assertEqual(listen.family_shift("Jonas", DAY, DAY), {"m1": -1, "m3": -1, "m4": -1})   # taste: not his
        self.assertEqual(listen.family_shift("familie", DAY, DAY), {"m1": 1, "m3": 1, "m4": 1})     # the family's
        since = dt.datetime.combine(DAY, dt.time())
        self.assertEqual([sid for _t, sid in listen.moments("Jonas", since)], ["own1", "own2", "own3"])
        self.assertEqual([sid for _t, sid in listen.family_moments(since)], ["m1", "m2", "m3", "m4"])
        self.assertEqual({r["id"] for r in listen.family_events(DAY, DAY) if r["k"] == "play"}, {"m1", "m3", "m4"})

    def test_another_order_stays_the_person_s(self):
        self.play("Jonas", ["m3", "m1", "m5", "m2"])                          # shuffled, an album of the same music
        self.play("Jonas", ["m1", "m2", "x"], start=3000)                     # only two in a row
        self.assertEqual(listen.summary("Jonas", DAY, DAY)[1], {"m1": 2, "m2": 2, "m3": 1, "m5": 1, "x": 1})
        self.assertEqual(listen.family_summary(DAY, DAY), ({}, {}))
        self.assertEqual(listen.family_shift("Jonas", DAY, DAY), {})

    def test_without_a_family(self):
        cfg = base_config()
        cfg["personen"] = [p for p in cfg["personen"] if not p.get("family")]
        config.save_config(cfg)
        self.play("Jonas", ["m1", "m2", "m3"])
        self.assertEqual(listen.summary("Jonas", DAY, DAY)[1], {"m1": 1, "m2": 1, "m3": 1})
        self.assertEqual(listen.family_shift("Jonas", DAY, DAY), {})

    def test_the_family_s_editions_stay_as_long_as_the_live_plays(self):
        for k in range(20):
            day = DAY - dt.timedelta(days=k + 1)
            feedback.record("famix", "familie", "day", day, MIX)
            feedback.record("jonasmix", "Jonas", "day", day, MIX)
        self.assertEqual(len(feedback.history()["famix"]), 21)               # recognized in 120 days of plays
        self.assertEqual(len(feedback.history()["jonasmix"]), feedback.KEEP_PERIODS)

    def test_the_mix_counts_as_used(self):
        self.play("Jonas", ["m1", "m2", "m3"])
        snap = {"since": "2026-01-01", "at": "2026-10-22T05:30"}
        with mock.patch.object(rueckblick, "last_snapshot", return_value=snap), \
                mock.patch.object(rueckblick, "plays_between", return_value=({}, None)):
            got = feedback.usage({"famix"}, today=DAY + dt.timedelta(days=2))
        self.assertEqual((got["famix"]["heard"], got["famix"]["played"]), (1, 3))


if __name__ == "__main__":
    unittest.main()
