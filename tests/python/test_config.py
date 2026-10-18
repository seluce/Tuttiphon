"""app/config.py: file names, server fields, normalizing, validating, .env, storage locations."""
from tests.python import env  # noqa: F401  (before app.*)

import copy
import os
import stat
import unittest
from pathlib import Path
from unittest import mock

from app import config
from tests.python.factory import base_config


class TestPlainPlaylistFile(unittest.TestCase):
    def test_accepts_plain_names(self):
        for name in ("Auto – Kinder.nsp", "mix.m3u", "MIX.M3U", "a.NSP", "x" * 251 + ".nsp"):
            self.assertTrue(config.plain_playlist_file(name), name)

    def test_rejects_paths_hidden_and_other_files(self):
        for name in ("../x.nsp", "sub/x.nsp", "/etc/x.nsp", "a\\b.nsp", ".hidden.nsp", "..nsp", "x.txt", "x.nsp.bak",
                     "x\0.nsp", "", "x" * 252 + ".nsp", None, 5, ["a.nsp"]):
            self.assertFalse(config.plain_playlist_file(name), repr(name))


class TestMergeServerFields(unittest.TestCase):
    def setUp(self):
        self.current = {
            "accounts": {"jonas": {"role": "user"}},
            "playlists": [
                {"id": "a", "name": "A", "file": "a.nsp", "takeover": {"backup": "a.orig"}, "cover": {"style": "x"}},
                {"id": "b", "name": "B", "file": "b.m3u"},
                {"id": "c", "name": "C"},
            ]}

    def merge(self, playlists, keep_accounts=False, accounts=None):
        incoming = {"playlists": copy.deepcopy(playlists), "accounts": accounts or {"jonas": {"role": "admin"}}}
        return config.merge_server_fields(incoming, self.current, keep_accounts)

    def test_existing_playlists_keep_server_fields(self):
        out = self.merge([{"id": "a", "name": "A neu", "file": "../../evil.nsp", "takeover": None, "cover": {"style": "y"}},
                          {"id": "b", "name": "B", "file": "a.nsp", "takeover": {"backup": "fremd"}},
                          {"id": "c", "name": "C", "file": "c.nsp", "cover": {"style": "z"}}])["playlists"]
        self.assertEqual(out[0], {"id": "a", "name": "A neu", "file": "a.nsp", "takeover": {"backup": "a.orig"},
                                  "cover": {"style": "x"}})
        self.assertEqual(out[1], {"id": "b", "name": "B", "file": "b.m3u"})
        self.assertEqual(out[2], {"id": "c", "name": "C"})   # server does not know a file name/cover (yet)

    def test_new_playlist_cannot_claim_handmade_file(self):
        # A new playlist (e.g. from a user) must not get a handmade file in the playlist folder as its name
        # – otherwise it would be overwritten, taken over into Navidrome and removed on delete.
        handmade = env.PLAYLISTS / "Papas Liste.nsp"
        handmade.write_text("{}")
        self.addCleanup(handmade.unlink)
        self.current["settings"] = config.load_config()["settings"]
        out = self.merge([{"id": "n1", "file": "Papas Liste.nsp"}, {"id": "n2", "file": "frei.nsp"}])["playlists"]
        self.assertEqual(out, [{"id": "n1"}, {"id": "n2", "file": "frei.nsp"}])

    def test_new_playlist_keeps_only_plain_unused_file(self):
        out = self.merge([{"id": "n1", "file": "neu.nsp", "cover": {"style": "q"}},
                          {"id": "n2", "file": "neu.nsp"},            # already taken by n1
                          {"id": "n3", "file": "a.nsp"},              # belongs to playlist a
                          {"id": "n4", "file": "../x.nsp"},
                          {"id": "n5", "file": "x.json"},
                          {"id": "n6"}])["playlists"]
        self.assertEqual(out, [{"id": "n1", "file": "neu.nsp"}, {"id": "n2"}, {"id": "n3"}, {"id": "n4"}, {"id": "n5"},
                               {"id": "n6"}])

    def test_file_of_deleted_playlist_is_not_reusable_in_the_same_save(self):
        out = self.merge([{"id": "n", "file": "b.m3u"}])["playlists"]   # b deleted, n wants its file
        self.assertNotIn("file", out[0])

    def test_accounts_come_from_the_server(self):
        self.assertEqual(self.merge([])["accounts"], {"jonas": {"role": "user"}})
        self.assertEqual(self.merge([], keep_accounts=True)["accounts"], {"jonas": {"role": "admin"}})


