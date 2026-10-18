"""app/feedback.py ("mixes learn"): history of the mix periods, evaluating completed periods, weights for
skipped songs and 1-star ratings given by hand.

The review (play counts in state/plays/) is replaced: rueckblick.last_snapshot and rueckblick.plays_between
return synthetic values."""
from tests.python import env  # noqa: F401  (before app.*)

import datetime as dt
import json
import os
import random
import shutil
import unittest
from collections import Counter
from unittest import mock

from app import feedback, rueckblick
from app.rules import Library
from tests.python.factory import song

MON = dt.date(2026, 10, 5)            # a Monday – weekly mix until Sunday
SUN = MON + dt.timedelta(days=6)
IDS = ["a", "b", "c", "d", "e", "f", "g"]


class FeedbackTest(unittest.TestCase):
    def setUp(self):
        for path in (feedback.HISTORY, feedback.FEEDBACK_DIR, feedback.DEEZER_STATE):
            self.assertIn(env.ROOT, path.parents)   # never the real data
        self.reset()
        self.addCleanup(self.reset)
        self.log = []

    @staticmethod
    def reset():
        feedback.HISTORY.unlink(missing_ok=True)
        feedback.DEEZER_STATE.unlink(missing_ok=True)
        shutil.rmtree(feedback.FEEDBACK_DIR, ignore_errors=True)
        feedback._cache.clear()

    def history(self):
        return json.loads(feedback.HISTORY.read_text())

    def feedback_of(self, user):
        return json.loads((feedback.FEEDBACK_DIR / f"{user.lower()}.json").read_text())

    def write_feedback(self, user, data):
        feedback.FEEDBACK_DIR.mkdir(parents=True, exist_ok=True)
        (feedback.FEEDBACK_DIR / f"{user.lower()}.json").write_text(json.dumps(data))


# ---------------------------------------------------------------------------- history

class TestHistory(FeedbackTest):
    def test_period_end(self):
        self.assertEqual(feedback.period_end("day", MON), MON)
        self.assertEqual(feedback.period_end("week", MON), SUN)
        self.assertEqual(feedback.period_end("month", dt.date(2026, 2, 1)), dt.date(2026, 2, 28))
        self.assertEqual(feedback.period_end("month", dt.date(2028, 2, 1)), dt.date(2028, 2, 29))
        self.assertEqual(feedback.period_end("month", dt.date(2026, 12, 1)), dt.date(2026, 12, 31))

    def test_record_replaces_the_same_period(self):
        feedback.record("pl1", "Jonas", "week", MON, ["a", "b"])
        feedback.record("pl1", "Jonas", "week", MON, ["c"])            # rewritten: the same week replaced
        feedback.record("pl2", "niklas", "day", MON, ("x",))
        self.assertEqual(self.history(), {
            "pl1": [{"day": "2026-10-05", "every": "week", "user": "Jonas", "ids": ["c"]}],
            "pl2": [{"day": "2026-10-05", "every": "day", "user": "niklas", "ids": ["x"]}]})

    def test_record_needs_user_and_songs(self):
        feedback.record("pl1", "", "day", MON, ["a"])
        feedback.record("pl1", None, "day", MON, ["a"])
        feedback.record("pl1", "Jonas", "day", MON, [])
        self.assertFalse(feedback.HISTORY.exists())

    def test_keeps_the_last_periods_sorted(self):
        days = [MON + dt.timedelta(days=k) for k in range(feedback.KEEP_PERIODS + 5)]
        for d in random.Random(3).sample(days, len(days)):          # recorded in arbitrary order
            feedback.record("pl1", "Jonas", "day", d, [f"s-{d.isoformat()}"])
        kept = [e["day"] for e in self.history()["pl1"]]
        self.assertEqual(kept, [d.isoformat() for d in days[-feedback.KEEP_PERIODS:]])

    def test_forget_removed(self):
        for pid in ("pl1", "pl2", "pl3"):
            feedback.record(pid, "Jonas", "day", MON, ["a"])
        feedback.forget_removed({"pl1", "pl3", "gibt-es-nicht"})
        self.assertEqual(sorted(self.history()), ["pl1", "pl3"])
        inode = feedback.HISTORY.stat().st_ino
        feedback.forget_removed({"pl1", "pl3"})                       # nothing to remove: file stays untouched
        self.assertEqual(feedback.HISTORY.stat().st_ino, inode)
        feedback.forget_removed(set())
        self.assertEqual(self.history(), {})

    def test_forget_removed_without_history(self):
        feedback.forget_removed({"pl1"})
        self.assertFalse(feedback.HISTORY.exists())


