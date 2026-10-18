"""The server log (stdout – docker logs) is always English, whatever the server language; the run log in the
interface keeps the server language."""
from tests.python import env  # noqa: F401  (before app.*)

import copy
import io
import json
import unittest
from contextlib import redirect_stdout

from app import events, i18n, tasks
from app.i18n import _, _s, _sn, english, join, said


@env.german   # the run log in German, the server log in English
class ServerLogTest(unittest.TestCase):
    def printed(self, fn):
        out = io.StringIO()
        with redirect_stdout(out):
            fn()
        return [line.split("] ", 1)[1] for line in out.getvalue().splitlines()]

    def test_translated_text_knows_its_english_form(self):
        text = _s("Tuttiphon {version} is starting", version="1.0")
        self.assertEqual(text, "Tuttiphon 1.0 startet")
        self.assertEqual(english(text), "Tuttiphon 1.0 is starting")
        self.assertEqual(english(_sn(2, "{n} song in Navidrome.", "{n} songs in Navidrome.")), "2 songs in Navidrome.")
        self.assertEqual(english(_("Shut down.")), "Shut down.")
        nested = _s("Canceling the running task “{name}”, saving its progress …", name=_s("Update everything"))
        self.assertIn("Alles aktualisieren", nested)
        self.assertEqual(english(nested), "Canceling the running task “Update everything”, saving its progress …")

    def test_gluing_keeps_both_forms(self):
        line = "▶ " + _s("Update everything") + " – 18.10.2026"
        self.assertEqual((line, english(line)), ("▶ Alles aktualisieren – 18.10.2026", "▶ Update everything – 18.10.2026"))
        both = join(", ", [_s("{step}: ok", step=_s("Write playlists")), "x"])
        self.assertEqual(english(both), "Write playlists: ok, x")
        error = RuntimeError(_s("A task is already running."))
        self.assertEqual(english("❌ " + said(error)), "❌ A task is already running.")
        self.assertEqual(english(_s("(Startup overview not possible: {error})", error=error)),
                         "(Startup overview not possible: A task is already running.)")

    def test_stays_a_normal_string(self):
        text = _s("Shut down.")
        self.assertEqual(json.dumps({"a": text}, ensure_ascii=False), '{"a": "Beendet."}')
        self.assertEqual(english(copy.deepcopy({"a": text})["a"]), "Shut down.")
        self.assertEqual({text: 1}["Beendet."], 1)
        self.assertEqual(english("plain"), "plain")

    def test_events_print_english(self):
        lines = self.printed(lambda: events.say(_s("Backup failed: {error}", error=_s("Shut down."))))
        self.assertEqual(lines, ["Backup failed: Shut down."])

    def test_run_log_in_server_language_server_log_in_english(self):
        runner = tasks.TaskRunner()
        lines = self.printed(lambda: (runner.log("━━ " + _s("Write playlists") + " ━━"),
                                      runner.log(_s("  ✓ Original archived."))))
        self.assertEqual(lines, ["━━ Write playlists ━━"])   # indented lines stay in the run log only
        self.assertEqual([x[2] for x in runner.lines][-2:], ["━━ Playlists schreiben ━━", "  ✓ Original archiviert."])


if __name__ == "__main__":
    unittest.main()
