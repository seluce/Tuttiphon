"""Notifications in other server languages: the run that processed new music is recognized in every language, and a
translation that fails falls back to English instead of stopping (or repeating) the message."""
from tests.python import env  # noqa: F401  (before app.*)

import unittest
from unittest import mock

from app import i18n, notify, webpush
from tests.python.factory import base_config


class NotifyLanguageTest(unittest.TestCase):
    def setUp(self):
        self.cfg = base_config()
        self.cfg["settings"]["notify"] = {"enabled": True, "events": {}, "topic": "admin-topic"}

    def test_new_music_in_another_server_language(self):
        sent = []
        with mock.patch.object(i18n, "server_lang", lambda: "fr"):
            name = i18n._sn(3, "Process new music ({n} file)", "Process new music ({n} files)")
            self.assertFalse(str(name).startswith(notify.NEW_MUSIC_RUN))   # French – the English form tells
            with mock.patch.object(notify, "deliver", lambda make, *a, **k: sent.append(make()) or True):
                notify.after_run({"name": name, "results": {"flac": "ok", "playlists": "ok"}, "summary": {}}, self.cfg)
        self.assertEqual(len(sent), 1)

    def test_a_broken_translation_falls_back_to_english(self):
        calls = []

        def make():
            calls.append(i18n.server_lang())
            if i18n.server_lang() == "fr":
                raise KeyError("a translated format that does not fit")
            return "Title", "Text"
        subs = {"anna": [{"endpoint": "https://push.example/1", "lang": "fr"},
                         {"endpoint": "https://push.example/2", "lang": "de"}]}
        got = []
        with mock.patch.object(webpush, "available", lambda: (True, "")), mock.patch.object(webpush, "_load", lambda: subs), \
                mock.patch.object(webpush, "send", lambda sub, title, body, path="", tag=None: got.append((sub["endpoint"], title)) or True):
            self.assertTrue(webpush.send_to(None, None, "#/", accounts=["anna"], make=make))
        self.assertEqual(sorted(got), [("https://push.example/1", "Title"), ("https://push.example/2", "Title")])
        self.assertIn("en", calls)   # French failed: English instead
        self.assertEqual(notify._in("fr", make), ("Title", "Text"))


if __name__ == "__main__":
    unittest.main()