class TestNormalizePlaylists(unittest.TestCase):
    def test_sound_playlists_become_mixes(self):
        cfg = base_config()
        cfg["playlists"] = [
            {"id": "a", "welt": "*", "stil": "klang-ruhig"},                                # the direction's sound
            {"id": "b", "welt": "kinder", "stil": "*", "sound": {"moods": ["froh"]}},          # own sound
            {"id": "c", "welt": "kinder", "stil": "klang-ruhig", "type": "mix", "mix": {"size": 10}},
            {"id": "d", "rules": [], "stil": "klang-ruhig"},                                   # taken over: stays
            {"id": "e", "welt": "kinder", "stil": "tanzen"},
            {"id": "f", "welt": "kinder", "stil": "*", "sound": {"moods": ["froh"]}, "mix": {"size": 12}},
        ]
        out = {p["id"]: p for p in config.normalize_playlists(cfg)["playlists"]}
        self.assertEqual((out["a"]["type"], out["a"]["mix"]), ("mix", {"size": 40, "perArtist": 3, "every": "week"}))
        self.assertEqual(out["b"]["type"], "mix")
        self.assertEqual(out["c"]["mix"], {"size": 10})
        self.assertNotIn("type", out["d"])
        self.assertNotIn("type", out["e"])
        self.assertEqual(out["f"]["mix"], {"size": 12})   # existing mix settings stay
        config.validate_config(cfg)


