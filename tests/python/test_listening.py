"""Listening and the song window: song info with lyrics and playlists, "more like this", child protection on playback.
No network: the song list comes from the factory, Navidrome is not asked."""
from tests.python import env  # noqa: F401  (before app.*)

import unittest
from unittest import mock

from app import auth, config, liedtext, rules, web
from app.rules import Library
from tests.python.factory import base_config, song

JONAS = {"user": "Jonas", "role": "user", "own": "jonas", "persons": ["jonas"], "local": False}
ADMIN = {"user": "niklas", "role": "admin", "own": None, "persons": [], "local": False}


class SongTest(unittest.TestCase):
    def setUp(self):
        env.reset_caches()
        self.cfg = base_config()
        self.cfg["playlists"] = [{"id": "kids", "person": "familie", "welt": "kinder", "stil": "*", "status": "aktiv", "minRating": 0},
                                 {"id": "privat", "person": "niklas", "welt": "kinder", "stil": "*", "status": "aktiv", "minRating": 0}]
        config.save_config(self.cfg)
        self.lib = Library([song("a1", "Lied eins", artist="Band A", genres=["Children"]),
                            song("a2", "Lied zwei", artist="Band A", genres=["Children"]),
                            song("b1", "Böses Lied", artist="Band B", genres=["Children"]),
                            song("x1", "Anderes", artist="Iron Test", genres=["Metal"])])
        p = mock.patch.object(web.CACHE, "get", return_value=self.lib)
        p.start()
        self.addCleanup(p.stop)
        self.addCleanup(auth.set_current, {"user": None, "role": "none", "own": None, "persons": [], "local": False})

    def test_song_with_lyrics_and_visible_playlists(self):
        auth.set_current(JONAS)
        with mock.patch.object(liedtext, "text_of", return_value="Zeile eins\nZeile zwei"):
            d = web.api_song({"id": "a1"})
        self.assertEqual((d["id"], d["title"], d["lyrics"]), ("a1", "Lied eins", "Zeile eins\nZeile zwei"))
        self.assertEqual([p["id"] for p in d["playlists"]], ["kids"])     # Jonas does not see Niklas's private one
        with self.assertRaises(ValueError):
            web.api_song({"id": "../etc"})

    def test_kid_safe_blocks_song_and_stream(self):
        self.cfg["personen"][1]["clean"] = True
        config.save_config(self.cfg)
        auth.set_current(JONAS)
        with mock.patch.object(liedtext, "derb", return_value=frozenset({"b1"})):
            with self.assertRaises(PermissionError):
                web.api_song({"id": "b1"})
            with self.assertRaises(PermissionError):
                web.api_song_more({"id": "b1"})
            self.assertTrue(web._child_blocked(config.load_config(), self.lib.songs[2]))
            auth.set_current(ADMIN)                                      # the administrator may listen to everything
            self.assertFalse(web._child_blocked(config.load_config(), self.lib.songs[2]))

    def test_more_like_this_respects_nogos(self):
        auth.set_current(JONAS)
        with mock.patch("app.classify.radio_artists", return_value=["Band A", "Band B", "Iron Test"]):
            d = web.api_song_more({"id": "a1"})
        ids = {s["id"] for s in d["songs"]}
        self.assertNotIn("a1", ids)                                      # not the song itself
        self.assertNotIn("x1", ids)                                      # Jonas does not like metal
        self.assertTrue({"a2", "b1"} <= ids)

    def test_rows_carry_the_song_id(self):
        self.assertEqual(self.lib.describe(0)["id"], "a1")
        self.assertEqual(rules._with_sound(self.lib, [1])[0]["id"], "a2")


