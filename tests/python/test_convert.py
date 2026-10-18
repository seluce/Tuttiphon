"""Converting to Opus or AAC with real files created in the test: tags (including MusicBrainz, ISRC, several artists),
cover and numbers arrive in the .m4a the way Navidrome reads them; ALAC → AAC replaces the original of the same name
only once it is in the archive; with "keep original" such a file stays as it is. Needs ffmpeg and mutagen."""
from tests.python import env  # noqa: F401  (before app.*)

import shutil
import subprocess
import unittest
from unittest import mock

from app import config, lautstaerke, opus
from tests.python.factory import base_config

HAVE = bool(shutil.which("ffmpeg")) and opus.mp4_available()
MBID = "0f3c3bd4-2c1b-4a5e-9d0e-1a2b3c4d5e6f"


def ffmpeg(*args):
    subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-y", *map(str, args)], check=True)


def flac(path, cover=True):
    """FLAC with everything Lidarr/Picard typically write into it."""
    from mutagen.flac import FLAC, Picture
    path.parent.mkdir(parents=True, exist_ok=True)
    ffmpeg("-f", "lavfi", "-i", "sine=frequency=440:duration=3", "-c:a", "flac", path)
    f = FLAC(str(path))
    f["TITLE"], f["ARTIST"], f["ALBUM"], f["ALBUMARTIST"] = "Barbie Girl", "Aqua", "Aquarium", "Aqua"
    f["DATE"], f["TRACKNUMBER"], f["TRACKTOTAL"], f["DISCNUMBER"] = "1997", "3", "12", "1"
    f["MUSICBRAINZ_TRACKID"], f["MUSICBRAINZ_ALBUMID"], f["ISRC"] = MBID, MBID, "DKBKA9700030"
    f["ARTISTS"] = ["Aqua", "René Dif"]
    f["LYRICS"], f["GENRE"], f["COMPILATION"] = "I'm a Barbie girl", "Eurodance", "1"
    f["ENCODER"] = "Lavf"
    if cover:
        img = path.parent / "bild.jpg"
        ffmpeg("-f", "lavfi", "-i", "color=red:s=32x32", "-frames:v", "1", img)
        pic = Picture()
        pic.type, pic.mime, pic.data = 3, "image/jpeg", img.read_bytes()
        f.add_picture(pic)
        img.unlink()
    f.save()
    return path


def codec(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "a:0", "-show_entries", "stream=codec_name",
                          "-of", "csv=p=0", str(path)], capture_output=True, text=True, check=True)
    return out.stdout.strip()