@env.german   # checks the German output of existing installations
class TestValidateConfig(unittest.TestCase):
    def setUp(self):
        self.cfg = base_config()
        self.cfg["playlists"] = [{"id": "p1", "welt": "kinder", "stil": "tanzen", "person": "jonas"},
                                 {"id": "p2", "welt": ["kinder", "metal"], "stil": "*"},
                                 {"id": "p3", "welt": "*", "stil": "80er", "limit": 50, "minRating": 4},
                                 {"id": "p4", "welt": "*", "stil": "*", "type": "mix", "radio": {"seed": ["Band A"]},
                                  "mix": {"size": 30, "every": "month", "perAlbum": 0}},
                                 {"id": "p5", "rules": [{"is": {"loved": True}}], "welt": "weg", "stil": "weg"}]

    def assertInvalid(self, change, message=None):
        cfg = copy.deepcopy(self.cfg)
        change(cfg)
        with self.assertRaises(ValueError) as ctx:
            config.validate_config(cfg)
        if message:
            self.assertIn(message, str(ctx.exception))

    def test_field_types(self):
        # reject wrong types (e.g. from a manipulated request) early instead of breaking runs/pages later
        self.assertInvalid(lambda c: c["personen"][0].update(prefix=5), "prefix muss Text sein")
        self.assertInvalid(lambda c: c["personen"][0].update(likes="x"), "likes ungültig")
        self.assertInvalid(lambda c: c["personen"][0].update(dislikes={"artists": [1]}), "dislikes ungültig")
        self.assertInvalid(lambda c: c["playlists"][0].update(excludeArtists="Band"), "excludeArtists")
        self.assertInvalid(lambda c: c["playlists"][0].update(name=["x"]), "name muss Text sein")
        self.assertInvalid(lambda c: c["playlists"][0].update(public="ja"), "public ungültig")
        self.assertInvalid(lambda c: c.update(personen={}), "personen ungültig")

    def test_valid_configs(self):
        config.validate_config(self.cfg)
        config.validate_config(copy.deepcopy(config.default_config()))

    def test_structure_and_ids(self):
        self.assertInvalid(lambda c: c.pop("personen"), "'personen' fehlt")
        self.assertInvalid(lambda c: c["welten"].append({"id": "kinder", "name": "doppelt"}), "eindeutige ids")
        self.assertInvalid(lambda c: c["stile"].append({"name": "ohne id"}), "eindeutige ids")
        self.assertInvalid(lambda c: c["welten"].append({"id": "*"}), "reserviert")

    def test_playlist_references(self):
        self.assertInvalid(lambda c: c["playlists"].append({"id": "x", "welt": "gibtsnicht", "stil": "*"}),
                           "unbekannte Welt")
        self.assertInvalid(lambda c: c["playlists"].append({"id": "x", "welt": ["kinder", "weg"], "stil": "*"}),
                           "unbekannte Welt")
        self.assertInvalid(lambda c: c["playlists"].append({"id": "x", "welt": "kinder", "stil": "weg"}),
                           "unbekannte Welt/Richtung")
        self.assertInvalid(lambda c: c["playlists"].append({"id": "x", "welt": "kinder", "stil": "*", "person": "otto"}),
                           "unbekannte Person")
        self.assertInvalid(lambda c: c["playlists"].append({"id": "x", "welt": "*", "stil": "*"}), "Alle × Alles")

    def test_radio_and_sound(self):
        self.assertInvalid(lambda c: c["playlists"][3].update(radio={"seed": []}), "Startband")
        self.assertInvalid(lambda c: c["playlists"][3].update(radio={"seed": [""]}), "Startband")
        self.assertInvalid(lambda c: c["playlists"].append({"id": "x", "welt": "*", "stil": "klang-ruhig"}),
                           "nur als Mix")
        self.assertInvalid(lambda c: c["playlists"][0].update(sound={"tempo": [1, 2]}))
        self.assertInvalid(lambda c: c["stile"][-1].update(sound={"energy": [0.8, 0.2]}), "Bereich")
        self.assertInvalid(lambda c: c["stile"][-1].update(sound={"moods": ["wütend"]}), "Stimmung")

    def test_numbers_and_mix_settings(self):
        self.assertInvalid(lambda c: c["playlists"][2].update(limit=0), "limit")
        self.assertInvalid(lambda c: c["playlists"][2].update(minRating=True), "minRating")   # bool does not count
        self.assertInvalid(lambda c: c["playlists"][2].update(minRating="4"), "minRating")
        self.assertInvalid(lambda c: c["playlists"][3]["mix"].update(every="year"), "Rhythmus")
        self.assertInvalid(lambda c: c["playlists"][3]["mix"].update(size=4), "size")
        self.assertInvalid(lambda c: c["playlists"][3].update(mix=[1]), "Mix-Einstellungen")
        self.assertInvalid(lambda c: c["playlists"][3].update(type="smart"), "unbekannte Art")

    def test_seasons_accounts_and_settings(self):
        self.assertInvalid(lambda c: c["stile"][1].update(season=["13-01", "01-06"]), "MM-TT")
        self.assertInvalid(lambda c: c["stile"][1].update(season=["11-25"]), "MM-TT")
        self.assertInvalid(lambda c: c.update(accounts={"jonas": {"role": "chef"}}), "Konten")
        self.assertInvalid(lambda c: c["settings"].update(dailyAt="24:00"), "dailyAt")
        self.assertInvalid(lambda c: c["settings"].update(dailyMode="manchmal"), "dailyMode")
        self.assertInvalid(lambda c: c["settings"].update(pipeline=["scan", "scan"]), "Alles aktualisieren")
        self.assertInvalid(lambda c: c["settings"].update(pipeline=["kaffee"]), "Alles aktualisieren")
        self.assertInvalid(lambda c: c["settings"]["deezer"].update(thresholds=[5, 4, 3, 2, 1]), "Deezer-Stufen")
        self.assertInvalid(lambda c: c["settings"]["backup"].update(dir="../anderswo"), "Sicherung")
        self.assertInvalid(lambda c: c["settings"]["opus"].update(archiveDir="/tmp/archiv"), "Archivordner")
        self.assertInvalid(lambda c: c["settings"]["opus"].update(owner="niklas"), "UID:GID")
        self.assertInvalid(lambda c: c["settings"].update(paths={"music": "Musik/../.."}), "..")
        self.assertInvalid(lambda c: c["settings"].update(paths={"temp": "/tmp"}), "Speicherort")
        config.validate_config({**copy.deepcopy(self.cfg), "accounts": {"jonas": {"role": "none"}, "x": {}}})


