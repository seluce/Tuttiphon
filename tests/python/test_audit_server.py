"""Findings of the server audit (0.17): one account must not be able to break playlists or pages for everyone (C1),
sign-in lockout without races (M1), limits per account (M2), kid-safe mode, notifications, headers and file modes
(L1–L11), damaged state files are set aside instead of overwritten, the stored password that stopped working (H1)."""
from tests.python import env  # noqa: F401  (before app.*)

import contextlib
import copy
import datetime as dt
import email.message
import io
import json
import os
import stat
import threading
import time
import unittest
from unittest import mock

from app import (auth, config, deezer, events, feedback, i18n, langzeit, lautstaerke, liedtext, mixer, notify, playlists,
                 rueckblick, similar, suggest, web, webpush)
from app.library import Library
from app.rules import BuildContext
from tests.python.factory import base_config, random_songs, song

JONAS = {"user": "Jonas", "role": "user", "own": ["jonas"], "persons": ["jonas"], "local": False}
NOBODY = {"user": None, "role": "none", "own": [], "persons": [], "local": False}


def save(cfg):
    """Write a configuration as it is – also with values validate_config would reject (state of an older version)."""
    config._write(cfg)
    env.reset_caches()


def merged(incoming, m=JONAS):
    config.save_from_ui(lambda cur: auth.merge_user_changes(cur, incoming, m), keep_accounts=True)
    env.reset_caches()
    return config.load_config()


def as_user(test, m=JONAS):
    auth.set_current(m)
    test.addCleanup(auth.set_current, NOBODY)


def request(method, path, body=b"", headers=None):
    """Run one request through web.Handler without a network – -> (status line, headers, body)."""
    h = web.Handler.__new__(web.Handler)
    h.rfile, h.wfile = io.BytesIO(body), io.BytesIO()
    h.command, h.path, h.request_version = method, path, "HTTP/1.1"
    h.requestline = f"{method} {path} HTTP/1.1"
    h.client_address = ("127.0.0.1", 40000)
    h.close_connection = True
    msg = email.message.Message()
    for k, v in {"Host": "127.0.0.1:8765", "Content-Length": str(len(body)), "X-Tuttiphon": "1", **(headers or {})}.items():
        msg[k] = v
    h.headers = msg
    getattr(h, "do_" + method)()
    raw = h.wfile.getvalue()
    head, _, content = raw.partition(b"\r\n\r\n")
    lines = head.decode("latin-1").split("\r\n")
    return lines[0], {k.lower(): v for k, v in (x.split(": ", 1) for x in lines[1:])}, content


class FiniteJsonTest(unittest.TestCase):
    """C1: 1e999, Infinity and NaN in a request are refused – they would end up as endless numbers in int()."""

    def body(self, raw):
        h = web.Handler.__new__(web.Handler)
        h.rfile = io.BytesIO(raw.encode())
        h.headers = {"Content-Length": str(len(raw.encode()))}
        return h._body()

    def test_non_finite_numbers_refused(self):
        for raw in ('{"minDuration": 1e999}', '{"x": [1, -1e400]}', '{"x": Infinity}', '{"x": -Infinity}', '{"x": NaN}',
                    '{"a": {"b": [{"c": 1E+999}]}}'):
            with self.assertRaises(ValueError, msg=raw):
                self.body(raw)
        self.assertEqual(self.body('{"a": 1.5, "b": [2, -3e10]}'), {"a": 1.5, "b": [2, -3e10]})

    def test_put_config_with_overflow_is_a_400(self):
        status, _h, content = request("PUT", "/api/config", b'{"settings": {"minDuration": 1e999}}')
        self.assertIn(" 400 ", status)
        self.assertIn("error", json.loads(content))


