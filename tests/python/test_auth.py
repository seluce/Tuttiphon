"""app/auth.py: sessions (tokens), roles, visibility and what users may save."""
from tests.python import env  # noqa: F401  (before app.*)

import base64
import copy
import datetime as dt
import json
import os
import stat
import unittest
from unittest import mock

from app import auth, config
from app.navidrome import NavidromeError
from tests.python.factory import base_config

JONAS = {"user": "Jonas", "role": "user", "own": ["jonas"], "local": False}
ADMIN = {"user": "niklas", "role": "admin", "own": ["niklas"], "local": False}
NAV_USERS = [{"name": "niklas", "admin": True, "fullName": "Niklas Test"},
             {"name": "Jonas", "admin": False, "fullName": "Jonas Test"},
             {"name": "oma", "admin": False, "fullName": "Oma"}]


def config_with_playlists():
    cfg = base_config()
    cfg["playlists"] = [
        {"id": "pi", "name": "Jonas eins", "person": "jonas", "welt": "kinder", "stil": "*", "file": "pi.nsp",
         "takeover": {"backup": "pi.orig"}},
        {"id": "pi2", "name": "Jonas zwei", "person": "jonas", "welt": "kinder", "stil": "tanzen"},
        {"id": "pf", "name": "Familie", "person": "familie", "welt": "metal", "stil": "*"},   # the family's: everyone's
        {"id": "pr", "name": "Niklas privat", "person": "niklas", "welt": "metal", "stil": "*"},
        {"id": "po", "name": "Oma", "person": "oma", "welt": "mittelalter", "stil": "*"},
        {"id": "pg", "name": "Geist", "person": "geist", "welt": "metal", "stil": "*"},   # person does not exist
    ]
    cfg["accounts"] = {"jonas": {"role": "user", "dismissed": ["a"], "ignored": ["b"]}, "niklas": {"role": "admin"}}
    cfg["dismissed"], cfg["ignored"] = ["admin-x"], ["admin-y"]
    return cfg


class TestTokens(unittest.TestCase):
    def setUp(self):
        env.reset_caches()

    def test_round_trip_and_files(self):
        token = auth.make_token("Jonas")
        self.assertEqual(auth.read_token(token), "Jonas")
        for path in (auth.SESSIONS_FILE, auth.STATE_DIR / "secret"):
            self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600, path)

    def test_local_administrator_session_ends_with_password_change(self):
        with mock.patch.dict(os.environ, {"TUTTIPHON_ADMIN_PASSWORD": "erstes-passwort"}):
            env.reset_caches()
            token = auth.make_token(auth.NOTFALL)
            self.assertEqual(auth.read_token(token), auth.NOTFALL)
        with mock.patch.dict(os.environ, {"TUTTIPHON_ADMIN_PASSWORD": "neues-passwort"}):
            env.reset_caches()
            self.assertIsNone(auth.read_token(token))

    def test_end_sessions_of_account(self):
        jonas, other = auth.make_token("Jonas"), auth.make_token("niklas")
        auth.end_sessions_of("jonas")
        self.assertIsNone(auth.read_token(jonas))
        self.assertEqual(auth.read_token(other), "niklas")

    def test_logout_revokes_only_this_session(self):
        first, second = auth.make_token("Jonas"), auth.make_token("Jonas")
        auth.end_session(first)
        self.assertIsNone(auth.read_token(first))
        self.assertEqual(auth.read_token(second), "Jonas")
        env.reset_caches()   # also after a restart (sessions from the file)
        self.assertIsNone(auth.read_token(first))
        self.assertEqual(auth.read_token(second), "Jonas")

    def test_expired_token(self):
        self.assertIsNone(auth.read_token(auth.make_token("Jonas", days=-1)))

    def test_manipulated_tokens(self):
        token = auth.make_token("Jonas")
        payload, sig = token.rsplit(".", 1)
        data = json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))
        data["u"] = "niklas"
        forged = base64.urlsafe_b64encode(json.dumps(data).encode()).decode().rstrip("=")
        for bad in (f"{forged}.{sig}", f"{payload}.{sig[:-1]}0" if sig[-1] != "0" else f"{payload}.{sig[:-1]}1",
                    payload, f"{payload}.", "", None, "a.b.c", "äöü.ß", f"{payload}.{sig}x"):
            self.assertIsNone(auth.read_token(bad), bad)
        auth.end_session(f"{forged}.{sig}")   # a forged token does not end someone else's session
        self.assertEqual(auth.read_token(token), "Jonas")

    def test_session_must_belong_to_the_token_user(self):
        token = auth.make_token("Jonas")
        payload = token.split(".")[0]
        sid = json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))["s"]
        sessions = json.loads(auth.SESSIONS_FILE.read_text())
        sessions[sid]["u"] = "niklas"
        auth.SESSIONS_FILE.write_text(json.dumps(sessions))
        env.reset_caches()
        self.assertIsNone(auth.read_token(token))

    def test_new_secret_invalidates_tokens(self):
        token = auth.make_token("Jonas")
        secret = auth.STATE_DIR / "secret"
        old = secret.read_text()
        self.addCleanup(secret.write_text, old)
        secret.write_text("0" * 64)
        self.assertIsNone(auth.read_token(token))