@unittest.skipUnless(HAVE, "ffmpeg and mutagen are missing")
class ConvertTest(unittest.TestCase):
    def setUp(self):
        self.dir = env.MUSIC / "Aqua" / "Aquarium"
        for d in (self.dir, env.ARCHIVE / "Aqua"):
            shutil.rmtree(d, ignore_errors=True)
            self.addCleanup(shutil.rmtree, d, True)
        p = mock.patch("app.opus.music_dir", return_value=env.MUSIC)
        p.start()
        self.addCleanup(p.stop)
        self.log = []

    def run_opus(self, **op):
        cfg = base_config()
        cfg["settings"]["opus"] = {"enabled": True, "formats": ["flac", "alac"], "minAgeMinutes": 0, **op}
        return opus.run(cfg, log=self.log.append)

    def test_flac_to_aac_keeps_tags_cover_and_archives(self):
        src = flac(self.dir / "03 Barbie Girl.flac")
        res = self.run_opus(codec="aac")
        self.assertEqual(res["converted"], 1, self.log)
        dst = self.dir / "03 Barbie Girl.m4a"
        self.assertEqual(codec(dst), "aac")
        self.assertFalse(src.exists())
        self.assertTrue((env.ARCHIVE / "Aqua" / "Aquarium" / src.name).exists())
        self.assertEqual(list(self.dir.glob(".*.part")), [])
        self.assertIn(str(dst), opus.RECENT)
        self.assertTrue(any("AAC 224 kbit/s" in line for line in self.log), self.log)   # default for AAC
        from mutagen.mp4 import MP4
        t = MP4(str(dst)).tags
        self.assertEqual((t["©nam"], t["©ART"], t["aART"], t["©day"]), (["Barbie Girl"], ["Aqua"], ["Aqua"], ["1997"]))
        self.assertEqual((t["trkn"], t["disk"], t["cpil"]), ([(3, 12)], [(1, 0)], True))
        ff = "----:com.apple.iTunes:"
        self.assertEqual([bytes(v).decode() for v in t[ff + "MusicBrainz Track Id"]], [MBID])   # this is how Navidrome reads them
        self.assertEqual([bytes(v).decode() for v in t[ff + "MusicBrainz Album Id"]], [MBID])
        self.assertEqual([bytes(v).decode() for v in t[ff + "ISRC"]], ["DKBKA9700030"])
        self.assertEqual([bytes(v).decode() for v in t[ff + "ARTISTS"]], ["Aqua", "René Dif"])
        self.assertEqual(t["©lyr"], ["I'm a Barbie girl"])
        self.assertNotIn(ff + "ENCODER", t)
        self.assertEqual(len(t["covr"]), 1)
        # loudness normalization can write into the .m4a afterwards
        self.assertIs(lautstaerke.write_tags(dst, lautstaerke.tag_values((-9.0, -1.0))), True)

    def test_opus_stays_default(self):
        flac(self.dir / "01 Lied.flac", cover=False)
        self.assertEqual(self.run_opus()["converted"], 1, self.log)
        self.assertEqual(codec(self.dir / "01 Lied.opus"), "opus")
        self.assertTrue(any("Opus 160 kbit/s" in line for line in self.log), self.log)

    def test_alac_to_aac_replaces_original_after_archive(self):
        src = self.dir / "05 Lied.m4a"
        src.parent.mkdir(parents=True, exist_ok=True)
        ffmpeg("-f", "lavfi", "-i", "sine=frequency=440:duration=3", "-c:a", "alac", "-metadata", "title=Lied",
               "-metadata", "artist=Aqua", src)
        from mutagen.mp4 import MP4, MP4FreeForm
        m = MP4(str(src))
        m.tags["----:com.apple.iTunes:MusicBrainz Track Id"] = [MP4FreeForm(MBID.encode())]
        m.save()
        # keep original: not possible, the file stays as it is
        self.assertEqual(self.run_opus(codec="aac", original="keep")["converted"], 0)
        self.assertEqual(codec(src), "alac")
        res = self.run_opus(codec="aac")
        self.assertEqual(res["converted"], 1, self.log)
        self.assertEqual(codec(src), "aac")
        archived = env.ARCHIVE / "Aqua" / "Aquarium" / "05 Lied.m4a"
        self.assertEqual(codec(archived), "alac")
        t = MP4(str(src)).tags
        self.assertEqual(t["©nam"], ["Lied"])
        self.assertEqual(bytes(t["----:com.apple.iTunes:MusicBrainz Track Id"][0]).decode(), MBID)
        self.assertEqual(self.run_opus(codec="aac")["converted"], 0)   # AAC is not converted again

    def test_keep_original_skips_converted(self):
        flac(self.dir / "02 Lied.flac", cover=False)
        self.assertEqual(self.run_opus(codec="aac", original="keep")["converted"], 1, self.log)
        self.assertTrue((self.dir / "02 Lied.flac").exists())
        self.assertEqual(self.run_opus(codec="aac", original="keep")["converted"], 0)


class SettingsTest(unittest.TestCase):
    def test_target_and_validation(self):
        self.assertEqual(opus.target({}), ("opus", ".opus", "Opus", 160))
        self.assertEqual(opus.target({"codec": "aac", "bitrate": 128}), ("aac", ".m4a", "AAC", 224))
        self.assertEqual(opus.target({"codec": "aac", "aacBitrate": 256}), ("aac", ".m4a", "AAC", 256))
        cfg = base_config()
        for bad in ({"codec": "mp3"}, {"codec": "aac", "aacBitrate": 1000}):
            with self.assertRaises(ValueError):
                config.validate_config({**cfg, "settings": {**cfg["settings"], "opus": bad}})

    @unittest.skipUnless(opus.mp4_available(), "mutagen is missing")
    def test_tag_names_like_picard(self):
        items = opus.mp4_items({"TITLE": ["A"], "MUSICBRAINZ_COMPOSERID": [MBID], "RELEASETYPE": ["album"],
                                "TRACKNUMBER": ["4/9"], "BPM": ["120.5"], "LABEL": ["Universal"]})
        self.assertEqual(items["©nam"], ["A"])
        self.assertEqual(items["trkn"], [(4, 9)])
        self.assertEqual(items["tmpo"], [120])
        for key in ("MusicBrainz Composer Id", "MusicBrainz Album Type", "LABEL"):
            self.assertIn("----:com.apple.iTunes:" + key, items)
        self.assertEqual(opus._norm_key("MusicBrainz Album Artist Id"), "MUSICBRAINZ_ALBUMARTISTID")
        self.assertEqual(opus._norm_key("Album Artist"), "ALBUMARTIST")


if __name__ == "__main__":
    unittest.main()
