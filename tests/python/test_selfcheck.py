"""app/selfcheck.py: Navidrome's song counts against Tuttiphon's own expectation.

Navidrome (native_api, navidrome_index), the playlist planning (plan, playlist_dir) and the library per person
(mixer.person_lib) are replaced – no requests, no write paths except state/selfcheck.json in the test folder."""
from tests.python import env  # noqa: F401  (before app.*)

import json
import shutil
import types
import unittest
from unittest import mock

from app import mixer, playlists, selfcheck
from tests.python.factory import base_config


class FakeNative:
    """Navidrome playlists: ID -> song count (or an exception that playlist_count raises)."""

    def __init__(self, counts):
        self.counts = counts
        self.asked = []

    def playlist_count(self, pid):
        self.asked.append(pid)
        value = self.counts[pid]
        if isinstance(value, Exception):
            raise value
        return value


class FakeLib:
    """Library as seen by one person: match() returns n hits (or raises error)."""

    def __init__(self, n, ratings_exact=True, user=None, error=None):
        self.n, self.ratings_exact, self.user, self.error = n, ratings_exact, user, error
        self.matched = []

    def match(self, nsp):
        self.matched.append(nsp)
        if self.error:
            raise self.error
        return frozenset(range(self.n))


class SelfcheckTest(unittest.TestCase):
    def setUp(self):
        env.reset_caches()
        self.assertIn(env.ROOT, selfcheck.FILE.parents)
        selfcheck.FILE.unlink(missing_ok=True)
        self.addCleanup(selfcheck.FILE.unlink, missing_ok=True)
        self.folder = env.ROOT / "selfcheck-playlists"
        shutil.rmtree(self.folder, ignore_errors=True)
        self.folder.mkdir()
        self.addCleanup(shutil.rmtree, self.folder, True)
        self.cfg = base_config()
        self.env = {"NAV_URL": "http://navidrome.invalid"}
        self.ctx = types.SimpleNamespace(lib=FakeLib(0, user="admin"))
        self.items, self.libs, self.index, self.counts, self.logs = [], {}, {}, {}, []

    def smart(self, pid, expected, actual, person="familie", limit=None, in_navidrome=True, **lib):
        nsp = {"name": f"Smart {pid}", "all": [{"is": {"loved": True}}]}
        if limit is not None:
            nsp["limit"] = limit
        self._add({"id": pid, "person": person}, f"{pid}.nsp", nsp, actual, in_navidrome)
        self.libs[pid] = FakeLib(expected, **lib)

    def mix(self, pid, entries, actual, write=True, in_navidrome=True):
        filename = f"{pid}.m3u"
        if write:
            lines = ["#EXTM3U", f"#PLAYLIST:Mix {pid}", "# Tuttiphon Daily Mix – automatisch erzeugt", ""]
            for k in range(entries):
                lines += [f"#EXTINF:200,Band - Lied {k}", f"../Band/Album/{pid}-{k}.opus"]
            (self.folder / filename).write_text("\n".join(lines) + "\n\n")
        self._add({"id": pid, "type": "mix", "person": "jonas"}, filename, {"name": f"Mix {pid}"}, actual, in_navidrome)

    def _add(self, p, filename, nsp, actual, in_navidrome):
        self.items.append((p, filename, nsp))
        if in_navidrome:
            self.index[filename] = {"id": f"nd-{p['id']}", "name": nsp["name"]}
            self.counts[f"nd-{p['id']}"] = actual

    def person_lib(self, cfg, p, base):
        self.assertIs(cfg, self.cfg)
        self.assertIs(base, self.ctx.lib)
        return self.libs[p["id"]]

    def run_check(self):
        self.native = FakeNative(self.counts)
        self.logs.clear()
        with mock.patch.object(playlists, "native_api", return_value=self.native) as native_api, \
             mock.patch.object(playlists, "navidrome_index", return_value=self.index) as index, \
             mock.patch.object(playlists, "plan", return_value=list(self.items)) as plan, \
             mock.patch.object(playlists, "playlist_dir", return_value=self.folder), \
             mock.patch.object(mixer, "person_lib", side_effect=self.person_lib) as person_lib, \
             mock.patch.object(selfcheck, "owner_count", side_effect=lambda e, user, pid: self.native.playlist_count(pid)):
            out = selfcheck.run(self.cfg, self.env, self.ctx, log=self.logs.append)
        native_api.assert_called_once_with(self.env)
        index.assert_called_once_with(self.native, self.cfg)
        plan.assert_called_once_with(self.cfg, self.ctx)
        self.person_lib_calls = person_lib.call_count
        return out

    def saved(self):
        return json.loads(selfcheck.FILE.read_text())

    def problem_ids(self, out):
        return [x["id"] for x in out["problems"]]


