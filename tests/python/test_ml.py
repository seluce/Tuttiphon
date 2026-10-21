"""app/ml.py (AI sound analysis) without Essentia: availability, fusing with our own measurement, state
(state/ml.json), pending songs and the run with a mock analysis process (FAKE_WORKER instead of ml_worker.py).

Essentia is deliberately not installed in the test environment; where the package matters,
importlib.util.find_spec is replaced – so the tests do not depend on what is installed."""
from tests.python import env  # noqa: F401  (before app.*)

import importlib.util
import itertools
import json
import os
import shutil
import signal
import threading
import time
import unittest
from unittest import mock

from app import audio, classify, config, lastfm, ml, ml_worker, similar
from app.ml_worker import FILES
from tests.python.factory import base_config, iso_days_ago, song

TMP = env.ROOT / "ml-test"

# Mock of app/ml_worker.py: first {"ready": 1}, then one answer per line. Behaviour from <script>.json:
#   fail: song IDs answered with {"error": …}, crash_after: exit on the next job after this many answers,
#   fatal: {"fatal": …} instead of "ready", keys: the features (ml.KEYS), log: file every job is written to,
#   sv: the sound vector sent along (base64), nosv: song IDs answered without one, hang: seconds before "ready",
#   flaky: song IDs answered with an error the first time only
FAKE_WORKER = r'''
import json, sys, time
conf = json.load(open(__file__ + ".json", encoding="utf-8"))
time.sleep(conf.get("hang", 0))
flaky = set(conf.get("flaky", []))

def send(obj):
    sys.stdout.write(json.dumps(obj) + "\n")
    sys.stdout.flush()

if conf.get("fatal"):
    send({"fatal": conf["fatal"]})
    sys.exit(0)
send({"ready": 1})
answered = 0
for line in sys.stdin:
    job = json.loads(line)
    with open(conf["log"], "a", encoding="utf-8") as f:
        f.write(json.dumps(job) + "\n")
    if conf.get("crash_after") is not None and answered >= conf["crash_after"]:
        sys.exit(3)
    if job["id"] in conf.get("fail", []) or job["id"] in flaky:
        flaky.discard(job["id"])
        send({"id": job["id"], "error": "x"})
    else:
        answer = {"id": job["id"], "ml": {"m": {k: 0.25 for k in conf["keys"]}, "g": {"Rock---Power Metal": 0.7},
                                          "t": {"calm": 0.3}}}
        if conf.get("sv") and job["id"] not in conf.get("nosv", []):
            answer["sv"] = conf["sv"]
        send(answer)
    answered += 1
'''

# Raw measurement of our own sound analysis (audio.analyse_file) – derive() turns it into the features
RAW = {"v": audio.VERSION, "depth": "standard", "bpm": 120.0, "beat": 0.7, "loud": -10.0, "dyn": 12.0,
       "cent": 1800, "flat": 0.2, "flux": 60.0}

_mtime = [1_700_000_000 * 10 ** 9]


