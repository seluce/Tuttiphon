"""Same recording twice (app/fingerprint.py): packing, reading fpcalc output, the comparison on synthetic fingerprints
(copies with bit noise and an offset match; karaoke-like copies, other lengths, silence and different songs do not),
the run with a fake fpcalc (new, unchanged, moved, gone, unreadable, time limit, turned off, not installed) and the
check in Check library. With fpcalc and ffmpeg installed, also with real files: FLAC and its Opus conversion."""
from tests.python import env  # noqa: F401  (before app.*)

import base64
import json
import random
import shutil
import struct
import subprocess
import time
import unittest
from unittest import mock

from app import backup, config, fingerprint, pflege
from app.rules import Library
from tests.python.factory import base_config, song

N = 960   # values of a 2-minute fingerprint (12 sections of 80)


def noisy(values, share, rnd, sections=None):
    """Copy with about `share` of the bits flipped – only in the given sections (of 80 values) if given."""
    out = list(values)
    for i in range(len(out)):
        if sections is not None and i // fingerprint.SECTION not in sections:
            continue
        mask = 0
        for b in range(32):
            if rnd.random() < share:
                mask |= 1 << b
        out[i] ^= mask
    return out


def fake(rnd, n=N):
    return [rnd.getrandbits(32) for _ in range(n)]


def groups_of(items):
    return sorted(sorted(g["ids"]) for g in fingerprint.compare([(sid, d, fingerprint.pack(v)) for sid, d, v in items]))


class PackingTest(unittest.TestCase):
    def test_roundtrip(self):
        rnd = random.Random(1)
        for values in ([], [0], [0xFFFFFFFF], [5, 5, 5, 7], fake(rnd)):
            self.assertEqual(list(fingerprint.unpack(fingerprint.pack(values))), values)

    def test_real_fingerprints_pack_small(self):
        rnd = random.Random(2)
        values, v = [], rnd.getrandbits(32)
        for _ in range(N):   # like Chromaprint: neighbouring values differ in a few bits
            v ^= (1 << rnd.randrange(32)) | (1 << rnd.randrange(32))
            values.append(v)
        raw = len(base64.b64encode(struct.pack(f"<{N}I", *values)))
        self.assertLess(len(fingerprint.pack(values)), raw / 2)   # well under the raw form

    def test_parse(self):
        out = json.dumps({"duration": 245.43, "fingerprint": [1, 4294967295, -1]})
        self.assertEqual(fingerprint.parse(out), (245.43, [1, 4294967295, 4294967295]))   # -signed output too
        for bad in ("", "nicht json", json.dumps({"duration": 3}), json.dumps({"duration": 3, "fingerprint": []}),
                    json.dumps([1, 2])):
            self.assertIsNone(fingerprint.parse(bad), bad)


