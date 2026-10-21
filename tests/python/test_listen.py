"""Live plays from the Navidrome plugin (app/listen.py): kept per account and day, plays into the recap only without
counter snapshots, real skips per player (or from the starts), the listening clock and the mixes learning from them,
POST /api/sonic/listen only with the plugin's key."""
from tests.python import env  # noqa: F401  (before app.*)

import datetime as dt
import json
import shutil
import time
import unittest
from unittest import mock

from app import feedback, listen, listenclock, rueckblick, sonic, web
from tests.python.test_audit_server import request

USER = "live-test"
T0 = time.mktime(dt.datetime(2026, 10, 20, 8, 0).timetuple())   # Tuesday 08:00 local time
DAY = dt.date(2026, 10, 20)


def at(seconds):
    return T0 + seconds


class ListenTest(unittest.TestCase):
    def setUp(self):
        self.clean()
        self.addCleanup(self.clean)

    def clean(self):
        shutil.rmtree(rueckblick._dir(USER), ignore_errors=True)
        listen._seen["pruned"].clear()
        rueckblick._between.clear()

    def ev(self, kind, sid, second, **kw):
        return listen.record(USER, kind, sid, now=at(second), **kw)

    def test_what_is_kept(self):
        for bad in (dict(user="", kind="play", song_id="a"), dict(user=USER, kind="listen", song_id="a"),
                    dict(user=USER, kind="play", song_id="")):
            with self.assertRaises(ValueError):
                listen.record(**bad, now=T0)
        self.assertFalse(listen.record(USER, "play", "a", t=T0 + 7200, now=T0))   # from the future
        self.assertTrue(self.ev("report", "a", 0, position=99999, state="nonsense", player="p" * 300))
        row = listen.events(USER, DAY, DAY)[0]
        self.assertEqual(set(row), {"t", "k", "id", "pl"})                       # the nonsense left out
        self.assertEqual(len(row["pl"]), 100)

    def test_plays_count_only_without_counter_snapshots(self):
        listen.record(USER, "play", "a", t=at(0), now=at(60))
        night = time.mktime(dt.datetime(2026, 10, 21, 2, 0).timetuple())
        listen.record(USER, "play", "b", t=night, now=night)                   # 02:00 – still the listening day before
        counted, days = rueckblick.plays_between(USER, DAY, DAY)
        self.assertEqual(dict(counted), {"a": 1, "b": 1})
        rueckblick.snapshot(USER, [{"id": "a", "playCount": 1}], dt.datetime(2026, 10, 20, 12, 0))   # now counters run
        listen.record(USER, "play", "a", t=at(3600), now=at(3660))
        rueckblick._between.clear()
        self.assertEqual(dict(rueckblick.plays_between(USER, DAY, DAY)[0]), {"a": 1, "b": 1})   # not counted twice

    def test_skips_per_player(self):
        self.ev("report", "a", 0, position=0, state="starting", player="phone")
        self.ev("report", "x", 5, position=0, state="starting", player="tablet")   # someone else on the same account
        self.ev("report", "a", 6, position=6, state="playing", player="phone")
        self.ev("report", "b", 9, position=0, state="starting", player="phone")    # a left after 6 s: skipped
        self.ev("report", "b", 200, position=190, state="playing", player="phone")
        self.ev("report", "c", 210, position=0, state="starting", player="phone")  # b played on: not skipped
        self.ev("report", "y", 400, position=0, state="starting", player="tablet")  # x went on for minutes: not
        self.assertEqual(listen.skips(USER, DAY, DAY), {"a": [DAY.isoformat()]})

    def test_skips_from_the_starts_and_plays_win(self):
        self.ev("start", "a", 0, position=0)
        self.ev("start", "b", 10, position=0)    # a after 10 s
        self.ev("start", "b", 40, position=30)   # Navidrome's "now playing" with a report: the same song going on
        listen.record(USER, "play", "b", t=at(10), now=at(200))
        self.ev("start", "c", 210, position=0)
        self.ev("start", "d", 215, position=0)   # c after 5 s, but it was scrobbled: played
        listen.record(USER, "play", "c", t=at(210), now=at(216))
        self.assertEqual(listen.skips(USER, DAY, DAY), {"a": [DAY.isoformat()]})
        self.assertEqual(listen.plays(USER, DAY, DAY), {"b": 1, "c": 1})

    def test_listening_clock_gets_every_play_once(self):
        self.ev("start", "a", 0, position=0)
        listen.record(USER, "play", "a", t=at(0), now=at(200))     # the same play
        self.ev("start", "a", 120, position=120)                     # going on
        self.ev("start", "b", 300, position=0)
        self.ev("start", "a", 3600, position=0)                      # a again an hour later: a new play
        with mock.patch.object(listen.dt, "date", wraps=dt.date) as d:
            d.today.return_value = DAY
            got = listen.moments(USER, dt.datetime(2026, 10, 20, 0, 0))
        self.assertEqual([sid for _t, sid in got], ["a", "b", "a"])
        with mock.patch.object(listenclock, "_stored", lambda user: []), \
                mock.patch.object(listen, "moments", lambda user, since: got):
            moms = listenclock.moments(USER, [], dt.datetime(2026, 10, 20, 12, 0))
        self.assertEqual([sid for _t, sid in moms], ["a", "b", "a"])

    def test_mixes_learn_from_live_skips(self):
        self.ev("start", "a", 0, position=0)
        self.ev("start", "b", 10, position=0)
        feedback._live_memo.clear()
        with mock.patch.object(feedback, "_cached", lambda *a, **k: {}):
            self.assertLess(feedback.factors(USER, DAY).get("a", 1), 1)
            listen.record(USER, "play", "a", t=at(600), now=at(800))
            listen.record(USER, "play", "a", t=at(900), now=at(1100))   # played twice since: made up for
            feedback._live_memo.clear()
            self.assertNotIn("a", feedback.factors(USER, DAY))
        history = {"mix": [{"day": "2026-10-19", "every": "day", "user": USER, "ids": ["a", "b", "c", "d"]}]}
        written = {}
        with mock.patch.object(feedback, "_load_to_write", lambda path, default: history), \
                mock.patch.object(feedback, "write_atomic", lambda path, text: written.update({str(path): text})), \
                mock.patch.object(listen, "has_plays", lambda user, start, end: True):
            out = feedback.learn(dt.date(2026, 10, 21))
        self.assertEqual((out["periods"], out["skips"]), (1, 0))   # live plays: no guessing from the mix history
        self.assertTrue(history["mix"][0]["done"])


class EndpointTest(unittest.TestCase):
    def setUp(self):
        sonic.remove_key()
        self.addCleanup(sonic.remove_key)
        self.addCleanup(lambda: shutil.rmtree(rueckblick._dir(USER), ignore_errors=True))

    def post(self, body, key=None):
        raw = json.dumps(body).encode()
        status, _h, content = request("POST", "/api/sonic/listen", raw,
                                      headers={"Authorization": f"Bearer {key}"} if key else {"X-Tuttiphon": ""})
        return int(status.split()[1]), json.loads(content or b"null")

    def test_only_with_the_key(self):
        self.assertEqual(self.post({"event": "play", "user": USER, "id": "a"})[0], 401)
        key = sonic.new_key()
        self.assertEqual(self.post({"event": "play", "user": USER, "id": "a"}, key), (200, {"ok": True}))
        self.assertEqual(self.post({"event": "dance", "user": USER, "id": "a"}, key)[0], 400)
        self.assertEqual(listen.status()["accounts"][-1:], [USER])
        status, _h, _c = request("POST", "/api/sonic/other", b"{}", headers={"Authorization": f"Bearer {key}"})
        self.assertIn(" 404 ", status)


if __name__ == "__main__":
    unittest.main()