# ---------------------------------------------------------------------------- learning

def snap(at, since="2026-01-01T05:30:00"):
    return {"since": since, "at": at}


AFTER_SUN = snap("2026-10-12T05:30:00")   # the daily play count after the end of the week


@env.german   # checks the German output of existing installations
class TestLearn(FeedbackTest):
    def learn(self, today, snapshot, plays=None):
        with mock.patch.object(rueckblick, "last_snapshot", return_value=snapshot) as last, \
             mock.patch.object(rueckblick, "plays_between", return_value=(Counter(plays or {}), {})) as between:
            out = feedback.learn(today=today, log=self.log.append)
        return out, last, between

    def entry(self, pid="pl1"):
        return self.history()[pid][-1]

    def test_running_period_is_left_alone(self):
        feedback.record("pl1", "Jonas", "week", MON, IDS)
        feedback.record("pl2", "Jonas", "day", SUN, IDS)
        out, last, between = self.learn(SUN, AFTER_SUN, {"a": 1, "b": 1, "c": 1})
        self.assertEqual(out, {"periods": 0, "skips": 0, "plays": 0})
        last.assert_not_called()
        between.assert_not_called()
        self.assertNotIn("done", self.entry("pl1"))
        self.assertNotIn("done", self.entry("pl2"))
        self.assertEqual(self.log, [])

    def test_waits_for_the_next_snapshot(self):
        feedback.record("pl1", "Jonas", "week", MON, IDS)
        today = SUN + dt.timedelta(days=2)
        for at in (None, "2026-10-11T23:59:00", "2026-10-12T03:59:59"):   # Sunday evening not yet safely counted
            out, _, between = self.learn(today, snap(at))
            self.assertEqual(out["periods"], 0, at)
            between.assert_not_called()
            self.assertNotIn("done", self.entry())
        out, last, between = self.learn(today, snap("2026-10-12T04:00:00"), {"a": 1, "b": 1, "c": 1})
        self.assertEqual(out["periods"], 1)
        last.assert_called_once_with("Jonas")
        between.assert_called_once_with("Jonas", MON, SUN)
        self.assertTrue(self.entry()["done"])

    def test_shuffled_listening_says_nothing(self):
        # listened shuffled (or single songs from albums): the heard ones are scattered -> nothing counts as skipped
        ids = [f"s{k}" for k in range(50)]
        feedback.record("pl1", "Jonas", "week", MON, ids)
        out, _, _ = self.learn(SUN + dt.timedelta(days=1), AFTER_SUN, {"s3": 1, "s20": 1, "s41": 1, "s47": 1})
        self.assertEqual(out, {"periods": 1, "skips": 0, "plays": 0})

    def test_too_few_heard_says_nothing(self):
        feedback.record("pl1", "Jonas", "week", MON, IDS)
        out, _, _ = self.learn(SUN + dt.timedelta(days=1), AFTER_SUN, {"a": 1, "g": 4, "fremd": 9})
        self.assertEqual(feedback.MIN_HEARD, 3)
        self.assertEqual(out, {"periods": 1, "skips": 0, "plays": 0})
        self.assertTrue(self.entry()["done"])
        self.assertFalse(feedback.FEEDBACK_DIR.exists())
        self.assertIn("1 Zeitraum ausgewertet", self.log[-1])   # singular

    def test_skipped_and_heard(self):
        feedback.record("pl1", "Jonas", "week", MON, IDS)
        out, _, _ = self.learn(SUN + dt.timedelta(days=1), AFTER_SUN, {"a": 1, "c": 3, "e": 1, "fremd": 5})
        # heard: a, c, e (e last) – not played before that: b, d; f and g come after the last one heard
        self.assertEqual(out, {"periods": 1, "skips": 2, "plays": 3})
        self.assertEqual(self.feedback_of("Jonas"), {
            "a": {"s": [], "p": 1}, "b": {"s": ["2026-10-11"], "p": 0}, "c": {"s": [], "p": 1},
            "d": {"s": ["2026-10-11"], "p": 0}, "e": {"s": [], "p": 1}})
        self.assertTrue(self.entry()["done"])
        self.assertIn("2× übersprungen, 3× gehört", self.log[-1])

    def test_no_double_counting(self):
        feedback.record("pl1", "Jonas", "week", MON, IDS)
        plays = {"a": 1, "c": 1, "e": 1}
        self.learn(SUN + dt.timedelta(days=1), AFTER_SUN, plays)
        first = self.feedback_of("Jonas")
        out, last, between = self.learn(SUN + dt.timedelta(days=2), AFTER_SUN, plays)
        self.assertEqual(out, {"periods": 0, "skips": 0, "plays": 0})
        last.assert_not_called()
        between.assert_not_called()
        self.assertEqual(self.feedback_of("Jonas"), first)

    def test_periods_add_up(self):
        feedback.record("pl1", "Jonas", "week", MON, IDS)
        self.learn(SUN + dt.timedelta(days=1), AFTER_SUN, {"a": 1, "c": 1, "e": 1})
        nxt = MON + dt.timedelta(days=7)
        feedback.record("pl1", "Jonas", "week", nxt, ["b", "a", "x", "y"])
        out, _, _ = self.learn(nxt + dt.timedelta(days=7), snap("2026-10-19T05:30:00"), {"a": 1, "x": 1, "y": 1})
        self.assertEqual(out, {"periods": 1, "skips": 1, "plays": 3})
        fb = self.feedback_of("Jonas")
        self.assertEqual(fb["b"], {"s": ["2026-10-11", "2026-10-18"], "p": 0})
        self.assertEqual(fb["a"], {"s": [], "p": 2})

    def test_skip_days_are_capped(self):
        self.write_feedback("Jonas", {"b": {"s": [f"2026-01-{d:02d}" for d in range(1, 11)], "p": 0}})
        feedback.record("pl1", "Jonas", "week", MON, IDS)
        self.learn(SUN + dt.timedelta(days=1), AFTER_SUN, {"a": 1, "c": 1, "e": 1})
        s = self.feedback_of("Jonas")["b"]["s"]
        self.assertEqual(len(s), 10)
        self.assertEqual((s[0], s[-1]), ("2026-01-02", "2026-10-11"))

    def test_feedback_per_account(self):
        feedback.record("pl1", "Jonas", "day", MON, ["a", "b", "c", "d"])
        feedback.record("pl2", "niklas", "day", MON, ["d", "e", "f", "g"])
        plays = {"a": 1, "c": 1, "d": 1, "f": 1, "g": 1}
        out, _, _ = self.learn(MON + dt.timedelta(days=1), snap("2026-10-06T05:30:00"), plays)
        self.assertEqual(out, {"periods": 2, "skips": 2, "plays": 6})
        self.assertEqual(set(self.feedback_of("Jonas")), {"a", "b", "c", "d"})
        self.assertEqual(self.feedback_of("niklas")["e"], {"s": ["2026-10-05"], "p": 0})
        self.assertNotIn("a", self.feedback_of("niklas"))

    def test_never_counted_is_dropped_after_two_weeks(self):
        feedback.record("pl1", "Jonas", "week", MON, IDS)
        out, _, between = self.learn(SUN + dt.timedelta(days=14), None)
        self.assertEqual(out["periods"], 0)
        self.assertNotIn("done", self.entry())                       # maybe the play count still comes
        out, _, between = self.learn(SUN + dt.timedelta(days=15), None)
        self.assertEqual(out, {"periods": 0, "skips": 0, "plays": 0})
        between.assert_not_called()
        self.assertTrue(self.entry()["done"])
        self.assertFalse(feedback.FEEDBACK_DIR.exists())

    def test_counting_started_after_the_period_began(self):
        feedback.record("pl1", "Jonas", "week", MON, IDS)
        late = snap("2026-10-20T05:30:00", since="2026-10-07T05:30:00")   # counting only from Wednesday
        out, _, between = self.learn(SUN + dt.timedelta(days=9), late, {"a": 1, "c": 1, "e": 1})
        self.assertEqual(out["periods"], 0)
        between.assert_not_called()
        self.assertNotIn("done", self.entry())
        self.learn(SUN + dt.timedelta(days=15), late)
        self.assertTrue(self.entry()["done"])