class EnvFileTest(unittest.TestCase):
    def setUp(self):
        env.reset_caches()
        config.ENV_FILE.unlink(missing_ok=True)
        self.addCleanup(env.reset_caches)
        self.addCleanup(config.ENV_FILE.unlink, missing_ok=True)

    def lines(self):
        return config.ENV_FILE.read_text(encoding="utf-8").splitlines()


class TestSaveEnv(EnvFileTest):
    def test_set_replace_and_append(self):
        config.save_env({"NAV_URL": "http://test.invalid:4533"})
        config.save_env({"NAV_ADMIN_USER": "admin-test", "NAV_URL": "http://andere.invalid"})
        self.assertEqual(self.lines(), ["NAV_URL=http://andere.invalid", "NAV_ADMIN_USER=admin-test"])
        self.assertEqual(stat.S_IMODE(config.ENV_FILE.stat().st_mode), 0o600)

    def test_commented_template_is_filled_in_place_and_kept_on_delete(self):
        config.ENV_FILE.write_text("# Zugang\n# NAV_URL=http://beispiel\n#LASTFM_API_KEY=\nRATING_USERS=a,b\n")
        config.save_env({"LASTFM_API_KEY": "key-test", "NAV_PASS_JONAS": "pw-test"})
        self.assertEqual(self.lines(), ["# Zugang", "# NAV_URL=http://beispiel", "LASTFM_API_KEY=key-test",
                                        "RATING_USERS=a,b", "NAV_PASS_JONAS=pw-test"])
        config.save_env({"RATING_USERS": None, "NAV_URL": None, "LASTFM_API_KEY": ""})   # "" = unchanged
        self.assertEqual(self.lines(), ["# Zugang", "# NAV_URL=http://beispiel", "LASTFM_API_KEY=key-test",
                                        "NAV_PASS_JONAS=pw-test"])

    def test_rejects_unknown_keys_and_control_characters(self):
        for updates in ({"PATH": "/x"}, {"NAV_PASS_": "x"}, {"nav_url": "x"}):
            with self.assertRaises(ValueError):
                config.save_env(updates)
        for value in ("a\nTUTTIPHON_ADMIN_PASSWORD=x", "tab\tx", 5):
            with self.assertRaises(ValueError):
                config.save_env({"NAV_ADMIN_PASS": value})
        self.assertFalse(config.ENV_FILE.exists())

    def test_round_trip_through_load_env(self):
        config.save_env({"NAV_PASS_JONAS": "p@ss w=rd#1", "NAV_URL": "http://test.invalid/"})
        e = config.load_env()
        self.assertEqual(e["NAV_PASS_JONAS"], "p@ss w=rd#1")
        self.assertEqual(e["NAV_URL"], "http://test.invalid")   # without trailing slash
        self.assertEqual(config.user_password(e, "jonas"), "p@ss w=rd#1")

    def test_round_trip_keeps_quotes_and_spaces_at_the_ends(self):
        # A password like 'geheim"' or ' geheim' must come back exactly the same on the next read (save_env adds
        # a pair of quotes for that, _read_env_file removes exactly one).
        for value in ('geheim"', "'geheim'", " geheim", "geheim "):
            config.save_env({"NAV_PASS_JONAS": value})
            self.assertEqual(config.load_env()["NAV_PASS_JONAS"], value)


