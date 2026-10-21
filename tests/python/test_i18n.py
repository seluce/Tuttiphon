"""Languages of the server texts: English source, German from app/locales/de; the request language for answers,
the server language (settings.language) for everything written down; the dictionaries ship with the program."""
from tests.python import env  # noqa: F401  (before app.*)

import copy
import json
import threading
import unittest
from unittest import mock

from app import config, i18n
from tests.python.factory import base_config


class LanguagesTest(unittest.TestCase):
    def setUp(self):
        env.reset_caches()
        i18n.use(None)
        i18n.forget_server_lang()
        self.addCleanup(i18n.use, None)
        self.addCleanup(i18n.forget_server_lang)

    def save_language(self, lang):
        cfg = base_config()
        cfg["settings"]["language"] = lang
        config.save_config(cfg)
        self.addCleanup(env.reset_caches)

    def test_german_dictionaries_ship_with_the_program(self):
        files = sorted(i18n.LOCALES.joinpath("de").glob("*.json"))
        self.assertTrue(files)
        for f in files:
            self.assertIsInstance(json.loads(f.read_text(encoding="utf-8")), dict, f.name)
        self.assertEqual(i18n.tr("Settings: unknown language", "de"), "Einstellungen: Sprache unbekannt")

    def test_server_language_for_written_texts(self):
        self.save_language("de")
        self.assertEqual(i18n._s("  ✓ Original archived."), "  ✓ Original archiviert.")
        i18n.use("en")                                                  # the page is English …
        self.assertEqual(i18n._("  ✓ Original archived."), "  ✓ Original archived.")
        self.assertEqual(i18n._s("  ✓ Original archived."), "  ✓ Original archiviert.")   # … the log stays German
        self.save_language("en")
        i18n.forget_server_lang()
        i18n.use(None)
        self.assertEqual(i18n._s("  ✓ Original archived."), "  ✓ Original archived.")

    def test_request_language_is_per_thread(self):
        self.save_language("en")
        i18n.use("de")
        seen = []
        t = threading.Thread(target=lambda: seen.append(i18n._("  ✓ Original archived.")))
        t.start()
        t.join()
        self.assertEqual(seen, ["  ✓ Original archived."])            # other threads: server language
        self.assertEqual(i18n._("  ✓ Original archived."), "  ✓ Original archiviert.")

    def test_values_counts_and_unknown(self):
        i18n.use("de")
        self.assertEqual(i18n._("Done: {ok} converted, {failed} errors.", ok=3, failed=0), "Fertig: 3 umgewandelt, 0 Fehler.")
        self.assertEqual(i18n._("not in any dictionary {x}", x=1), "not in any dictionary 1")   # missing → English
        self.assertEqual(i18n.N_("Done"), "Done")                      # only marks
        i18n.use("fr")                                                  # unknown language → server language
        self.assertIn(i18n.current(), i18n.LANGS)

    def test_new_server_language_renames_only_delivered_names(self):
        cfg = copy.deepcopy(config.default_config())
        cfg["settings"]["language"] = "en"
        tanzen = next(s for s in cfg["stile"] if s["id"] == "tanzen")
        tanzen["name"] = "Dance & Romp"
        own = next(s for s in cfg["stile"] if s["id"] == "rock")
        own["name"] = "Unsere Rockmusik"                                # chosen by someone – stays
        config.save_config(cfg)
        self.addCleanup(env.reset_caches)
        cfg["settings"]["language"] = "de"
        config.save_from_ui(cfg)
        fresh = {s["id"]: s["name"] for s in config.load_config()["stile"]}
        self.assertEqual((fresh["tanzen"], fresh["rock"]), ("Tanzen & Toben", "Unsere Rockmusik"))
        self.assertEqual(i18n.tr(config.default_config()["settings"]["allName"], "de"), "Alle")

    def test_scene_names_follow_the_language(self):
        from app import scenes
        i18n.use("en")
        self.assertEqual(scenes.scene("kinder")["name"], "Kids' music")
        i18n.use("de")
        self.assertEqual(scenes.scene("kinder")["name"], "Kindermusik")
        self.assertIs(scenes.catalog(), scenes.catalog())                # stable per language (cache keys use id())

    def test_language_setting_is_checked(self):
        cfg = base_config()
        cfg["settings"]["language"] = "xx"
        with self.assertRaises(ValueError):
            config.validate_config(cfg)
        cfg["settings"]["language"] = "pl"
        config.validate_config(cfg)

    def test_status_sends_the_name_templates_of_the_server_language(self):
        """The interface builds the name of a new playlist like the server – with the server's templates."""
        import json
        from tests.python.test_audit_server import request
        with mock.patch.object(i18n, "server_lang", lambda: "de"):
            status, _h, content = request("GET", "/api/status")
        names = json.loads(content)["names"]
        self.assertEqual((names["all"], names["hits"], names["everything"]), ("{world} · Querbeet", "{world} · Die Hits", "Alles"))

    def test_plural_forms(self):
        """A count picks its form by the rules of the language – Polish has several, French counts 0 as one; the
        English form for the log follows the English rules."""
        self.assertEqual([i18n.category(n, "pl") for n in (1, 2, 4, 5, 12, 22, 25, 0)],
                         ["one", "few", "few", "many", "many", "few", "many", "many"])
        self.assertEqual([i18n.category(n, "fr") for n in (0, 1, 2)], ["one", "one", "other"])
        self.assertEqual([i18n.category(n, "de") for n in (0, 1, 2)], ["other", "one", "other"])
        fake = {"pl": {"{n} song": "{n} piosenka", "{n} songs": {"few": "{n} piosenki", "many": "{n} piosenek"}},
                "fr": {"{n} song": "{n} chanson", "{n} songs": "{n} chansons"}}
        with mock.patch.dict(i18n._dicts, fake):
            i18n.use("pl")
            self.assertEqual([str(i18n._n(n, "{n} song", "{n} songs")) for n in (1, 3, 5)],
                             ["1 piosenka", "3 piosenki", "5 piosenek"])
            self.assertEqual(i18n._n(5, "{n} song", "{n} songs").en, "5 songs")
            i18n.use("fr")
            zero = i18n._n(0, "{n} song", "{n} songs")
            self.assertEqual((str(zero), zero.en), ("0 chanson", "0 songs"))
            self.assertEqual(i18n.tr("{n} songs", "pl"), "{n} piosenek")   # without a count: a form all the same
        i18n.use(None)


if __name__ == "__main__":
    unittest.main()
