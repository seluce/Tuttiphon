"""Password of the local administrator set in the browser (1.1): only a hash is kept, the first start on the network
waits for the setup with a one-time code from the server log, changing it needs the current one, docker-compose wins."""
from tests.python import env  # noqa: F401  (before app.*)

import contextlib
import hashlib
import http.client
import io
import json
import os
import socket
import stat
import threading
import types
import unittest
from http.server import ThreadingHTTPServer
from unittest import mock

from app import auth, config, localadmin, web


@contextlib.contextmanager
def admin_env(pw):
    with mock.patch.dict(os.environ, {"TUTTIPHON_ADMIN_PASSWORD": pw}):
        env.reset_caches()
        try:
            yield
        finally:
            env.reset_caches()


def clean():
    localadmin.HASH_FILE.unlink(missing_ok=True)
    localadmin.CODE_FILE.unlink(missing_ok=True)
    localadmin._cache.update(key=None, hash="")
    web.Handler._pw_cache = (0.0, None)
    for d in (web._login_fails, web._login_blocked_said):
        d.clear()
    web._login_pending.clear()


class HashTest(unittest.TestCase):
    def setUp(self):
        clean()
        self.addCleanup(clean)

    def test_hash_and_verify(self):
        h = localadmin.make_hash("ein-gutes-passwort")
        self.assertNotIn("ein-gutes-passwort", h)
        self.assertTrue(localadmin.verify_hash("ein-gutes-passwort", h))
        self.assertFalse(localadmin.verify_hash("ein-gutes-passwort!", h))
        self.assertNotEqual(h, localadmin.make_hash("ein-gutes-passwort"))   # own salt every time
        for broken in ("", "scrypt:1:2", "md5:x:y", "scrypt:999999999:8:1:AA:AA", None):
            self.assertFalse(localadmin.verify_hash("ein-gutes-passwort", broken))
        without_scrypt = types.SimpleNamespace(pbkdf2_hmac=hashlib.pbkdf2_hmac)   # a Python built without it
        with mock.patch.object(localadmin, "hashlib", without_scrypt):
            pbkdf2 = localadmin.make_hash("ein-gutes-passwort")
        self.assertTrue(pbkdf2.startswith("pbkdf2:"))
        self.assertTrue(localadmin.verify_hash("ein-gutes-passwort", pbkdf2))

    def test_sources_and_setting_it(self):
        with admin_env(""):
            self.assertEqual(localadmin.source(), "")
            self.assertFalse(auth.required())
            with contextlib.redirect_stdout(io.StringIO()):
                localadmin.setup_code()
            localadmin.set_password("ein-gutes-passwort")
            self.assertEqual(localadmin.source(), "stored")
            self.assertTrue(localadmin.check("ein-gutes-passwort"))
            self.assertFalse(localadmin.check("falsch-falsch"))
            self.assertNotIn("ein-gutes-passwort", localadmin.HASH_FILE.read_text())
            self.assertEqual(stat.S_IMODE(localadmin.HASH_FILE.stat().st_mode), 0o600)
            self.assertFalse(localadmin.CODE_FILE.exists())   # the setup is over
            with self.assertRaises(ValueError):
                localadmin.set_password("kurz")
        with admin_env("aus-der-compose"):   # docker-compose wins and can only be changed there
            self.assertEqual(localadmin.source(), "env")
            self.assertTrue(localadmin.check("aus-der-compose"))
            self.assertFalse(localadmin.check("ein-gutes-passwort"))
            with self.assertRaises(ValueError):
                localadmin.set_password("noch-ein-passwort")

    def test_sessions_end_when_the_password_changes(self):
        with admin_env(""):
            localadmin.set_password("ein-gutes-passwort")
            self.assertEqual(auth.login("", "ein-gutes-passwort"), auth.NOTFALL)
            token = auth.make_token(auth.NOTFALL)
            self.assertEqual(auth.read_token(token), auth.NOTFALL)
            localadmin.set_password("ein-neues-passwort")
            self.assertIsNone(auth.read_token(token))
            with self.assertRaises(auth.LoginError):
                auth.login("", "ein-gutes-passwort")

    def test_setup_code(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code, created = localadmin.setup_code()
        self.assertTrue(created)
        self.assertRegex(code, r"^[A-HJ-NP-Z2-9]{4}-[A-HJ-NP-Z2-9]{4}$")
        self.assertIn(f"enter the setup code {code}", out.getvalue())   # the server log, in English
        self.assertEqual(localadmin.setup_code(), (code, False))         # stays the same, also after a restart
        self.assertEqual(stat.S_IMODE(localadmin.CODE_FILE.stat().st_mode), 0o600)
        self.assertTrue(localadmin.check_code(code))
        self.assertTrue(localadmin.check_code(" " + code.lower().replace("-", "") + " "))
        self.assertFalse(localadmin.check_code("AAAA-AAAA"))
        self.assertFalse(localadmin.check_code(""))
        localadmin.CODE_FILE.unlink()
        self.assertFalse(localadmin.check_code(code))


def _loopback(address, *args, **kwargs):
    if address[0] != "127.0.0.1":
        raise env.NetworkBlocked("only 127.0.0.1")
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(10)
    env._real_connect(s, address)
    return s


class ServerTest(unittest.TestCase):
    """A real server on 127.0.0.1, as the container sees it (Handler.network on)."""

    def setUp(self):
        clean()
        self.addCleanup(clean)
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), web.Handler)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)
        web.Handler.network = True
        self.addCleanup(setattr, web.Handler, "network", False)
        sleep = mock.patch.object(web.time, "sleep")
        sleep.start()
        self.addCleanup(sleep.stop)
        quiet = contextlib.redirect_stdout(io.StringIO())
        self.log = quiet.__enter__()
        self.addCleanup(quiet.__exit__, None, None, None)

    def request(self, method, path, body=None, cookie=None, header=True):
        web.Handler._pw_cache = (0.0, None)
        headers = {"Content-Type": "application/json"}
        if header:
            headers["X-Tuttiphon"] = "1"
        if cookie:
            headers["Cookie"] = cookie.split(";")[0]
        with mock.patch("socket.create_connection", _loopback):
            c = http.client.HTTPConnection("127.0.0.1", self.server.server_address[1], timeout=20)
            c.request(method, path, body=json.dumps(body) if body is not None else None, headers=headers)
            r = c.getresponse()
            data = r.read()
            c.close()
        return r.status, json.loads(data or b"null"), r.getheader("Set-Cookie")

    def test_first_start_setup(self):
        with admin_env(""):
            status, info, _ = self.request("GET", "/api/login")
            self.assertTrue(info["setup"])
            code = localadmin.CODE_FILE.read_text().strip()
            self.assertIn(code, self.log.getvalue())
            self.assertEqual(self.request("GET", "/api/status")[0], 401)
            self.assertEqual(self.request("POST", "/api/setup", {"code": code, "password": "ein-gutes-passwort"},
                                          header=False)[0], 403)
            status, data, _ = self.request("POST", "/api/setup", {"code": "AAAA-AAAA", "password": "ein-gutes-passwort"})
            self.assertEqual(status, 401)
            self.assertIn("setup code", data["error"])
            self.assertEqual(self.request("POST", "/api/setup", {"code": code, "password": "kurz"})[0], 401)
            self.assertFalse(localadmin.configured())
            status, data, cookie = self.request("POST", "/api/setup", {"code": code, "password": "ein-gutes-passwort"})
            self.assertEqual((status, data["user"]), (200, auth.NOTFALL))
            self.assertIn("HttpOnly", cookie)
            self.assertEqual(localadmin.source(), "stored")
            self.assertFalse(localadmin.CODE_FILE.exists())
            status, st, _ = self.request("GET", "/api/status", cookie=cookie)   # signed in as local administrator
            self.assertEqual((status, st["env"]["adminPassword"]), (200, "stored"))
            self.assertFalse(self.request("GET", "/api/login")[1]["setup"])
            self.assertEqual(self.request("POST", "/api/setup", {"code": code, "password": "noch-ein-passwort"})[0], 409)
            self.assertTrue(localadmin.check("ein-gutes-passwort"))
            self.assertIn("Setup: the password of the local administrator is set.", self.log.getvalue())

    def test_guessing_the_code_is_blocked(self):
        with admin_env(""):
            self.request("GET", "/api/login")
            code = localadmin.CODE_FILE.read_text().strip()
            for _ in range(10):
                self.request("POST", "/api/setup", {"code": "AAAA-AAAA", "password": "ein-gutes-passwort"})
            self.assertEqual(self.request("POST", "/api/setup", {"code": code, "password": "ein-gutes-passwort"})[0], 429)
            self.assertFalse(localadmin.configured())

    def test_changing_it(self):
        with admin_env(""):
            localadmin.set_password("ein-gutes-passwort")
            _s, _d, cookie = self.request("POST", "/api/login", {"username": "", "password": "ein-gutes-passwort"})
            status, data, _ = self.request("POST", "/api/admin-password",
                                           {"current": "falsch-falsch", "password": "ein-neues-passwort"}, cookie=cookie)
            self.assertEqual(status, 400)   # not 401 – that would send the page to the sign-in
            self.assertTrue(localadmin.check("ein-gutes-passwort"))
            status, _d, new_cookie = self.request("POST", "/api/admin-password",
                                                  {"current": "ein-gutes-passwort", "password": "ein-neues-passwort"},
                                                  cookie=cookie)
            self.assertEqual(status, 200)
            self.assertTrue(localadmin.check("ein-neues-passwort"))
            self.assertEqual(self.request("GET", "/api/status", cookie=cookie)[0], 401)       # old sessions end …
            self.assertEqual(self.request("GET", "/api/status", cookie=new_cookie)[0], 200)   # … this browser stays in
        with admin_env("aus-der-compose"):
            _s, _d, cookie = self.request("POST", "/api/login", {"username": "", "password": "aus-der-compose"})
            status, data, _ = self.request("POST", "/api/admin-password",
                                           {"current": "aus-der-compose", "password": "ein-neues-passwort"}, cookie=cookie)
            self.assertEqual(status, 400)
            self.assertIn("docker-compose.yaml", data["error"])

    def test_users_cannot_change_it(self):
        with admin_env(""), mock.patch.object(auth, "role_of", return_value="user"):
            localadmin.set_password("ein-gutes-passwort")
            token = auth.make_token("lukas")
            status, _d, _c = self.request("POST", "/api/admin-password",
                                          {"current": "ein-gutes-passwort", "password": "ein-neues-passwort"},
                                          cookie=f"tuttiphon={token}")
            self.assertEqual(status, 403)
            self.assertTrue(localadmin.check("ein-gutes-passwort"))

    def test_on_the_pc_setting_it_turns_on_sign_in(self):
        web.Handler.network = False
        with admin_env(""):
            self.assertEqual(self.request("GET", "/api/status")[0], 200)   # no sign-in yet
            status, _d, cookie = self.request("POST", "/api/admin-password", {"password": "ein-gutes-passwort"})
            self.assertEqual(status, 200)
            self.assertEqual(self.request("GET", "/api/status")[0], 401)
            self.assertEqual(self.request("GET", "/api/status", cookie=cookie)[0], 200)


if __name__ == "__main__":
    unittest.main()
