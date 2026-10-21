"""Downloading the AI models while the image is built (ml_worker.download): from essentia.upf.edu with pauses between
the attempts; if it does not answer, the rest from the copy in the releases (one zip) – every file only with the
right checksum. Made-up files, no network."""
from tests.python import env  # noqa: F401  (before app.*)

import hashlib
import io
import os
import tempfile
import unittest
import zipfile
from unittest import mock

from app import ml_worker

DATA = {name: f"model {name}".encode() for name in ml_worker.FILES}
SUMS = {name: hashlib.sha256(data).hexdigest() for name, data in DATA.items()}


def mirror_zip(files):
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w") as z:
        for name, data in files.items():
            z.writestr(name, data)
        z.writestr("README.txt", "license note")
    return out.getvalue()


class DownloadTest(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.mkdtemp(dir=env.ROOT)
        self.calls = []
        for p in (mock.patch.dict(ml_worker.FILES, SUMS), mock.patch.object(ml_worker.time, "sleep", lambda s: None),
                  mock.patch.dict(os.environ, {"TUTTIPHON_MODELS_MIRROR": "https://mirror.test/models.zip"})):
            p.start()
            self.addCleanup(p.stop)

    def run_with(self, fetch):
        def recorder(url, timeout=60):
            self.calls.append(url)
            return fetch(url)
        with mock.patch.object(ml_worker, "_fetch", recorder), mock.patch("builtins.print"):
            return ml_worker.download(self.folder)

    def test_from_the_source(self):
        self.assertTrue(self.run_with(lambda url: DATA[url.rsplit("/", 1)[1]]))
        self.assertEqual(ml_worker.missing_models(self.folder), [])
        self.assertFalse(any("mirror" in u for u in self.calls))

    def test_a_short_outage_passes(self):
        failed = set()

        def flaky(url):
            name = url.rsplit("/", 1)[1]
            if name not in failed:   # every file fails once
                failed.add(name)
                raise OSError("504 Gateway Timeout")
            return DATA[name]
        self.assertTrue(self.run_with(flaky))
        self.assertFalse(any("mirror" in u for u in self.calls))

    def test_source_down_the_copy_fills_in(self):
        def down(url):
            if "mirror" in url:
                return mirror_zip(DATA)
            raise OSError("504 Gateway Timeout")
        self.assertTrue(self.run_with(down))
        self.assertEqual(ml_worker.missing_models(self.folder), [])
        self.assertEqual(sum("essentia" in u for u in self.calls), len(ml_worker.WAITS))   # gives up after one file
        self.assertEqual(sum("mirror" in u for u in self.calls), 1)

    def test_only_with_the_right_checksum(self):
        bad = {**DATA, next(iter(DATA)): b"something else"}
        self.assertFalse(self.run_with(lambda url: mirror_zip(bad) if "mirror" in url else (_ for _ in ()).throw(OSError("down"))))
        self.assertEqual(ml_worker.missing_models(self.folder), [next(iter(DATA))])

    def test_without_a_copy(self):
        with mock.patch.dict(os.environ, {"TUTTIPHON_MODELS_MIRROR": ""}):
            self.assertFalse(self.run_with(lambda url: (_ for _ in ()).throw(OSError("down"))))
        self.assertFalse(any("mirror" in u for u in self.calls))


if __name__ == "__main__":
    unittest.main()
