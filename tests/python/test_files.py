"""Files in the music folder (only in the temp folder): saving lyrics (app/lyrics.py), files to convert and
covers (app/opus.py), detecting new music (app/watch.py)."""
from tests.python import env  # noqa: F401  (before app.*)

import os
import shutil
import stat
import time
import unittest
from unittest import mock

from app import lyrics, opus, watch

SYNCED = "[00:01.00] Hallo\n[00:03.50] Welt"


def res(synced=None, plain=None, instrumental=False):
    return {"synced": synced, "plain": plain, "instrumental": instrumental}


class FolderTest(unittest.TestCase):
    name = "test"

    def setUp(self):
        env.reset_caches()
        self.root = env.MUSIC / f"zz-{self.name}"
        shutil.rmtree(self.root, ignore_errors=True)
        self.root.mkdir(parents=True)
        self.addCleanup(shutil.rmtree, self.root, True)

    def touch(self, rel, text="x"):
        path = self.root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
        return path


class TestLyricsWrite(FolderTest):
    name = "lyrics"

    def setUp(self):
        super().setUp()
        self.audio = self.touch("Band/Album/01 Lied.opus")
        self.lrc = self.audio.with_name("01 Lied.lrc")
        self.txt = self.audio.with_name("01 Lied.txt")

    def write(self, result, ly=None, dry_run=False):
        return lyrics._write(ly if ly is not None else {}, self.audio, "01 Lied", result, dry_run)

    def test_synced(self):
        self.assertEqual(self.write(res(SYNCED, "Hallo Welt")), ("synced", False))
        self.assertEqual(self.lrc.read_text(), SYNCED + "\n")
        self.assertFalse(self.txt.exists())
        self.assertEqual(stat.S_IMODE(self.lrc.stat().st_mode), 0o664)
        self.assertEqual([p.name for p in self.audio.parent.iterdir() if p.name.startswith(".")], [])   # no leftovers

    def test_synced_replaces_plain_text(self):
        self.txt.write_text("alt")
        self.assertEqual(self.write(res(SYNCED)), ("synced", True))
        self.assertFalse(self.txt.exists())

    def test_synced_keeps_plain_text_without_cleanup(self):
        self.txt.write_text("alt")
        self.assertEqual(self.write(res(SYNCED), {"cleanup": False}), ("synced", True))
        self.assertTrue(self.txt.exists())
        self.assertTrue(self.lrc.exists())

    def test_instrumental(self):
        self.assertEqual(self.write(res(instrumental=True)), ("instrumental", False))
        self.assertEqual(self.lrc.read_text(), lyrics.INSTRUMENTAL)

    def test_instrumental_never_replaces_text(self):
        # existing text stays – an instrumental marker next to it would block any further search
        self.txt.write_text("alt")
        self.assertEqual(self.write(res(instrumental=True)), ("plain-had", False))
        self.assertEqual(self.txt.read_text(), "alt")
        self.assertFalse(self.lrc.exists())

    def test_instrumental_skip(self):
        self.assertEqual(self.write(res(instrumental=True), {"instrumental": "skip"}), ("skip", False))
        self.assertFalse(self.lrc.exists())

    def test_plain(self):
        self.assertEqual(self.write(res(plain="Nur Text")), ("plain", False))
        self.assertEqual(self.txt.read_text(), "Nur Text\n")
        self.assertFalse(self.lrc.exists())

    def test_plain_already_there(self):
        self.txt.write_text("schon da")
        self.assertEqual(self.write(res(plain="Neuer Text")), ("plain-had", False))
        self.assertEqual(self.txt.read_text(), "schon da")

    def test_plain_not_wanted_and_nothing_found(self):
        self.assertEqual(self.write(res(plain="Nur Text"), {"savePlain": False}), ("none", False))
        self.assertEqual(self.write(None), ("none", False))
        self.assertEqual(sorted(p.name for p in self.audio.parent.iterdir()), ["01 Lied.opus"])

    def test_dry_run_writes_nothing(self):
        self.txt.write_text("alt")
        self.assertEqual(self.write(res(SYNCED), dry_run=True), ("synced", True))
        self.assertEqual(self.write(res(instrumental=True), dry_run=True), ("plain-had", False))
        self.assertFalse(self.lrc.exists())
        self.assertEqual(self.txt.read_text(), "alt")