class BrokenPlaylistTest(unittest.TestCase):
    """C1: values that would break int() are refused when saving – and a playlist saved like that before only
    fails on its own (plan, write, status, band and song window)."""

    def setUp(self):
        env.reset_caches()
        env.clear_dir(env.PLAYLISTS)
        playlists.MANAGED_FILE.unlink(missing_ok=True)
        playlists._broken_said.clear()
        self.lib = Library(random_songs(300))
        self.addCleanup(save, base_config())
        self.addCleanup(env.clear_dir, env.PLAYLISTS)
        self.addCleanup(playlists.MANAGED_FILE.unlink, missing_ok=True)

    def test_validation_refuses_values_that_break_writing(self):
        bad = [{"minDuration": "abc"}, {"minDuration": {"x": 1}}, {"minDuration": 1e999}, {"minDuration": float("nan")},
               {"minDuration": -5}, {"minDuration": True}, {"radio": {"seed": ["Band A"], "bands": "x"}},
               {"radio": {"seed": ["Band A"], "bands": 0}}, {"radio": {"seed": ["Band A"], "bands": 2.5}},
               {"type": "mix", "mix": {"flavor": 5}}, {"stil": ["*"]}, {"limit": float("inf")},
               {"name": "x" * 500}, {"color": "url(https://example.com/x)"}]
        for extra in bad:
            cfg = base_config()
            cfg["playlists"] = [{"id": "t", "person": "jonas", "welt": "kinder", "stil": "*", **extra}]
            with self.assertRaises(ValueError, msg=extra):
                config.validate_config(cfg)
        cfg = base_config()
        cfg["playlists"] = [{"id": "t", "person": "jonas", "welt": "kinder", "stil": "*", "minDuration": None},
                            {"id": "u", "person": "jonas", "welt": "kinder", "stil": "*", "minDuration": 90},
                            {"id": "r", "person": "jonas", "welt": "*", "stil": "*", "type": "mix",
                             "radio": {"seed": ["Band A"], "bands": 25}, "color": "#a0f"}]
        config.validate_config(cfg)
        cfg["welten"][0]["minDuration"] = "x"
        with self.assertRaises(ValueError):
            config.validate_config(cfg)

    def broken_config(self, value=1e999):
        cfg = base_config()
        cfg["playlists"] = [{"id": "ok", "person": "familie", "welt": "kinder", "stil": "*", "status": "aktiv"},
                            {"id": "evil", "person": "jonas", "welt": "kinder", "stil": "*", "status": "aktiv",
                             "minDuration": value, "radio": None}]
        save(cfg)
        return cfg   # as in memory: a stored endless number becomes null when loading (see test_endless_number_loads_as_null)

    def test_plan_skips_and_logs_a_broken_playlist(self):
        for value in (1e999, "abc", {"x": 1}):
            cfg = self.broken_config(value)
            lines, failed = [], []
            out = playlists.plan(cfg, BuildContext(self.lib), log=lines.append, failed=failed)
            self.assertEqual([p["id"] for p, _f, _n in out], ["ok"])
            self.assertEqual([p["id"] for p, _e in failed], ["evil"])
            self.assertTrue(any("evil" in x for x in lines), lines)

    def test_write_keeps_the_file_of_a_broken_playlist(self):
        cfg = base_config()
        cfg["playlists"] = [{"id": "ok", "person": "familie", "welt": "kinder", "stil": "*", "status": "aktiv"},
                            {"id": "evil", "person": "jonas", "welt": "kinder", "stil": "*", "status": "aktiv"}]
        save(cfg)
        cfg = config.load_config()
        playlists.write(cfg, BuildContext(self.lib), log=lambda *a: None)
        files = {p["id"]: p["file"] for p in cfg["playlists"]}
        self.assertTrue((env.PLAYLISTS / files["evil"]).exists())
        cfg["playlists"][1]["minDuration"] = float("inf")   # broken afterwards (saved by an older version)
        res = playlists.write(cfg, BuildContext(self.lib), log=lambda *a: None)
        self.assertTrue((env.PLAYLISTS / files["evil"]).exists())   # not removed from Navidrome
        self.assertTrue((env.PLAYLISTS / files["ok"]).exists())
        self.assertEqual(len(res["failed"]), 1)
        self.assertEqual(playlists.load_managed()["current"].get(files["evil"]), "evil")

    def test_status_shows_the_broken_one_and_the_others(self):
        cfg = self.broken_config()   # an endless number in memory: OverflowError in int()
        with contextlib.redirect_stdout(io.StringIO()) as out:
            st = playlists.status(cfg, BuildContext(self.lib))
            playlists.status(cfg, BuildContext(self.lib))
        rows = {r["id"]: r for r in st["playlists"]}
        self.assertEqual(rows["evil"]["state"], "fehler")
        self.assertNotEqual(rows["ok"]["state"], "fehler")
        self.assertEqual(out.getvalue().count("evil"), 1)   # said once, not every time the list is computed

    def test_endless_number_loads_as_null(self):
        self.broken_config(float("inf"))
        self.assertIn("Infinity", config.CONFIG_FILE.read_text(encoding="utf-8"))   # as an older version wrote it
        evil = next(p for p in config.load_config()["playlists"] if p["id"] == "evil")
        self.assertIsNone(evil["minDuration"])
        status, _h, content = request("GET", "/api/config")
        self.assertIn(" 200 ", status)
        self.assertNotIn(b"Infinity", content)
        json.loads(content, parse_constant=lambda c: self.fail(c))

    def test_band_window_and_playlists_page_for_everyone(self):
        self.broken_config("abc")
        with mock.patch.object(web.CACHE, "get", lambda force=False: self.lib), \
                mock.patch.object(web.images, "artist_info", lambda aid: {}), \
                mock.patch.object(web.playlists, "native_api", side_effect=web.NavidromeError("offline")), \
                contextlib.redirect_stdout(io.StringIO()):
            for m in ({"user": "niklas", "role": "admin", "own": ["niklas"], "persons": [], "local": False},
                      {"user": "oma", "role": "user", "own": ["oma"], "persons": ["oma"], "local": False}):
                auth.set_current(m)
                self.addCleanup(auth.set_current, NOBODY)
                web._memo.clear()
                self.assertTrue(web.api_artist({"name": "Band A"})["songs"])
                self.assertIn("playlists", web.api_playlists())