class CompareTest(unittest.TestCase):
    def setUp(self):
        self.rnd = random.Random(7)

    def test_copies_match_others_do_not(self):
        a, b = fake(self.rnd), fake(self.rnd)
        items = [("flac", 200.0, a), ("opus", 200.3, noisy(a, 0.06, self.rnd)),    # converted: a few bits differ
                 ("best-of", 201.5, [self.rnd.getrandbits(32) for _ in range(9)] + noisy(a, 0.04, self.rnd)[:-9]),
                 ("other", 200.1, b), ("other2", 199.8, noisy(b, 0.45, self.rnd))]  # almost random: another song
        self.assertEqual(groups_of(items), [["best-of", "flac", "opus"]])
        sim = fingerprint.compare([(s, d, fingerprint.pack(v)) for s, d, v in items])[0]["sim"]
        self.assertTrue(0.8 < sim < 1, sim)

    def test_similarity_values(self):
        a = fake(self.rnd)
        big = fingerprint._big
        self.assertEqual(fingerprint.similarity(big(a), N, big(a), N, 0), 1.0)
        self.assertAlmostEqual(fingerprint.similarity(big(a), N, big(noisy(a, 0.05, self.rnd)), N, 0), 0.9, delta=0.02)
        self.assertIsNone(fingerprint.similarity(big(a), N, big(fake(self.rnd)), N, 0))
        shifted = fake(self.rnd, 20) + a
        self.assertEqual(fingerprint.similarity(big(a), N, big(shifted), N + 20, 20), 1.0)   # a[i] ~ shifted[i + 20]
        self.assertIsNone(fingerprint.similarity(big(a[:50]), 50, big(a[:50]), 50, 0))         # overlap too short

    def test_karaoke_does_not_match(self):
        """Same backing track, vocals missing in some sections: low overall, but several sections far apart."""
        a = fake(self.rnd)
        karaoke = noisy(noisy(a, 0.02, self.rnd), 0.35, self.rnd, sections={2, 5, 8})
        big = fingerprint._big
        diff = sum(bin(x ^ y).count("1") for x, y in zip(a, karaoke)) / (32 * N)
        self.assertLess(diff, fingerprint.MAX_BER)                     # overall it would pass …
        self.assertEqual(groups_of([("song", 150.0, a), ("karaoke", 150.0, karaoke)]), [])   # … the sections do not
        one_bad = noisy(noisy(a, 0.02, self.rnd), 0.35, self.rnd, sections={0})   # e.g. another fade-in: one is allowed
        self.assertIsNotNone(fingerprint.similarity(big(a), N, big(one_bad), N, 0))

    def test_length_window_silence_and_short_songs(self):
        a = fake(self.rnd)
        self.assertEqual(groups_of([("a", 200.0, a), ("b", 203.5, a)]), [])          # lengths 3.5 s apart
        self.assertEqual(groups_of([("a", 200.0, a), ("b", 202.9, a)]), [["a", "b"]])
        silence = [627964279] * N
        self.assertEqual(groups_of([("s1", 120.0, silence), ("s2", 120.0, silence)]), [])
        short = fake(self.rnd, 60)
        self.assertEqual(groups_of([("k1", 7.0, short), ("k2", 7.0, short)]), [])

    def test_transitive_groups_and_many_songs(self):
        a = fake(self.rnd)
        items = [("x1", 300.0, a), ("x2", 301.0, noisy(a, 0.05, self.rnd)), ("x3", 302.0, noisy(a, 0.05, self.rnd))]
        items += [(f"r{i}", 100 + i * 0.01, fake(self.rnd, 400)) for i in range(400)]   # same lengths, other songs
        self.assertEqual(groups_of(items), [["x1", "x2", "x3"]])

    def test_stop(self):
        self.assertIsNone(fingerprint.compare([("a", 1.0, fingerprint.pack([1] * 100))], stop=lambda: True))


class FakeFpcalc:
    """Stands in for subprocess.Popen: answers like `fpcalc -raw -json` from a table path -> (duration, values)."""
    table = {}
    calls = []

    def __init__(self, cmd, **_kw):
        self.path = cmd[-1]
        FakeFpcalc.calls.append(self.path)
        hit = FakeFpcalc.table.get(self.path)
        self.returncode = 0 if hit else 2
        self.out = json.dumps({"duration": hit[0], "fingerprint": hit[1]}) if hit else ""

    def communicate(self, timeout=None):
        return self.out, "" if self.returncode == 0 else "ERROR: Could not open the input file"

    def poll(self):
        return self.returncode

    def kill(self):
        pass


