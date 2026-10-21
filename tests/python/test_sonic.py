"""Sound similarity for the Navidrome plugin (app/sonic.py): similar songs, songs like a band or an album, similar
bands, a sound path between two songs – from made-up sound vectors (see test_similar.py) – and the plugin's key."""
from tests.python import env  # noqa: F401  (before app.*)

import json
import unittest
from unittest import mock

from app import classify, sonic, web
from app.rules import Library
from tests.python.factory import base_config, song
from tests.python.test_audit_server import request
from tests.python.test_similar import reset, vector, write_vectors

# bands of three scenes – the children's bands are in the separate world "kinder"
BANDS = {"Eisen": "metal", "Stahl": "metal", "Blech": "metal", "Kita": "kinder", "Sandkasten": "kinder",
         "Harfe": "folk", "Dudel": "folk", "Flöte": "folk"}


def library(per_band=6):
    return Library([song(f"{b}-{n}", title=f"{b} Lied {n}", artist=b, album=f"Album {b} {n // 3}", album_id=f"al-{b}-{n // 3}")
                    for b in BANDS for n in range(per_band)])


def config():
    cfg = base_config()
    cfg["welten"][0].update(artists=["Kita", "Sandkasten"], genres=[])   # the children's music
    cfg["settings"]["allMinRating"] = 0
    return cfg


class SonicTest(unittest.TestCase):
    def setUp(self):
        reset()
        self.addCleanup(reset)
        sonic._memo.clear()
        self.cfg, self.lib = config(), library()
        write_vectors({s["id"]: vector(BANDS[s["artist"]], k) for k, s in enumerate(self.lib.songs)})

    def bands(self, scored):
        return [self.lib.songs[i]["artist"] for i, _sc in scored]

    def test_similar_songs_sound_alike_and_stay_out_of_the_children_music(self):
        got = sonic.similar_songs(self.cfg, self.lib, "Eisen-0", 12)
        bands = self.bands(got)
        self.assertTrue(got)
        self.assertNotIn("Eisen-0", [self.lib.songs[i]["id"] for i, _sc in got])
        self.assertTrue(set(bands[:6]) <= {"Eisen", "Stahl", "Blech"})        # the nearest: metal
        self.assertFalse({"Kita", "Sandkasten"} & set(bands))                 # a separate world stays out …
        self.assertTrue(all(0 <= sc <= 1 for _i, sc in got))
        self.assertLessEqual(max(bands.count(b) for b in set(bands)), 3)      # a few per band
        kids = self.bands(sonic.similar_songs(self.cfg, self.lib, "Kita-0", 6))
        self.assertTrue(set(kids[:3]) <= {"Kita", "Sandkasten"})              # … unless the song is from it

    def test_without_a_vector_the_radio_fills_in(self):
        write_vectors({s["id"]: vector(BANDS[s["artist"]], k) for k, s in enumerate(self.lib.songs) if s["artist"] != "Harfe"})
        with mock.patch.object(classify, "radio_artists", lambda seeds, lib, limit=25: ["Harfe", "Dudel"]):
            got = self.bands(sonic.similar_songs(self.cfg, self.lib, "Harfe-0", 6))
        self.assertTrue(got)
        self.assertTrue(set(got) <= {"Harfe", "Dudel"})

    def test_artist_album_and_similar_bands(self):
        with mock.patch.object(classify, "radio_artists", lambda seeds, lib, limit=25: [seeds[0], "Stahl", "Blech", "Kita"]):
            radio = self.bands(sonic.songs_like_artist(self.cfg, self.lib, name="Eisen", count=12))
            by_id = self.bands(sonic.songs_like_artist(self.cfg, self.lib, artist_id="ar-Eisen", count=12))
            near = sonic.similar_artists(self.cfg, self.lib, name="Eisen", limit=5)
        self.assertIn("Eisen", radio)
        self.assertLessEqual(radio.count("Eisen"), 4)                         # the band itself: up to a third
        self.assertTrue(set(radio) <= {"Eisen", "Stahl", "Blech", "Harfe", "Dudel", "Flöte"})
        self.assertEqual(radio, by_id)
        self.assertEqual(near, [("Stahl", "ar-Stahl"), ("Blech", "ar-Blech"), ("Kita", "ar-Kita")])   # never itself
        album = sonic.songs_like_album(self.cfg, self.lib, album_id="al-Harfe-0", count=6)
        ids = [self.lib.songs[i]["id"] for i, _sc in album]
        self.assertTrue(ids)
        self.assertFalse({"Harfe-0", "Harfe-1", "Harfe-2"} & set(ids))      # not from the album itself
        self.assertTrue(set(self.bands(album)[:3]) <= {"Harfe", "Dudel", "Flöte"})

    def test_an_artist_who_only_takes_part(self):
        self.lib.songs[0]["artists"].append({"id": "ar-Gast", "name": "Gast"})   # on one Eisen song
        sonic._memo.clear()
        with mock.patch.object(classify, "radio_artists", lambda seeds, lib, limit=25: [seeds[0], "Stahl"]):
            by_id = self.bands(sonic.songs_like_artist(self.cfg, self.lib, artist_id="ar-Gast", count=6))
            by_name = sonic.similar_artists(self.cfg, self.lib, name="gast", limit=3)
        self.assertTrue(by_id)
        self.assertTrue(set(by_id) <= {"Eisen", "Stahl", "Blech"})   # the band it plays with: Eisen
        self.assertEqual(by_name, [("Stahl", "ar-Stahl")])

    def test_path_from_metal_to_folk(self):
        got = sonic.path(self.cfg, self.lib, "Eisen-0", "Harfe-0", 8)
        ids = [self.lib.songs[i]["id"] for i, _sc in got]
        self.assertEqual((ids[0], ids[-1], len(ids)), ("Eisen-0", "Harfe-0", 8))
        self.assertEqual(len(set(ids)), 8)
        scenes = [BANDS[self.lib.songs[i]["artist"]] for i, _sc in got]
        self.assertEqual(scenes[1], "metal")                                  # starts close to the start …
        self.assertEqual(scenes[-2], "folk")                                  # … and ends close to the end
        self.assertEqual(sonic.path(self.cfg, self.lib, "Eisen-0", "gibt-es-nicht", 8), [])

    def test_kid_safe_with_a_child_profile(self):
        explicit = self.lib.songs[1]   # Eisen-1, the nearest of Eisen-0
        explicit["explicitStatus"] = "explicit"
        sonic._memo.clear()
        self.assertIn("Eisen-1", [s["id"] for s in sonic.as_songs(self.lib, sonic.similar_songs(self.cfg, self.lib, "Eisen-0", 12))])
        self.cfg["personen"][1]["child"] = True   # someone listening could be a child
        sonic._memo.clear()
        self.assertNotIn("Eisen-1", [s["id"] for s in sonic.as_songs(self.lib, sonic.similar_songs(self.cfg, self.lib, "Eisen-0", 12))])

    def test_answer(self):
        out = sonic.answer(self.cfg, self.lib, "similar", {"id": "Eisen-0", "count": "3"})
        self.assertEqual(len(out["songs"]), 3)
        self.assertEqual(set(out["songs"][0]), {"id", "title", "artist", "album", "durationMs", "similarity"})
        self.assertEqual(out["songs"][0]["durationMs"], 200000)
        with self.assertRaises(KeyError):
            sonic.answer(self.cfg, self.lib, "unknown", {})


