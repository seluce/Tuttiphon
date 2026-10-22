"""Audit of the plugin's answers and the live plays (app/sonic.py, app/listen.py, app/mixer.py): never played songs only
when they sound alike and without spoiling the similarities, the family's kid-safe mode on a guess, cached answers
after the family changed, short answers filled up within the view, the path without sorting the library at every step,
the day files of the live plays (bounded cache, every day in between, a damaged byte) and the count of a remembered
"Album of the week" / "Next episode"."""
from tests.python import env  # noqa: F401  (before app.*)

import copy
import datetime as dt
import json
import shutil
import time
import types
import unittest
from unittest import mock

from app import classify, listen, mixer, rueckblick, rules, sonic
from app.rules import Library
from tests.python.factory import base_config, song
from tests.python.test_similar import reset, vector, write_vectors
from tests.python.test_sonic import BANDS, config, library


def ids_of(lib, scored):
    return [lib.songs[i]["id"] for i, _sc in scored]


class SonicCase(unittest.TestCase):
    def setUp(self):
        reset()
        self.addCleanup(reset)
        self.clean()
        self.addCleanup(self.clean)
        self.cfg, self.lib = config(), library()
        write_vectors({s["id"]: vector(BANDS[s["artist"]], k) for k, s in enumerate(self.lib.songs)})

    def clean(self):
        shutil.rmtree(rueckblick.PLAYS_DIR, ignore_errors=True)
        listen._seen["pruned"].clear()
        listen._active.clear()
        sonic._memo.clear()
        sonic._stars.clear()
        sonic._given.clear()
        rueckblick._ever.clear()

    def play(self, user, sid, ago=0):
        self.assertTrue(listen.record(user, "report", sid, position=20, state="playing", player="phone", cfg=self.cfg,
                                      now=time.time() - ago))

    def ask(self, sid="Eisen-0", count=12):
        return sonic.answer(self.cfg, self.lib, "similar", {"id": sid, "count": str(count)})["songs"]


class NeverPlayedTest(SonicCase):
    """_mix_new(): the song brought in takes the place and similarity of the song it pushes on, the others keep theirs;
    a song that sounds like something else never comes in; one overdue comes first."""

    def mix(self, out, ranked, since, played, every=3):
        me = {"person": {"id": "niklas", "newEvery": every}, "user": "niklas", "sure": True}
        with mock.patch.object(sonic, "_played", return_value=frozenset(self.lib.songs[i]["id"] for i in played)), \
                mock.patch.object(sonic, "_since_new", return_value=since):
            return sonic._mix_new(self.lib, out, ranked, me)

    def test_similarities_stay_and_far_songs_stay_out(self):
        out = [(0, 0.9), (1, 0.85), (2, 0.8), (3, 0.75), (4, 0.7), (5, 0.65)]          # Eisen-0 … 5, all played
        ranked = out[:4] + [(6, 0.72)] + out[4:] + [(30, 0.05)]                       # Stahl-0 near, Harfe-0 far
        got = self.mix(out, ranked, since=0, played=range(6))                          # new ones at places 3 and 6
        self.assertEqual([i for i, _sc in got], [0, 1, 6, 2, 3, 4])                    # Harfe-0 not at place 6
        scores = [sc for _i, sc in got]
        self.assertEqual(scores[2], 0.8)                                               # the place's similarity …
        self.assertEqual(scores[4:], [0.75, 0.7])                                      # … the others keep their own
        self.assertEqual(scores, sorted(scores, reverse=True))

    def test_an_overdue_one_comes_first(self):
        out = [(0, 0.9), (1, 0.85), (2, 0.8), (3, 0.75), (4, 0.7), (5, 0.65)]
        ranked = out[:2] + [(6, 0.86)] + out[2:]
        got = self.mix(out, ranked, since=6, played=range(6), every=5)                 # 6 songs since the last new one
        self.assertEqual(got[0][0], 6)                                                 # not only as 4th (every 9th)
        got = self.mix(out, ranked, since=2, played=range(6), every=5)
        self.assertEqual(got[2][0], 6)                                                 # in time: as 3rd

    def test_no_far_song_in_the_smart_queue(self):
        """Only folk songs were never played – far from metal: the answer about a metal song stays as it is."""
        folk = {s["id"] for s in self.lib.songs if BANDS[s["artist"]] == "folk"}
        folder = rueckblick._dir("niklas")
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "first.json").write_text(json.dumps({s["id"]: "2026-10-01" for s in self.lib.songs
                                                       if s["id"] not in folk}))
        self.play("niklas", "Eisen-0")
        got = self.ask(count=6)
        self.assertEqual(sonic.status()["lastFor"], "Niklas")
        self.assertFalse(folk & {x["id"] for x in got})
        self.assertGreater(min(x["similarity"] for x in got), 0.5)                     # not pushed down to 0