class TestLyricsCleanup(FolderTest):
    name = "cleanup"

    def test_txt_goes_only_next_to_synced_lyrics(self):
        cases = {   # .lrc content -> does the .txt with the same name go?
            "01": ("[00:01.00] Hallo\n[00:03.50] Welt\n", True),
            "02": ("[ar: Band]\n[ti: Lied]\n[00:01.00]<00:01.00> Hal<00:01.40>lo\n", True),   # word timing
            "03": (lyrics.INSTRUMENTAL, False),   # only marks the song as instrumental
            "04": ("", False),
            "05": ("[ar: Band]\n[ti: Lied]\n", False),   # header only
            "06": ("[00:01.00]\n[00:02.00]  \n", False),   # time stamps without words
            "07": ("Text ohne Zeitstempel\n", False),
        }
        for stem, (lrc, _gone) in cases.items():
            self.touch(f"A/{stem}.lrc", lrc)
            self.touch(f"A/{stem}.txt", "echter Text\n")
        self.touch("A/08.txt", "nur Text\n")
        self.assertEqual(lyrics.cleanup(self.root, log=lambda *_: None), 2)
        for stem, (_lrc, gone) in cases.items():
            self.assertEqual((self.root / "A" / f"{stem}.txt").exists(), not gone, stem)
        self.assertTrue((self.root / "A" / "08.txt").exists())
        self.assertFalse(lyrics.has_synced_lines(None))


class TestLyricsResult(unittest.TestCase):
    def test_result_normalizes(self):
        self.assertEqual(lyrics._result("ohne Zeitstempel", "  Text  "), res(None, "Text"))
        self.assertIsNone(lyrics._result("ohne Zeitstempel", "   "))
        self.assertEqual(lyrics._result(SYNCED, None, instrumental=True), res(SYNCED, None, False))
        self.assertEqual(lyrics._result(None, None, instrumental=True), res(instrumental=True))

    def test_lookup_prefers_synced_and_tries_main_artist(self):
        class Fake:
            def __init__(self, answers):
                self.answers, self.asked = answers, []

            def find(self, artist, title, album, duration):
                self.asked.append(artist)
                return self.answers.get(artist)
        first = Fake({"Band A": res(plain="Text A")})
        second = Fake({"Band A": res(SYNCED)})
        self.assertEqual(lyrics.lookup([("eins", first), ("zwei", second)], "Band A feat. B", "Lied", "", 200),
                         (res(SYNCED), "zwei"))
        self.assertEqual(first.asked, ["Band A feat. B", "Band A"])
        only_plain = Fake({"Band A": res(plain="Text A")})
        self.assertEqual(lyrics.lookup([("eins", only_plain), ("zwei", Fake({}))], "Band A", "Lied", "", 200),
                         (res(plain="Text A"), "eins"))
        self.assertEqual(lyrics.lookup([("eins", Fake({}))], "Band A", "Lied", "", 200), (None, None))
        # text from an earlier provider takes precedence over "instrumental" from a later one
        self.assertEqual(lyrics.lookup([("eins", Fake({"Band A": res(plain="Text A")})),
                                        ("zwei", Fake({"Band A": res(instrumental=True)}))], "Band A", "Lied", "", 200),
                         (res(plain="Text A"), "eins"))


class TestOpusSources(FolderTest):
    name = "opus"

    def found(self, **op):
        return sorted(str(p.relative_to(self.root)) for p in opus.find_sources({"minAgeMinutes": 0, **op})
                      if self.root in p.parents)

    def test_keep_mode_skips_converted_files(self):
        for rel in ("A/a.flac", "A/b.flac", "A/b.opus", "A/c.wav", "A/._d.flac", "A/@eaDir/e.flac", "A/.versteckt/f.flac",
                    "#recycle/g.flac", "B/h.FLAC", "B/i.mp3"):
            self.touch(rel)
        self.assertEqual(self.found(original="keep"), ["A/a.flac", "B/h.FLAC"])
        self.assertEqual(self.found(original="archive"), ["A/a.flac", "A/b.flac", "B/h.FLAC"])
        self.assertEqual(self.found(original="keep", formats=["flac", "wav"]), ["A/a.flac", "A/c.wav", "B/h.FLAC"])

    def test_fresh_files_wait(self):
        self.touch("A/neu.flac")
        self.assertEqual(self.found(original="keep", minAgeMinutes=5), [])
        self.assertEqual(self.found(original="keep"), ["A/neu.flac"])

    def test_m4a_only_when_alac(self):
        self.touch("A/alac.m4a")
        self.touch("A/aac.m4a")
        with mock.patch.object(opus, "_codec", side_effect=lambda p: "alac" if p.name == "alac.m4a" else "aac"):
            self.assertEqual(self.found(original="keep", formats=["alac"]), ["A/alac.m4a"])

    def test_folder_has_cover(self):
        cases = {("Cover.JPG",): True, ("folder.png",): True, ("front.webp",): True, ("album.jpeg",): True,
                 ("back.jpg", "01.opus"): False, ("cover.txt",): False, ("albumart.jpg",): False,
                 (".cover-1-2.jpg.part",): False, (): False}
        for k, (names, expected) in enumerate(cases.items()):
            folder = self.root / f"c{k}"
            folder.mkdir()
            for n in names:
                (folder / n).write_text("x")
            self.assertEqual(opus._folder_has_cover(folder), expected, names)
        self.assertTrue(opus._folder_has_cover(self.root / "gibt-es-nicht"))   # when in doubt, write nothing