class KeyTest(unittest.TestCase):
    def setUp(self):
        sonic.remove_key()
        self.addCleanup(sonic.remove_key)

    def test_key(self):
        self.assertFalse(sonic.check_key("tp_x"))
        self.assertFalse(sonic.status()["key"])
        key = sonic.new_key()
        self.assertTrue(key.startswith("tp_") and len(key) > 40)
        self.assertNotIn(key, sonic.KEY_FILE.read_text())          # only its hash is stored
        self.assertTrue(sonic.check_key(key))
        self.assertFalse(sonic.check_key(key + "x"))
        self.assertFalse(sonic.check_key(""))
        self.assertTrue(sonic.status()["key"])
        again = sonic.new_key()
        self.assertFalse(sonic.check_key(key))                     # a new key ends the old one
        self.assertTrue(sonic.check_key(again))
        self.assertEqual(set(json.loads(sonic.KEY_FILE.read_text())), {"sha256", "at"})


class EndpointTest(unittest.TestCase):
    """GET /api/sonic/<what> through web.Handler: only with the plugin's key; the admin functions."""

    def setUp(self):
        reset()
        sonic._memo.clear()
        sonic.remove_key()
        self.addCleanup(reset)
        self.addCleanup(sonic.remove_key)
        self.lib = library()
        write_vectors({s["id"]: vector(BANDS[s["artist"]], k) for k, s in enumerate(self.lib.songs)})
        for x in (mock.patch.object(web.CACHE, "get", lambda: self.lib), mock.patch.object(web, "load_config", config)):
            x.start()
            self.addCleanup(x.stop)

    def get(self, path, key=None):
        status, _h, body = request("GET", path, headers={"Authorization": f"Bearer {key}"} if key else {})
        return int(status.split()[1]), json.loads(body or b"null")

    def test_only_with_the_key(self):
        self.assertEqual(self.get("/api/sonic/similar?id=Eisen-0")[0], 401)            # no key set up at all
        key = sonic.new_key()
        self.assertEqual(self.get("/api/sonic/similar?id=Eisen-0")[0], 401)            # none sent
        self.assertEqual(self.get("/api/sonic/similar?id=Eisen-0", "tp_wrong")[0], 401)
        status, body = self.get("/api/sonic/similar?id=Eisen-0&count=4", key)
        self.assertEqual((status, len(body["songs"])), (200, 4))
        self.assertEqual(self.get("/api/sonic/path?from=Eisen-0&to=Harfe-0&count=5", key)[1]["songs"][-1]["id"], "Harfe-0")
        self.assertEqual(self.get("/api/sonic/artists?name=Eisen&count=3", key)[0], 200)
        self.assertEqual(self.get("/api/sonic/whatever", key)[0], 400)

    def test_admin_functions(self):
        for path in ("/api/plugin", "/api/plugin/key", "/api/plugin/key/remove", "/plugin/tuttiphon.ndp"):
            self.assertIn(path, web.Handler.ADMIN_ONLY)
        status, body = self.get("/api/plugin")   # local without a password: the administrator
        self.assertEqual((status, body["key"]), (200, False))
        with mock.patch.object(sonic, "PLUGIN_FILES", (env.ROOT / "nothing.ndp",)):
            self.assertEqual(request("GET", "/plugin/tuttiphon.ndp")[0].split()[1], "404")
        ndp = env.ROOT / "tuttiphon.ndp"
        ndp.write_bytes(b"PK-test")
        self.addCleanup(ndp.unlink)
        with mock.patch.object(sonic, "PLUGIN_FILES", (ndp,)):
            status, headers, body = request("GET", "/plugin/tuttiphon.ndp")
        self.assertEqual((status.split()[1], headers["content-type"], body), ("200", "application/zip", b"PK-test"))
        status, _h, body = request("POST", "/api/plugin/key", b"{}")
        key = json.loads(body)["key"]
        self.assertTrue(sonic.check_key(key))


if __name__ == "__main__":
    unittest.main()