class RunTest(unittest.TestCase):
    def setUp(self):
        for f in (fingerprint.STATE_FILE, fingerprint.MATCH_FILE):
            f.unlink(missing_ok=True)
            self.addCleanup(f.unlink, missing_ok=True)
        rnd = random.Random(3)
        self.a, self.b = fake(rnd), fake(rnd)
        music = str(env.MUSIC)
        FakeFpcalc.table = {f"{music}/A/a.flac": (200.0, self.a), f"{music}/A/a.opus": (200.2, noisy(self.a, 0.05, rnd)),
                            f"{music}/B/b.opus": (180.0, self.b), f"{music}/B/moved.opus": (180.0, self.b)}
        FakeFpcalc.calls = []
        self.paths = {"s1": "A/a.flac", "s2": "A/a.opus", "s3": "B/b.opus", "s4": "C/broken.opus"}
        self.songs = [song("s1", title="Lied", album="A", duration=200), song("s2", title="Lied", album="A", duration=200),
                      song("s3", title="Anderes", album="B", duration=180), song("s4", title="Kaputt", album="C")]
        self.songs[0]["suffix"] = "flac"
        self.cfg = base_config()
        for p in (mock.patch.object(fingerprint, "tool", return_value="/usr/bin/fpcalc"),
                  mock.patch.object(fingerprint.subprocess, "Popen", FakeFpcalc),
                  mock.patch.object(fingerprint.time, "sleep")):
            p.start()
            self.addCleanup(p.stop)

    def lib(self):
        lib = Library(self.songs)
        lib.path_loader = lambda: (dict(self.paths), {})
        return lib

    def run_once(self, **kw):
        lines = []
        out = fingerprint.run(self.cfg, self.lib(), log=lines.append, budget=0, **kw)
        return out, lines

    def test_run_compare_and_keep(self):
        self.assertEqual(fingerprint.pending(self.cfg, self.lib()), 4)
        out, lines = self.run_once()
        self.assertEqual((out["fingerprinted"], out["errors"], out["groups"]), (3, 1, 1))
        self.assertEqual(FakeFpcalc.calls.count(f"{env.MUSIC}/C/broken.opus"), 3)   # tried a few times (NAS)
        m = fingerprint.load_matches()
        self.assertEqual(m["groups"][0]["ids"], ["s1", "s2"])
        self.assertEqual(m["paths"], {"s1": "A/a.flac", "s2": "A/a.opus"})
        self.assertEqual((m["songs"], m["errors"]), (3, 1))
        state = fingerprint.load()
        self.assertEqual(state["songs"]["s3"][0], 180.0)
        self.assertEqual(list(fingerprint.unpack(state["songs"]["s3"][1])), self.b)
        self.assertEqual(state["songs"]["s3"][2], "B/b.opus")
        self.assertTrue(any("1 recording is there more than once" in x for x in lines), lines)

        FakeFpcalc.calls = []   # nothing new: no fpcalc, the broken file waits 30 days, the large file stays as it is
        before = fingerprint.STATE_FILE.stat().st_mtime_ns
        out, _ = self.run_once()
        self.assertEqual((out["fingerprinted"], out["errors"], FakeFpcalc.calls), (0, 0, []))
        self.assertEqual(fingerprint.STATE_FILE.stat().st_mtime_ns, before)
        self.assertEqual(fingerprint.pending(self.cfg, self.lib()), 0)

        self.paths["s3"] = "B/moved.opus"   # moved: fingerprinted again
        del self.paths["s2"]                # gone: forgotten, the group dissolves
        self.songs = [s for s in self.songs if s["id"] != "s2"]
        out, _ = self.run_once()
        self.assertEqual((out["fingerprinted"], out["groups"]), (1, 0))
        self.assertEqual(FakeFpcalc.calls, [f"{env.MUSIC}/B/moved.opus"])
        self.assertNotIn("s2", fingerprint.load()["songs"])
        self.assertEqual(fingerprint.load_matches()["groups"], [])

    def test_partial_song_list_keeps_the_fingerprints(self):
        self.run_once()
        self.assertEqual(sorted(fingerprint.load()["songs"]), ["s1", "s2", "s3"])
        full = list(self.songs)
        self.songs = full[:1]   # Navidrome delivered only part of the list
        with mock.patch.object(fingerprint, "FEW_GONE", 0):
            self.run_once()
            state = fingerprint.load()
            self.assertEqual(sorted(state["songs"]), ["s1", "s2", "s3"])   # nothing thrown away
            self.assertEqual(sorted(state["missing"]), ["s2", "s3", "s4"])
            self.songs = full   # back again: nothing to do, nothing missing any more
            FakeFpcalc.calls = []
            out, _ = self.run_once()
            self.assertEqual((out["fingerprinted"], FakeFpcalc.calls), (0, []))
            self.assertNotIn("missing", fingerprint.load())
            self.songs = full[:1]
            self.run_once()
            later = time.time() + (fingerprint.GONE_DAYS + 1) * 86400
            with mock.patch.object(fingerprint.time, "time", return_value=later):   # missing for more than a week
                self.run_once()
        self.assertEqual(sorted(fingerprint.load()["songs"]), ["s1"])

    def test_nothing_due_does_not_read_the_large_file(self):
        self.run_once()
        real = fingerprint.read_text
        reads = []

        def counting(path, *a, **kw):
            reads.append(path)
            return real(path, *a, **kw)
        with mock.patch.object(fingerprint, "read_text", side_effect=counting):
            out, lines = self.run_once()
            self.assertEqual(fingerprint.pending(self.cfg, self.lib()), 0)
            self.assertNotIn(fingerprint.STATE_FILE, reads)
            self.assertEqual((out["fingerprinted"], out["groups"]), (0, 1))
            self.assertTrue(any("3 songs done, 0 pending" in x for x in lines), lines)
            later = time.time() + (fingerprint.RETRY_DAYS + 1) * 86400   # the broken file is due again
            with mock.patch.object(fingerprint.time, "time", return_value=later):
                self.assertEqual(fingerprint.pending(self.cfg, self.lib()), 1)
            self.assertIn(fingerprint.STATE_FILE, reads)
            reads.clear()
            self.paths["s3"] = "B/moved.opus"   # the song list changed: the large file is read again
            out, _ = self.run_once()
            self.assertIn(fingerprint.STATE_FILE, reads)
            self.assertEqual(out["fingerprinted"], 1)

    def test_time_limit_and_cancel(self):
        out, _ = self.run_once(until=time.time() - 1)
        self.assertEqual((out["fingerprinted"], out["later"], FakeFpcalc.calls), (0, 4, []))
        out = fingerprint.run(self.cfg, self.lib(), log=lambda *_: None, budget=0, stop=lambda: True)
        self.assertEqual((out["fingerprinted"], out["errors"], out["later"]), (0, 0, 4))
        self.assertEqual(fingerprint.pending(self.cfg, self.lib()), 4)   # nothing counted as broken

    def test_off_or_not_installed(self):
        self.cfg["settings"]["analysis"]["fingerprints"] = False
        self.assertEqual(self.run_once()[0]["fingerprinted"], 0)
        self.assertEqual(fingerprint.pending(self.cfg, self.lib()), 0)
        self.cfg["settings"]["analysis"]["fingerprints"] = True
        with mock.patch.object(fingerprint, "tool", return_value=None):
            self.assertEqual(self.run_once()[0]["fingerprinted"], 0)
            self.assertEqual(fingerprint.pending(self.cfg, self.lib()), 0)
            st = fingerprint.stats(self.cfg, self.lib())
            self.assertEqual((st["available"], st["why"], st["songs"], st["total"]), (False, "not installed", 0, 4))
        self.assertFalse(fingerprint.STATE_FILE.exists())
        self.assertEqual(FakeFpcalc.calls, [])

    def test_check_library(self):
        lib = self.lib()
        ids = [c["id"] for c in pflege.report(self.cfg, lib)["checks"]]
        self.assertNotIn("aufnahme", ids)   # not compared yet: no check (it would say "all good")
        self.run_once()
        lib = self.lib()
        lib.album_meta = {"al-A": (True, None), "al-B": (False, None)}   # Navidrome knows the covers: that check runs too
        rep = pflege.report(self.cfg, lib)
        self.assertEqual(rep["albums"], 3)
        self.assertEqual(next(c for c in rep["checks"] if c["id"] == "cover")["count"], 1)
        c = next(c for c in rep["checks"] if c["id"] == "aufnahme")
        self.assertEqual((c["count"], c["level"], c["progress"]), (1, "info", {"done": 3, "total": 4}))
        item = c["items"][0]
        self.assertEqual(item["title"], "Lied")
        self.assertEqual(item["detail"], "FLAC and OPUS · 2×")
        self.assertEqual([(x["id"], x["format"], x["path"]) for x in item["copies"]],
                         [("s1", "FLAC", "A/a.flac"), ("s2", "OPUS", "A/a.opus")])
        self.assertGreater(item["similarity"], 0.8)
        self.assertEqual(rep["fingerprints"]["groups"], 1)

    def test_setting_and_backup(self):
        self.assertIs(config.default_config()["settings"]["analysis"]["fingerprints"], True)
        cfg = base_config()
        cfg["settings"]["analysis"]["fingerprints"] = "ja"
        with self.assertRaises(ValueError):
            config.validate_config(cfg)
        self.assertTrue(backup.SKIP_NAMES.search("fingerprints.json"))
        self.assertFalse(backup.SKIP_NAMES.search("fingerprint_matches.json"))   # small – stays in the backup