@env.german   # checks the German output of existing installations
class TestSmart(SelfcheckTest):
    def test_within_tolerance(self):
        self.smart("a", 50, 50 + selfcheck.TOLERANCE)
        self.smart("b", 50, 50 - selfcheck.TOLERANCE)
        self.smart("c", 0, 0)
        out = self.run_check()
        self.assertEqual(out, {"checked": 3, "skipped": 0, "problems": []})
        self.assertEqual(self.saved()["mismatch"], [])
        self.assertIn("alles wie erwartet", self.logs[-1])

    def test_big_difference_is_reported_at_once(self):
        self.smart("mehr", 50, 56)      # 6 > 10 % of 50
        self.smart("weniger", 50, 40)
        out = self.run_check()
        self.assertEqual(out["problems"], [
            {"id": "mehr", "name": "Smart mehr", "kind": "smart", "expected": 50, "actual": 56},
            {"id": "weniger", "name": "Smart weniger", "kind": "smart", "expected": 50, "actual": 40}])
        self.assertTrue(any("Smart mehr: Navidrome zeigt 56 Songs, erwartet 50" in line for line in self.logs))
        self.assertFalse(any(".m3u" in line for line in self.logs))
        self.assertIn("2 weichen ab", self.logs[-1])

    def test_small_difference_only_when_it_repeats(self):
        self.smart("a", 50, 55)         # exactly 10 %: not yet a big difference
        self.smart("b", 50, 50)
        out = self.run_check()
        self.assertEqual(out["problems"], [])
        self.assertEqual([x["id"] for x in self.saved()["mismatch"]], ["a"])
        out = self.run_check()          # again the next time -> report
        self.assertEqual(self.problem_ids(out), ["a"])
        self.counts["nd-a"] = 51        # fine again …
        self.assertEqual(self.run_check()["problems"], [])
        self.assertEqual(self.saved()["mismatch"], [])
        self.counts["nd-a"] = 54        # … then a small difference again only counts the second time
        self.assertEqual(self.run_check()["problems"], [])

    def test_small_difference_of_another_playlist_does_not_count(self):
        self.smart("a", 50, 54)
        self.run_check()
        self.items.clear()
        self.smart("b", 50, 54)
        self.assertEqual(self.run_check()["problems"], [])

    def test_owner_ratings_unknown_are_skipped(self):
        self.smart("durchschnitt", 50, 80, ratings_exact=False)
        self.smart("fremd", 50, 80, person="jonas", user="niklas")   # library of another account
        self.smart("ohne-konto", 50, 80, person="jonas", user=None)
        self.smart("regel", 50, 80, error=ValueError("unbekanntes Feld"))   # Tuttiphon cannot evaluate it itself
        self.smart("jonas", 50, 50, person="jonas", user="JONAS")   # case does not matter
        out = self.run_check()
        self.assertEqual(out, {"checked": 1, "skipped": 4, "problems": []})
        self.assertEqual(self.native.asked, ["nd-jonas"])
        self.assertIn("4 ohne Sterne des Besitzers übersprungen", self.logs[-1])
        self.assertEqual(self.saved()["skipped"], 4)

    def test_limit(self):
        self.smart("begrenzt", 500, 100, limit=100)
        self.smart("klein", 30, 30, limit=100)
        self.smart("ohne", 30, 30, limit=0)
        out = self.run_check()
        self.assertEqual(out, {"checked": 3, "skipped": 0, "problems": []})
        self.smart("zu-wenig", 500, 80, limit="100")
        self.assertEqual(self.run_check()["problems"][-1]["expected"], 100)

    def test_not_yet_in_navidrome(self):
        self.smart("neu", 50, None, in_navidrome=False)
        self.smart("da", 50, 50)
        out = self.run_check()
        self.assertEqual(out, {"checked": 1, "skipped": 0, "problems": []})
        self.assertEqual(self.native.asked, ["nd-da"])