class LoginLockoutTest(unittest.TestCase):
    """M1: attempts that are still being checked with Navidrome count – 200 at once do not get 200 tries."""

    class Fake(web.Handler):
        def __init__(self, user, pw, ip="192.0.2.7"):
            self.user, self.pw, self.ip, self.code = user, pw, ip, None

        def _body(self):
            return {"username": self.user, "password": self.pw}

        def _client(self):
            return self.ip, False

        def _json(self, obj, code=200, headers=None):
            self.code = code

    def setUp(self):
        web._login_fails.clear()
        web._login_pending.clear()
        web._login_blocked_said.clear()

    def test_parallel_attempts_are_counted(self):
        tried, lock = [], threading.Lock()

        def fake_login(username, password, remember=True):
            with lock:
                tried.append(password)
            time.sleep(0.05)
            raise auth.LoginError("wrong")
        handlers = [self.Fake("lukas", f"pw{i}") for i in range(60)]
        with mock.patch.object(auth, "login", fake_login), mock.patch.object(web.time, "sleep", lambda s: None), \
                contextlib.redirect_stdout(io.StringIO()) as out:
            threads = [threading.Thread(target=h._login) for h in handlers]
            for t in threads:
                t.start()
            for t in threads:
                t.join()
        self.assertEqual(len(tried), 10)
        self.assertEqual(sum(1 for h in handlers if h.code == 429), 50)
        self.assertEqual(dict(web._login_pending), {})
        self.assertEqual(out.getvalue().count("blocked"), 1)   # the block is said once, not 50 times

    def test_not_counting_errors_release_the_reservation(self):
        with mock.patch.object(auth, "login", side_effect=auth.LoginError("offline", counts=False)), \
                contextlib.redirect_stdout(io.StringIO()):
            for i in range(30):
                h = self.Fake("lukas", "x")
                h._login()
                self.assertEqual(h.code, 401)
        self.assertEqual(dict(web._login_pending), {})
        self.assertEqual(web._login_fails, {})

    def test_sign_in_name_cannot_fake_log_lines(self):
        with mock.patch.object(auth, "login", side_effect=auth.LoginError("wrong")), \
                mock.patch.object(web.time, "sleep", lambda s: None), contextlib.redirect_stdout(io.StringIO()) as out:
            self.Fake("x\nSigned in: niklas\r\x1b[2J" + "y" * 300, "pw")._login()
        lines = out.getvalue().splitlines()
        self.assertEqual(len(lines), 1, lines)
        self.assertNotIn("\x1b", lines[0])
        self.assertLess(len(lines[0]), 160)

    def test_events_clean(self):
        self.assertEqual(events.clean("a b\x00c\n"), "abc\n")
        self.assertEqual(events.clean("a\nb\tc", keep_lines=False), "a b c")


class QuotaTest(unittest.TestCase):
    """M2: an account can create at most MAX_USER_PLAYLISTS playlists and MAX_USER_PERSONS profiles."""

    def setUp(self):
        save(base_config())
        self.addCleanup(save, base_config())

    def incoming(self):
        return copy.deepcopy(auth.view_config(config.load_config(), JONAS))

    def test_playlists_limited(self):
        inc = self.incoming()
        inc["playlists"] += [{"id": f"x{i}", "person": "jonas", "welt": "kinder", "stil": "*"}
                             for i in range(auth.MAX_USER_PLAYLISTS)]
        self.assertEqual(sum(p["person"] == "jonas" for p in merged(inc)["playlists"]), auth.MAX_USER_PLAYLISTS)
        inc = self.incoming()
        inc["playlists"].append({"id": "one-more", "person": "jonas", "welt": "kinder", "stil": "*"})
        with self.assertRaises(ValueError):
            merged(inc)
        inc = self.incoming()   # changing or deleting stays possible
        inc["playlists"] = [p for p in inc["playlists"] if p["id"] != "x0"]
        self.assertEqual(sum(p["person"] == "jonas" for p in merged(inc)["playlists"]), auth.MAX_USER_PLAYLISTS - 1)

    def test_no_second_profile(self):
        inc = self.incoming()
        inc["personen"] += [{"id": f"j{i}", "name": f"J {i}", "user": "Jonas"} for i in range(5)]
        out = merged(inc)
        self.assertEqual(sum((p.get("user") or "") == "Jonas" for p in out["personen"]), 1)   # one person per account

    def test_text_lengths_and_colors(self):
        for field, value in (("name", "x" * 500), ("prefix", "y" * 100), ("color", "url(https://example.com/t)"),
                             ("color", "red; background: url(x)"), ("icon", "z" * 200)):
            inc = self.incoming()
            next(p for p in inc["personen"] if p["id"] == "jonas")[field] = value
            with self.assertRaises(ValueError, msg=field):
                merged(inc)
        for color in ("#a0f", "#AA00ff", "hsl(210 60% 50%)", "hsl(12, 50%, 40%)", ""):
            inc = self.incoming()
            next(p for p in inc["personen"] if p["id"] == "jonas")["color"] = color
            merged(inc)