def write_json(path, data):
    """Write the file and set a modification time never used before – this way the caches (file stamp from
    mtime_ns and size) see every change, no matter how coarse the file system's timestamps are."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")
    _mtime[0] += 10 ** 9
    os.utime(path, ns=(_mtime[0], _mtime[0]))


def values(**over):
    """AI values as a dict (as in state/ml.json), default 0.5."""
    v = {k: 0.5 for k in ml.KEYS}
    v.update(over)
    return v


def mtuple(**over):
    """AI values as a tuple in the order of ml.KEYS (like ml.features())."""
    v = values(**over)
    return tuple(v[k] for k in ml.KEYS)


def own(**over):
    """Our own measurement (result of audio.derive)."""
    f = {"bpm": 110.0, "beat": 0.6, "energy": 0.5, "dance": 0.5, "bright": 0.5, "rough": 0.2, "arousal": 0.5,
         "valence": 0.5}
    f.update(over)
    return f


class FakeLib:
    """Song list with main artist and real file path (paths: song ID -> path, missing = not found)."""

    def __init__(self, songs, paths=None):
        self.songs = songs
        self.paths = {s["id"]: s["path"] for s in songs} if paths is None else paths

    def _main_artist(self, s):
        return s["artist"]

    def real_path(self, i):
        return self.paths.get(self.songs[i]["id"])


VECTOR = similar.encode([((k * 37) % 23) - 11 for k in range(similar.DIM)])   # any valid sound vector


def reset_caches():
    audio._cache.update(stamp=None, songs={})
    ml._cache.clear()
    ml._cache.update(stamp=None, songs={}, styles={}, labels={}, tempo={}, keys={}, instr={}, scores={}, themes={})
    similar._store.update(stamp=None, ids=frozenset(), rows={}, mean=None)
    similar._indexes.clear()
    classify._memo.clear()


_real_find_spec = importlib.util.find_spec


def spec_without_essentia(name, *args, **kwargs):
    return None if name == "essentia" else _real_find_spec(name, *args, **kwargs)


def spec_with_essentia(name, *args, **kwargs):   # only for available(): nothing is imported
    return object() if name == "essentia" else _real_find_spec(name, *args, **kwargs)


class MlTest(unittest.TestCase):
    def setUp(self):
        for path in (ml.STATE_FILE, audio.STATE_FILE, similar.STATE_FILE):
            self.assertIn(env.ROOT, path.parents)   # never the real data
        self.clean()
        self.addCleanup(self.clean)
        TMP.mkdir(parents=True)
        self.cfg = base_config()
        self.logs = []

    @staticmethod
    def clean():
        ml.STATE_FILE.unlink(missing_ok=True)
        audio.STATE_FILE.unlink(missing_ok=True)
        similar.STATE_FILE.unlink(missing_ok=True)
        for broken in similar.STATE_FILE.parent.glob("sound_vectors.defekt-*.json"):
            broken.unlink()
        shutil.rmtree(TMP, ignore_errors=True)
        reset_caches()

    def write_audio(self, ids, extra=None):
        songs = {sid: {**RAW, "path": f"x/{sid}.opus"} for sid in ids}
        songs.update(extra or {})
        write_json(audio.STATE_FILE, {"songs": songs})

    def write_ml(self, songs, **top):
        write_json(ml.STATE_FILE, {"v": ml.VERSION, "songs": songs, **top})

    def write_vectors(self, ids):
        write_json(similar.STATE_FILE, {"v": similar.VERSION, "dim": similar.DIM, "songs": {sid: VECTOR for sid in ids}})

    def saved(self):
        return json.loads(ml.STATE_FILE.read_text())


# ---------------------------------------------------------------------------- Availability

@env.german   # checks the German output of existing installations
class TestAvailable(MlTest):
    def test_without_essentia(self):
        with mock.patch.object(importlib.util, "find_spec", side_effect=spec_without_essentia):
            ok, why = ml.available()
        self.assertFalse(ok)
        self.assertIn("Essentia", why)

    def test_models_missing(self):
        models = TMP / "models"
        models.mkdir()
        with mock.patch.object(importlib.util, "find_spec", side_effect=spec_with_essentia), \
             mock.patch.object(ml, "MODELS_DIR", models):
            ok, why = ml.available()
            self.assertFalse(ok)
            self.assertIn("Modelle fehlen", why)
            self.assertIn(f"({len(FILES)} Dateien)", why)
            for name in list(FILES)[1:]:
                (models / name).write_bytes(b"")
            ok, why = ml.available()
            self.assertFalse(ok)
            self.assertIn("(1 Dateien)", why)

    def test_ready_with_all_models(self):
        models = TMP / "models"
        models.mkdir()
        for name in FILES:
            (models / name).write_bytes(b"")
        with mock.patch.object(importlib.util, "find_spec", side_effect=spec_with_essentia), \
             mock.patch.object(ml, "MODELS_DIR", models):
            self.assertEqual(ml.available(), (True, ""))


# ---------------------------------------------------------------------------- Fusing

class TestFuse(unittest.TestCase):
    OUT = ("valence", "arousal", "dance", "inst", "acoustic", "electronic")

    def test_values_stay_between_0_and_1(self):
        for combo in itertools.product((0.0, 1.0), repeat=len(ml.KEYS)):
            for level in (0.0, 1.0):
                f = own(valence=level, arousal=level, dance=level)
                for tv in (None, 0.0, 1.0):
                    fused = ml.fuse(f, combo, tv)
                    for key in self.OUT:
                        self.assertTrue(0 <= fused[key] <= 1, (key, combo, level, tv, fused[key]))

    def test_happy_party_song(self):
        fused = ml.fuse(own(valence=0.3), mtuple(happy=1.0, sad=0.0, party=1.0))
        self.assertGreater(fused["valence"], 0.75)
        self.assertIn("froh", audio.moods(fused))

    def test_sad_relaxed_song(self):
        fused = ml.fuse(own(), mtuple(happy=0.0, sad=1.0, relaxed=1.0, aggressive=0.0, party=0.0))
        neutral = ml.fuse(own(), mtuple())
        self.assertLess(fused["valence"], 0.2)
        self.assertLess(fused["arousal"], 0.35)
        self.assertLess(fused["valence"], neutral["valence"])
        self.assertLess(fused["arousal"], neutral["arousal"])

    def test_lastfm_mood_counts(self):
        f, m = own(), mtuple()
        self.assertAlmostEqual(ml.fuse(f, m)["valence"], 0.5)
        self.assertAlmostEqual(ml.fuse(f, m, 1.0)["valence"], 0.625)    # (0.6·0.5 + 0.15·0.5 + 0.25·1) / 1
        self.assertAlmostEqual(ml.fuse(f, m, 0.0)["valence"], 0.375)
        sad = mtuple(happy=0.1, sad=0.9)
        self.assertLess(ml.fuse(f, sad, 0.0)["valence"], ml.fuse(f, sad)["valence"])
        self.assertLess(ml.fuse(f, sad)["valence"], ml.fuse(f, sad, 1.0)["valence"])

    def test_takes_over_voice_acoustic_and_keeps_own_measurement(self):
        f = own(bpm=132.0, energy=0.8, dance=0.2)
        before = dict(f)
        fused = ml.fuse(f, mtuple(voice=0.3, acoustic=0.9, electronic=0.05, dance=0.8))
        self.assertEqual(f, before)                         # our own measurement stays unchanged
        self.assertEqual(fused["inst"], 0.7)
        self.assertEqual((fused["acoustic"], fused["electronic"]), (0.9, 0.05))
        self.assertEqual(fused["vsrc"], "ml")
        self.assertAlmostEqual(fused["dance"], 0.5)          # mean of measurement and AI
        self.assertEqual((fused["bpm"], fused["energy"], fused["beat"]), (132.0, 0.8, 0.6))


class TestMoods(unittest.TestCase):
    def moods(self, **m):
        return audio.moods(ml.fuse(own(), mtuple(**m)))

    def test_instrumental(self):
        self.assertIn("instrumental", self.moods(voice=0.2))     # inst 0.8
        self.assertIn("instrumental", self.moods(voice=0.0))
        self.assertNotIn("instrumental", self.moods(voice=0.21))
        self.assertNotIn("instrumental", audio.moods(own()))      # never without AI

    def test_acoustic(self):
        self.assertIn("akustisch", self.moods(acoustic=0.75, electronic=0.39))
        self.assertNotIn("akustisch", self.moods(acoustic=0.74, electronic=0.0))
        self.assertNotIn("akustisch", self.moods(acoustic=0.9, electronic=0.4))
        self.assertNotIn("akustisch", audio.moods(own()))

    def test_melancholic_with_ml_source(self):
        f = own(valence=0.2, arousal=0.3)
        self.assertNotIn("melancholisch", audio.moods(f))        # sound estimate only: not certain enough
        fused = ml.fuse(f, mtuple(happy=0.0, sad=1.0, relaxed=0.8, aggressive=0.1, party=0.1))
        self.assertEqual(fused["vsrc"], "ml")
        self.assertIn("melancholisch", audio.moods(fused))


# ---------------------------------------------------------------------------- State

class TestFeaturesAndStyles(MlTest):
    def setUp(self):
        super().setUp()
        self.lib = FakeLib([song("s1", artist="Band A"), song("s2", artist="Band A"), song("s3", artist="Band A"),
                            song("s4", artist="Band C"), song("s5", artist="Band B"), song("s6", artist="Band B"),
                            song("s7", artist="Band C"), song("s8", artist="Band D"), song("nicht", artist="Band E")])
        many = {f"Rock---Stil {k}": 1.0 - 0.05 * k for k in range(10)}
        self.write_ml({
            "s1": {"v": 1, "path": "a/s1.opus", "depth": "standard", "m": values(happy=0.9),
                   "g": {"Rock---Power Metal": 0.6, "Rock---Heavy Metal": 0.3, "Electronic---Synth-pop": 0.05},
                   "t": {"party": 0.2}},
            "s2": {"v": 1, "path": "a/s2.opus", "depth": "standard", "m": {"happy": 0.1},
                   "g": {"Rock---Power Metal": 0.4, "Rock---Heavy Metal": 0.5}},
            "s3": {"v": 1, "path": "a/s3.opus", "depth": "standard", "error": True, "at": 1},
            "s4": {"v": 1, "path": "c/s4.opus", "error": True, "m": values(), "g": {"Pop---Disco": 1.0}},
            "s5": {"v": 1, "path": "b/s5.opus", "m": values(), "g": {"Folk, World, & Country---Folk": 0.3,
                                                                     "Rock---Folk Rock": 0.25, "Pop---Schlager": 0.02}},
            "s6": {"v": 1, "path": "b/s6.opus", "m": values(), "g": {"Pop---Folk": 0.2, "Ambient": 0.1}},
            "s7": {"v": 1, "path": "c/s7.opus", "m": values(), "g": {}},
            "s8": {"v": 1, "path": "d/s8.opus", "m": values(), "g": many},
            "ohne-m": {"v": 1, "path": "x.opus", "g": {"Rock---Punk": 1.0}},
        })

    def test_features(self):
        feats = ml.features()
        self.assertEqual(set(feats), {"s1", "s2", "s5", "s6", "s7", "s8"})   # not errors and entries without values
        self.assertEqual(feats["s1"], mtuple(happy=0.9))
        self.assertEqual(feats["s2"], mtuple(happy=0.1))                      # missing values: 0.5
        self.assertIsNotNone(ml.stamp())

    def test_artist_styles(self):
        styles = ml.artist_styles(self.lib)
        self.assertEqual(styles["Band A"], {"power metal": 1.0, "heavy metal": 0.8})      # Synth-pop < 15 % is dropped
        self.assertEqual(styles["Band B"], {"folk": 1.0, "folk rock": 0.5, "ambient": 0.2})   # folk from two genres
        self.assertEqual(list(styles["Band D"]), [f"stil {k}" for k in range(8)])          # at most 8 styles
        self.assertEqual(styles["Band D"]["stil 0"], 1)
        self.assertNotIn("Band C", styles)     # only errors and empty styles
        self.assertNotIn("Band E", styles)     # not analysed
        for artist, st in styles.items():
            self.assertEqual(max(st.values()), 1, artist)
            self.assertTrue(all(k == k.lower() and "---" not in k for k in st), artist)
            self.assertTrue(all(x >= 0.15 for x in st.values()), artist)

    def test_artist_styles_memo_and_refresh(self):
        first = ml.artist_styles(self.lib)
        self.assertIs(ml.artist_styles(self.lib), first)
        self.write_ml({"s1": {"v": 1, "path": "a/s1.opus", "m": values(happy=0.2), "g": {"Pop---Schlager": 0.9}}})
        self.assertEqual(ml.features(), {"s1": mtuple(happy=0.2)})
        self.assertEqual(ml.artist_styles(self.lib), {"Band A": {"schlager": 1.0}})

    def test_without_state(self):
        ml.STATE_FILE.unlink()
        self.assertEqual(ml.features(), {})
        self.assertIsNone(ml.stamp())
        self.assertEqual(ml.artist_styles(FakeLib([song("s1")])), {})


# ---------------------------------------------------------------------------- Pending songs

class TestTodo(MlTest):
    def setUp(self):
        super().setUp()
        songs = [song("a", created=iso_days_ago(10)), song("b", created=iso_days_ago(1)),
                 song("c", created=iso_days_ago(5)), song("d", created=iso_days_ago(20)),
                 song("kaputt", created=iso_days_ago(0)), song("ungemessen", created=iso_days_ago(0)),
                 song("ohne-pfad", created=iso_days_ago(0))]
        paths = {s["id"]: f"Band/Album/{s['id']}.opus" for s in songs if s["id"] != "ohne-pfad"}
        self.lib = FakeLib(songs, paths)
        self.write_audio(["a", "b", "c", "d", "ohne-pfad"],
                         {"kaputt": {"v": audio.VERSION, "path": "x/kaputt.opus", "error": True, "t": 1}})

    def ids(self, todo):
        return [self.lib.songs[i]["id"] for _, i, _ in todo]

    def done(self, sid, **over):
        return {"v": ml.VERSION, "path": f"Band/Album/{sid}.opus", "depth": "standard", "m": values(), **over}

    def test_only_measured_songs_newest_first(self):
        todo = ml._todo(self.lib, {}, "standard", False)
        self.assertEqual(self.ids(todo), ["b", "c", "a", "d"])
        self.assertEqual([rel for _, _, rel in todo], [f"Band/Album/{x}.opus" for x in "bcad"])

    def test_done_songs_are_left_out(self):
        songs = {"a": self.done("a"), "c": self.done("c", depth="gruendlich")}
        self.assertEqual(self.ids(ml._todo(self.lib, songs, "standard", False)), ["b", "d"])
        # all again – the songs the AI has never heard first
        self.assertEqual(self.ids(ml._todo(self.lib, songs, "standard", True)), ["b", "d", "c", "a"])

    def test_never_heard_songs_before_new_version(self):
        songs = {"b": self.done("b", v=ml.VERSION - 1), "c": self.done("c", v=ml.VERSION - 1)}   # e.g. after an update
        self.assertEqual(self.ids(ml._todo(self.lib, songs, "standard", False)), ["a", "d", "b", "c"])

    def test_missing_sound_vector_is_due_again(self):
        songs = {x: self.done(x) for x in "abcd"}
        songs["d"]["nosv"] = 1                         # the analysis had no usable sound: not again and again
        self.assertEqual(self.ids(ml._todo(self.lib, songs, "standard", False)), [])            # not checked
        self.assertEqual(self.ids(ml._todo(self.lib, songs, "standard", False, {"a", "c"})), ["b"])

    def test_path_or_version_changed(self):
        songs = {"a": self.done("a", path="Alt/a.opus"), "b": self.done("b", v=ml.VERSION - 1),
                 "c": {k: v for k, v in self.done("c").items() if k != "v"}, "d": self.done("d")}
        self.assertEqual(self.ids(ml._todo(self.lib, songs, "standard", False)), ["b", "c", "a"])

    def test_newer_version_counts_as_current(self):
        # analyzed by a newer Tuttiphon (then went back to an older one): not analyzed again needlessly
        songs = {x: self.done(x) for x in "abcd"}
        songs["b"]["v"] = ml.VERSION + 1
        self.assertEqual(self.ids(ml._todo(self.lib, songs, "standard", False)), [])
        for bad in ("3", True, None):   # not a version number: due again
            songs["b"]["v"] = bad
            self.assertEqual(self.ids(ml._todo(self.lib, songs, "standard", False)), ["b"], bad)

    def test_failed_retry_of_a_good_result_waits_for_retry_days(self):
        now = time.time()
        songs = {x: self.done(x, path="Alt/x.opus") for x in "abcd"}   # all due again (other path)
        songs["a"]["retry"] = int(now - 3600)                              # tried an hour ago: wait
        songs["b"]["retry"] = int(now - (ml.RETRY_DAYS + 1) * 86400)       # long ago: due again
        self.assertEqual(self.ids(ml._todo(self.lib, songs, "standard", False)), ["b", "c", "d"])
        self.assertEqual(self.ids(ml._todo(self.lib, songs, "standard", True)), ["b", "c", "a", "d"])   # all again

    def test_errors_wait_for_retry_days(self):
        now = time.time()
        songs = {"a": self.done("a", error=True, at=int(now - (ml.RETRY_DAYS - 1) * 86400)),
                 "b": self.done("b", error=True, at=int(now - (ml.RETRY_DAYS + 1) * 86400)),
                 "c": self.done("c", error=True),                              # without a timestamp: try again
                 "d": self.done("d", error=True, at=int(now), depth="schnell")}  # error: depth does not matter
        self.assertEqual(self.ids(ml._todo(self.lib, songs, "gruendlich", False)), ["b", "c"])

    def test_deeper_analysis_is_due_again(self):
        songs = {x: self.done(x) for x in "abcd"}
        songs["d"]["depth"] = "gruendlich"
        self.assertEqual(self.ids(ml._todo(self.lib, songs, "schnell", False)), [])
        self.assertEqual(self.ids(ml._todo(self.lib, songs, "standard", False)), [])
        self.assertEqual(self.ids(ml._todo(self.lib, songs, "gruendlich", False)), ["b", "c", "a"])
        del songs["a"]["depth"]                                                # not given: standard
        self.assertEqual(self.ids(ml._todo(self.lib, songs, "standard", False)), [])

    def test_depth_is_at_most_thorough(self):
        an = self.cfg["settings"]["analysis"]
        for depth, expected in (("schnell", "schnell"), ("standard", "standard"), ("gruendlich", "gruendlich"),
                                ("tief", "gruendlich"), ("quatsch", "standard")):
            an["depth"] = depth
            self.assertEqual(ml._depth(self.cfg), expected, depth)
        del self.cfg["settings"]["analysis"]
        self.assertEqual(ml._depth(self.cfg), "standard")

    def test_pending(self):
        with mock.patch.object(importlib.util, "find_spec", side_effect=spec_without_essentia):
            self.assertEqual(ml.pending(self.cfg, self.lib), 0)                 # without Essentia: nothing pending
        with mock.patch.object(ml, "available", return_value=(True, "")):
            self.assertEqual(ml.pending(self.cfg, self.lib), 4)
            self.write_ml({"a": self.done("a"), "b": self.done("b")})
            self.write_vectors(["a", "b"])
            self.assertEqual(ml.pending(self.cfg, self.lib), 2)
            self.write_vectors(["a"])
            self.assertEqual(ml.pending(self.cfg, self.lib), 3)                # b lacks its sound vector
            self.cfg["settings"]["analysis"]["ml"] = False
            self.assertEqual(ml.pending(self.cfg, self.lib), 0)

    def test_pending_with_full_depth_uses_thorough(self):
        self.cfg["settings"]["analysis"]["depth"] = "tief"
        self.write_ml({x: self.done(x, depth="gruendlich") for x in "abcd"})
        self.write_vectors("abcd")
        with mock.patch.object(ml, "available", return_value=(True, "")):
            self.assertEqual(ml.pending(self.cfg, self.lib), 0)                # "gruendlich" suffices for "tief"
            self.write_ml({x: self.done(x) for x in "abcd"})
            self.assertEqual(ml.pending(self.cfg, self.lib), 4)


# ---------------------------------------------------------------------------- Run

@env.german   # checks the German output of existing installations
class TestRun(MlTest):
    def setUp(self):
        super().setUp()
        self.songs = [song(f"s{k}", created=iso_days_ago(k), duration=200 if k % 2 else 60) for k in range(6)]
        self.lib = FakeLib(self.songs, {s["id"]: f"Band/Album/{s['id']}.opus" for s in self.songs})
        self.write_audio([s["id"] for s in self.songs])
        self.models = TMP / "models"
        self.models.mkdir()
        self.worker = TMP / "fake_worker.py"
        self.worker.write_text(FAKE_WORKER, encoding="utf-8")
        self.jobs_file = TMP / "jobs.jsonl"
        self.seen = []
        self.track = mock.Mock(side_effect=lambda proc, running: self.seen.append(proc))
        self.addCleanup(self.close_pipes)

    def close_pipes(self):
        """ml._Worker.close() only closes stdin – close the output pipe of the finished processes here."""
        for proc in self.seen:
            if proc.stdout and not proc.stdout.closed:
                proc.stdout.close()

    def run_ml(self, stop=None, until=None, only=None, **conf):
        (TMP / "fake_worker.py.json").write_text(json.dumps({"keys": list(ml.KEYS), "log": str(self.jobs_file),
                                                             "sv": VECTOR, **conf}))
        with mock.patch.object(ml, "available", return_value=(True, "")), \
             mock.patch.object(ml, "WORKER", self.worker), mock.patch.object(ml, "MODELS_DIR", self.models):
            return ml.run(self.cfg, self.lib, log=self.logs.append, stop=stop, until=until, track=self.track,
                          only=only)

    def jobs(self):
        if not self.jobs_file.exists():
            return []
        return [json.loads(line) for line in self.jobs_file.read_text().splitlines()]

    def procs(self, running):
        return [c.args[0] for c in self.track.call_args_list if c.args[1] is running]

    def assert_processes_ended(self, starts):
        started, closed = self.procs(True), self.procs(False)
        self.assertEqual(len(started), starts)
        self.assertEqual(started, closed)              # every started process was also signed off again
        self.assertEqual(len({id(p) for p in started}), starts)
        for p in started:
            self.assertIsNotNone(p.poll())
            self.assertEqual(p.args[1:], [str(self.worker), str(self.models)])

    def test_without_essentia_nothing_happens(self):
        with mock.patch.object(importlib.util, "find_spec", side_effect=spec_without_essentia), \
             mock.patch.object(ml.subprocess, "Popen", side_effect=AssertionError("no process")):
            out = ml.run(self.cfg, self.lib, log=self.logs.append, track=self.track)
        self.assertEqual(set(out), {"skipped"})
        self.assertIn("Essentia", out["skipped"])
        self.assertFalse(ml.STATE_FILE.exists())
        self.assertEqual(self.logs, [])
        self.track.assert_not_called()

    def test_results_and_errors_are_saved(self):
        with mock.patch.object(ml, "RETRY_PAUSE", 0):
            out = self.run_ml(fail=["s2"])
        self.assertEqual(out, {"analysed": 5, "errors": 1, "later": 0})
        jobs = self.jobs()
        # newest first; the unreadable song is tried ATTEMPTS times (the NAS share is sometimes briefly unreadable)
        self.assertEqual([j["id"] for j in jobs], ["s0", "s1"] + ["s2"] * ml.ATTEMPTS + ["s3", "s4", "s5"])
        jobs = [j for k, j in enumerate(jobs) if j["id"] != "s2" or k == 2]
        music = config.paths(self.cfg)["music"]
        self.assertEqual(jobs[1]["path"], str(music / "Band/Album/s1.opus"))
        self.assertEqual(jobs[1]["segments"], [[70.0, 60]])     # standard: 60 s from the middle
        self.assertIsNone(jobs[0]["segments"])                  # short song: whole
        data = self.saved()
        self.assertEqual(data["v"], ml.VERSION)
        self.assertEqual(data["open"], 0)
        self.assertRegex(data["lastRun"], r"^\d\d\.\d\d\.\d{4} \d\d:\d\d$")
        self.assertEqual(data["songs"]["s1"], {"v": ml.VERSION, "path": "Band/Album/s1.opus", "depth": "standard",
                                               "m": {k: 0.25 for k in ml.KEYS},
                                               "g": {"Rock---Power Metal": 0.7}, "t": {"calm": 0.3}})
        err = data["songs"]["s2"]
        self.assertEqual({k: err[k] for k in ("v", "path", "depth", "error")},
                         {"v": ml.VERSION, "path": "Band/Album/s2.opus", "depth": "standard", "error": True})
        self.assertLessEqual(abs(err["at"] - time.time()), 60)
        self.assertNotIn("m", err)
        self.assertEqual(set(ml.features()), {"s0", "s1", "s3", "s4", "s5"})
        self.assertIn("5 neu analysiert, 1 nicht lesbar", self.logs[-1])
        self.assert_processes_ended(1)
        # the sound vectors land in their own file, not in ml.json
        vectors = json.loads(similar.STATE_FILE.read_text())
        self.assertEqual((vectors["v"], vectors["dim"]), (similar.VERSION, similar.DIM))
        self.assertEqual(vectors["songs"], {sid: VECTOR for sid in ("s0", "s1", "s3", "s4", "s5")})
        self.assertNotIn("sv", data["songs"]["s1"])
        self.assertEqual(similar.stored(), {"s0", "s1", "s3", "s4", "s5"})

    def test_sound_vectors_follow_the_results(self):
        self.write_vectors(["s2", "s4", "weg"])          # s2 becomes unreadable, s4 has no usable sound any more
        out = self.run_ml(fail=["s2"], nosv=["s4"])
        self.assertEqual(out["analysed"], 5)
        vectors = json.loads(similar.STATE_FILE.read_text())["songs"]
        self.assertEqual(set(vectors), {"s0", "s1", "s3", "s5", "weg"})   # songs not analyzed keep theirs
        self.assertEqual(self.saved()["songs"]["s4"]["nosv"], 1)
        self.track.reset_mock()
        with mock.patch.object(ml, "available", return_value=(True, "")):
            self.assertEqual(ml.pending(self.cfg, self.lib), 0)        # s4 is not due again and again

    def test_damaged_sound_vectors_are_set_aside(self):
        similar.STATE_FILE.write_text("{kaputt")
        out = self.run_ml()
        self.assertEqual(out["analysed"], 6)
        broken = list(similar.STATE_FILE.parent.glob("sound_vectors.defekt-*.json"))
        self.assertEqual(len(broken), 1)
        self.assertEqual(broken[0].read_text(), "{kaputt")
        self.assertEqual(len(json.loads(similar.STATE_FILE.read_text())["songs"]), 6)
        self.assertTrue(any("beschädigt" in line for line in self.logs))

    def test_second_run_has_nothing_to_do(self):
        self.run_ml()
        self.track.reset_mock()
        with mock.patch.object(ml, "available", return_value=(True, "")):
            self.assertEqual(ml.pending(self.cfg, self.lib), 0)
        out = self.run_ml()
        self.assertEqual(out, {"analysed": 0, "errors": 0, "later": 0})
        self.assertIn("alles analysiert", self.logs[-1])
        self.track.assert_not_called()                           # no process started

    def test_full_depth_runs_thorough(self):
        self.cfg["settings"]["analysis"]["depth"] = "tief"
        self.songs[1]["duration"] = 300
        out = self.run_ml()
        self.assertEqual(out["analysed"], 6)
        segments = {j["id"]: j["segments"] for j in self.jobs()}
        self.assertEqual(segments["s1"], [[40.0, 40], [130.0, 40], [220.0, 40]])   # 3 × 40 s instead of the whole song
        self.assertEqual({e["depth"] for e in self.saved()["songs"].values()}, {"gruendlich"})

    def test_stop_before_start(self):
        stop = threading.Event()
        stop.set()
        out = self.run_ml(stop=stop)
        self.assertEqual(out, {"analysed": 0, "errors": 0, "later": 6})
        self.assertEqual(self.jobs(), [])
        data = self.saved()
        self.assertEqual((data["songs"], data["open"]), ({}, 6))
        self.assertIn("6 folgen beim nächsten Lauf", self.logs[-1])
        self.assert_processes_ended(1)

    def test_deadline_passed(self):
        out = self.run_ml(until=time.time() - 1)
        self.assertEqual(out, {"analysed": 0, "errors": 0, "later": 6})
        self.assertEqual(self.jobs(), [])

    def test_crashing_worker_is_restarted_then_given_up(self):
        self.songs += [song(f"s{k}", created=iso_days_ago(k)) for k in range(6, 10)]
        self.lib = FakeLib(self.songs, {s["id"]: f"Band/Album/{s['id']}.opus" for s in self.songs})
        self.write_audio([s["id"] for s in self.songs])
        out = self.run_ml(crash_after=1)    # every process manages one song and dies on the next
        self.assertEqual(out, {"analysed": 4, "errors": 4, "later": 2})
        songs = self.saved()["songs"]
        self.assertEqual(sorted(sid for sid, e in songs.items() if e.get("error")), ["s1", "s3", "s5", "s7"])
        self.assertEqual(sorted(sid for sid, e in songs.items() if not e.get("error")), ["s0", "s2", "s4", "s6"])
        self.assertNotIn("s8", songs)
        self.assertEqual(self.saved()["open"], 2)
        self.assertTrue(any("bricht immer wieder ab" in line for line in self.logs))
        self.assert_processes_ended(4)      # restarted 3 ×, gives up after the 4th crash

    def test_hanging_start_is_given_up(self):
        # TensorFlow hangs while loading: the run must end (otherwise the night window and the daily refresh wait)
        started = time.time()
        with mock.patch.object(ml, "START_TIMEOUT", 1):
            out = self.run_ml(hang=60)
        self.assertLess(time.time() - started, 30)
        self.assertEqual(out, {"analysed": 0, "errors": 0, "later": 6})
        self.assertTrue(any("⚠ KI-Klanganalyse" in line and "nicht bereit" in line for line in self.logs), self.logs)
        self.assertEqual(self.saved()["open"], 6)
        self.assert_processes_ended(1)

    def test_cancel_while_the_models_load(self):
        stop = threading.Event()

        def cancel():   # like TaskRunner.cancel(): set the flag, end the tracked processes
            stop.set()
            for proc in self.seen:
                try:
                    os.killpg(proc.pid, signal.SIGTERM)
                except OSError:
                    pass
        timer = threading.Timer(0.5, cancel)
        timer.start()
        self.addCleanup(timer.cancel)
        out = self.run_ml(stop=stop, hang=60)
        self.assertEqual(out["analysed"], 0)
        self.assertTrue(any("abgebrochen, während die Modelle geladen wurden" in line for line in self.logs), self.logs)
        self.assertFalse(any("startet nicht" in line for line in self.logs))
        self.assert_processes_ended(1)

    def test_briefly_unreadable_file_is_tried_again(self):
        with mock.patch.object(ml, "RETRY_PAUSE", 0):
            out = self.run_ml(flaky=["s2"])
        self.assertEqual(out, {"analysed": 6, "errors": 0, "later": 0})
        self.assertEqual([j["id"] for j in self.jobs()].count("s2"), 2)
        self.assertNotIn("error", self.saved()["songs"]["s2"])

    def test_failed_song_keeps_its_good_result(self):
        # analyzed before (older version: due again), now not readable – the old values and vector stay
        old = {"v": ml.VERSION - 1, "path": "Band/Album/s2.opus", "depth": "standard", "m": values(happy=0.9),
               "g": {"Rock---Folk": 0.5}}
        self.write_ml({"s2": old})
        self.write_vectors(["s2"])
        with mock.patch.object(ml, "RETRY_PAUSE", 0):
            out = self.run_ml(fail=["s2"])
        self.assertEqual(out, {"analysed": 5, "errors": 1, "later": 0})
        entry = self.saved()["songs"]["s2"]
        self.assertNotIn("error", entry)
        self.assertEqual({k: entry[k] for k in old}, old)
        self.assertLessEqual(abs(entry["retry"] - time.time()), 60)
        self.assertIn("s2", json.loads(similar.STATE_FILE.read_text())["songs"])
        self.assertEqual(ml.features()["s2"], mtuple(happy=0.9))
        self.track.reset_mock()
        with mock.patch.object(ml, "available", return_value=(True, "")):
            self.assertEqual(ml.pending(self.cfg, self.lib), 0)        # not due again until RETRY_DAYS
        self.assertEqual(ml.stats()["errors"], 0)

    def test_only_the_given_songs(self):
        self.write_ml({}, open=17)
        out = self.run_ml(only={"s1", "s4"})
        self.assertEqual(out, {"analysed": 2, "errors": 0, "later": 0})
        self.assertEqual([j["id"] for j in self.jobs()], ["s1", "s4"])
        self.assertEqual(self.saved()["open"], 17)                      # the backlog stays as it was
        self.assertTrue(any("2 der neuen Songs offen" in line for line in self.logs), self.logs)

    def test_worker_that_does_not_start(self):
        out = self.run_ml(fatal="Modell kaputt")
        self.assertEqual(out, {"analysed": 0, "errors": 0, "later": 6})
        self.assertTrue(any("⚠ KI-Klanganalyse: Modell kaputt" in line for line in self.logs))
        self.assertEqual(self.saved()["open"], 6)
        self.assert_processes_ended(1)


# ---------------------------------------------------------------------------- Interplay with classify

class TestSongFeatures(MlTest):
    def setUp(self):
        super().setUp()
        self.lib = FakeLib([song("mit-ki", artist="Band A"), song("ohne-ki", artist="Band A"),
                            song("ungemessen", artist="Band A")])
        self.write_audio(["mit-ki", "ohne-ki"])
        self.write_ml({"mit-ki": {"v": 1, "path": "x/mit-ki.opus", "depth": "standard",
                                  "m": values(happy=0.9, sad=0.05, voice=0.1), "g": {}}})

    def features(self, lastfm_data):
        classify._memo.clear()
        with mock.patch.object(lastfm, "artist", return_value=lastfm_data) as artist:
            out = classify.song_features(self.lib)
        artist.assert_called_with("Band A")
        return out

    def test_uses_ml_values(self):
        out = self.features(None)
        own_f = audio.features()
        self.assertEqual(set(out), {0, 1})
        self.assertEqual(out[0], ml.fuse(own_f["mit-ki"], ml.features()["mit-ki"], None))
        self.assertEqual((out[0]["vsrc"], out[0]["inst"]), ("ml", 0.9))
        self.assertIn("instrumental", audio.moods(out[0]))
        self.assertEqual(out[1], own_f["ohne-ki"])                # without AI and Last.fm: only our own measurement
        self.assertNotIn("vsrc", out[1])

    def test_lastfm_mood_is_fused_too(self):
        out = self.features({"tags": [["happy", 60], ["sad", 20]]})   # Last.fm mood 0.75
        own_f = audio.features()
        self.assertEqual(out[0], ml.fuse(own_f["mit-ki"], ml.features()["mit-ki"], 0.75))
        self.assertEqual(out[1]["vsrc"], "tags")


# ---------------------------------------------------------------------------- Instruments, key and tempo

class TestKeyTempoInstruments(MlTest):
    def setUp(self):
        super().setUp()
        self.lib = FakeLib([song("klavier", artist="Pianist"), song("rock", artist="Band R"),
                            song("uneinig", artist="Band R"), song("alt", artist="Band R"), song("ohne", artist="X")])
        self.write_audio(["klavier", "rock", "uneinig", "alt", "ohne"],
                         {"ohne": {**RAW, "path": "x/ohne.opus", "bpm": None, "beat": 0}})
        self.write_ml({
            "klavier": {"v": ml.VERSION, "path": "x", "m": values(), "k": "Ab minor", "ks": 0.9, "b": 79.8, "bc": 1.0,
                        "i": {"piano": 0.85, "guitar": 0.05, "unbekannt": 0.5}},
            "rock": {"v": ml.VERSION, "path": "x", "m": values(), "k": "D minor", "ks": 0.3, "b": 105.6, "bc": 0.67,
                     "i": {"drums": 0.7, "electricguitar": 0.66, "bass": 0.6}},
            "uneinig": {"v": ml.VERSION, "path": "x", "m": values(), "b": 150.0, "bc": 0.5, "k": "H moll", "ks": 0.9},
            "alt": {"v": 1, "path": "x", "m": values()},                     # analyzed before VERSION 2
            "ohne": {"v": ml.VERSION, "path": "x", "m": values(), "b": 92.0, "bc": 0.5},
        })

    def test_camelot_wheel(self):
        for key, code in (("C major", "8B"), ("A minor", "8A"), ("G major", "9B"), ("E minor", "9A"),
                          ("F major", "7B"), ("D minor", "7A"), ("F# minor", "11A"), ("C# minor", "12A"),
                          ("Ab minor", "1A"), ("G# minor", "1A"), ("Eb minor", "2A"), ("B major", "1B"),
                          ("Bb minor", "3A"), ("Ab major", "4B"), ("E major", "12B")):
            self.assertEqual(ml.camelot(key), code, key)
        for bad in ("H moll", "C", "", None, "C dorian"):
            self.assertIsNone(ml.camelot(bad))
        self.assertEqual(ml.key_distance("8A", "8A"), 0)
        self.assertEqual(ml.key_distance("8A", "8B"), 1)      # relative major/minor
        self.assertEqual(ml.key_distance("12A", "1A"), 1)     # around the wheel
        self.assertEqual(ml.key_distance("1B", "12A"), 2)
        self.assertEqual(ml.key_distance("8A", "2B"), 7)

    def test_state_is_read(self):
        self.assertEqual(ml.tempo()["klavier"], (79.8, 1.0))
        self.assertEqual(ml.keys(), {"klavier": ("Ab minor", 0.9), "rock": ("D minor", 0.3)})   # "H moll": unknown
        self.assertEqual(ml.instruments()["klavier"], {"piano": 0.85, "guitar": 0.05})        # unknown class dropped
        self.assertNotIn("alt", ml.instruments())
        self.assertIn("alt", ml.features())               # older entries stay usable

    def test_song_features_take_the_ai_tempo_when_it_agrees(self):
        with mock.patch.object(lastfm, "artist", return_value=None):
            feats = classify.song_features(self.lib)
        own_f = audio.features()
        self.assertEqual((feats[0]["bpm"], feats[0]["bsrc"]), (79.8, "ml"))
        self.assertEqual(feats[0], ml.fuse(audio.with_tempo(own_f["klavier"], 79.8), ml.features()["klavier"])
                         | {"camelot": "1A", "instr": {"piano": 0.85, "guitar": 0.05}})
        self.assertEqual(feats[1]["bpm"], 105.6)                              # 2 of 3 windows agree
        self.assertNotIn("camelot", feats[1])                                 # key too uncertain
        self.assertEqual(feats[2]["bpm"], own_f["uneinig"]["bpm"])            # windows disagree: our own tempo
        self.assertNotIn("bsrc", feats[2])
        self.assertEqual(feats[4]["bpm"], 92.0)                               # no own tempo: the AI's anyway
        self.assertEqual(feats[3]["bpm"], own_f["alt"]["bpm"])

    def test_with_tempo_recomputes_what_depends_on_it(self):
        f = audio.derive(RAW)                                                 # 120 BPM
        slow = audio.with_tempo(f, 60.0)
        self.assertEqual((slow["energy"], slow["bright"], slow["beat"]), (f["energy"], f["bright"], f["beat"]))
        self.assertLess(slow["arousal"], f["arousal"])
        self.assertLess(slow["dance"], f["dance"])                            # outside 90–145 BPM
        same = audio.with_tempo(f, 120.0)
        for k in ("dance", "arousal", "valence"):
            self.assertAlmostEqual(same[k], f[k], delta=0.002)

    def test_instruments_in_sound_filters(self):
        with mock.patch.object(lastfm, "artist", return_value=None):
            feats = classify.song_features(self.lib)
        piano, rock = feats[0], feats[1]
        self.assertTrue(audio.matches(piano, {"instruments": ["piano"]}))
        self.assertFalse(audio.matches(piano, {"instruments": ["guitar"]}))      # 0.05 is noise
        self.assertTrue(audio.matches(rock, {"instruments": ["piano", "electricguitar"]}))   # one of them
        self.assertFalse(audio.matches(feats[3], {"instruments": ["piano"]}))     # without instruments: no
        self.assertFalse(audio.matches(piano, {"instruments": ["piano"], "bpm": [100, 200]}))
        cfg = base_config()
        cfg["stile"].append({"id": "klavier", "name": "Klavier", "sound": {"instruments": ["piano"]}})
        config.validate_config(cfg)
        cfg["stile"][-1]["sound"] = {"instruments": ["dudelsack"]}
        with self.assertRaises(ValueError):
            config.validate_config(cfg)

    def test_song_window_details(self):
        with mock.patch.object(lastfm, "artist", return_value=None):
            info = classify.song_details(self.lib, 0)
        self.assertEqual(info["key"], "Ab minor")
        self.assertEqual((info["camelot"], info["keyStrength"], info["bpmSource"]), ("1A", 0.9, "ai"))
        self.assertEqual([x["id"] for x in info["instruments"]], ["piano", "guitar"])
        self.assertEqual(info["instruments"][0]["label"], "piano")
        with mock.patch.object(lastfm, "artist", return_value=None):
            self.assertEqual(classify.song_details(self.lib, 2)["bpmSource"], "measured")
            self.assertNotIn("key", classify.song_details(self.lib, 3))

    def test_catalog_and_search(self):
        cat = ml.instrument_catalog(self.lib)
        self.assertTrue(cat["available"])
        self.assertEqual(len(cat["instruments"]), 40)
        counts = {x["id"]: x["songs"] for x in cat["instruments"]}
        self.assertEqual((counts["piano"], counts["drums"], counts["guitar"]), (1, 1, 0))
        self.assertEqual(ml.instrument_word("klaviermusik"), ["piano"])
        self.assertEqual(ml.instrument_word("akustikgitarre"), ["acousticguitar", "classicalguitar"])   # longest wins
        self.assertEqual(ml.instrument_word("gitarren")[0], "guitar")
        self.assertIsNone(ml.instrument_word("kinderlieder"))
        for word in ("harpyie", "synthpop", "organic", "drummer"):         # short words: only with fitting endings
            self.assertIsNone(ml.instrument_word(word), word)
        for word, first in (("harps", "harp"), ("geigenmusik", "violin"), ("synthesizer", "synthesizer"),
                            ("orgelmusik", "organ"), ("saxofon", "saxophone")):
            self.assertEqual(ml.instrument_word(word)[0], first, word)
        for word, first in (("guitare", "guitar"), ("chitarra", "guitar"), ("gitaar", "guitar"), ("gitara", "guitar"),
                            ("violon", "violin"), ("violoncelle", "cello"), ("tromba", "trumpet"),
                            ("trombone", "trombone"), ("batterie", "drums"), ("fisarmonica", "accordion")):
            self.assertEqual(ml.instrument_word(word)[0], first, word)   # the other languages of the interface
        for word, theme in (("noël", "christmas"), ("navidad", "christmas"), ("kerstmis", "christmas"),
                            ("kolędy", "christmas"), ("épique", "epic"), ("sombre", "dark"), ("zomer", "summer")):
            self.assertEqual(ml.theme_word(word), [theme], word)
        hits = ml.search_instruments("Klavier", self.lib)
        self.assertEqual([(x["id"], x["count"]) for x in hits], [("piano", 1)])
        self.assertEqual(ml.search_instruments("drums", self.lib)[0]["ids"], ["drums"])
        self.assertEqual(ml.search_instruments("ab", self.lib), [])
        self.assertEqual(len(set(ml.INSTRUMENTS) | {v for ids in ml.INSTRUMENT_WORDS.values() for v in ids}), 40)

    def test_stats(self):
        out = ml.stats()
        self.assertEqual(out["current"], 4)
        self.assertIn(["piano", 1], out["instruments"])


class TestWorkerHelpers(unittest.TestCase):
    """Parts of ml_worker.py that need neither Essentia nor numpy."""

    def test_files_contain_the_instrument_model(self):
        for name in ("mtg_jamendo_instrument-discogs-effnet-1.json", "mtg_jamendo_instrument-discogs-effnet-1.pb"):
            self.assertRegex(FILES[name], r"^[0-9a-f]{64}$")
        self.assertEqual(len(FILES), 29)
        self.assertEqual(ml_worker.TOPS["instruments"][1], "i")

    def test_tempo_consensus(self):
        self.assertEqual(ml_worker.consensus([96.2, 96.1, 140.0]), (96.2, 0.67))
        self.assertEqual(ml_worker.consensus([120.0]), (120.0, 1.0))
        self.assertEqual(ml_worker.consensus([153.1, 93.8]), (153.1, 0.5))   # disagreement: the first one
        self.assertEqual(ml_worker.consensus([0, None, 300]), (None, 0.0))

    def test_projection_is_fixed(self):
        try:
            import numpy  # noqa: F401
        except ImportError:
            self.skipTest("numpy is only in the Docker image")
        a, b = ml_worker.sound_projection(1280), ml_worker.sound_projection(1280)
        self.assertEqual(a.shape, (1280, ml_worker.SOUND_DIM))
        self.assertTrue((a == b).all())
        self.assertEqual(set(a.flatten().tolist()), {-1.0, 1.0})


if __name__ == "__main__":
    unittest.main()
