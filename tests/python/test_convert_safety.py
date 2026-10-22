"""Converting keeps the original whenever the new file might not hold the whole song – with real files created in the
test: a FLAC with zeros in the middle, a cut-off WAV, a FLAC with decoding errors; a missing or read-only archive
converts nothing; ALAC → AAC never loses the song; an interrupted move to the archive is finished in the next run; the
archive must lie outside the music folder; tags from WAV/AIFF arrive in AAC; the front cover is embedded into Opus and
cover.jpg is only written for a folder with one album; two originals with the same name are left alone; existing
archive folders keep their permissions. Needs ffmpeg and mutagen."""
from tests.python import env  # noqa: F401  (before app.*)

import base64
import errno
import os
import shutil
import subprocess
import unittest
from pathlib import Path
from unittest import mock

from app import config, opus
from tests.python.factory import base_config

HAVE = bool(shutil.which("ffmpeg")) and opus.mp4_available()


def ffmpeg(*args):
    subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-y", *map(str, args)], check=True)


def tone(path, seconds=3, args=("-c:a", "flac"), meta=None, cover=None, source=None):
    path.parent.mkdir(parents=True, exist_ok=True)
    cmd = ["-f", "lavfi", "-i", source or f"sine=frequency=440:duration={seconds}"]
    if cover:
        cmd += ["-i", cover, "-map", "0:a", "-map", "1:v", "-c:v", "copy", "-disposition:v", "attached_pic"]
    for k, v in (meta or {}).items():
        cmd += ["-metadata", f"{k}={v}"]
    ffmpeg(*cmd, *args, path)
    return path


def image(path, color):
    ffmpeg("-f", "lavfi", "-i", f"color=c={color}:s=64x64", "-frames:v", "1", path)
    return path


def codec(path):
    return subprocess.run(["ffprobe", "-v", "error", "-select_streams", "a:0", "-show_entries", "stream=codec_name",
                           "-of", "csv=p=0", str(path)], capture_output=True, text=True).stdout.strip()


def tree(root):
    return sorted(str(p.relative_to(root)) for p in Path(root).rglob("*") if p.is_file())


