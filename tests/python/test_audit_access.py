"""Findings of the 0.16 audit: the administrator password cannot be deleted by an empty value, placeholders in any
spelling, on the network never without a password, sign-in only from the interface, the sign-in lock per account and
address, trusted reverse proxies, links in the shared folder are not followed."""
from tests.python import env  # noqa: F401  (before app.*)

import http.client
import json
import os
import socket
import threading
import unittest
from http.server import ThreadingHTTPServer
from unittest import mock

from app import auth, config, instances, tasks, web


class TestAdminPassword(unittest.TestCase):
    def setUp(self):
        env.reset_caches()
        self.addCleanup(env.reset_caches)
        self.env_before = config.ENV_FILE.read_text() if config.ENV_FILE.exists() else None
        self.addCleanup(self._restore)

    def _restore(self):
        if self.env_before is None:
            config.ENV_FILE.unlink(missing_ok=True)
        else:
            config.ENV_FILE.write_text(self.env_before)
        env.reset_caches()

    def test_empty_value_keeps_the_password(self):
        config.ENV_FILE.write_text("TUTTIPHON_ADMIN_PASSWORD=erstes-passwort\n")
        env.reset_caches()
        config.save_env({"TUTTIPHON_ADMIN_PASSWORD": "", "NAV_URL": "http://nav.test"})
        env.reset_caches()
        self.assertEqual(config.admin_password(), "erstes-passwort")
        self.assertTrue(auth.required())
        config.save_env({"TUTTIPHON_ADMIN_PASSWORD": "zweites-passwort"})
        env.reset_caches()
        self.assertEqual(config.admin_password(), "zweites-passwort")
        self.assertEqual(config.ENV_FILE.read_text().count("TUTTIPHON_ADMIN_PASSWORD="), 1)

    def test_placeholders_in_any_spelling(self):
        for pw in ("change-me", "Change-Me", " CHANGE-ME ", "kurz", "", None, 5):
            self.assertTrue(config.weak_password(pw), pw)
        self.assertFalse(config.weak_password("ein-gutes-passwort"))
        with self.assertRaises(ValueError):
            web.api_env_save({"TUTTIPHON_ADMIN_PASSWORD": "Change-Me"})


def _loopback(address, *args, **kwargs):
    """Only here: connections to 127.0.0.1 (otherwise the test environment blocks every network)."""
    if address[0] != "127.0.0.1":
        raise env.NetworkBlocked("only 127.0.0.1")
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(10)
    env._real_connect(s, address)
    return s


class TestServer(unittest.TestCase):
    """A real server on 127.0.0.1 – as the container would see it, with Handler.network switched on."""

    def setUp(self):
        env.reset_caches()
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), web.Handler)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)
        self.addCleanup(setattr, web.Handler, "network", False)
        self.addCleanup(setattr, web.Handler, "_pw_cache", (0.0, None))
        self.addCleanup(env.reset_caches)

    def request(self, method, path, body=None, headers=None):
        web.Handler._pw_cache = (0.0, None)
        with mock.patch("socket.create_connection", _loopback):
            c = http.client.HTTPConnection("127.0.0.1", self.server.server_address[1], timeout=10)
            c.request(method, path, body=json.dumps(body) if body is not None else None,
                      headers={"Content-Type": "application/json", **(headers or {})})
            r = c.getresponse()
            data = r.read()
            c.close()
        return r.status, data, r.getheader("Set-Cookie")

    def test_on_the_network_never_without_a_password(self):
        web.Handler.network = True
        with mock.patch.dict(os.environ, {"TUTTIPHON_ADMIN_PASSWORD": ""}), \
                mock.patch.object(web, "admin_password", return_value=""):
            status, _, _ = self.request("GET", "/api/status")
            self.assertEqual(status, 503)
        with mock.patch.object(web, "admin_password", return_value="Change-Me"):
            self.assertEqual(self.request("GET", "/api/status")[0], 503)
        with mock.patch.object(web, "admin_password", return_value="ein-gutes-passwort"):
            self.assertEqual(self.request("GET", "/api/status")[0], 401)   # sign-in required, not open
        web.Handler.network = False
        with mock.patch.object(web, "admin_password", return_value=""):
            self.assertNotEqual(self.request("GET", "/api/status")[0], 503)   # only on the PC: local without sign-in

    def test_sign_in_page_learns_whether_navidrome_is_connected(self):
        # public, before signing in: until address and admin access are there, only the local administrator gets in
        with mock.patch.object(web, "admin_password", return_value="ein-gutes-passwort"):
            with mock.patch.object(web, "load_env", return_value={"NAV_URL": "http://nav.test"}):
                status, data, _ = self.request("GET", "/api/login")
                self.assertEqual((status, json.loads(data)), (200, {"navidrome": False}))
            full = {"NAV_URL": "http://nav.test", "NAV_ADMIN_USER": "admin-test", "NAV_ADMIN_PASS": "pw-test"}
            with mock.patch.object(web, "load_env", return_value=full):
                status, data, _ = self.request("GET", "/api/login")
                self.assertEqual(json.loads(data), {"navidrome": True})
                self.assertNotIn(b"admin-test", data)   # nothing but the yes/no
            self.assertEqual(self.request("GET", "/api/status")[0], 401)   # everything else still needs a sign-in

    def test_sign_in_only_from_the_interface(self):
        with mock.patch.object(web, "admin_password", return_value="ein-gutes-passwort"):
            status, _, _ = self.request("POST", "/api/login", {"username": "", "password": "falsch-falsch"})
            self.assertEqual(status, 403)
            with mock.patch.object(auth, "admin_password", return_value="ein-gutes-passwort"), \
                    mock.patch.object(web.time, "sleep"):
                status, _, cookie = self.request("POST", "/api/login", {"username": "", "password": "ein-gutes-passwort"},
                                                 {"X-Tuttiphon": "1"})
            self.assertEqual(status, 200)
            self.assertNotIn("Secure", cookie)   # directly, without a trusted proxy