class TestRoles(unittest.TestCase):
    def setUp(self):
        env.reset_caches()
        auth.USERS_FILE.unlink(missing_ok=True)
        self.addCleanup(auth.USERS_FILE.unlink, missing_ok=True)
        self.addCleanup(env.reset_caches)

    def test_role_from_navidrome_and_accounts(self):
        cfg = base_config()
        cfg["accounts"] = {"jonas": {"role": "admin"}, "oma": {"role": "none"}, "geist": {"role": "admin"}}
        with mock.patch.object(auth, "navidrome_users", return_value=NAV_USERS):
            self.assertEqual(auth.role_of("niklas", cfg), "admin")
            self.assertEqual(auth.role_of("NIKLAS", cfg), "admin")
            self.assertEqual(auth.role_of("jonas", cfg), "admin")       # setting beats Navidrome
            self.assertEqual(auth.role_of("oma", cfg), "none")
            self.assertEqual(auth.role_of("geist", cfg), "none")       # not (or no longer) in Navidrome
            self.assertEqual(auth.role_of(auth.NOTFALL, cfg), "admin")
            self.assertEqual(auth.role_of("Jonas", base_config()), "user")

    def test_without_any_account_list(self):
        cfg = base_config()
        cfg["accounts"] = {"jonas": {"role": "admin"}}
        with mock.patch.object(auth, "navidrome_users", return_value=[]):
            self.assertEqual(auth.role_of("niklas", cfg), "user")
            self.assertEqual(auth.role_of("jonas", cfg), "admin")

    def test_remembered_account_list_when_navidrome_is_down(self):
        auth.USERS_FILE.write_text(json.dumps(NAV_USERS))
        down = mock.patch("app.playlists.native_api", side_effect=NavidromeError("weg"))
        with down:
            self.assertEqual(auth.role_of("niklas", base_config()), "admin")   # not suddenly a user
            self.assertEqual(auth.role_of("fremd", base_config()), "none")

    def test_account_list_is_remembered(self):
        fresh = [{"userName": "niklas", "isAdmin": True, "name": "Niklas"}, {"userName": "neu", "isAdmin": False}]
        api = mock.Mock()
        api.users.return_value = fresh
        with mock.patch("app.playlists.native_api", return_value=api):
            users = auth.navidrome_users(force=True)
        self.assertEqual(users, [{"name": "niklas", "admin": True, "fullName": "Niklas"},
                                 {"name": "neu", "admin": False, "fullName": "neu"}])
        self.assertEqual(json.loads(auth.USERS_FILE.read_text()), users)
        env.reset_caches()   # restart, Navidrome unreachable
        with mock.patch("app.playlists.native_api", side_effect=NavidromeError("weg")):
            self.assertEqual(auth.role_of("neu", base_config()), "user")
            self.assertEqual(auth.role_of("Jonas", base_config()), "none")