@unittest.skipUnless(shutil.which("fpcalc") and shutil.which("ffmpeg"), "fpcalc or ffmpeg missing")
class RealFilesTest(unittest.TestCase):
    """A FLAC file and its Opus conversion are the same recording; a different melody is not."""

    def make(self, path, notes, codec):
        expr = "+".join(f"between(mod(t,4),{k * 0.5},{k * 0.5 + 0.5})*sin(2*PI*{f}*t)" for k, f in enumerate(notes))
        subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-f", "lavfi", "-i",
                        f"aevalsrc='0.4*({expr})':s=44100:d=40", *codec, str(path)], check=True)
        return path

    def test_conversion_matches(self):
        d = env.ROOT / "fp-real"
        d.mkdir(exist_ok=True)
        self.addCleanup(shutil.rmtree, d, True)
        melody, other = [262, 330, 392, 523, 440, 349, 294, 247], [220, 247, 262, 294, 330, 349, 392, 440]
        flac = self.make(d / "a.flac", melody, ["-c:a", "flac"])
        opus = self.make(d / "a.opus", melody, ["-c:a", "libopus", "-b:a", "96k"])
        diff = self.make(d / "b.flac", other, ["-c:a", "flac"])
        items = []
        for name, path in (("flac", flac), ("opus", opus), ("other", diff)):
            dur, values = fingerprint.measure(path)
            items.append((name, dur, fingerprint.pack(values)))
        self.assertEqual(sorted(sorted(g["ids"]) for g in fingerprint.compare(items)), [["flac", "opus"]])


if __name__ == "__main__":
    unittest.main()
