"""Loudness normalization (ReplayGain): reading measurements, album loudness, tag values – and with real files created
in the test: the values are in there afterwards, the audio is bit-identical, other tags stay, foreign values stay untouched.
The file tests need ffmpeg and mutagen (skipped otherwise)."""
from tests.python import env  # noqa: F401  (before app.*)

import os
import shutil
import subprocess
import unittest
from unittest import mock

from app import config, lautstaerke
from app.rules import Library
from tests.python.factory import base_config, song

SUMMARY = """[Parsed_ebur128_0 @ 0x1] Summary:

  Integrated loudness:
    I:          -9.8 LUFS
    Threshold: -20.0 LUFS

  True peak:
    Peak:        0.8 dBFS
"""
HAVE = bool(shutil.which("ffmpeg")) and lautstaerke.available()[0]


def make(path, freq=440, volume=0.5, fmt="opus", title="Testlied"):
    """Short audio file with a title tag."""
    path.parent.mkdir(parents=True, exist_ok=True)
    codec = {"opus": ["-c:a", "libopus", "-b:a", "64k"], "mp3": ["-c:a", "libmp3lame", "-b:a", "128k"],
             "flac": ["-c:a", "flac"]}[fmt]
    subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-f", "lavfi", "-i", f"sine=frequency={freq}:duration=4",
                    "-af", f"volume={volume}", *codec, "-metadata", f"title={title}", "-metadata", "artist=Band A",
                    str(path)], check=True)
    return path


def audio_md5(path):
    out = subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-i", str(path), "-map", "0:a:0", "-f", "md5", "-"],
                         capture_output=True, text=True, check=True)
    return out.stdout.strip()


class CalculationTest(unittest.TestCase):
    def test_parse(self):
        self.assertEqual(lautstaerke.parse_ebur128(SUMMARY), (-9.8, 0.8))
        self.assertIsNone(lautstaerke.parse_ebur128("nichts"))

    def test_album_and_values(self):
        self.assertAlmostEqual(lautstaerke.album_loudness([(-10, -1, 100), (-10, -3, 300)])[0], -10, places=6)
        loud, peak = lautstaerke.album_loudness([(-6, 0.5, 60), (-12, -2, 60)])
        self.assertTrue(-9 < loud < -7.9)                          # energy mean is closer to the loud song
        self.assertEqual(peak, 0.5)
        v = lautstaerke.tag_values((-9.8, 0.8), (-8.0, 1.2))
        self.assertEqual(v["REPLAYGAIN_TRACK_GAIN"], "-8.20 dB")    # −18 LUFS reference
        self.assertEqual(v["REPLAYGAIN_ALBUM_GAIN"], "-10.00 dB")
        self.assertEqual(v["REPLAYGAIN_TRACK_PEAK"], f"{10 ** (0.8 / 20):.6f}")
        self.assertEqual(lautstaerke.tag_values((-20, -3))["REPLAYGAIN_TRACK_GAIN"], "+2.00 dB")