class KidSafeAccountTest(unittest.TestCase):
    """L1/L2: kid-safe mode stays on for a user (only the administrator turns it off), the search hides songs tagged
    as explicit."""

    def setUp(self):
        cfg = base_config()
        cfg["personen"][1]["clean"] = True
        save(cfg)
        self.addCleanup(save, base_config())
        as_user(self)

    def test_kid_safe_stays_on(self):
        inc = copy.deepcopy(auth.view_config(config.load_config(), JONAS))
        next(p for p in inc["personen"] if p["id"] == "jonas")["clean"] = False
        out = merged(inc)
        self.assertTrue(next(p for p in out["personen"] if p["id"] == "jonas")["clean"])

    def test_search_hides_explicit_songs(self):
        lib = Library([song("e1", "Explicit Song", genres=["Children"]), song("c1", "Explicit Clean")])
        lib.songs[0]["explicitStatus"] = "explicit"
        with mock.patch.object(web.CACHE, "get", lambda force=False: lib), mock.patch.object(liedtext, "ready", lambda: False), \
                mock.patch.object(liedtext, "status", lambda: {"running": True}), \
                mock.patch.object(liedtext, "derb", lambda allow=(): frozenset()):
            res = web.api_search({"q": "explicit"})
            self.assertEqual([s["id"] for s in res["songs"]], ["c1"])
            auth.set_current({**JONAS, "role": "admin"})
            self.assertEqual(len(web.api_search({"q": "explicit"})["songs"]), 2)

    def test_search_checks_kid_safe_once_per_request(self):
        # the search looks at thousands of songs – the account and its settings must not be read again for each one
        lib = Library([song(f"s{i}", f"Explicit {i}") for i in range(300)])
        calls = []
        real = auth.current
        with mock.patch.object(web.CACHE, "get", lambda force=False: lib), mock.patch.object(liedtext, "ready", lambda: False), \
                mock.patch.object(liedtext, "status", lambda: {"running": True}), \
                mock.patch.object(liedtext, "derb", lambda allow=(): frozenset()), \
                mock.patch.object(auth, "current", lambda: calls.append(1) or real()):
            web.api_search({"q": "explicit"})
        self.assertLess(len(calls), 10)


class NotifyTestTest(unittest.TestCase):
    """L3: a user's test message only goes to their own topic – never to the administrator's or someone else's."""

    def setUp(self):
        cfg = base_config()
        cfg["settings"]["notify"] = {"enabled": True, "topic": "admin-topic"}
        cfg["personen"][3]["push"] = "oma-topic"
        save(cfg)
        self.addCleanup(save, base_config())
        web._notify_tests.clear()
        as_user(self)
        self.sent = []
        patcher = mock.patch.object(notify, "send", lambda topic, *a, **k: self.sent.append(topic) or True)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_no_fallback_to_the_admin_topic(self):
        with self.assertRaises(ValueError):
            web.api_notify_test({"person": "jonas"})
        for topic in ("admin-topic", "ADMIN-topic", "oma-topic"):
            web._notify_tests.clear()
            with self.assertRaises(PermissionError):
                web.api_notify_test({"person": "jonas", "topic": topic})
        self.assertEqual(self.sent, [])
        web.api_notify_test({"person": "jonas", "topic": "jonas-own"})
        self.assertEqual(self.sent, ["jonas-own"])

    def test_admin_keeps_the_fallback(self):
        auth.set_current({**JONAS, "role": "admin"})
        web.api_notify_test({})
        self.assertEqual(self.sent, ["admin-topic"])


