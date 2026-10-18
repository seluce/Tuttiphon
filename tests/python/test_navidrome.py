"""Navidrome access: a missing or invalid address or missing credentials lead to an understandable NavidromeError –
not to a ValueError from urllib, which would otherwise answer every page of the interface with an error."""
from tests.python import env  # noqa: F401  (before app.*)

import unittest

from app.navidrome import Navidrome, NativeApi, NavidromeError


@env.german   # checks the German output of existing installations
class TestAccess(unittest.TestCase):
    def test_missing_url(self):
        for cls in (Navidrome, NativeApi):
            with self.assertRaisesRegex(NavidromeError, "Adresse fehlt"):
                cls("", "root", "pw")

    def test_invalid_url(self):
        for cls in (Navidrome, NativeApi):
            with self.assertRaisesRegex(NavidromeError, "ungültig"):
                cls("192.168.1.10:4533", "root", "pw")

    def test_missing_credentials(self):
        with self.assertRaisesRegex(NavidromeError, "unvollständig"):
            Navidrome("http://navidrome.invalid", "root", "")
        with self.assertRaisesRegex(NavidromeError, "Admin-Zugang fehlt"):
            NativeApi("http://navidrome.invalid", None, None)


if __name__ == "__main__":
    unittest.main()
