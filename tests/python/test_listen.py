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

    def rep(self, sid, second, pos, player="phone", **kw):
        return self.ev("report", sid, second, position=pos, state="playing", player=player, **kw)

    def test_what_is_kept(self):
        for bad in (dict(user="", kind="play", song_id="a"), dict(user=USER, kind="listen", song_id="a"),
                    dict(user=USER, kind="play", song_id=""), dict(user="\ud800x", kind="play", song_id="a"),
                    dict(user="a\nb", kind="play", song_id="a")):
            with self.assertRaises(ValueError):
                listen.record(**bad, now=T0)
        self.assertFalse(listen.record(USER, "play", "a", t=T0 + 7200, now=T0))   # from the future
        self.assertFalse(self.ev("start", "a", 0, position=120))                  # a song going on: not a start
        self.assertTrue(self.ev("report", "a", 0, position=99999, state="nonsense", player="p" * 300, duration=200))
        row = listen.events(USER, DAY, DAY)[0]
        self.assertEqual(set(row), {"t", "k", "id", "pl", "dur"})                # the nonsense left out
        self.assertEqual(len(row["pl"]), 100)
        path = listen._file(USER, DAY.isoformat())
        self.assertEqual(path.stat().st_mode & 0o777, 0o640)

    def test_only_accounts_with_a_person(self):
        cfg = {"personen": [{"id": "x", "user": "Live-Test"}, {"id": "y", "user": "gesperrt"}],
               "accounts": {"gesperrt": {"role": "none"}}}
        self.assertTrue(listen.record(USER, "play", "a", t=at(0), now=at(10), cfg=cfg))
        self.assertFalse(listen.record("gesperrt", "play", "a", t=at(0), now=at(10), cfg=cfg))   # blocked
        self.assertFalse(listen.record("fremd", "play", "a", t=at(0), now=at(10), cfg=cfg))      # no person

    def test_plays_count_only_without_counter_snapshots_and_once(self):
        listen.record(USER, "play", "a", t=at(0), now=at(60))
        self.assertTrue(listen.record(USER, "play", "a", t=at(0), now=at(70)))   # Navidrome retrying: kept once
        night = time.mktime(dt.datetime(2026, 10, 21, 2, 0).timetuple())
        listen.record(USER, "play", "b", t=night, now=night)                   # 02:00 – still the listening day before
        counted, days = rueckblick.plays_between(USER, DAY, DAY)
        self.assertEqual(dict(counted), {"a": 1, "b": 1})
        self.assertEqual(listen.plays(USER, DAY, DAY), {"a": 1})
        rueckblick.snapshot(USER, [{"id": "a", "playCount": 1}], dt.datetime(2026, 10, 20, 12, 0))   # now counters run
        listen.record(USER, "play", "a", t=at(3600), now=at(3660))
        rueckblick._between.clear()
        self.assertEqual(dict(rueckblick.plays_between(USER, DAY, DAY)[0]), {"a": 1, "b": 1})   # not counted twice

    def test_skips_per_player(self):
        self.rep("z", 0, 0)
        self.rep("z", 190, 190)                     # z played on
        self.rep("a", 200, 0)
        self.rep("x", 205, 0, player="tablet")      # someone else on the same account
        self.rep("a", 206, 6)
        self.rep("b", 209, 0)                        # a left after 9 s: skipped
        self.rep("b", 400, 190)
        self.rep("c", 410, 0)                        # b played on: not skipped
        self.rep("y", 600, 0, player="tablet")       # x went on for minutes: not
        self.assertEqual(listen.skips(USER, DAY, DAY), {"a": [DAY.isoformat()]})

    def test_what_is_no_skip(self):
        self.rep("z", 0, 0)
        self.rep("z", 190, 190)
        self.rep("a", 200, 0)
        self.rep("b", 203, 0)                        # a moment of b (cross-fade, a report arriving late) …
        self.rep("a", 204, 4)                        # … and a again: still a
        self.rep("a", 400, 200)
        self.rep("c", 410, 0)
        self.rep("d", 413, 0)                        # c after 3 s …
        self.rep("c", 416, 0)                        # … but back to it ("previous"): d is no skip
        self.rep("c", 600, 190)
        self.rep("e", 610, 0, duration=20)           # a short track played to its end, not scrobbled
        self.rep("f", 630, 0)
        self.rep("f", 800, 170)
        self.rep("g", 800 + 7200, 0)                 # two hours later: the car resumes yesterday's queue …
        self.rep("h", 800 + 7203, 0)                 # … and the next song comes at once: g is no judgement
        self.rep("h", 800 + 7400, 190)
        self.rep("i", 800 + 7410, 0)
        self.assertEqual(listen.skips(USER, DAY, DAY), {})

    def test_skips_from_the_starts_and_plays_win(self):
        self.ev("start", "z", 0, position=0)
        self.ev("start", "a", 200, position=0)
        self.ev("start", "b", 210, position=0)    # a after 10 s
        listen.record(USER, "play", "b", t=at(210), now=at(400))
        self.ev("start", "c", 410, position=0)
        self.ev("start", "d", 415, position=0)    # c after 5 s, but it was scrobbled: played
        listen.record(USER, "play", "c", t=at(408), now=at(416))
        self.ev("start", "e", 600, position=0)
        self.assertEqual(listen.skips(USER, DAY, DAY), {"a": [DAY.isoformat()]})
        self.assertEqual(listen.plays(USER, DAY, DAY), {"b": 1, "c": 1})

    def test_the_moment_for_the_smart_queue(self):
        """The last minutes, song after song: what was skipped, what was listened to on, skips in a row right before the
        song playing now – which is not judged yet."""
        self.rep("z", 0, 0)
        self.rep("a", 200, 0)                        # z played on
        self.rep("b", 210, 0)                        # a after 10 s
        self.rep("c", 300, 0)                        # b played on
        self.rep("d", 305, 0)                        # c after 5 s
        self.rep("e", 312, 0)                        # d after 7 s – e is playing now
        got = listen.moment(USER, now=at(315))
        self.assertEqual(got, {"skipped": ["a", "c", "d"], "kept": ["z", "b"], "streak": 2})
        self.ev("start", "f", 320, position=0)        # f started, its player's report not here yet: e was skipped too
        self.assertEqual(listen.moment(USER, now=at(321))["streak"], 3)
        self.assertEqual(listen.moment(USER, now=at(321 + 1800))["skipped"], [])   # half an hour later: forgotten
        self.rep("f", 330, 20)
        self.rep("g", 600, 0)                        # f played on: the run of skips is over
        self.assertEqual(listen.moment(USER, now=at(601))["streak"], 0)

    def test_listening_clock_gets_every_play_once(self):
        self.ev("start", "a", 0, position=0)
        listen.record(USER, "play", "a", t=at(0), now=at(200))     # the same play
        self.ev("start", "b", 300, position=0)
        self.ev("start", "a", 599, position=0)                       # a again ten minutes later: a new play
        with mock.patch.object(listen.dt, "date", wraps=dt.date) as d:
            d.today.return_value = DAY
            got = listen.moments(USER, dt.datetime(2026, 10, 20, 0, 0))
        self.assertEqual([sid for _t, sid in got], ["a", "b", "a"])
        with mock.patch.object(listenclock, "_stored", lambda user: []), \
                mock.patch.object(listen, "moments", lambda user, since: got):
            played = [{"id": "a", "played": dt.datetime.fromtimestamp(at(601)).astimezone(dt.timezone.utc)
                       .strftime("%Y-%m-%dT%H:%M:%SZ")}]   # Navidrome's last play of a: 08:10:01, the live one 08:09:59
            moms = listenclock.moments(USER, played, dt.datetime(2026, 10, 20, 12, 0))
        self.assertEqual([sid for _t, sid in moms], ["a", "b", "a"])   # not a fourth one from Navidrome's list
        self.assertTrue(listen.has_live(USER, DAY, DAY))
        self.assertFalse(listen.has_live(USER, DAY - dt.timedelta(days=1), DAY - dt.timedelta(days=1)))

    def test_mixes_learn_from_live_skips(self):
        self.ev("start", "z", 0, position=0)
        self.ev("start", "a", 200, position=0)
        self.ev("start", "b", 210, position=0)
        feedback._live_memo.clear()
        with mock.patch.object(feedback, "_cached", lambda *a, **k: {}):
            self.assertLess(feedback.factors(USER, DAY).get("a", 1), 1)
            listen.record(USER, "play", "a", t=at(600), now=at(800))
            listen.record(USER, "play", "a", t=at(900), now=at(1100))   # played twice since: made up for
            self.assertNotIn("a", feedback.factors(USER, DAY))
        history = {"mix": [{"day": "2026-10-19", "every": "day", "user": USER, "ids": ["a", "b", "c", "d"]}]}
        written = {}
        with mock.patch.object(feedback, "_load_to_write", lambda path, default: history), \
                mock.patch.object(feedback, "write_atomic", lambda path, text: written.update({str(path): text})), \
                mock.patch.object(listen, "has_live", lambda user, start, end: True):
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
        cfg = {"personen": [{"id": "x", "user": USER}], "settings": {}}
        with mock.patch.object(web, "load_config", lambda: cfg):
            self.assertEqual(self.post({"event": "play", "user": USER, "id": "a"}, key), (200, {"ok": True}))
            self.assertEqual(self.post({"event": "play", "user": "fremd", "id": "a"}, key), (200, {"ok": False}))
        self.assertEqual(self.post({"event": "dance", "user": USER, "id": "a"}, key)[0], 400)
        self.assertIn(USER, listen.status()["accounts"])
        status, _h, _c = request("POST", "/api/sonic/other", b"{}", headers={"Authorization": f"Bearer {key}"})
        self.assertIn(" 404 ", status)


if __name__ == "__main__":
    unittest.main()