class TestVisibility(unittest.TestCase):
    def setUp(self):
        self.cfg = config_with_playlists()
        self.by_id = {p["id"]: p for p in self.cfg["playlists"]}

    def test_visible_playlist(self):
        """Own playlists and the family's (for everyone) – a person's are their own."""
        visible = {pid for pid, p in self.by_id.items() if auth.visible_playlist(p, self.cfg, JONAS)}
        self.assertEqual(visible, {"pi", "pi2", "pf"})
        self.assertTrue(all(auth.visible_playlist(p, self.cfg, ADMIN) for p in self.cfg["playlists"]))

    def test_who_may_change_the_family_playlists(self):
        self.assertTrue(auth.own_playlist(self.by_id["pf"], JONAS, self.cfg))     # everyone, by default
        self.assertFalse(auth.own_playlist(self.by_id["po"], JONAS, self.cfg))
        self.cfg["settings"]["familyEdit"] = "admins"
        self.assertFalse(auth.own_playlist(self.by_id["pf"], JONAS, self.cfg))
        self.assertTrue(auth.visible_playlist(self.by_id["pf"], self.cfg, JONAS))  # still for everyone to hear
        self.assertTrue(auth.own_playlist(self.by_id["pf"], ADMIN, self.cfg))

    def test_one_person_per_account_and_no_sign_in_for_the_family(self):
        self.assertEqual(auth.persons_of("JONAS", self.cfg), ["jonas"])
        self.assertEqual(auth.persons_of("familie", self.cfg), [])     # the family is nobody's own person
        self.assertEqual(auth.family_account(self.cfg), "familie")
        with mock.patch.object(auth, "navidrome_users", lambda force=False: USERS + [
                {"name": "familie", "admin": False, "fullName": "Familie"}]):
            self.assertEqual(auth.role_of("Familie", self.cfg), "none")

    def test_view_config_for_users(self):
        before = copy.deepcopy(self.cfg)
        out = auth.view_config(self.cfg, JONAS)
        self.assertEqual(self.cfg, before)   # the original stays unchanged
        self.assertEqual([p["id"] for p in out["playlists"]], ["pi", "pi2", "pf"])
        self.assertNotIn("accounts", out)
        self.assertLessEqual(set(out["settings"]), set(auth.USER_SETTINGS) | {"notify"})
        self.assertEqual(set(out["settings"]["notify"]), {"enabled", "server"})   # without the administrator's topic
        self.assertNotIn("paths", out["settings"])
        persons = {p["id"]: p for p in out["personen"]}
        self.assertEqual(set(persons), {"familie", "jonas", "niklas", "oma"})   # names of everyone (family mix)
        self.assertEqual(persons["jonas"], self.cfg["personen"][1])    # own person complete
        self.assertEqual(persons["oma"], {"id": "oma", "name": "Oma", "prefix": "Oma · ",
                                          "color": "#aa0000"})        # without likes, no-gos, account
        self.assertEqual(persons["familie"], {"id": "familie", "name": "Familie", "prefix": "", "family": True})
        self.assertEqual((out["dismissed"], out["ignored"]), (["a"], ["b"]))

    def test_view_config_for_admins(self):
        out = auth.view_config(self.cfg, ADMIN)
        self.assertEqual(len(out["playlists"]), len(self.cfg["playlists"]))
        self.assertIn("accounts", out)
        self.assertEqual((out["dismissed"], out["ignored"]), (["admin-x"], ["admin-y"]))
        self.assertIs(auth.view_config(self.cfg, {**ADMIN, "local": True}), self.cfg)