# ---------------------------------------------------------------------------- weights

class TestFactors(FeedbackTest):
    T = dt.date(2026, 10, 12)

    def day(self, n):
        return (self.T - dt.timedelta(days=n)).isoformat()

    def test_weights(self):
        H = feedback.HALF_LIFE
        self.write_feedback("Jonas", {
            "einmal": {"s": [self.day(0)], "p": 0},
            "zweimal": {"s": [self.day(0), self.day(0)], "p": 0},
            "halbwert": {"s": [self.day(H)], "p": 0},
            "zwei-halbwert": {"s": [self.day(2 * H)], "p": 0},
            "ausgeglichen": {"s": [self.day(0)], "p": 1},
            "gehoert": {"s": [self.day(0)], "p": 2},
            "nur-gehoert": {"s": [], "p": 3},
            "gedeckelt": {"s": [self.day(0)] * 8, "p": 0},
            "vergessen": {"s": [self.day(600)], "p": 0},          # 0.5^(600/120) ≈ 0.03 – no longer counts
            "kaputt": {"s": ["gestern", self.day(0)], "p": 0},
            "zukunft": {"s": [self.day(-5)], "p": 0},
            "ohne-felder": {},
        })
        f = feedback.factors("Jonas", today=self.T)
        F = feedback.SKIP_FACTOR
        expected = {"einmal": F, "zweimal": F ** 2, "halbwert": F ** 0.5, "zwei-halbwert": F ** 0.25,
                    "ausgeglichen": F ** 0.5, "gedeckelt": F ** feedback.MAX_SKIPS, "kaputt": F, "zukunft": F}
        self.assertEqual(set(f), set(expected))
        for sid, value in expected.items():
            self.assertAlmostEqual(f[sid], value, places=9, msg=sid)
            self.assertLess(f[sid], 1)

    def test_more_skips_never_weigh_more(self):
        last = 1.0
        for n in range(1, 10):
            self.write_feedback(f"konto{n}", {"x": {"s": [self.day(0)] * n, "p": 0}})
            value = feedback.factors(f"konto{n}", today=self.T)["x"]
            self.assertLessEqual(value, last)
            self.assertGreater(value, 0)
            last = value

    def test_without_account_or_file(self):
        self.write_feedback("Jonas", {"x": {"s": [dt.date.today().isoformat()], "p": 0}})   # stats(): today
        self.assertEqual(feedback.factors("", today=self.T), {})
        self.assertEqual(feedback.factors(None, today=self.T), {})
        self.assertEqual(feedback.factors("niemand", today=self.T), {})
        self.assertEqual(feedback.stats("Jonas"), {"seltener": 1})

    def test_cache_follows_the_file(self):
        self.write_feedback("Jonas", {"x": {"s": [self.day(0)], "p": 0}})
        first = feedback.factors("Jonas", today=self.T)
        self.assertIs(feedback.factors("Jonas", today=self.T), first)   # unchanged: from the cache
        self.write_feedback("Jonas", {"x": {"s": [self.day(0), self.day(0)], "p": 0}, "y": {"s": [self.day(0)]}})
        second = feedback.factors("Jonas", today=self.T)
        self.assertEqual(set(second), {"x", "y"})
        self.assertAlmostEqual(second["x"], feedback.SKIP_FACTOR ** 2)
        os.unlink(feedback.FEEDBACK_DIR / "jonas.json")
        self.assertEqual(feedback.factors("Jonas", today=self.T), {})

    # Notable: _cached() remembers the result only by file state – the day (today) is not part of the key.
    # Whoever asks factors() for another day (preview, long server run past midnight) gets the result
    # for that day – not the cached one from the first call.
    def test_cache_respects_today(self):
        self.write_feedback("Jonas", {"x": {"s": [self.day(0)], "p": 0}})
        feedback.factors("Jonas", today=self.T)
        later = feedback.factors("Jonas", today=self.T + dt.timedelta(days=feedback.HALF_LIFE))
        self.assertAlmostEqual(later["x"], feedback.SKIP_FACTOR ** 0.5)