@unittest.skipUnless(HAVE, "ffmpeg and mutagen are missing")
class FilesTest(unittest.TestCase):
    def setUp(self):
        self.dir = env.MUSIC / "Laut" / "Album"
        shutil.rmtree(self.dir, ignore_errors=True)
        lautstaerke.STATE_FILE.unlink(missing_ok=True)
        self.addCleanup(shutil.rmtree, self.dir, True)
        self.addCleanup(lautstaerke.STATE_FILE.unlink, missing_ok=True)

    def test_write_keeps_audio_and_other_tags(self):
        for fmt in ("opus", "mp3", "flac"):
            path = make(self.dir / f"a.{fmt}", fmt=fmt)
            before = audio_md5(path)
            values = lautstaerke.tag_values((-9.5, -1.0), (-9.0, -0.5))
            self.assertIs(lautstaerke.write_tags(path, values), True, fmt)
            self.assertEqual(audio_md5(path), before, fmt)          # audio unchanged
            got = lautstaerke.read_tags(path)
            self.assertEqual({k: got[k] for k in values}, values, fmt)
            import mutagen
            f = mutagen.File(str(path), easy=True)
            self.assertEqual(f["title"][0], "Testlied", fmt)          # other tags stay
            self.assertEqual(list(self.dir.glob(".*.tmp")), [])       # no temporary file left

    def test_run_measures_writes_and_leaves_foreign_values(self):
        loud = make(self.dir / "01.opus", volume=0.9)
        quiet = make(self.dir / "02.opus", volume=0.1)
        foreign = make(self.dir / "03.opus")
        lautstaerke.write_tags(foreign, {"REPLAYGAIN_TRACK_GAIN": "-3.00 dB", "REPLAYGAIN_TRACK_PEAK": "0.500000"})
        lib = Library([song(f"s{k}", album_id="al-x", duration=4) for k in (1, 2, 3)])
        lib.path_loader = lambda: ({"s1": "Laut/Album/01.opus", "s2": "Laut/Album/02.opus", "s3": "Laut/Album/03.opus"}, {})
        cfg = base_config()
        cfg["settings"]["loudness"] = {"enabled": True}
        with mock.patch("app.opus.music_dir", return_value=env.MUSIC):
            out = lautstaerke.run(cfg, lib, log=lambda *_: None, budget=0)
            self.assertEqual((out["measured"], out["written"], out["skipped"]), (3, 2, 1))
            a, b = lautstaerke.read_tags(loud), lautstaerke.read_tags(quiet)
            ga, gb = (float(x["REPLAYGAIN_TRACK_GAIN"].split()[0]) for x in (a, b))
            self.assertGreater(gb - ga, 15)                           # quiet song is raised clearly
            self.assertEqual(a["REPLAYGAIN_ALBUM_GAIN"], b["REPLAYGAIN_ALBUM_GAIN"])
            self.assertEqual(lautstaerke.read_tags(foreign)["REPLAYGAIN_TRACK_GAIN"], "-3.00 dB")
            again = lautstaerke.run(cfg, lib, log=lambda *_: None, budget=0)
        self.assertEqual((again["measured"], again["written"]), (0, 0))   # nothing twice
        self.assertEqual(lautstaerke.pending(cfg, lib), 0)

    def test_hard_linked_file_stays_as_it_is(self):
        path = make(self.dir / "01.opus")
        seed = env.ROOT / "downloads-01.opus"   # e.g. the torrent program still shares the file Lidarr imported
        os.link(path, seed)
        self.addCleanup(seed.unlink, missing_ok=True)
        before = path.read_bytes()
        res = lautstaerke.write_tags(path, lautstaerke.tag_values((-9.0, -1.0)))
        self.assertIsNot(res, True)
        self.assertEqual((path.read_bytes(), os.stat(path).st_ino), (before, os.stat(seed).st_ino))   # link intact
        lib = Library([song("s1", album_id="al-l", duration=4)])
        lib.path_loader = lambda: ({"s1": "Laut/Album/01.opus"}, {})
        cfg = base_config()
        cfg["settings"]["loudness"] = {"enabled": True}
        lines = []
        with mock.patch("app.opus.music_dir", return_value=env.MUSIC):
            out = lautstaerke.run(cfg, lib, log=lines.append, budget=0)
            self.assertEqual((out["measured"], out["written"], out["linked"], out["errors"]), (1, 0, 1, 0))
            self.assertTrue(any("hard link" in x for x in lines), lines)
            self.assertEqual(path.read_bytes(), before)
            self.assertEqual(lautstaerke.pending(cfg, lib), 0)   # does not make every night analysis due
            seed.unlink()   # shared no longer: the values follow
            out = lautstaerke.run(cfg, lib, log=lambda *_: None, budget=0)
        self.assertEqual((out["written"], out["linked"]), (1, 0))
        self.assertIn("REPLAYGAIN_TRACK_GAIN", lautstaerke.read_tags(path))

    def test_keeps_owner_permissions_and_id3_version(self):
        from mutagen.id3 import ID3
        mp3 = self.dir / "a.mp3"
        mp3.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-f", "lavfi", "-i", "sine=duration=3", "-c:a",
                        "libmp3lame", "-id3v2_version", "3", "-metadata", "title=Alt", str(mp3)], check=True)
        self.assertEqual(ID3(str(mp3)).version[:2], (2, 3))
        os.chmod(mp3, 0o640)
        st = os.stat(mp3)
        self.assertIs(lautstaerke.write_tags(mp3, lautstaerke.tag_values((-9.0, -1.0)), owner="4321:4321"), True)
        tags = ID3(str(mp3))
        self.assertEqual(tags.version[:2], (2, 3))   # some players read only ID3v2.3
        self.assertEqual(str(tags["TIT2"]), "Alt")
        after = os.stat(mp3)
        self.assertEqual((after.st_mode & 0o7777, after.st_uid, after.st_gid), (0o640, st.st_uid, st.st_gid))

    def test_measure_runs_with_low_priority_in_its_own_group(self):
        seen = {}

        class Proc:
            returncode = 0

            def __init__(self, cmd, **kw):
                seen.update(cmd=cmd, **kw)

            def communicate(self, timeout=None):
                return "", SUMMARY
        with mock.patch.object(lautstaerke.subprocess, "Popen", Proc):
            self.assertEqual(lautstaerke.measure("x.flac"), (-9.8, 0.8))
        self.assertTrue(seen["start_new_session"])   # "Cancel" ends the whole group
        if shutil.which("nice"):
            self.assertEqual(seen["cmd"][1:3], ["-n", "19"])

    def test_off_by_default(self):
        cfg = base_config()
        self.assertEqual(lautstaerke.run(cfg, Library([song("a")]), log=lambda *_: None)["measured"], 0)
        with self.assertRaises(ValueError):
            config.validate_config({**cfg, "settings": {**cfg["settings"], "loudness": {"enabled": "ja"}}})


if __name__ == "__main__":
    unittest.main()