class ResponsesTest(unittest.TestCase):
    """L6, HEAD and 500: security headers, Server without the Python version, HEAD answers, errors without details."""

    def setUp(self):
        save(base_config())
        auth.set_current(NOBODY)

    def test_headers_and_head(self):
        status, headers, content = request("GET", "/api/changelog")
        self.assertIn(" 200 ", status)
        self.assertEqual(headers["x-content-type-options"], "nosniff")
        self.assertEqual(headers["x-frame-options"], "DENY")
        self.assertIn("frame-ancestors 'none'", headers["content-security-policy"])
        self.assertEqual(headers["referrer-policy"], "same-origin")
        self.assertEqual(headers["server"], "Tuttiphon")
        status, headers, content = request("HEAD", "/api/changelog")
        self.assertIn(" 200 ", status)
        self.assertEqual(content, b"")
        self.assertGreater(int(headers["content-length"]), 0)

    def test_500_without_details(self):
        def boom(q):
            raise TypeError("secret /volume1/path detail")
        with mock.patch.dict(web.Handler.GET_ROUTES, {"/api/home": boom}), contextlib.redirect_stdout(io.StringIO()) as log:
            status, _h, content = request("GET", "/api/home")
        self.assertIn(" 500 ", status)
        self.assertNotIn("secret", content.decode())
        self.assertNotIn("TypeError", content.decode())
        self.assertIn("secret", log.getvalue())   # the details are in the server log

    def test_changelog_nested_bullets(self):
        text = "# Changes\n\n## 1.0 – 2026-10-17\n\n- Top item\n  continued\n- Group:\n  - first sub\n    continued\n  - second sub\n"
        with mock.patch.object(web, "read_text", lambda path: text):
            out = web.api_changelog()
        self.assertEqual(out[0]["items"], ["Top item continued", "Group:", "first sub continued", "second sub"])
        self.assertEqual(out[0]["levels"], [0, 0, 1, 1])

    def test_changelog_without_dates_and_unreleased(self):
        text = "# Changes\n\n## Unreleased\n\n- New\n\n## 1.1.0\n\n- Feature\n\n## 1.0 – 2026-10-17\n\n- Old\n"
        with mock.patch.object(web, "read_text", lambda path: text):
            out = web.api_changelog()
        self.assertEqual([(v["version"], v["date"], v["unreleased"]) for v in out],
                         [("Unreleased", "", True), ("1.1.0", "", False), ("1.0", "2026-10-17", False)])
        self.assertEqual(out[1]["items"], ["Feature"])


class SmallFixesTest(unittest.TestCase):
    def test_m3u_name_without_line_breaks(self):
        lib = Library([song("a")])
        lib.real_path = lambda i: "A/a.opus"
        text = mixer.m3u(lib, [0], "Mix\r\n#EXTINF:0,evil\nx", "..")
        self.assertEqual(text.splitlines()[1], "#PLAYLIST:Mix #EXTINF:0,evil x")

    def test_public_url_only_http(self):
        with self.assertRaises(ValueError), mock.patch.object(web, "save_env") as saved:
            web.api_env_save({"NAV_PUBLIC_URL": "javascript:alert(1)"})
        saved.assert_not_called()
        self.assertEqual(web.nav_web_url({"NAV_PUBLIC_URL": "javascript:alert(1)", "NAV_URL": "http://nas:4533/"}),
                         "http://nas:4533")
        self.assertEqual(web.nav_web_url({"NAV_PUBLIC_URL": "https://music.example.org/"}), "https://music.example.org")

    def test_users_do_not_get_dismissed_dates(self):
        cfg = base_config()
        cfg["dismissed"], cfg["dismissedAt"] = ["x|y"], {"x|y": "2026-01-01"}
        self.assertNotIn("dismissedAt", auth.view_config(cfg, JONAS))
        self.assertIn("dismissedAt", auth.view_config(cfg, {**JONAS, "role": "admin"}))

    def test_file_modes(self):
        inside, outside = config.STATE_DIR / "modes.json", env.ROOT / "modes.txt"
        config.write_atomic(inside, "{}")
        config.write_atomic(outside, "x")
        self.assertEqual(stat.S_IMODE(inside.stat().st_mode), 0o640)
        self.assertEqual(stat.S_IMODE(outside.stat().st_mode), 0o664)
        inside.unlink()
        outside.unlink()

    def test_password_save_only_invalidates_on_change(self):
        as_user(self)
        with mock.patch.object(web, "load_env", lambda: {"NAV_URL": "http://nav", web.pass_key("Jonas"): "same"}), \
                mock.patch.object(web.Navidrome, "ping", lambda self: {}), mock.patch.object(web, "save_env") as saved, \
                mock.patch.object(web.CACHE, "invalidate") as inv, mock.patch.object(auth, "note_password"):
            web.api_me_password({"password": "same"})
            saved.assert_not_called()
            inv.assert_not_called()
            web.api_me_password({"password": "new"})
            saved.assert_called_once()
            inv.assert_called_once()


