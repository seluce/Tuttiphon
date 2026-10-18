"""“Mix” only for real mixes: a smart playlist with a whole music world (or all favorite worlds of a person) is called
“All Sorts” / “Querbeet”. Generated names follow the server language; configuration v8 renames the stored
“Linus’ Mix” of earlier suggestions, names someone typed stay. Also: the “New: <band>” entry of “To review” opens
the band window. Temp folder only, no network."""
from tests.python import env  # noqa: F401  (before app.*)

import datetime as dt
import unittest
from unittest import mock

from app import config, i18n, rules, suggest
from app.rules import BuildContext, Library
from tests.python.factory import base_config, iso_days_ago, song

OCT = dt.date(2026, 10, 12)


def english(target):
    return mock.patch("app.i18n.server_lang", new=lambda: "en")(target)


def world_songs():
    """Enough rated songs for Jonas' two favorite worlds (kids: Band A/B, medieval: Spielleute)."""
    out = []
    for k in range(12):
        out.append(song(f"a{k}", artist="Band A", genres=["Children"], rating=4))
        out.append(song(f"b{k}", artist="Band B", genres=["Children"], rating=4))
        out.append(song(f"m{k}", artist="Spielleute", album="Mittelaltermarkt", rating=4))
    return out


class NamesTest(unittest.TestCase):
    def setUp(self):
        self.cfg = base_config()

    def name(self, **p):
        return rules.playlist_name(self.cfg, {"id": "t", "person": "familie", "stil": "*", **p})

    @env.german
    def test_world_without_vibe_is_querbeet_in_german(self):
        self.assertEqual(self.name(welt="kinder"), "Kinder · Querbeet")
        self.assertEqual(self.name(welt=["kinder", "mittelalter"], person="jonas"), "Jonas · Kinder + Mittelalter · Querbeet")
        self.assertEqual(self.name(welt="kinder", hits=True), "Kinder · Die Hits")

    @english
    def test_world_without_vibe_is_all_sorts_in_english(self):
        self.assertEqual(self.name(welt="kinder"), "Kinder · All Sorts")
        self.assertEqual(self.name(welt="kinder", hits=True), "Kinder · The Hits")

    @env.german
    def test_real_mixes_keep_mix(self):
        self.assertEqual(self.name(welt="kinder", type="mix"), "Daily Mix · Kinder")
        self.assertEqual(self.name(welt="kinder", type="mix", mix={"every": "week"}), "Weekly Mix · Kinder")

    @env.german
    def test_new_name_applies_without_a_new_file(self):
        """A generated name is not stored: the playlist keeps its file, so Navidrome keeps the same playlist."""
        from app import playlists
        p = {"id": "kinder-alles", "person": "familie", "welt": "kinder", "stil": "*", "status": "aktiv",
             "file": "Kinder · Mix.nsp"}
        self.cfg["playlists"] = [p]
        (_p, filename, nsp), = playlists.plan(self.cfg, BuildContext(Library([]), OCT))
        self.assertEqual((filename, nsp["name"]), ("Kinder · Mix.nsp", "Kinder · Querbeet"))
        self.assertNotIn("name", p)

    def test_possessive_and_apostrophes(self):
        for lang, who, want in (("en", "Lukas", "Lukas’s All Sorts"), ("de", "Lukas", "Lukas’ Querbeet"),
                                ("de", "Anna", "Annas Querbeet"), ("en", "Anna", "Anna’s All Sorts")):
            self.assertEqual(i18n.tr("{name}’s All Sorts", lang, name=who, owner=suggest.possessive(who)), want)
        self.assertEqual(i18n.tr("{name}’s Daily Mix", "en", name="Lukas", owner="Lukas’"), "Lukas’s Daily Mix")
        self.assertEqual(i18n.tr("{name}’s Daily Mix", "de", name="Lukas", owner="Lukas’"), "Lukas’ Daily Mix")


class SuggestionNameTest(unittest.TestCase):
    def suggest(self):
        cfg = base_config()
        cfg["personen"][1]["likes"]["welten"] = ["kinder", "mittelalter"]
        out = suggest.suggestions(cfg, Library(world_songs()), today=OCT, only_person="jonas")
        return {s["key"]: s for s in out}

    @env.german
    def test_personal_playlist_across_worlds_is_querbeet(self):
        s = self.suggest()["jonas|kinder+mittelalter|*|"]
        self.assertNotEqual(s["playlist"].get("type"), "mix")   # a smart playlist – no mix
        self.assertEqual((s["playlist"]["name"], s["title"]), ("Jonas’ Querbeet", "Jonas’ Querbeet"))

    @english
    def test_english_names_use_title_case_for_the_kind(self):
        got = self.suggest()
        self.assertEqual(got["jonas|kinder+mittelalter|*|"]["title"], "Jonas’s All Sorts")
        self.assertEqual(got["jonas|kinder+mittelalter|*||mix"]["title"], "Jonas’s Daily Mix")