@env.german   # checks the German output of existing installations
class TestMix(SelfcheckTest):
    def test_counts_m3u_entries(self):
        self.mix("ok", 10, 10)
        self.mix("fehlt", 10, 6)       # Navidrome does not find 4 paths
        out = self.run_check()
        self.assertEqual(out["checked"], 2)
        self.assertEqual(out["problems"], [{"id": "fehlt", "name": "Mix fehlt", "kind": "mix", "expected": 10,
                                            "actual": 6}])
        self.assertTrue(any("Mix fehlt" in line and "Pfade in der .m3u prüfen" in line for line in self.logs))
        self.assertEqual(self.person_lib_calls, 0)   # mixes need no stars

    def test_comments_and_blank_lines_do_not_count(self):
        self.mix("leer", 0, 0)
        self.mix("drei", 3, 3)
        self.assertEqual(self.run_check(), {"checked": 2, "skipped": 0, "problems": []})
        self.assertEqual(selfcheck._m3u_entries(self.folder / "drei.m3u"), 3)
        self.assertIsNone(selfcheck._m3u_entries(self.folder / "gibt-es-nicht.m3u"))

    def test_missing_file_is_not_checked(self):
        self.mix("ohne-datei", 10, 3, write=False)
        self.mix("da", 5, 5)
        out = self.run_check()
        self.assertEqual(out, {"checked": 1, "skipped": 0, "problems": []})
        self.assertEqual(self.native.asked, ["nd-da"])


@env.german   # checks the German output of existing installations
class TestRobust(SelfcheckTest):
    def test_error_in_one_playlist_does_not_stop_the_others(self):
        self.smart("a", 50, 50)
        self.smart("kaputt", 50, RuntimeError("Navidrome antwortet nicht"))
        self.mix("m", 10, 2)
        out = self.run_check()
        self.assertEqual(out["checked"], 2)
        self.assertEqual(self.problem_ids(out), ["m"])
        self.assertEqual(self.native.asked, ["nd-a", "nd-kaputt", "nd-m"])
        self.assertTrue(any("Selbstkontrolle Smart kaputt: Navidrome antwortet nicht" in line for line in self.logs))

    def test_writes_the_result(self):
        self.smart("a", 50, 70)
        self.smart("b", 50, 53)
        self.smart("c", 50, 90, ratings_exact=False)
        self.run_check()
        data = self.saved()
        self.assertEqual(set(data), {"at", "checked", "skipped", "mismatch", "problems"})
        self.assertRegex(data["at"], r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d$")
        self.assertEqual((data["checked"], data["skipped"]), (2, 1))
        self.assertEqual([x["id"] for x in data["mismatch"]], ["a", "b"])
        self.assertEqual([x["id"] for x in data["problems"]], ["a"])
        self.assertEqual(selfcheck.load(), data)

    def test_load_tolerates_broken_state(self):
        for text in ("{kaputt", "[1, 2]", ""):
            selfcheck.FILE.write_text(text)
            self.assertEqual(selfcheck.load(), {})
        self.smart("a", 50, 54)
        selfcheck.FILE.write_text("{kaputt")
        self.assertEqual(self.run_check()["problems"], [])   # without a readable previous run: only remember for now
        self.assertEqual(len(self.saved()["mismatch"]), 1)


if __name__ == "__main__":
    unittest.main()