class FamilyViewTest(SonicCase):
    def test_the_family_s_kid_safe_mode_on_a_guess(self):
        """The family's kid-safe mode stays when the listener is only guessed (the family's shared device may ask) –
        only a sure listener gets their own view."""
        self.lib.songs[1]["explicitStatus"] = "explicit"   # Eisen-1, the nearest of Eisen-0
        self.cfg["personen"][0]["clean"] = True            # the family
        self.assertNotIn("Eisen-1", [x["id"] for x in self.ask()])             # the family's answer
        self.play("niklas", "Stahl-0")                     # the only one playing: a guess for Niklas
        got = [x["id"] for x in self.ask()]
        self.assertEqual((sonic.status()["lastFor"], sonic.status()["lastGuess"]), ("Niklas", True))
        self.assertNotIn("Eisen-1", got)
        self.clean()
        self.play("niklas", "Eisen-0")                     # sure: his own view
        got = [x["id"] for x in self.ask()]
        self.assertEqual((sonic.status()["lastFor"], sonic.status()["lastGuess"]), ("Niklas", False))
        self.assertIn("Eisen-1", got)

    def test_another_family_is_not_answered_from_the_cache(self):
        self.cfg["personen"][3]["dislikes"] = {"artists": ["Blech"], "genres": []}   # Oma

        def bands(cfg):
            return {self.lib.songs[i]["artist"] for i, _sc in sonic.similar_songs(cfg, self.lib, "Eisen-0", 12)}
        self.assertIn("Blech", bands(self.cfg))                                       # the family's answer, cached
        cfg = copy.deepcopy(self.cfg)
        cfg["personen"][0]["family"] = False
        cfg["personen"][3]["family"] = True                # now Oma's entry is the family
        self.assertNotIn("Blech", bands(cfg))


class FillTest(SonicCase):
    """A short answer (few bands) is filled up to the count from the songs that may come – never children's music of
    the separate world, explicit songs or dislikes – so Navidrome need not add its own picks."""

    def setUp(self):
        super().setUp()
        p = mock.patch.object(classify, "radio_artists", lambda seeds, lib, limit=25: [])
        p.start()
        self.addCleanup(p.stop)

    def test_similar_songs_and_artist_radio_are_filled_up(self):
        got = sonic.similar_songs(self.cfg, self.lib, "Eisen-0", 30)
        ids = ids_of(self.lib, got)
        self.assertEqual(len(ids), 30)
        self.assertEqual(len(set(ids)), 30)
        self.assertNotIn("Eisen-0", ids)
        self.assertFalse({"Kita", "Sandkasten"} & {self.lib.songs[i]["artist"] for i, _sc in got})
        scores = [sc for _i, sc in got]
        self.assertEqual(scores, sorted(scores, reverse=True))
        self.assertEqual(len(sonic.songs_like_artist(self.cfg, self.lib, name="Eisen", count=30)), 30)
        self.assertEqual(len(sonic.songs_like_album(self.cfg, self.lib, album_id="al-Harfe-0", count=30)), 30)

    def test_the_fill_keeps_to_the_view(self):
        self.lib.songs[9]["explicitStatus"] = "explicit"   # Stahl-3
        self.cfg["personen"][1]["child"] = True            # Jonas: kid-safe for everyone
        self.cfg["personen"][2]["dislikes"] = {"artists": ["Blech"], "genres": []}   # Niklas
        self.play("niklas", "Eisen-0")
        got = self.ask(count=40)
        self.assertEqual(sonic.status()["lastFor"], "Niklas")
        self.assertFalse({"Blech", "Kita", "Sandkasten"} & {x["artist"] for x in got})
        self.assertNotIn("Stahl-3", {x["id"] for x in got})
        self.assertEqual(len(got), 36 - 6 - 1 - 1)          # all that may come: not Blech, Eisen-0, Stahl-3