class TestMergeUserChanges(unittest.TestCase):
    def setUp(self):
        self.current = config_with_playlists()
        self.incoming = copy.deepcopy(auth.view_config(self.current, JONAS))   # what the interface knows

    def merged(self):
        return auth.merge_user_changes(self.current, self.incoming, JONAS)

    def persons(self, cfg):
        return {p["id"]: p for p in cfg["personen"]}

    def playlists(self, cfg):
        return {p["id"]: p for p in cfg["playlists"]}

    def test_user_cannot_set_server_playlist_fields(self):
        # rules of taken-over playlists, backups etc. are set only by the server/admin – not via own playlists either
        self.current["playlists"][1]["rules"] = [{"is": {"artist": "Band A"}}]
        self.incoming = copy.deepcopy(auth.view_config(self.current, JONAS))
        mine = next(p for p in self.incoming["playlists"] if p["id"] == "pi2")
        mine.update(rules=[{"is": {"artist": "Fremd"}}], sortRaw="x", takeover={"backup": "y"})
        new = {"id": "pneu", "name": "Neu", "person": "jonas", "welt": "kinder", "stil": "*",
               "rules": [], "rulesExtra": {"offset": 5}, "originalName": "Papas Liste"}
        self.incoming["playlists"].append(new)
        out = self.playlists(self.merged())
        self.assertEqual(out["pi2"].get("rules"), [{"is": {"artist": "Band A"}}])
        self.assertNotIn("sortRaw", out["pi2"])
        self.assertNotIn("takeover", out["pi2"])
        self.assertFalse({"rules", "rulesExtra", "originalName"} & set(out["pneu"]))

    def test_unchanged_save_changes_nothing_but_the_account_lists(self):
        out = self.merged()
        expected = copy.deepcopy(self.current)
        for acc in expected["accounts"].values():   # plus only: since when something has been hidden
            if acc.get("dismissed"):
                acc["dismissedAt"] = {k: dt.date.today().isoformat() for k in acc["dismissed"]}
        self.assertEqual(out, expected)

    def test_only_own_persons_change(self):
        inc = self.persons(self.incoming)
        inc["jonas"].update(name="Jonas neu", user="niklas", family=True, dislikes={"artists": [], "genres": []})
        inc["familie"]["name"] = "Gekapert"
        inc["oma"]["name"] = "Omi"
        out = self.persons(self.merged())
        self.assertEqual(out["jonas"]["name"], "Jonas neu")
        self.assertNotIn("family", out["jonas"])
        self.assertEqual(out["jonas"]["user"], "Jonas")              # account stays
        self.assertEqual(out["familie"], self.current["personen"][0])  # only administrators change the family
        self.assertEqual(out["oma"], self.current["personen"][3])
        self.assertEqual(out["niklas"], self.current["personen"][2])

    def test_one_own_person_for_an_account_without_one(self):
        self.incoming["personen"].append({"id": "jonas-kind", "name": "Jonas Kind", "user": "Jonas"})
        self.assertNotIn("jonas-kind", self.persons(self.merged()))   # Jonas has his person already
        mia = {"user": "mia", "role": "user", "own": [], "local": False}
        incoming = copy.deepcopy(auth.view_config(self.current, mia))
        incoming["personen"] += [
            {"id": "fremd", "name": "Fremd", "user": "niklas"},
            {"id": "neu", "name": "Neu", "user": "mia"},
            {"id": "Böse!", "name": "Böse", "user": "mia"},
            {"id": "leer", "name": "  ", "user": "mia"},
            {"id": "mia", "name": "Mia", "user": "mia", "family": True, "child": True, "role": "admin"},
            {"id": "mia-2", "name": "Mia zwei", "user": "mia"},
            "kein dict",
        ]
        out = {p["id"]: p for p in auth.merge_user_changes(self.current, incoming, mia)["personen"]}
        self.assertEqual(out["mia"], {"id": "mia", "name": "Mia", "user": "mia"})   # her one person, nothing else
        for pid in ("fremd", "neu", "Böse!", "leer", "mia-2"):
            self.assertNotIn(pid, out)

    def test_only_own_playlists_change(self):
        inc = self.playlists(self.incoming)
        inc["pi"]["name"] = "Jonas umbenannt"
        inc["pf"]["name"] = "Familie neu"       # the family's: everyone may (settings.familyEdit "all")
        inc["pi2"]["person"] = "oma"           # giving away is not possible
        self.incoming["playlists"].append({**self.playlists(self.current)["po"], "person": "jonas"})   # taking over neither
        out = self.playlists(self.merged())
        self.assertEqual(out["pi"]["name"], "Jonas umbenannt")
        self.assertEqual(out["pf"]["name"], "Familie neu")
        self.assertEqual(out["pi2"], self.playlists(self.current)["pi2"])
        self.assertEqual(out["po"], self.playlists(self.current)["po"])
        self.assertIn("pr", out)   # the user does not see it – it stays anyway
        self.current["settings"]["familyEdit"] = "admins"
        self.incoming = copy.deepcopy(auth.view_config(self.current, JONAS))
        self.incoming["playlists"] = [p for p in self.incoming["playlists"] if p["id"] != "pf"]   # deleting it
        self.assertEqual(self.playlists(self.merged())["pf"], self.playlists(self.current)["pf"])

    def test_delete_own_and_add_new_playlists(self):
        self.incoming["playlists"] = [p for p in self.incoming["playlists"] if p["id"] != "pi2"]
        self.incoming["playlists"] += [
            {"id": "n1", "person": "jonas", "welt": "kinder", "stil": "*", "takeover": {"backup": "x"}},
            {"id": "n2", "person": "familie", "welt": "kinder", "stil": "*"},   # for the family: everyone may
            {"id": "n3", "person": "oma", "welt": "kinder", "stil": "*"},
            {"id": "n4", "welt": "kinder", "stil": "*"},          # without a person: nobody's
            {"welt": "kinder", "stil": "*"},                       # without id
        ]
        out = self.merged()
        ids = [p["id"] for p in out["playlists"]]
        self.assertNotIn("pi2", ids)
        self.assertEqual(ids[-2:], ["n1", "n2"])
        self.assertNotIn("takeover", out["playlists"][-2])
        self.assertNotIn("n3", ids)
        self.assertNotIn("n4", ids)
        self.assertEqual(len(ids), len(self.current["playlists"]) - 1 + 2)

    def test_server_fields_survive_the_whole_save(self):
        # like api_save_config: first the own changes, then the server fields from the current state
        inc = self.playlists(self.incoming)
        inc["pi"].update(file="../../fremd.nsp", takeover=None)
        out = config.merge_server_fields(self.merged(), self.current, keep_accounts=True)
        pi = self.playlists(out)["pi"]
        self.assertEqual((pi["file"], pi["takeover"]), ("pi.nsp", {"backup": "pi.orig"}))

    def test_account_lists_and_untouchable_parts(self):
        self.incoming["dismissed"] = [f"d{i}" for i in range(600)] + [5, None]
        self.incoming["ignored"] = "kein-array"
        self.incoming["settings"] = {"autoApply": False, "paths": {"music": "/"}}
        self.incoming["welten"] = []
        self.incoming["accounts"] = {"jonas": {"role": "admin"}}
        out = self.merged()
        self.assertEqual(out["accounts"]["jonas"]["dismissed"], [f"d{i}" for i in range(100, 600)])
        self.assertEqual(out["accounts"]["jonas"]["ignored"], ["b"])
        self.assertEqual(out["accounts"]["jonas"]["role"], "user")
        self.assertEqual(out["settings"], self.current["settings"])
        self.assertEqual(out["welten"], self.current["welten"])
        self.assertEqual(out["dismissed"], ["admin-x"])


if __name__ == "__main__":
    unittest.main()