class StoredPasswordTest(unittest.TestCase):
    """H1: the interface learns when Navidrome no longer accepts the stored password of an account."""

    def setUp(self):
        auth.PASSWORDS_FILE.unlink(missing_ok=True)
        auth._pw.update(key=None, data={}, checking={})
        self.addCleanup(auth.PASSWORDS_FILE.unlink, missing_ok=True)
        self.addCleanup(auth._pw.update, key=None, data={}, checking={})

    def test_note_and_read(self):
        self.assertFalse(auth.password_rejected("Jonas"))
        auth.note_password("Jonas", False)
        self.assertTrue(auth.password_rejected("jonas"))
        auth.note_password("Jonas", True)
        self.assertFalse(auth.password_rejected("Jonas"))
        auth.note_password("Jonas", False)
        auth.note_password("Jonas", None)   # a new password: not tried yet
        self.assertFalse(auth.password_rejected("Jonas"))

    def test_background_check(self):
        err = web.NavidromeError("Navidrome: error 40")
        with mock.patch.object(auth.Navidrome, "ping", side_effect=err):
            auth.check_password_soon("Jonas", {"NAV_URL": "http://nav", config.pass_key("Jonas"): "old"})
            for t in [t for t in threading.enumerate() if t.name == "password-check"]:
                t.join(5)
        self.assertTrue(auth.password_rejected("Jonas"))
        with mock.patch.object(auth.Navidrome, "ping", side_effect=AssertionError("asked again too soon")):
            auth.check_password_soon("Jonas", {"NAV_URL": "http://nav", config.pass_key("Jonas"): "old"})

    def test_unreachable_is_not_rejected(self):
        with mock.patch.object(auth.Navidrome, "ping", side_effect=web.NavidromeError("timed out")):
            auth.check_password_soon("Lukas", {"NAV_URL": "http://nav", config.pass_key("Lukas"): "pw"})
            for t in [t for t in threading.enumerate() if t.name == "password-check"]:
                t.join(5)
        self.assertFalse(auth.password_rejected("Lukas"))

    def test_fields_in_me_and_status(self):
        save(base_config())
        auth.note_password("Jonas", False)
        with mock.patch.object(auth, "load_env", lambda: {config.pass_key("Jonas"): "pw"}), \
                mock.patch.object(auth, "check_password_soon"), mock.patch.object(auth, "navidrome_users", lambda force=False: []):
            me = auth.me("Jonas")
        self.assertTrue(me["passwordStored"])
        self.assertTrue(me["passwordRejected"])


class DamagedStateTest(unittest.TestCase):
    """Damaged state files are set aside (*.defekt-*) instead of being replaced by an empty state."""

    def tearDown(self):
        import shutil
        for name in ("anna", "bert"):
            shutil.rmtree(rueckblick._dir(name), ignore_errors=True)
        rueckblick._between.clear()
        for path in list(feedback.FEEDBACK_DIR.glob("carla*")) if feedback.FEEDBACK_DIR.is_dir() else []:
            path.unlink()
        for path in config.STATE_DIR.glob("push_keys*"):
            path.unlink()
        save(base_config())

    def test_deezer_state_set_aside(self):
        good = json.dumps({"version": 1, "songs": {f"s{i}": {"r": 400000} for i in range(50)}})
        deezer.STATE_FILE.write_text(good[:-1], encoding="utf-8")
        self.addCleanup(lambda: [p.unlink() for p in deezer.STATE_FILE.parent.glob("deezer*.json")])

        class FakeNav:
            def __init__(self, *a, **k):
                pass

            def all_songs(self):
                return [{"id": "s1", "title": "t", "artist": "a"}]
        lines = []
        with mock.patch.object(deezer, "Navidrome", FakeNav), self.assertRaises(RuntimeError):
            deezer.run({"NAV_URL": "http://x"}, mode="new", log=lines.append, cfg=base_config())
        aside = list(deezer.STATE_FILE.parent.glob("deezer.defekt-*.json"))
        self.assertEqual(len(aside), 1)
        self.assertEqual(aside[0].read_text(encoding="utf-8"), good[:-1])
        self.assertFalse(deezer.STATE_FILE.exists())

    def test_lyrics_index_rebuilt_and_kid_safe_playlists_rewritten(self):
        liedtext.DB_FILE.write_bytes(b"this is not a database" * 100)
        liedtext._derb_cache.update(stamp=None, ids=frozenset())
        self.addCleanup(lambda: [p.unlink() for p in liedtext.DB_FILE.parent.glob("liedtexte*")])
        with contextlib.redirect_stdout(io.StringIO()) as out:
            self.assertEqual(liedtext.status()["songs"], 0)   # set aside, a fresh empty index
        self.assertTrue(list(liedtext.DB_FILE.parent.glob("liedtexte.defekt-*.db")))
        self.assertIn("liedtexte.defekt-", out.getvalue())
        folder = env.MUSIC / "Grob" / "Album"
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "r.txt").write_text("fuck this", encoding="utf-8")
        lib = Library([song("r")])
        lib.path_loader = lambda: ({"r": "Grob/Album/r.opus"}, {})
        found = []
        liedtext.on_indexed(found.append)
        self.addCleanup(liedtext._after_index.remove, found.append)
        with mock.patch.object(liedtext, "_state", {**liedtext._state, "running": False, "soon": 0}):
            liedtext.update_soon(lib)
            for t in [t for t in threading.enumerate() if t.name == "liedtexte"]:
                t.join(10)
        self.assertEqual(found, [frozenset({"r"})])
        self.assertEqual(liedtext.derb(), frozenset({"r"}))

    def test_kid_safe_hook_applies_even_without_auto_apply(self):
        cfg = base_config()
        cfg["settings"]["autoApply"] = False
        cfg["personen"][1]["clean"] = True
        save(cfg)
        with mock.patch.object(web.AUTO, "schedule") as sched, contextlib.redirect_stdout(io.StringIO()):
            web._kidsafe_after_index(frozenset({"r"}))
        sched.assert_called_once_with(force=True)
        cfg["personen"][1]["clean"] = False
        save(cfg)
        with mock.patch.object(web.AUTO, "schedule") as sched:
            web._kidsafe_after_index(frozenset({"r"}))
        sched.assert_not_called()

    def test_recap_files_set_aside(self):
        folder = rueckblick._dir("anna")
        folder.mkdir(parents=True, exist_ok=True)
        base = {"since": "2025-01-01T05:30:00", "at": "2026-10-16T05:30:00", "counts": {"a": 5}}
        (folder / "baseline.json").write_text(json.dumps(base)[:-2], encoding="utf-8")
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertIsNone(rueckblick.snapshot("anna", [{"id": "a", "playCount": 9}], now=dt.datetime(2026, 10, 17, 5, 30)))
        self.assertTrue(list(folder.glob("baseline.defekt-*.json")))
        (folder / "first.json").write_text(json.dumps({f"x{i}": "2025-03-01" for i in range(50)})[:-1], encoding="utf-8")
        with contextlib.redirect_stdout(io.StringIO()):
            rueckblick.snapshot("anna", [{"id": "a", "playCount": 12}, {"id": "b", "playCount": 1}],
                                now=dt.datetime(2026, 10, 18, 5, 30))
        aside = list(folder.glob("first.defekt-*.json"))
        self.assertEqual(len(aside), 1)
        self.assertEqual(len(aside[0].read_text(encoding="utf-8")), len(json.dumps({f"x{i}": "2025-03-01" for i in range(50)})) - 1)

    def test_recap_stops_when_briefly_unreadable(self):
        folder = rueckblick._dir("bert")
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "baseline.json").write_text(json.dumps({"since": "x", "at": "2026-10-16T05:30:00", "counts": {}}))
        before = (folder / "baseline.json").read_text()
        with mock.patch.object(rueckblick, "read_text", side_effect=PermissionError(13, "busy")), self.assertRaises(OSError):
            rueckblick.snapshot("bert", [{"id": "a", "playCount": 1}])
        self.assertEqual((folder / "baseline.json").read_text(), before)

    def test_feedback_set_aside(self):
        feedback.FEEDBACK_DIR.mkdir(parents=True, exist_ok=True)
        path = feedback._feedback_file("Carla")
        path.write_text('{"s1": {"s": ["2026-01-01"]', encoding="utf-8")
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(feedback._load_to_write(path, {}), {})
        self.assertTrue(list(feedback.FEEDBACK_DIR.glob("carla.defekt-*.json")))
        self.assertFalse(path.exists())

    def test_vapid_key_kept_when_briefly_unreadable(self):
        if not webpush.available()[0]:
            self.skipTest("cryptography missing")
        webpush.KEYS_FILE.unlink(missing_ok=True)
        key = webpush.public_key()
        with mock.patch.object(webpush, "read_text", side_effect=PermissionError(13, "busy")), self.assertRaises(OSError):
            webpush.public_key()
        self.assertEqual(webpush.public_key(), key)
        webpush.KEYS_FILE.write_text("{broken", encoding="utf-8")
        self.assertNotEqual(webpush.public_key(), key)
        self.assertTrue(list(webpush.KEYS_FILE.parent.glob("push_keys.defekt-*.json")))