class PathTest(SonicCase):
    def test_the_library_is_sorted_only_when_the_nearest_do_not_do(self):
        keys = []

        def spy(*args, **kw):
            keys.append(kw.get("key"))
            return sorted(*args, **kw)
        with mock.patch.object(sonic, "sorted", spy, create=True):
            got = sonic.path(self.cfg, self.lib, "Eisen-0", "Harfe-0", 8)
        self.assertEqual(len(got), 8)
        self.assertEqual([k for k in keys if k is not None], [])                      # no sorting of all songs
        none_near = types.SimpleNamespace(nlargest=lambda n, rows, key=None: [])
        with mock.patch.object(sonic, "heapq", none_near):                             # the whole list as fallback
            ids = ids_of(self.lib, sonic.path(self.cfg, self.lib, "Eisen-0", "Harfe-0", 8))
        self.assertEqual((ids[0], ids[-1], len(set(ids))), ("Eisen-0", "Harfe-0", 8))
        self.assertEqual(ids, ids_of(self.lib, got))


USER = "audit-days"
NOON = dt.time(12, 0)


def stamp(day, at=NOON):
    return int(time.mktime(dt.datetime.combine(day, at).timetuple()))


class DayFileTest(unittest.TestCase):
    def setUp(self):
        self.clean()
        self.addCleanup(self.clean)
        self.today = dt.date.today()

    def clean(self):
        shutil.rmtree(rueckblick._dir(USER), ignore_errors=True)
        listen._seen["pruned"].clear()
        with listen._days_lock:
            listen._days.clear()
        listen._summary_days.clear()

    def write(self, day, rows, raw=b""):
        path = listen._file(USER, day.isoformat())
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"".join(json.dumps(r).encode() + b"\n" for r in rows) + raw)

    def test_the_cache_stays_small_and_summaries_stay_right(self):
        start = self.today - dt.timedelta(days=59)
        for k in range(60):
            day = start + dt.timedelta(days=k)
            self.write(day, [{"t": stamp(day), "k": "play", "id": f"s{k % 3}"}])
        self.assertEqual(len(listen.events(USER, start, self.today)), 60)
        self.assertLess(len(listen._days), 60)                                      # not every day file kept
        self.assertLessEqual(len(listen._days), listen.DAYS_CACHED)
        self.assertEqual(listen.plays(USER, start, self.today), {"s0": 20, "s1": 20, "s2": 20})
        listen._summary_days.clear()
        self.assertEqual(listen.plays(USER, start, self.today), {"s0": 20, "s1": 20, "s2": 20})
        self.assertLessEqual(len(listen._days), listen.DAYS_CACHED)

    def test_every_day_in_between(self):
        days = [self.today - dt.timedelta(days=k) for k in (2, 1, 0)]
        for day, sid in zip(days, ("before", "between", "now")):
            self.write(day, [{"t": stamp(day, dt.time(12, 30) if sid == "before" else NOON), "k": "report",
                              "id": sid, "pos": 20.0, "st": "playing", "pl": "phone"}])
        now = stamp(self.today, dt.time(12, 10))
        self.assertEqual(listen.heard(USER, 2 * 86400, now=now), {"before", "between", "now"})
        self.assertEqual(listen.sequence(USER, 2 * 86400, now=now), ["before", "between", "now"])

    def test_a_damaged_byte_costs_one_line(self):
        day = self.today
        good = [{"t": stamp(day), "k": "play", "id": "a"}, {"t": stamp(day) + 300, "k": "play", "id": "b"}]
        self.write(day, good, raw=b'{"t": ' + str(stamp(day) + 600).encode() + b', "k": "play", "id": "c\xff"}\n'
                   + b'{"t": ' + str(stamp(day) + 900).encode() + b', "k": "play", "id": "d"}\n')
        self.assertEqual([r["id"] for r in listen.events(USER, day, day)], ["a", "b", "d"])
        self.assertEqual(listen.plays(USER, day, day), {"a": 1, "b": 1, "d": 1})
        t = stamp(day) + 1200
        self.assertTrue(listen.record(USER, "play", "e", t=t, now=t + 5))        # the duplicate check reads the day
        self.assertTrue(listen.record(USER, "play", "e", t=t, now=t + 9))        # Navidrome retrying: kept once
        self.assertEqual([r["id"] for r in listen.events(USER, day, day)], ["a", "b", "d", "e"])