# ---------------------------------------------------------------------------- 1 star by hand

class TestManualDislikes(FeedbackTest):
    def setUp(self):
        super().setUp()
        self.songs = [
            song("deezer1", rating=1),     # 1 star from the Deezer rating -> not by hand
            song("hand1", rating=1),       # Deezer had set 3 -> set to 1 by hand
            song("ohne-deezer", rating=1),
            song("anderes-konto", rating=1),
            song("zwei", rating=2),
            song("ohne", rating=None),
        ]
        self.write_deezer({
            "deezer1": {"r": 900, "s": 1, "t": 1, "u": {"JONAS": 1, "niklas": 4}},
            "hand1": {"r": 10, "s": 3, "t": 1, "u": {"Jonas": 3}},
            "anderes-konto": {"r": 10, "s": 1, "t": 1, "u": {"niklas": 1}},
            "zwei": {"r": 10, "s": 1, "t": 1, "u": {"jonas": 1}},
            "alt-protokoll": {"seed": True},              # from the old log: unknown who set it
            "alt-unbekannt": {"r": None, "s": None, "t": 1, "u": {}},
        })
        self.songs += [song("alt-protokoll", rating=1), song("alt-unbekannt", rating=1)]   # count as automatic

    def write_deezer(self, songs):
        feedback.DEEZER_STATE.write_text(json.dumps({"songs": songs}))

    def lib(self, user="Jonas", exact=True):
        return Library(self.songs, ratings_exact=exact, user=user)

    def test_manual_one_star(self):
        self.assertEqual(feedback.manual_dislikes(self.lib(), "Jonas"), {"hand1", "ohne-deezer", "anderes-konto"})

    def test_account_case_does_not_matter(self):
        expected = {"hand1", "ohne-deezer", "anderes-konto"}
        self.assertEqual(feedback.manual_dislikes(self.lib(user="jonas"), "JONAS"), expected)
        self.assertEqual(feedback.manual_dislikes(self.lib(user="JONAS"), "jonas"), expected)

    def test_only_with_the_exact_ratings_of_this_account(self):
        self.assertEqual(feedback.manual_dislikes(self.lib(user="niklas"), "Jonas"), set())
        self.assertEqual(feedback.manual_dislikes(self.lib(user=None), "Jonas"), set())
        self.assertEqual(feedback.manual_dislikes(self.lib(exact=False), "Jonas"), set())   # average: unknown
        self.assertEqual(feedback.manual_dislikes(self.lib(), ""), set())
        self.assertEqual(feedback.manual_dislikes(self.lib(), None), set())

    def test_without_deezer_state_every_one_star_counts(self):
        feedback.DEEZER_STATE.unlink()
        self.assertEqual(feedback.manual_dislikes(self.lib(), "Jonas"),
                         {"deezer1", "hand1", "ohne-deezer", "anderes-konto", "alt-protokoll", "alt-unbekannt"})

    def test_deezer_state_is_reread_when_changed(self):
        self.assertNotIn("deezer1", feedback.manual_dislikes(self.lib(), "Jonas"))
        self.write_deezer({"deezer1": {"r": 900, "s": 3, "t": 2, "u": {"Jonas": 3, "niklas": 4}}})   # different size
        self.assertEqual(feedback.manual_dislikes(self.lib(), "Jonas"),
                         {"deezer1", "hand1", "ohne-deezer", "anderes-konto", "alt-protokoll", "alt-unbekannt"})


if __name__ == "__main__":
    unittest.main()