class TestLoginLock(unittest.TestCase):
    def setUp(self):
        web._login_fails.clear()
        self.addCleanup(web._login_fails.clear)

    def fail(self, ip, n, name=""):
        h = web.Handler.__new__(web.Handler)
        h.client_address = (ip, 1)
        h.headers = {}
        for _ in range(n):
            h._body = lambda: {"username": name, "password": "falsch-falsch"}
            sent = {}
            h._json = lambda data, status=200, headers=None: sent.update(status=status) or status
            with mock.patch.object(auth, "login", side_effect=auth.LoginError("x")), mock.patch.object(web.time, "sleep"), \
                    mock.patch.object(web.events, "say"), mock.patch.object(web, "load_env", return_value={}):
                h._login()
        return sent["status"]

    def test_one_address_cannot_lock_an_account_for_everyone(self):
        self.assertEqual(self.fail("10.0.0.66", 11), 429)        # this address is locked for the account …
        self.assertEqual(self.fail("10.0.0.7", 1), 401)          # … everyone else may still try
        self.assertEqual(self.fail("10.0.0.66", 1, "jonas"), 401)   # and the address for other accounts (until 30)


class TestTrustedProxy(unittest.TestCase):
    def test_client_address_only_from_trusted_proxies(self):
        h = {"X-Forwarded-For": "6.6.6.6, 203.0.113.9", "X-Forwarded-Proto": "https"}
        self.assertEqual(web.client_of("172.18.0.5", h, []), ("172.18.0.5", False))              # nothing trusted
        self.assertEqual(web.client_of("172.18.0.5", h, ["10.0.0.0/8"]), ("172.18.0.5", False))  # not this one
        self.assertEqual(web.client_of("172.18.0.5", h, ["172.16.0.0/12"]), ("203.0.113.9", True))
        # a chain of trusted proxies: the last address none of them added counts
        h2 = {"X-Forwarded-For": "6.6.6.6, 203.0.113.9, 172.18.0.9"}
        self.assertEqual(web.client_of("172.18.0.5", h2, ["172.16.0.0/12"]), ("203.0.113.9", False))
        self.assertEqual(web.client_of("172.18.0.5", {}, ["172.18.0.5"]), ("172.18.0.5", False))
        self.assertEqual(web.client_of("172.18.0.5", h, ["kein-netz"]), ("172.18.0.5", False))
        self.assertEqual(web.client_of("::ffff:172.18.0.5", h, ["172.16.0.0/12"]), ("203.0.113.9", True))   # via "::"


class TestSharedFolderLinks(unittest.TestCase):
    def setUp(self):
        env.reset_caches()
        self.addCleanup(env.reset_caches)

    def test_lock_file_link_is_not_followed(self):
        victim = env.ROOT / "opfer.txt"
        victim.write_text("geheim")
        os.chmod(victim, 0o600)
        self.addCleanup(victim.unlink, missing_ok=True)
        link = instances.shared_dir() / "task.lock"
        link.unlink(missing_ok=True)
        link.symlink_to(victim)
        self.addCleanup(link.unlink, missing_ok=True)
        lock = tasks._InstanceLock()
        with mock.patch.object(instances, "busy_elsewhere", return_value=False):
            lock.acquire()
        lock.release()
        self.assertEqual(os.stat(victim).st_mode & 0o777, 0o600)
        self.assertFalse(link.is_symlink())

    def test_shared_folder_as_link_is_not_used(self):
        target = env.ROOT / "fremd"
        target.mkdir(exist_ok=True)
        os.chmod(target, 0o700)
        link = env.ROOT / "geteilt-link"
        link.unlink(missing_ok=True)
        link.symlink_to(target)
        self.addCleanup(link.unlink, missing_ok=True)
        with mock.patch.dict(os.environ, {"TUTTIPHON_SHARED_DIR": str(link)}):
            instances._state.update(dir=None, at=0.0)
            self.assertEqual(instances.shared_dir(), instances.STATE_DIR)
        instances._state.update(dir=None, at=0.0)
        self.assertEqual(os.stat(target).st_mode & 0o777, 0o700)

    def test_broken_report_does_not_break_the_list(self):
        folder = instances.shared_dir()
        bad = folder / "instance-pc_kaputt.json"
        bad.write_text(json.dumps({"id": "pc:kaputt", "ts": "x", "host": "kaputt"}))
        self.addCleanup(bad.unlink, missing_ok=True)
        self.assertEqual([o for o in instances.others() if o["host"] == "kaputt"], [])

    def test_write_atomic_never_follows_a_link(self):
        victim = env.ROOT / "opfer2.txt"
        victim.write_text("geheim")
        os.chmod(victim, 0o600)
        self.addCleanup(victim.unlink, missing_ok=True)
        path = env.ROOT / "ziel.json"
        path.unlink(missing_ok=True)
        path.symlink_to(victim)
        self.addCleanup(path.unlink, missing_ok=True)
        config.write_atomic(path, "{}", mode=0o666)
        self.assertEqual(os.stat(victim).st_mode & 0o777, 0o600)   # the link was replaced, not followed
        self.assertFalse(path.is_symlink())
        self.assertEqual(os.stat(path).st_mode & 0o777, 0o666)


if __name__ == "__main__":
    unittest.main()