class RememberedCountTest(unittest.TestCase):
    """A remembered "Album of the week" / "Next episode" shows how many there were to choose from, not 1."""

    def setUp(self):
        mixer.MIX_STATE.unlink(missing_ok=True)
        self.addCleanup(mixer.MIX_STATE.unlink, missing_ok=True)
        self.cfg = base_config()
        self.cfg["settings"]["allMinRating"] = 0
        self.lib = Library([song(f"{a}{n}", title=f"Lied {a}{n}", artist=f"Band {a}", album=f"Album {a}",
                                 album_id=f"al-{a}") for a in "ABC" for n in range(4)])
        self.p = {"id": "aotw", "person": "niklas", "welt": rules.ALL, "stil": rules.ALL, "type": "mix", "album": True,
                  "mix": {"every": "week"}}

    def test_album_of_the_week(self):
        cands = [(1.0, "al-A"), (2.0, "al-B"), (1.0, "al-C")]
        today = dt.date.today()
        with mock.patch.object(mixer, "album_candidates", return_value=cands):
            order, n = mixer.pick(self.cfg, self.lib, self.p, {}, today, keep=True)
            self.assertEqual((len(order), n), (4, 3))
            again, n = mixer.album_order(self.cfg, self.lib, self.lib, self.p, {}, today)
            self.assertEqual((again, n), (order, 3))                                  # remembered – still 3
            self.assertEqual(mixer.pick(self.cfg, self.lib, self.p, {}, today)[1], 3)
            state = mixer._load_state()
            del state["aotw"]["albums"]                                               # remembered by an older version
            mixer.MIX_STATE.write_text(json.dumps(state))
            self.assertEqual(mixer.album_order(self.cfg, self.lib, self.lib, self.p, {}, today), (order, 3))


class RememberedEpisodesTest(unittest.TestCase):
    def setUp(self):
        from tests.python import test_episodes
        self.t = test_episodes.EpisodeTest("test_episode_numbers")
        self.t.setUp()
        self.addCleanup(self.t.clean)

    def test_next_episode(self):
        t = self.t
        t.finish("t2", 30)
        t.finish("d1a", 5)
        t.finish("d1b", 4)
        nsp = rules.build_nsp(t.cfg, t.p, rules.BuildContext(t.lib))
        today = dt.date.today()
        order, n = mixer.pick(t.cfg, t.lib, t.p, nsp, today, keep=True)
        self.assertEqual(n, 2)                                                        # Die drei ??? and TKKG
        self.assertEqual(mixer.episode_order(t.cfg, t.lib, t.lib, t.p, nsp, today), (order, 2))
        state = mixer._load_state()
        del state[t.p["id"]]["albums"]
        mixer.MIX_STATE.write_text(json.dumps(state))
        self.assertEqual(mixer.episode_order(t.cfg, t.lib, t.lib, t.p, nsp, today), (order, 2))


if __name__ == "__main__":
    unittest.main()