class TestLoadEnv(EnvFileTest):
    def test_sources_and_precedence(self):
        config.ENV_FILE.write_text("NAV_URL=\nNAV_ADMIN_PASS=datei-pw\nNAV_PASS_JONAS='jonas-pw'\nSONSTWAS=1\n")
        with mock.patch.dict(os.environ, {"NAV_ADMIN_USER": "umgebung-admin", "NAV_ADMIN_PASS": "",
                                          "NAV_PASS_JONAS": "   ", "HOME_TEST": "x"}):
            e = config.load_env()
        self.assertEqual(e["NAV_URL"], "")                            # empty value in .env counts as not set
        self.assertEqual(e["NAV_ADMIN_USER"], "umgebung-admin")       # environment wins
        self.assertEqual(e["NAV_ADMIN_PASS"], "datei-pw")             # empty variable does not override the file
        self.assertEqual(e["NAV_PASS_JONAS"], "jonas-pw")               # only spaces: likewise
        self.assertEqual(e["SONSTWAS"], "1")
        self.assertNotIn("HOME_TEST", e)

    def test_reloads_after_file_change(self):
        config.ENV_FILE.write_text("NAV_ADMIN_USER=eins\n")
        self.assertEqual(config.load_env()["NAV_ADMIN_USER"], "eins")
        config.ENV_FILE.write_text("NAV_ADMIN_USER=zweizwei\n")
        self.assertEqual(config.load_env()["NAV_ADMIN_USER"], "zweizwei")
        e = config.load_env()
        e["NAV_ADMIN_USER"] = "verändert"   # a copy – the cache stays untouched
        self.assertEqual(config.load_env()["NAV_ADMIN_USER"], "zweizwei")


class TestPaths(unittest.TestCase):
    def cfg(self, **st):
        return {"settings": {"playlistDir": "Music/00_SmartPlaylists", **st}}

    def test_defaults_next_to_base(self):
        p = config.paths(self.cfg())
        self.assertEqual(p, {"music": env.MUSIC, "playlists": env.PLAYLISTS, "archive": env.ARCHIVE})

    def test_relative_music_dir(self):
        p = config.paths(self.cfg(paths={"music": "Medien/Musik", "playlists": "", "archive": ""}))
        self.assertEqual(p["music"], env.BASE / "Medien" / "Musik")
        self.assertEqual(p["playlists"], env.BASE / "Medien" / "Musik" / "00_SmartPlaylists")
        self.assertEqual(p["archive"], env.BASE / "Medien" / "Archiv")   # next to the music folder
        p = config.paths(self.cfg(paths={"music": "Musik", "playlists": "Listen", "archive": "Alt/Archiv"}))
        self.assertEqual(p, {"music": env.BASE / "Musik", "playlists": env.BASE / "Musik" / "Listen",
                             "archive": env.BASE / "Alt" / "Archiv"})

    def test_relative_paths_do_not_depend_on_working_directory(self):
        old = os.getcwd()
        try:
            os.chdir(env.ROOT)
            self.assertEqual(config.paths(self.cfg(paths={"music": "Musik"}))["music"], env.BASE / "Musik")
        finally:
            os.chdir(old)

    def test_legacy_playlist_dir_and_archive_setting(self):
        p = config.paths(self.cfg(playlistDir="Playlists", opus={"archiveDir": "Altes"}))
        self.assertEqual(p["playlists"], env.BASE / "Playlists")
        self.assertEqual(p["archive"], env.BASE / "Altes")

    def test_environment_wins(self):
        with mock.patch.dict(os.environ, {"MUSIC_DIR": "/nas/Music", "ARCHIVE_DIR": "/nas/Archiv"}):
            p = config.paths(self.cfg(paths={"music": "Musik", "archive": "X"}))
        self.assertEqual(p, {"music": Path("/nas/Music"), "playlists": Path("/nas/Music/00_SmartPlaylists"),
                             "archive": Path("/nas/Archiv")})


if __name__ == "__main__":
    unittest.main()