class TestWatchFindNew(FolderTest):
    name = "watch"

    def test_finds_new_audio_files(self):
        for rel in ("A/neu.opus", "A/neu.flac", "A/song.mp3", "A/sub/z.m4a", "A/cover.jpg", "A/neu.lrc",
                    "A/.versteckt.opus", "A/._x.flac", "A/@eaDir/y.flac", "#recycle/r.opus"):
            self.touch(rel)
        recent = self.root / "A" / "eben-umgewandelt.opus"
        recent.write_text("x")
        opus.RECENT[str(recent)] = time.time()
        self.addCleanup(opus.RECENT.pop, str(recent), None)
        now = time.time()
        found = [str(p.relative_to(self.root)) for p in watch.find_new(self.root, now - 60, now + 60)[0]]
        self.assertEqual(found, ["A/neu.flac", "A/neu.opus", "A/song.mp3", "A/sub/z.m4a"])

    def test_time_window(self):
        self.touch("A/neu.opus")
        now = time.time()
        self.assertEqual(watch.find_new(self.root, now + 30, now + 60)[0], [])   # changed before the window
        new, seen = watch.find_new(self.root, now - 60, now - 30)
        self.assertEqual((new, seen), ([], set()))   # not unchanged long enough yet – not remembered either
        self.assertEqual(len(watch.find_new(self.root, now - 60, now + 60)[0]), 1)

    def test_known_paths_are_not_new(self):
        # permissions or tags changed (new ctime), but path already known -> no new music
        self.touch("A/alt.opus")
        self.touch("A/neu.opus")
        now = time.time()
        new, seen = watch.find_new(self.root, now - 60, now + 60, known={"A/alt.opus"})
        self.assertEqual([str(p.relative_to(self.root)) for p in new], ["A/neu.opus"])
        self.assertEqual(seen, {"A/alt.opus", "A/neu.opus"})

    def test_reads_only_changed_folders(self):
        for rel in ("A/eins.opus", "B/zwei.opus", "B/C/drei.opus"):
            self.touch(rel)
        now = time.time()
        new, seen, dirs = watch.scan(self.root, now - 60, now + 60)
        self.assertEqual(len(new), 3)
        read = []
        real = os.scandir

        def counting(path):
            read.append(os.path.relpath(path, self.root))
            return real(path)
        with mock.patch("os.scandir", counting):
            new, seen2, dirs2 = watch.scan(self.root, now - 60, now + 60, seen, dirs)
        self.assertEqual((new, seen2, read), ([], seen, []))      # nothing changed: no folder read again
        time.sleep(0.01)
        self.touch("B/C/vier.opus")                                # a new file changes only its folder
        with mock.patch("os.scandir", counting):
            new, seen3, _ = watch.scan(self.root, now - 60, time.time() + 60, seen2, dirs2)
        self.assertEqual([str(p.relative_to(self.root)) for p in new], ["B/C/vier.opus"])
        self.assertEqual(read, ["B/C"])
        self.assertIn("B/C/vier.opus", seen3)

    def test_fresh_folder_is_read_again(self):
        self.touch("A/eins.opus")
        now = time.time()
        _, _, dirs = watch.scan(self.root, now - 60, now - 30)     # file not finished yet
        self.assertIsNone(dirs["A"][0])
        new, _, dirs = watch.scan(self.root, now - 60, now + 60, set(), dirs)
        self.assertEqual(len(new), 1)
        self.assertIsNotNone(dirs["A"][0])


if __name__ == "__main__":
    unittest.main()