class NextStepsTest(unittest.TestCase):
    def test_no_favourites_prompt_when_taste_is_known(self):
        env.reset_caches()
        cfg = base_config()
        cfg["personen"][1]["likes"] = {"welten": [], "stile": [], "artists": []}   # Jonas: nothing picked by hand
        config.save_config(cfg)
        m = {**JONAS, "passwordStored": True}
        with mock.patch.object(web.CACHE, "get", return_value=Library([song("a")])):
            with mock.patch("app.taste.profile", return_value={"enough": True}):
                self.assertNotIn("likes|jonas", [x["key"] for x in web.user_inbox(m)])
            with mock.patch("app.taste.profile", return_value={"enough": False}):
                self.assertIn("likes|jonas", [x["key"] for x in web.user_inbox(m)])


@env.german   # checks the German output of existing installations
class WorldResetTest(unittest.TestCase):
    def test_preview(self):
        env.reset_caches()
        cfg = base_config()
        kinder = cfg["welten"][0]
        kinder.update(scene="kinder", autoScene=True, artists=["Band A", "Handband"], genres=["Children"])
        cfg["playlists"] = [{"id": "k", "person": "familie", "welt": "kinder", "stil": "*", "status": "aktiv"}]
        config.save_config(cfg)
        lib = Library([song("a", artist="Band A"), song("h", artist="Handband"), song("l", artist="Lichterkinder")])
        auth.set_current(ADMIN)
        self.addCleanup(auth.set_current, {"user": None, "role": "none", "own": None, "persons": [], "local": False})
        with mock.patch.object(web.CACHE, "get", return_value=lib), \
                mock.patch.object(rules, "scene_members", return_value=["Band A", "Lichterkinder"]):
            d = web.api_welt_reset({"id": "kinder"})
            with self.assertRaises(ValueError):
                web.api_welt_reset({"id": "metal"})                              # without a scene
        self.assertEqual((d["name"], d["before"], d["after"]), ("Kindermusik", 3, 2))
        self.assertEqual((d["dropped"], d["added"]), (["Handband"], []))
        self.assertEqual(d["renamed"][0][1].split(" ")[0], "Kindermusik")         # the playlist would get a new name
        self.assertEqual(config.load_config()["welten"][0]["artists"], ["Band A", "Handband"])   # preview only
        self.assertIn("/api/welt/neu", web.Handler.ADMIN_ONLY)


class KidSafeListTest(unittest.TestCase):
    def test_words_per_song(self):
        self.assertEqual(liedtext.rude_words("So ein Scheiß, scheiß drauf, verdammte Hurensöhne und fuck"),
                         [["scheiß", 2], ["hurensöhne", 1], ["fuck", 1]])
        self.assertEqual(liedtext.rude_words("Ein Marsch durch den Wald"), [])

    def test_api_lists_words(self):
        env.reset_caches()
        config.save_config(base_config())
        lib = Library([song("a1", "Böses Lied", artist="Band A")])
        auth.set_current(ADMIN)
        self.addCleanup(auth.set_current, {"user": None, "role": "none", "own": None, "persons": [], "local": False})
        with mock.patch.object(web.CACHE, "get", return_value=lib), \
                mock.patch.object(liedtext, "derb_details", return_value={"a1": [["fuck", 3]]}):
            d = web.api_kinderschutz({})
        self.assertEqual(d["songs"][0]["words"], [["fuck", 3]])


class LyricsIndexTest(unittest.TestCase):
    def setUp(self):
        liedtext.DB_FILE.unlink(missing_ok=True)
        self.addCleanup(liedtext.DB_FILE.unlink, missing_ok=True)

    def test_text_of(self):
        folder = env.MUSIC / "Text" / "Album"
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "t1.lrc").write_text("[00:01.00]Erste Zeile\n[00:05.00]Zweite Zeile\n", encoding="utf-8")
        lib = Library([song("t1"), song("t2")])
        lib.path_loader = lambda: ({"t1": "Text/Album/t1.opus", "t2": "Text/Album/t2.opus"}, {})
        liedtext.update(lib, base_config())
        self.assertEqual(liedtext.text_of("t1"), "Erste Zeile\nZweite Zeile")
        self.assertIsNone(liedtext.text_of("t2"))


if __name__ == "__main__":
    unittest.main()
