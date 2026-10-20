"""Covers of the formats (covers.py): which playlist is a format, the format cover is offered only there, a format
without a cover gets it by itself (not over an image set in Navidrome, not after it was removed)."""
from tests.python import env  # noqa: F401  (before app.*)

import copy
import io
import unittest
from unittest import mock

from app import covers, web
from app.rules import Library
from tests.python.factory import base_config, song

JPEG = b"\xff\xd8\xff\xe0format"


def playlist(pid, **extra):
    return {"id": pid, "person": "jonas", "welt": "*", "stil": "*", "type": "mix", "file": f"{pid}.nsp",
            "mix": {"every": "week"}, **extra}


class KindTest(unittest.TestCase):
    def test_formats_and_their_style(self):
        self.assertEqual(covers.format_kind(playlist("a", album=True)), "album")
        self.assertEqual(covers.format_kind(playlist("u", unheard=True)), "unheard")
        self.assertEqual(covers.format_kind(playlist("m", daytime="morning")), "morning")
        self.assertEqual(covers.format_kind(playlist("s", mix={"flavor": "geschmack"})), "sound")
        self.assertEqual(covers.format_kind({**playlist("r"), "stil": "wiederentdecken", "type": None}), "rediscover")
        self.assertIsNone(covers.format_kind({**playlist("r"), "welt": "kinder", "stil": "wiederentdecken", "type": None}))
        plain = {**playlist("p"), "welt": "kinder", "type": None}
        self.assertIsNone(covers.format_kind(plain))
        self.assertIsNone(covers.default_style(plain))
        self.assertNotIn("format", covers.available_styles(plain))
        if covers.HAVE_PIL:
            self.assertEqual(covers.default_style(playlist("u", unheard=True)), "format")
            self.assertEqual(next(iter(covers.available_styles(playlist("u", unheard=True)))), "format")   # first

    @unittest.skipUnless(covers.HAVE_PIL, "needs Pillow")
    @env.german
    def test_render(self):
        from PIL import Image
        cfg = base_config()
        lib = Library([song(f"s{k}", artist="Gruppe A", album="Platte", genres=("Pop",), rating=4) for k in range(10)])
        with mock.patch.object(covers.images, "get_image", lambda *a, **k: None):   # no album art here
            data = covers.render(cfg, lib, playlist("a", album=True), "format")
        im = Image.open(io.BytesIO(data))
        self.assertEqual((im.format, im.size), ("JPEG", (covers.SIZE, covers.SIZE)))
        self.assertEqual(covers.format_title(cfg, playlist("a", album=True), "x"), "Album der Woche")
        self.assertEqual(covers.format_title(cfg, playlist("s", mix={"flavor": "geschmack"}), "Mein Sound"), "Mein Sound")


@unittest.skipUnless(covers.HAVE_PIL, "needs Pillow")
class AutoTest(unittest.TestCase):
    def run_refresh(self, cfg, by_file):
        native = mock.Mock()
        with mock.patch.object(covers, "render", lambda *a: JPEG), \
                mock.patch.object(covers, "signature", lambda *a: "sig1"), \
                mock.patch.object(covers, "load_config", lambda: copy.deepcopy(cfg)):
            n = covers.refresh_auto(cfg, Library([]), native, by_file, log=lambda *a: None)
        return n, native.upload_playlist_image.call_args_list

    def test_a_format_gets_its_cover_once(self):
        cfg = base_config()
        cfg["playlists"] = [playlist("u", unheard=True), {**playlist("p"), "welt": "kinder", "type": None}]
        by_file = {"u.nsp": {"id": "n-u"}, "p.nsp": {"id": "n-p"}}
        n, calls = self.run_refresh(cfg, by_file)
        self.assertEqual((n, [c.args[0] for c in calls]), (1, ["n-u"]))   # not the ordinary playlist
        cv = cfg["playlists"][0]["cover"]
        self.assertEqual((cv["style"], cv["auto"], cv["sig"], cv["nid"]), ("format", True, "sig1", "n-u"))
        self.assertNotIn("cover", cfg["playlists"][1])
        self.assertEqual(self.run_refresh(cfg, by_file)[0], 0)   # unchanged material: nothing again

    def test_not_over_an_image_or_after_removing(self):
        cfg = base_config()
        cfg["playlists"] = [playlist("u", unheard=True), playlist("a", album=True, cover={"style": "none"}),
                            playlist("m", daytime="morning", status="pausiert")]
        by_file = {"u.nsp": {"id": "n-u", "uploadedImage": "set-by-hand.jpg"}, "a.nsp": {"id": "n-a"}, "m.nsp": {"id": "n-m"}}
        self.assertEqual(self.run_refresh(cfg, by_file), (0, []))
        self.assertNotIn("cover", cfg["playlists"][0])


class RemoveTest(unittest.TestCase):
    def remove(self, p):
        fresh = {"playlists": [copy.deepcopy(p)]}
        native = mock.Mock()
        with mock.patch.object(web, "_own_playlist_id", lambda pid: p), \
                mock.patch.object(web, "_navidrome_playlist", lambda x: (native, {"id": "n1"})), \
                mock.patch.object(web, "update_config", lambda fn: fn(fresh)), \
                mock.patch.object(covers, "forget_own", lambda pid: None):
            web.api_cover_remove({"id": p["id"]})
        native.delete_playlist_image.assert_called_once_with("n1")
        return fresh["playlists"][0].get("cover")

    @unittest.skipUnless(covers.HAVE_PIL, "needs Pillow")
    def test_a_removed_format_cover_stays_away(self):
        self.assertEqual(self.remove(playlist("u", unheard=True, cover={"style": "format", "auto": True})), {"style": "none"})

    def test_an_ordinary_playlist_has_none_again(self):
        self.assertIsNone(self.remove({**playlist("p"), "type": None, "welt": "kinder", "cover": {"style": "mosaik"}}))


if __name__ == "__main__":
    unittest.main()