@unittest.skipUnless(HAVE, "ffmpeg and mutagen are missing")
class SafetyTest(unittest.TestCase):
    def setUp(self):
        self.music = env.MUSIC / "Sicher"
        self.archive = env.ROOT / "archiv-sicher"
        for d in (self.music, self.archive):
            shutil.rmtree(d, ignore_errors=True)
            self.addCleanup(shutil.rmtree, d, True)
        self.archive.mkdir()
        self.dir = self.music / "Band" / "Album"
        for p in (mock.patch("app.opus.music_dir", return_value=self.music),
                  mock.patch("app.opus.archive_dir", side_effect=lambda *a, **k: self.archive)):
            p.start()
            self.addCleanup(p.stop)
        self.log = []

    def run_opus(self, **op):
        cfg = base_config()
        cfg["settings"]["opus"] = {"enabled": True, "formats": ["flac", "wav", "aiff", "alac"], "minAgeMinutes": 0,
                                   "owner": None, **op}
        return opus.run(cfg, log=self.log.append)

    def text(self):
        return "\n".join(self.log)

    # ------------------------------------------------------------ incomplete or damaged originals (H1)

    def test_flac_with_zeros_in_the_middle_keeps_the_original(self):
        src = tone(self.dir / "01 Lied.flac", source="anoisesrc=d=30:c=pink:a=0.3")
        data = bytearray(src.read_bytes())
        mid = len(data) // 2
        data[mid:mid + 200_000] = bytes(200_000)   # like a download that was never finished (preallocated)
        src.write_bytes(bytes(data))
        res = self.run_opus(original="delete")
        self.assertEqual((res["converted"], res["errors"]), (0, 1), self.log)
        self.assertEqual(tree(self.music), ["Band/Album/01 Lied.flac"])   # no Opus, no .part, the original stays
        self.assertIn("length does not match", self.text())

    def test_cut_off_wav_keeps_the_original(self):
        src = tone(self.dir / "02 Lied.wav", seconds=10, args=("-c:a", "pcm_s16le"))
        self.assertAlmostEqual(opus.declared_length(src), 10, places=2)
        with open(src, "r+b") as f:   # a copy that stopped halfway: the header still says 10 s
            f.truncate(src.stat().st_size // 2)
        self.assertAlmostEqual(opus.declared_length(src), 10, places=2)
        res = self.run_opus(original="archive")
        self.assertEqual((res["converted"], res["errors"]), (0, 1), self.log)
        self.assertEqual(tree(self.music), ["Band/Album/02 Lied.wav"])
        self.assertEqual(tree(self.archive), [])

    def test_decoding_errors_keep_the_original(self):
        src = tone(self.dir / "03 Lied.flac", source="anoisesrc=d=20:c=pink:a=0.3")
        with open(src, "r+b") as f:   # cut off in the middle of a frame: ffmpeg reports errors, but ends with 0
            f.truncate(int(src.stat().st_size * 0.6))
        res = self.run_opus(original="delete")
        self.assertEqual(res["converted"], 0, self.log)
        self.assertTrue(src.exists())
        self.assertFalse(src.with_suffix(".opus").exists())

    def test_complete_files_still_convert(self):
        for name, args in (("a.flac", ("-c:a", "flac")), ("b.wav", ("-c:a", "pcm_s24le")), ("c.aiff", ())):
            tone(self.dir / name, seconds=4.4, args=args)
        res = self.run_opus(original="archive")
        self.assertEqual((res["converted"], res["errors"]), (3, 0), self.log)
        self.assertEqual(tree(self.music), ["Band/Album/a.opus", "Band/Album/b.opus", "Band/Album/c.opus"])
        self.assertEqual(tree(self.archive), ["Band/Album/a.flac", "Band/Album/b.wav", "Band/Album/c.aiff"])
        res = self.run_opus(codec="aac", original="keep", formats=["alac"])   # nothing left
        self.assertEqual(res["converted"], 0)

    def test_declared_length_from_the_header(self):
        for name, args in (("x.flac", ("-c:a", "flac")), ("x.wav", ("-c:a", "pcm_s16le")), ("x.aiff", ()),
                           ("x.wv", ("-c:a", "wavpack"))):
            p = tone(self.dir / name, seconds=2.5, args=args)
            self.assertAlmostEqual(opus.declared_length(p), 2.5, places=2, msg=name)
        self.assertIsNone(opus.declared_length(self.dir / "fehlt.flac"))

    # ------------------------------------------------------------ the archive (H3, L6, M3, L2)

    def test_missing_archive_converts_nothing_and_is_not_created(self):
        tone(self.dir / "01.flac")
        shutil.rmtree(self.archive)
        with self.assertRaises(RuntimeError) as ctx:
            self.run_opus(original="archive")
        self.assertIn("does not exist", str(ctx.exception))
        self.assertFalse(self.archive.exists())   # never the archive folder itself (in the container: not mounted)
        self.assertEqual(tree(self.music), ["Band/Album/01.flac"])
        self.assertEqual(self.run_opus(original="delete")["converted"], 1)   # without the archive it is not needed

    @unittest.skipIf(hasattr(os, "geteuid") and os.geteuid() == 0, "root may write everywhere")
    def test_read_only_archive_converts_nothing(self):
        tone(self.dir / "01.flac")
        os.chmod(self.archive, 0o555)
        self.addCleanup(os.chmod, self.archive, 0o755)
        with self.assertRaises(RuntimeError) as ctx:
            self.run_opus(original="archive")
        self.assertIn("not writable", str(ctx.exception))
        self.assertEqual(tree(self.music), ["Band/Album/01.flac"])   # no Opus twin next to the FLAC

    def test_archive_inside_the_music_folder_is_refused(self):
        tone(self.dir / "01.flac")
        inside = self.music / "Archiv"
        inside.mkdir()
        with mock.patch("app.opus.archive_dir", return_value=inside), self.assertRaises(RuntimeError) as ctx:
            self.run_opus(original="archive")
        self.assertIn("inside", str(ctx.exception))
        self.assertEqual(tree(self.music), ["Band/Album/01.flac"])
        cfg = base_config()
        for paths in ({"archive": "Music/Archiv"}, {"archive": "Music"}, {"music": "Platten", "archive": "Platten/Alt"},
                      {"archive": str(env.MUSIC / "x")}):
            cfg["settings"]["paths"] = paths
            with self.assertRaises(ValueError, msg=paths):
                config.validate_config(cfg)
            self.assertTrue(config.archive_in_music(cfg), paths)
        cfg["settings"]["paths"] = {"archive": "Archiv"}
        config.validate_config(cfg)
        cfg["settings"]["paths"] = {"archive": "Music/Archiv"}   # next to the music folder's parent: inside it
        with self.assertRaises(ValueError):
            config.validate_config(cfg)
        # saved like this before the check existed: other saves keep working (the conversion refuses to run)
        with mock.patch.dict(config._cfg_cache, {"cfg": cfg}):
            config.validate_config(cfg)

    def test_paths_check_reports_an_archive_inside_the_music_folder(self):
        from app import web
        with self.assertRaises(ValueError):
            web.api_paths_check({"archive": "Music/Archiv"})
        info = web.api_paths_check({"archive": "Archiv"})
        self.assertFalse(info["archive"]["insideMusic"])

    def test_existing_archive_folders_keep_their_permissions(self):
        old = self.archive / "Band"
        old.mkdir()
        os.chmod(old, 0o2775)
        tone(self.dir / "01.flac")
        tone(self.music / "Band" / "Neu" / "02.flac")
        self.assertEqual(self.run_opus(original="archive")["converted"], 2, self.log)
        self.assertEqual(os.stat(old).st_mode & 0o7777, 0o2775)   # existing: untouched (setgid, group write)
        self.assertEqual(os.stat(old / "Album").st_mode & 0o777, 0o755)   # created now
        self.assertEqual(tree(self.archive), ["Band/Album/01.flac", "Band/Neu/02.flac"])

    # ------------------------------------------------------------ interrupted or failing moves (M1, M2)

    def test_alac_to_aac_never_loses_the_song(self):
        src = tone(self.dir / "05 Lied.m4a", args=("-c:a", "alac"), meta={"title": "Lied", "artist": "Band"})
        real = os.replace

        def failing(a, b):
            if ".m4a.encode." in str(a):   # the new file into the place of the original
                raise PermissionError(errno.EACCES, "Permission denied")
            return real(a, b)
        with mock.patch("app.opus.os.replace", side_effect=failing):
            res = self.run_opus(codec="aac", original="archive")
        self.assertEqual((res["converted"], res["errors"]), (0, 1), self.log)
        self.assertEqual(codec(src), "alac")   # the original is still where it was …
        self.assertEqual(tree(self.archive), [])   # … and the copy made for the archive was taken back
        self.assertEqual(tree(self.music), ["Band/Album/05 Lied.m4a"])
        res = self.run_opus(codec="aac", original="archive")
        self.assertEqual(res["converted"], 1, self.log)
        self.assertEqual(codec(src), "aac")
        self.assertEqual(codec(self.archive / "Band" / "Album" / "05 Lied.m4a"), "alac")

    def test_interrupted_move_to_another_volume_is_finished_next_time(self):
        src = tone(self.dir / "06 Lied.flac")
        original = src.read_bytes()
        real_unlink = Path.unlink

        def cross_device(a, b):
            raise OSError(errno.EXDEV, "Invalid cross-device link")

        def locked(path, missing_ok=False):
            if path == src:
                raise PermissionError(errno.EACCES, "Permission denied")
            return real_unlink(path, missing_ok=missing_ok)
        with mock.patch("app.opus.os.rename", side_effect=cross_device), mock.patch.object(Path, "unlink", locked), \
                mock.patch("app.opus.time.sleep"):
            res = self.run_opus(original="archive")
        self.assertEqual(res["errors"], 1, self.log)
        self.assertEqual(tree(self.music), ["Band/Album/06 Lied.flac", "Band/Album/06 Lied.opus"])
        self.assertEqual(tree(self.archive), ["Band/Album/06 Lied.flac"])   # copied, but the original stayed
        self.log.clear()
        res = self.run_opus(original="archive")   # next run: the copy in the archive is identical – only remove here
        self.assertEqual((res["converted"], res["errors"]), (1, 0), self.log)
        self.assertEqual(tree(self.music), ["Band/Album/06 Lied.opus"])
        self.assertEqual(tree(self.archive), ["Band/Album/06 Lied.flac"])
        self.assertEqual((self.archive / "Band" / "Album" / "06 Lied.flac").read_bytes(), original)
        self.assertIn("identical", self.text())

    def test_different_file_of_the_same_name_in_the_archive_stays(self):
        tone(self.dir / "07 Lied.flac")
        other = tone(self.archive / "Band" / "Album" / "07 Lied.flac", seconds=5)   # e.g. an earlier edition
        before = other.read_bytes()
        res = self.run_opus(original="archive")
        self.assertEqual(res["converted"], 1, self.log)
        self.assertEqual(other.read_bytes(), before)   # never overwritten
        self.assertEqual(tree(self.archive), ["Band/Album/07 Lied (2).flac", "Band/Album/07 Lied.flac"])

    # ------------------------------------------------------------ tags and covers (M4, M5)

    def test_wav_and_aiff_tags_arrive_in_aac(self):
        tone(self.dir / "wav.wav", args=("-c:a", "pcm_s16le"), meta={"title": "Wav Titel", "artist": "Wav Band",
                                                                     "album": "Wav Album", "track": "3"})
        tone(self.dir / "aiff.aiff", args=(), meta={"title": "Aiff Titel"})   # NAME chunk – mutagen does not read it
        res = self.run_opus(codec="aac", original="keep")
        self.assertEqual(res["converted"], 2, self.log)
        from mutagen.mp4 import MP4
        t = MP4(str(self.dir / "wav.m4a")).tags
        self.assertEqual((t["©nam"], t["©ART"], t["©alb"], t["trkn"]), (["Wav Titel"], ["Wav Band"], ["Wav Album"], [(3, 0)]))
        self.assertEqual(MP4(str(self.dir / "aiff.m4a")).tags["©nam"], ["Aiff Titel"])

    def test_lost_tags_count_as_failure(self):
        tone(self.dir / "wav.wav", args=("-c:a", "pcm_s16le"), meta={"title": "Titel", "artist": "Band"})
        with mock.patch("app.opus.mp4_items", return_value={}):   # as if nothing could be carried over
            res = self.run_opus(codec="aac", original="delete")
        self.assertEqual(res["converted"], 0, self.log)
        self.assertEqual(tree(self.music), ["Band/Album/wav.wav"])

    def test_opus_embeds_the_front_cover(self):
        from mutagen.flac import FLAC, Picture
        from mutagen.oggopus import OggOpus
        red, blue = image(env.ROOT / "rot.jpg", "red"), image(env.ROOT / "blau.jpg", "blue")
        self.addCleanup(red.unlink)
        self.addCleanup(blue.unlink)
        singles = self.music / "Band" / "Singles"   # every song its own album and cover
        tone(singles / "a.flac", cover=red, meta={"album": "Single A"})
        tone(singles / "b.flac", cover=blue, meta={"album": "Single B"})
        for n in (1, 2):   # an album: back cover first, front cover second
            f = FLAC(str(tone(self.dir / f"0{n}.flac", meta={"album": "Album"})))
            for path, kind in ((blue, 4), (red, 3)):
                pic = Picture()
                pic.type, pic.mime, pic.data = kind, "image/jpeg", path.read_bytes()
                f.add_picture(pic)
            f.save()
        res = self.run_opus(original="delete")
        self.assertEqual(res["converted"], 4, self.log)

        def embedded(path):
            pic = Picture(base64.b64decode(OggOpus(str(path))["METADATA_BLOCK_PICTURE"][0]))
            return pic.type, pic.data
        self.assertEqual(embedded(singles / "a.opus"), (3, red.read_bytes()))
        self.assertEqual(embedded(singles / "b.opus"), (3, blue.read_bytes()))
        self.assertEqual(embedded(self.dir / "01.opus"), (3, red.read_bytes()))   # the front cover, not the back
        self.assertFalse(any(singles.glob("cover.*")))   # a folder of singles gets no common cover
        self.assertEqual((self.dir / "cover.jpg").read_bytes(), red.read_bytes())

    # ------------------------------------------------------------ two originals with the same name (L1)

    def test_two_originals_with_the_same_name_are_left_alone(self):
        tone(self.dir / "Song.flac", seconds=3)
        tone(self.dir / "Song.wav", seconds=4, args=("-c:a", "pcm_s16le"))
        res = self.run_opus(original="archive", jobs=2)
        self.assertEqual((res["converted"], res["errors"]), (0, 2), self.log)
        self.assertEqual(tree(self.music), ["Band/Album/Song.flac", "Band/Album/Song.wav"])
        self.assertIn("rename one of the two", self.text())
        # earlier version: Song.flac already converted and archived – the Opus file is not offered for deleting
        (self.dir / "Song.flac").rename(self.archive / "Song.flac")
        (self.archive / "Band" / "Album").mkdir(parents=True)
        (self.archive / "Song.flac").rename(self.archive / "Band" / "Album" / "Song.flac")
        tone(self.dir / "Song.opus", seconds=3, args=("-c:a", "libopus"))
        self.log.clear()
        res = self.run_opus(original="archive")
        self.assertEqual(res["errors"], 1, self.log)
        self.assertIn("belongs to another original (Song.flac in the archive)", self.text())
        self.assertEqual(tree(self.music), ["Band/Album/Song.opus", "Band/Album/Song.wav"])

    def test_an_existing_file_of_another_format_is_not_taken(self):
        tone(self.dir / "Song.flac")
        tone(self.dir / "Song.opus", args=("-c:a", "libvorbis", "-f", "ogg"))   # Vorbis under the name .opus
        res = self.run_opus(original="delete")
        self.assertEqual(res["errors"], 1, self.log)
        self.assertTrue((self.dir / "Song.flac").exists())


if __name__ == "__main__":
    unittest.main()