class LongTermTest(unittest.TestCase):
    """L2: long-term maintenance also forgets vanished songs in the sound vectors and the loudness."""

    def setUp(self):
        for path in (langzeit.STATE_FILE, similar.STATE_FILE, lautstaerke.STATE_FILE):
            path.unlink(missing_ok=True)
            self.addCleanup(path.unlink, missing_ok=True)

    def test_prunes_vectors_and_loudness(self):
        vec = similar.encode([1.0] * similar.DIM)
        similar.save({"keep": vec, "gone": vec})
        lautstaerke.save({"songs": {i: {"path": f"{i}.flac", "l": -9.0} for i in ("keep", "gone")}})
        lib = Library([song("keep")] + [song(f"x{k}") for k in range(5)])
        t0 = dt.date(2026, 9, 1)
        with mock.patch.object(liedtext, "compact", return_value=None):
            langzeit.run(lib, log=lambda *a: None, today=t0, force=True)
            langzeit.run(lib, log=lambda *a: None, today=t0 + dt.timedelta(days=31), force=True)
        data = json.loads(similar.STATE_FILE.read_text())
        self.assertEqual(sorted(data["songs"]), ["keep"])
        self.assertEqual(data["v"], similar.VERSION)
        self.assertEqual(sorted(json.loads(lautstaerke.STATE_FILE.read_text())["songs"]), ["keep"])


