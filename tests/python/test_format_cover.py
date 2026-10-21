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
        car = playlist("car", welt=["kinder", "metal"], together=["jonas", "oma"], name="Autofahrt")   # the car ride
        self.assertIsNone(covers.format_kind(car))
        self.assertIsNone(covers.format_kind({**playlist("f"), "welt": "metal", "type": None, "fav": {"days": 60}}))
        self.assertEqual(covers.format_kind({**playlist("f"), "type": None, "fav": {"days": 60}}), "fav")
        self.assertEqual(covers.format_kind(playlist("t", together=["jonas", "oma"])), "together")
        plain = {**playlist("p"), "welt": "kinder", "type": None}
        self.assertIsNone(covers.format_kind(plain))
        self.assertIsNone(covers.default_style(plain))
        self.assertNotIn("format", covers.available_styles(plain))
        if covers.HAVE_PIL:
            self.assertEqual(covers.default_style(playlist("u", unheard=True)), "format")
            self.assertEqual(next(iter(covers.available_styles(playlist("u", unheard=True)))), "format")   # first

    def test_format_signature_follows_its_texts(self):
        cfg = base_config()
        pv = {"covers": ["c1"], "topArtists": [], "name": "Entdeckt für Jonas", "color": None}
        p = playlist("u", unheard=True)
        with mock.patch.object(covers.rules, "preview", lambda *a, **k: pv):
            before, plain = covers.signature(cfg, None, p, "format"), covers.signature(cfg, None, p)
            cfg["personen"][1]["name"] = "Jona"   # "for Jona" on the cover now
            self.assertNotEqual(covers.signature(cfg, None, p, "format"), before)
            self.assertEqual(covers.signature(cfg, None, p), plain)   # the other styles as before

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
    def run_refresh(self, cfg, by_file, reported=None, dropped=None, images=None):
        native = mock.Mock()
        native.playlists.return_value = [{"id": nid, "uploadedImage": img} for nid, img in (reported or {}).items()]
        native.playlist_image.side_effect = lambda nid: images[nid] if images and isinstance(images[nid], bytes) \
            else (_ for _ in ()).throw(OSError("gone"))
        with mock.patch.object(covers, "render", lambda *a: JPEG), \
                mock.patch.object(covers, "signature", lambda *a: "sig1"), \
                mock.patch.object(covers, "load_config", lambda: copy.deepcopy(cfg)):
            n = covers.refresh_auto(cfg, Library([]), native, by_file, log=lambda *a: None, dropped=dropped)
        self.native = native
        return n, native.upload_playlist_image.call_args_list

    def test_a_format_gets_its_cover_once(self):
        cfg = base_config()
        cfg["playlists"] = [playlist("u", unheard=True), {**playlist("p"), "welt": "kinder", "type": None}]
        by_file = {"u.nsp": {"id": "n-u"}, "p.nsp": {"id": "n-p"}}
        n, calls = self.run_refresh(cfg, by_file, reported={"n-u": "n-u_1.jpg"})
        self.assertEqual((n, [c.args[0] for c in calls]), (1, ["n-u"]))   # not the ordinary playlist
        cv = cfg["playlists"][0]["cover"]
        self.assertEqual((cv["style"], cv["auto"], cv["sig"], cv["nid"], cv["img"]), ("format", True, "sig1", "n-u", "n-u_1.jpg"))
        self.assertNotIn("cover", cfg["playlists"][1])
        by_file["u.nsp"]["uploadedImage"] = "n-u_1.jpg"   # our own image
        self.assertEqual(self.run_refresh(cfg, by_file)[0], 0)   # unchanged material: nothing again

    def test_not_over_an_image_or_after_removing(self):
        cfg = base_config()
        cfg["playlists"] = [playlist("u", unheard=True), playlist("a", album=True, cover={"style": "none"}),
                            playlist("m", daytime="morning", status="pausiert")]
        by_file = {"u.nsp": {"id": "n-u", "uploadedImage": "set-by-hand.jpg"}, "a.nsp": {"id": "n-a"}, "m.nsp": {"id": "n-m"}}
        self.assertEqual(self.run_refresh(cfg, by_file), (0, []))
        self.assertNotIn("cover", cfg["playlists"][0])

    def test_an_image_set_later_in_navidrome_stays(self):
        cfg = base_config()
        ours = {"style": "format", "auto": True, "sig": "old", "nid": "n-u", "img": "n-u_1.jpg"}
        cfg["playlists"] = [playlist("u", unheard=True, cover=dict(ours)), playlist("d", unheard=True, cover=dict(ours, nid="n-d"))]
        by_file = {"u.nsp": {"id": "n-u", "uploadedImage": "n-u_2.jpg"},   # set by hand in Navidrome
                   "d.nsp": {"id": "n-d", "uploadedImage": ""}}            # removed there
        n, calls = self.run_refresh(cfg, by_file)
        self.assertEqual((n, calls), (2, []))   # nothing uploaded over it
        self.assertEqual(cfg["playlists"][0]["cover"]["style"], "navidrome")
        self.assertEqual(cfg["playlists"][1]["cover"]["style"], "none")

    def test_same_name_another_image_stays(self):
        """Navidrome names the image after the playlist – an image of the same type set by hand keeps the name, its
        content tells."""
        cfg = base_config()
        ours = {"style": "format", "auto": True, "sig": "old", "img": "n_tuttiphon.jpeg", "hash": covers.digest(JPEG)}
        cfg["playlists"] = [playlist("u", unheard=True, cover=dict(ours, nid="n-u")),
                            playlist("k", unheard=True, cover=dict(ours, nid="n-k")),
                            playlist("g", unheard=True, cover=dict(ours, nid="n-g"))]
        by_file = {f"{x}.nsp": {"id": f"n-{x}", "uploadedImage": "n_tuttiphon.jpeg"} for x in "ukg"}
        n, calls = self.run_refresh(cfg, by_file, images={"n-u": b"set by hand", "n-k": JPEG, "n-g": None})
        self.assertEqual(cfg["playlists"][0]["cover"]["style"], "navidrome")   # not overwritten
        self.assertEqual(sorted(c.args[0] for c in calls), ["n-g", "n-k"])     # still ours / unknown: renewed
        self.assertEqual(cfg["playlists"][1]["cover"]["hash"], covers.digest(JPEG))
        self.assertEqual(n, 3)

    def test_no_longer_a_format(self):
        cfg = base_config()
        cfg["playlists"] = [{**playlist("r"), "welt": "kinder", "stil": "wiederentdecken", "type": None,
                             "cover": {"style": "format", "auto": True, "sig": "x", "nid": "n-r"}}]
        dropped = set()
        n, calls = self.run_refresh(cfg, {"r.nsp": {"id": "n-r"}}, dropped=dropped)
        self.assertEqual((n, calls, dropped), (1, [], {"r"}))
        self.native.delete_playlist_image.assert_called_once_with("n-r")
        self.assertNotIn("cover", cfg["playlists"][0])

    def test_writing_back_respects_changes_in_between(self):
        from app import config, tasks
        stored = base_config()
        stored["playlists"] = [playlist("u", unheard=True), playlist("d", unheard=True), playlist("r", unheard=True,
                               cover={"style": "format", "auto": True, "sig": "x", "nid": "n-r"})]
        meanwhile = copy.deepcopy(stored)
        meanwhile["playlists"][1]["cover"] = {"style": "none"}   # removed while the run was uploading

        def refresh(cfg, lib, native, by_file, log=None, dropped=None):
            for p in cfg["playlists"]:
                if p["id"] in ("u", "d"):
                    p["cover"] = {"style": "format", "auto": True, "sig": "s", "nid": f"n-{p['id']}"}
                else:
                    p["cover"]["sig"] = "new"
            return 3
        native = mock.Mock()
        with mock.patch.object(tasks, "load_config", lambda: copy.deepcopy(stored)), \
                mock.patch.object(tasks, "update_config", lambda fn: fn(meanwhile)), \
                mock.patch.object(covers, "refresh_auto", refresh), \
                mock.patch.object(tasks.playlists, "native_api", lambda env: native), \
                mock.patch.object(tasks.playlists, "navidrome_index", lambda native, cfg: {}):
            tasks.TaskRunner()._refresh_covers({}, mock.Mock())
        got = {p["id"]: p.get("cover") for p in meanwhile["playlists"]}
        self.assertEqual(got["u"]["nid"], "n-u")            # new auto cover written
        self.assertEqual(got["d"], {"style": "none"})       # the removal wins …
        native.delete_playlist_image.assert_called_once_with("n-d")   # … and the image goes again
        self.assertEqual(got["r"]["sig"], "new")


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