class MigrationTest(unittest.TestCase):
    def old(self, lang, *playlists):
        cfg = base_config()
        cfg["version"] = 7
        cfg["settings"]["language"] = lang
        cfg["personen"].append({"id": "linus", "name": "Linus", "user": "linus", "prefix": "Linus · ",
                                "likes": {"welten": [], "stile": [], "artists": []},
                                "dislikes": {"artists": [], "genres": []}})
        base = {"person": "linus", "welt": ["kinder", "mittelalter"], "stil": "*", "minRating": 3, "status": "aktiv"}
        cfg["playlists"] = [{**base, "id": f"p{k}", "file": f"f{k}.nsp", **p} for k, p in enumerate(playlists)]
        return cfg

    def names(self, cfg):
        return [p.get("name") for p in config.migrate(cfg)["playlists"]]

    def test_suggested_names_become_querbeet_in_a_german_installation(self):
        cfg = self.old("de", {"name": "Linus’ Mix"}, {"name": "Linus’s mix"},   # stored in German or English
                       {"name": "Jonas’ Mix", "person": "jonas"})
        self.assertEqual(self.names(cfg), ["Linus’ Querbeet", "Linus’ Querbeet", "Jonas’ Querbeet"])
        self.assertEqual(cfg["version"], config.CONFIG_VERSION)
        self.assertEqual([p["file"] for p in cfg["playlists"]], ["f0.nsp", "f1.nsp", "f2.nsp"])   # same playlists

    def test_english_installation_gets_all_sorts(self):
        self.assertEqual(self.names(self.old("en", {"name": "Linus’s mix"}, {"name": "Linus’ Mix"})),
                         ["Linus’s All Sorts", "Linus’s All Sorts"])

    def test_chosen_names_and_real_mixes_stay(self):
        cfg = self.old("de", {"name": "Linus' Mix"},                      # typed by hand (straight apostrophe)
                       {"name": "Mein Mix"}, {"name": "Linus’ Mixtape"},
                       {"name": "Linus’ Mix", "type": "mix", "mix": {"every": "day"}},   # a real mix
                       {"name": "Linus’ Mix", "stil": "tanzen"},           # with a vibe: not the suggestion
                       {"name": "Linus’ Mix", "person": "jonas"},          # name of another person
                       {"name": "Linus’ Mix", "hits": True})
        self.assertEqual(self.names(cfg), ["Linus' Mix", "Mein Mix", "Linus’ Mixtape", "Linus’ Mix", "Linus’ Mix",
                                           "Linus’ Mix", "Linus’ Mix"])

    def test_current_version_is_not_touched(self):
        cfg = self.old("de", {"name": "Linus’ Mix"})
        cfg["version"] = config.CONFIG_VERSION
        self.assertEqual(self.names(cfg), ["Linus’ Mix"])

    def test_default_config_needs_no_migration(self):
        self.assertEqual(config.default_config()["version"], config.CONFIG_VERSION)


class NewBandActionTest(unittest.TestCase):
    def inbox(self):
        cfg = base_config()
        cfg["settings"]["analysis"] = {"classify": "off"}
        songs = [song(f"n{k}", artist="Neue Band", genres=["Rock"], created=iso_days_ago(3)) for k in range(4)]
        out = suggest.inbox(cfg, Library(songs), {}, None, [], {})
        return next(x for x in out if x["key"] == "new|Neue Band")

    @env.german
    def test_new_band_opens_the_band_window(self):
        item = self.inbox()
        self.assertEqual(item["actions"][-1], {"label": "Musikwelt zuordnen …", "do": "artist", "artist": "Neue Band"})
        self.assertFalse(any(a.get("do") == "goto" and a.get("tab") == "welten" for a in item["actions"]))

    @english
    def test_english_label(self):
        self.assertEqual(self.inbox()["actions"][-1]["label"], "Assign music world …")


if __name__ == "__main__":
    unittest.main()
