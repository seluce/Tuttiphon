"""Compression: text answers go out with gzip when the browser accepts it – files of the build folder compressed once
per version, JSON on the fly; small answers, images and browsers without gzip get the plain form. Real server on
127.0.0.1 with a temp build folder; no network."""
from tests.python import env  # noqa: F401  (before app.*)

import email.message
import gzip
import http.client
import io
import json
import os
import socket
import threading
import unittest
from http.server import ThreadingHTTPServer
from unittest import mock

from app import web

SCRIPT = ("export function hallo(name) { return 'Hallo ' + name }\n" * 200).encode()


def _loopback(address, *args, **kwargs):
    """Only for this test: connections to 127.0.0.1 (otherwise the test environment blocks every network)."""
    if address[0] != "127.0.0.1":
        raise env.NetworkBlocked("only 127.0.0.1")
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(10)
    env._real_connect(s, address)
    return s


class BuildFolderTest(unittest.TestCase):
    def setUp(self):
        env.reset_caches()
        web._packed_files.clear()
        self.assets = web.WEB_DIR / "assets"
        self.assets.mkdir(parents=True, exist_ok=True)
        self.files = {"app-test.js": SCRIPT, "tiny-test.js": b"export const a = 1\n",
                      "pic-test.png": b"\x89PNG\r\n\x1a\n" + bytes(4000)}
        for name, data in self.files.items():
            (self.assets / name).write_bytes(data)
            self.addCleanup((self.assets / name).unlink, missing_ok=True)
        server = ThreadingHTTPServer(("127.0.0.1", 0), web.Handler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        self.port = server.server_address[1]

    def get(self, path, accept="gzip, deflate, br", method="GET"):
        with mock.patch("socket.create_connection", _loopback):
            c = http.client.HTTPConnection("127.0.0.1", self.port, timeout=10)
            c.request(method, path, headers={"Accept-Encoding": accept} if accept else {})
            r = c.getresponse()
            body = r.read()
            c.close()
        return r, body

    def test_scripts_go_out_compressed(self):
        r, body = self.get("/assets/app-test.js")
        self.assertEqual(r.status, 200)
        self.assertEqual((r.getheader("Content-Encoding"), r.getheader("Vary")), ("gzip", "Accept-Encoding"))
        self.assertEqual(int(r.getheader("Content-Length")), len(body))
        self.assertLess(len(body), len(SCRIPT) / 3)
        self.assertEqual(gzip.decompress(body), SCRIPT)
        self.assertIn("immutable", r.getheader("Cache-Control"))

    def test_compressed_once_and_again_after_a_new_build(self):
        self.get("/assets/app-test.js")
        with mock.patch.object(web.gzip, "compress", side_effect=AssertionError("compressed again")):
            self.assertEqual(gzip.decompress(self.get("/assets/app-test.js")[1]), SCRIPT)   # from memory
        new = SCRIPT + b"// new build\n"
        path = self.assets / "app-test.js"
        path.write_bytes(new)
        os.utime(path, ns=(path.stat().st_atime_ns, path.stat().st_mtime_ns + 10 ** 9))
        self.assertEqual(gzip.decompress(self.get("/assets/app-test.js")[1]), new)

    def test_plain_without_gzip(self):
        for accept in (None, "br", "gzip;q=0", "identity"):
            r, body = self.get("/assets/app-test.js", accept)
            self.assertIsNone(r.getheader("Content-Encoding"), accept)
            self.assertEqual(body, SCRIPT)
            self.assertEqual(r.getheader("Vary"), "Accept-Encoding")   # a cache in between keeps both forms apart

    def test_small_files_and_images_stay_as_they_are(self):
        for name in ("tiny-test.js", "pic-test.png"):
            r, body = self.get(f"/assets/{name}")
            self.assertIsNone(r.getheader("Content-Encoding"), name)
            self.assertIsNone(r.getheader("Vary"), name)
            self.assertEqual(body, self.files[name])

    def test_head_announces_the_same_length(self):
        got, body = self.get("/assets/app-test.js")
        head, empty = self.get("/assets/app-test.js", method="HEAD")
        self.assertEqual(empty, b"")
        self.assertEqual(head.getheader("Content-Encoding"), "gzip")
        self.assertEqual(head.getheader("Content-Length"), got.getheader("Content-Length"))


class JsonTest(unittest.TestCase):
    class Fake(web.Handler):
        def __init__(self, accept=None):   # no connection: only what _send needs
            self.headers = email.message.Message()
            if accept:
                self.headers["Accept-Encoding"] = accept
            self.command, self.wfile, self.sent, self.code = "GET", io.BytesIO(), {}, None

        def send_response(self, code, message=None):
            self.code = code

        def send_header(self, key, value):
            self.sent[key] = value

        def end_headers(self):
            pass

    def test_large_answers_compressed(self):
        data = {"songs": [{"id": f"s{i}", "title": "Lied über Bäume"} for i in range(200)]}
        h = self.Fake("gzip")
        h._json(data)
        self.assertEqual((h.code, h.sent["Content-Encoding"], h.sent["Cache-Control"]), (200, "gzip", "no-store"))
        self.assertEqual(json.loads(gzip.decompress(h.wfile.getvalue())), data)
        self.assertEqual(int(h.sent["Content-Length"]), len(h.wfile.getvalue()))
        plain = self.Fake()
        plain._json(data)
        self.assertNotIn("Content-Encoding", plain.sent)
        self.assertEqual(json.loads(plain.wfile.getvalue()), data)

    def test_small_answers_and_errors_plain(self):
        h = self.Fake("gzip")
        h._json({"error": "not found"}, 404)   # i18n-ignore – technical code
        self.assertNotIn("Content-Encoding", h.sent)
        self.assertEqual(json.loads(h.wfile.getvalue()), {"error": "not found"})   # i18n-ignore – technical code

    def test_downloads_stay_as_they_are(self):
        h = self.Fake("gzip")
        h._send(bytes(5000), "application/zip", headers={"Content-Disposition": 'attachment; filename="x.zip"'})
        self.assertNotIn("Content-Encoding", h.sent)
        self.assertEqual(len(h.wfile.getvalue()), 5000)


class AcceptHeaderTest(unittest.TestCase):
    def test_takes_gzip(self):
        for accept, ok in (("gzip", True), ("gzip, deflate, br, zstd", True), ("br;q=1.0, GZIP;q=0.5", True),
                           ("gzip;q=0", False), ("gzip;q=0.0", False), ("gzip;q=x", False), ("deflate", False),
                           ("x-gzip", False), ("", False), (None, False)):
            self.assertEqual(web._takes_gzip(accept), ok, accept)


if __name__ == "__main__":
    unittest.main()