class ConfigFileTest(unittest.TestCase):
    """Config L3/L8: a damaged config.json stops the start with a clear message; while running, the last good state
    stays; migration backups of the same second keep both."""

    def tearDown(self):
        save(base_config())
        for p in config.DATA_DIR.glob("config.defekt-*.json"):
            p.unlink()

    def test_damaged_at_start(self):
        config.CONFIG_FILE.write_text('{"version": 10, "settings": {', encoding="utf-8")
        env.reset_caches()
        with self.assertRaises(config.ConfigDamaged) as cm:
            config.load_config()
        self.assertIn("config.json", str(cm.exception))
        self.assertEqual(config.CONFIG_FILE.read_text(encoding="utf-8"), '{"version": 10, "settings": {')   # untouched
        with self.assertRaises(SystemExit):
            web.serve("127.0.0.1", 0)

    def test_damaged_while_running(self):
        save(base_config())
        good = config.load_config()
        time.sleep(0.01)
        config.CONFIG_FILE.write_text("[]", encoding="utf-8")
        os.utime(config.CONFIG_FILE, ns=(time.time_ns(), time.time_ns() + 10**9))
        with contextlib.redirect_stdout(io.StringIO()) as out:
            self.assertEqual(config.load_config(), good)
            self.assertEqual(config.load_config(), good)
        self.assertEqual(out.getvalue().count("keeps working"), 1)
        self.assertTrue(list(config.DATA_DIR.glob("config.defekt-*.json")))

    def test_bom_and_null_lists(self):
        cfg = base_config()
        cfg["ignored"] = None
        config.CONFIG_FILE.write_text("﻿" + json.dumps(cfg), encoding="utf-8")
        env.reset_caches()
        self.assertEqual(config.load_config()["ignored"], [])

    def test_migration_backups_unique(self):
        env.clear_dir(config.BACKUP_DIR)
        config._migration_backup(9, "a")
        config._migration_backup(9, "b")
        self.assertEqual(sorted(p.read_text() for p in config.BACKUP_DIR.glob("config_v9_*.json")), ["a", "b"])


class SettingsValidationTest(unittest.TestCase):
    """Config M4/L5: wrong types are a ValueError (400), not a crash; the name pattern only knows {welt} and {stil};
    sound features of a newer version are ignored (going back keeps saving possible)."""

    def bad(self, **settings):
        cfg = base_config()
        cfg["settings"].update(settings)
        with self.assertRaises(ValueError, msg=settings):
            config.validate_config(cfg)

    def test_settings(self):
        for pattern in ("{Welt} · {Stil}", "{welt} {", "{welt} · {stil} {0}", "{welt.x}", "{welt:>99999999}", "{welt!r}"):
            self.bad(namePattern=pattern)
        self.bad(start="x")
        self.bad(deezer="x")
        self.bad(deezer={"thresholds": [1, 2, 3, 4, True]})
        self.bad(limit="100")
        self.bad(minDuration="x")
        self.bad(hitsShare="0.3")
        self.bad(excludeTitles="Live")
        self.bad(familyEdit="everyone")
        self.bad(autoApply="yes")
        self.bad(kinderschutz={"allow": "abc"})
        self.bad(lyrics={"providers": [{"id": "lrclib", "on": "no"}]})
        cfg = base_config()
        cfg["settings"]["namePattern"] = "{stil} – {welt}"
        config.validate_config(cfg)

    def test_sound(self):
        cfg = base_config()
        cfg["stile"].append({"id": "v", "name": "V", "sound": {"bpm": [False, True]}})
        with self.assertRaises(ValueError):
            config.validate_config(cfg)
        cfg["stile"][-1]["sound"] = {"energy": [0.2, 0.8], "futureFeature": [0, 1]}
        config.validate_config(cfg)

    def test_type_errors_become_value_errors(self):
        cfg = base_config()
        cfg["playlists"] = [{"id": "t", "person": "jonas", "welt": "kinder", "stil": ["x"]}]
        with self.assertRaises(ValueError):
            config.validate_config(cfg)
        cfg = base_config()
        cfg["settings"] = "x"
        with self.assertRaises(ValueError):
            config.validate_config(cfg)


@env.german
class SuggestionNamesTest(unittest.TestCase):
    """Texts: names that go to Navidrome are in the server language, card titles in the language of the page."""

    def test_names_server_language(self):
        cfg = base_config()
        cfg["personen"][1]["likes"]["welten"] = ["kinder", "metal"]
        songs = random_songs(1500, seed=3)
        i18n.use("en")
        self.addCleanup(i18n.use, None)
        out = suggest.suggestions(cfg, Library(songs), only_person="jonas")
        named = [s for s in out if (s.get("playlist") or {}).get("name")]
        self.assertTrue(named)
        for s in named:
            self.assertNotEqual(s["playlist"]["name"], s["title"], s["key"])
        sorts = next(s for s in named if "Querbeet" in s["playlist"]["name"])
        self.assertEqual(sorts["playlist"]["name"], "Jonas’ Querbeet")
        self.assertEqual(sorts["title"], "Jonas’s All Sorts")


if __name__ == "__main__":
    unittest.main()
