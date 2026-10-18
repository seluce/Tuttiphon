"""Findings of check 0.7 (edge cases): child protection independent of the account, protection in the family mix for
everyone, review with no-gos, lyrics index on NAS errors, self-created worlds on save, covers only for folders with one
album, tidy-up, notifications only after delivery, day assignment in the review, own covers."""
from tests.python import env  # noqa: F401  (before app.*)

import copy
import datetime as dt
import json
import os
import unittest
from collections import Counter
from unittest import mock

from app import albumcover, auth, classify, config, covers, liedtext, mixer, notify, rueckblick, rules, suggest, taste
from app.rules import BuildContext, Library
from tests.python.factory import base_config, song

JONAS = {"user": "Jonas", "role": "user", "own": ["jonas"], "persons": ["jonas"], "local": False}


class KidSafeTest(unittest.TestCase):
    def test_pool_without_account_rules(self):
        free = rules._account_free([
            {"is": {"genre": "Rock"}},
            {"gt": {"rating": 3}},
            {"any": [{"is": {"loved": True}}, {"is": {"artist": "Band A"}}]},   # OR with favorites: removed entirely
            {"all": [{"inTheLast": {"lastplayed": 30}}, {"is": {"artist": "Band B"}}]},   # AND: only the account rule removed
        ])
        self.assertEqual(free, [{"is": {"genre": "Rock"}}, {"all": [{"is": {"artist": "Band B"}}]}])

    def test_rude_favorite_is_excluded_for_every_account(self):
        lib = Library([song("a", "Böses Lied", genres=["Children"]), song("b", "Liebes Lied", genres=["Children"])])
        cfg = base_config()
        with mock.patch.object(liedtext, "derb", return_value=frozenset({"a"})):
            out = rules.clean_rules(cfg, [{"is": {"loved": True}}], BuildContext(lib))   # library's account: no favorite
        self.assertEqual(out, [{"isNot": {"title": "Böses Lied"}}])


class FamilyMixTest(unittest.TestCase):
    def test_private_member_still_protects(self):
        cfg = base_config()
        cfg["personen"][1]["clean"] = True                         # Jonas: child protection, private
        p = {"id": "t", "person": "oma", "welt": ["kinder"], "stil": "*", "type": "mix", "together": ["oma", "jonas"]}
        lib = Library([song("s1", genres=["Children"])])
        with mock.patch.object(liedtext, "derb", return_value=frozenset()):
            nsp = rules.build_nsp(cfg, p, BuildContext(lib))
        self.assertIn({"isNot": {"artist": "Nordwind"}}, nsp["all"])   # Jonas's no-go still applies
        self.assertEqual([x["id"] for x in rules.together_of(cfg, p)], ["oma"])   # her taste does not count

    def test_review_skips_nogos(self):
        cfg = base_config()
        lib = Library([song("o1", artist="Band A"), song("n1", artist="Nordwind"), song("m1", artist="Iron Test", genres=["Metal"])])
        p = {"id": "r", "person": "jonas", "welt": "*", "stil": "*", "type": "mix", "review": {"period": "month"},
             "mix": {"size": 5, "every": "month"}}
        with mock.patch.object(rueckblick, "plays_between", return_value=(Counter({"o1": 2, "n1": 9, "m1": 5}), {})), \
                mock.patch.object(taste, "profile", return_value=None), \
                mock.patch.object(classify, "song_features", return_value={}):
            order = mixer.review_order(cfg, lib, p, dt.date(2026, 11, 2))
        self.assertEqual([lib.songs[i]["id"] for i in order], ["o1"])

    def test_dropped_members_turn_into_taste_mix(self):
        cfg = base_config()
        cfg["playlists"] = [{"id": "t", "person": "jonas", "welt": "*", "stil": "*", "type": "mix", "together": ["jonas", "oma"]}]
        incoming = copy.deepcopy(cfg)
        incoming["playlists"][0]["together"] = ["jonas", "niklas"]   # Niklas is private -> dropped
        out = auth.merge_user_changes(cfg, incoming, JONAS)
        p = out["playlists"][0]
        self.assertNotIn("together", p)
        self.assertEqual(p["mix"]["flavor"], "geschmack")
        config.validate_config(out)

    def test_quiet_tail_after_spreading(self):
        lib = Library([song("s0", artist="A"), song("s1", artist="A"), song("s2", artist="B"), song("s3", artist="A")])
        feats = {0: {"arousal": 0.9}, 1: {"arousal": 0.8}, 2: {"arousal": 0.7}, 3: {"arousal": 0.1, "inst": 0.9}}
        order = mixer.calm_down(lib, [0, 1, 2, 3], feats, quiet_end=1)
        self.assertEqual(order[-1], 3)


class LyricsIndexTest(unittest.TestCase):
    def setUp(self):
        liedtext.DB_FILE.unlink(missing_ok=True)
        liedtext._derb_cache.update(stamp=None, ids=frozenset())
        self.addCleanup(liedtext.DB_FILE.unlink, missing_ok=True)
        self.folder = env.MUSIC / "NAS" / "Album"
        self.folder.mkdir(parents=True, exist_ok=True)
        (self.folder / "a.txt").write_text("Ein Lied über den Regen und den Wind", encoding="utf-8")
        self.lib = Library([song("a")])
        self.lib.path_loader = lambda: ({"a": "NAS/Album/a.opus"}, {})

    def test_keeps_rows_when_folder_is_briefly_unreadable(self):
        liedtext.update(self.lib, base_config())
        self.assertEqual(liedtext.status()["songs"], 1)
        real = os.listdir

        def flaky(path):
            if str(path).endswith("Album"):
                raise PermissionError(13, "kurz nicht lesbar")
            return real(path)
        lib = Library([song("a")])
        lib.path_loader = self.lib.path_loader
        with mock.patch("os.listdir", flaky):
            liedtext.update(lib, base_config())
        self.assertEqual(liedtext.status()["songs"], 1)
        (self.folder / "a.txt").unlink()
        lib = Library([song("a")])
        lib.path_loader = self.lib.path_loader
        liedtext.update(lib, base_config())   # really gone: forgotten
        self.assertEqual(liedtext.status()["songs"], 0)

    def test_failed_read_keeps_last_result(self):
        liedtext._derb_cache.update(stamp="alt", ids=frozenset({"x"}))
        liedtext.update(self.lib, base_config())
        with mock.patch.object(liedtext, "_connect", side_effect=liedtext.sqlite3.OperationalError("locked")):
            self.assertEqual(liedtext.derb(), frozenset({"x"}))


class WorldsTest(unittest.TestCase):
    def test_admin_save_keeps_new_auto_worlds(self):
        current = base_config()
        current["welten"].append({"id": "die-80er", "name": "Die 80er", "scene": "achtziger", "auto": "2026-10-13",
                                  "artists": [], "genres": []})
        old_ui = base_config()                                         # the interface does not know the new world yet
        out = config.merge_server_fields(copy.deepcopy(old_ui), current)
        self.assertIn("die-80er", [w["id"] for w in out["welten"]])
        old_ui["dismissed"] = ["scene|achtziger"]                      # deleted and hidden: stays away
        out = config.merge_server_fields(copy.deepcopy(old_ui), current)
        self.assertNotIn("die-80er", [w["id"] for w in out["welten"]])


class CoverTest(unittest.TestCase):
    def test_skip_folders_with_several_albums(self):
        root = env.MUSIC
        (root / "Lose").mkdir(parents=True, exist_ok=True)
        lib = Library([song("a", album_id="al1"), song("b", album_id="al2")])
        lib.path_loader = lambda: ({"a": "Lose/a.opus", "b": "Lose/b.opus"}, {})
        meta = [{"id": "al1", "name": "Eins", "albumArtist": "X", "createdAt": "2025-01-01"},
                {"id": "al2", "name": "Zwei", "albumArtist": "X", "createdAt": "2025-01-01"}]
        self.assertEqual(albumcover.candidates(lib, root, meta, {}, dt.date(2026, 10, 13)), [])

    def test_own_cover_comes_back_after_recreation(self):
        cfg = base_config()
        cfg["playlists"] = [{"id": "weihnacht", "person": "familie", "welt": "kinder", "stil": "weihnachten", "status": "aktiv",
                             "file": "w.nsp", "cover": {"style": "eigenes", "nid": "alt"}}]
        config.save_config(cfg)
        img = b"\xff\xd8\xff" + b"0" * 9000
        covers.keep_own("weihnacht", img)
        self.addCleanup(covers.forget_own, "weihnacht")
        native = mock.Mock()
        n = covers.refresh_auto(cfg, Library([]), native, {"w.nsp": {"id": "neu", "name": "Weihnachten"}}, log=lambda *_: None)
        self.assertEqual(n, 1)
        self.assertEqual(native.upload_playlist_image.call_args[0][:2], ("neu", img))
        self.assertEqual(cfg["playlists"][0]["cover"]["nid"], "neu")


class TidyUpTest(unittest.TestCase):
    def test_duplicates_compare_everything_that_selects(self):
        cfg = base_config()
        a = {"id": "a", "person": "jonas", "welt": "*", "stil": "*", "type": "mix", "together": ["jonas", "oma"], "status": "aktiv"}
        cfg["playlists"] = [a, {**a, "id": "b", "together": ["oma", "jonas"]}, {**a, "id": "c", "together": ["jonas", "familie"]},
                            {**a, "id": "d", "minDuration": 60}]
        self.assertEqual([[p["id"] for p in g] for g in suggest.duplicate_playlists(cfg)], [["a", "b"]])

    def test_seasonal_never_counts_as_unused(self):
        cfg = base_config()
        cfg["playlists"] = [{"id": "w", "person": "familie", "welt": "kinder", "stil": "weihnachten", "status": "aktiv",
                             "created": "2025-01-01", "minRating": 0}]
        lib = Library([song("x", "Jingle Bell", genres=["Children", "Christmas"])])
        with mock.patch.object(rueckblick, "last_snapshot", return_value={"since": "2025-01-01T00:00:00"}), \
                mock.patch.object(rueckblick, "plays_between", return_value=(Counter(), {})):
            self.assertEqual(suggest.unused_playlists(cfg, lib, today=dt.date(2026, 12, 5)), [])


class NotifyTest(unittest.TestCase):
    def setUp(self):
        notify.SENT_FILE.unlink(missing_ok=True)
        self.addCleanup(notify.SENT_FILE.unlink, missing_ok=True)

    def test_marked_only_after_delivery(self):
        self.assertFalse(notify.once("k", lambda: False))
        self.assertTrue(notify.once("k", lambda: True))
        self.assertFalse(notify.once("k", lambda: True))

    def test_cancelled_run_is_no_success_and_failures_once_a_day(self):
        cfg = base_config()
        cfg["settings"]["notify"] = {"enabled": True, "topic": "t"}
        with mock.patch.object(notify, "send", return_value=True) as send:
            notify.after_run({"name": "Neue Musik", "results": {"flac": "ok", "scan": "abgebrochen"}}, cfg)
            self.assertEqual(send.call_count, 0)
            for _ in range(2):
                notify.after_run({"name": "Nacht", "results": {"scan": "fehler"}}, cfg)
            self.assertEqual(send.call_count, 1)


class RecapTest(unittest.TestCase):
    def test_plays_count_for_the_middle_of_the_span(self):
        user = "tagtest"
        folder = rueckblick._dir(user)
        rueckblick.snapshot(user, [{"id": "s", "playCount": 1}], dt.datetime(2026, 10, 12, 7, 0))
        rueckblick.snapshot(user, [{"id": "s", "playCount": 3}], dt.datetime(2026, 10, 13, 7, 0))   # state at 7 o'clock
        self.assertTrue((folder / "2026-10-12.json").exists())
        rueckblick.snapshot(user, [{"id": "s", "playCount": 4}], dt.datetime(2026, 10, 13, 17, 0))  # in the afternoon
        self.assertEqual(json.loads((folder / "2026-10-13.json").read_text()), {"s": 1})



class CacheTest(unittest.TestCase):
    def test_plays_between_sees_new_snapshots(self):
        user = "cachetest"
        rueckblick.snapshot(user, [{"id": "s", "playCount": 1}], dt.datetime(2026, 10, 1, 7, 0))
        rueckblick.snapshot(user, [{"id": "s", "playCount": 2}], dt.datetime(2026, 10, 2, 7, 0))
        span = (dt.date(2026, 9, 1), dt.date(2026, 10, 31))
        self.assertEqual(rueckblick.plays_between(user, *span)[0], Counter({"s": 1}))
        first = rueckblick.plays_between(user, *span)[0]
        first["s"] = 99                                              # callers may change their result
        rueckblick.snapshot(user, [{"id": "s", "playCount": 5}], dt.datetime(2026, 10, 5, 7, 0))
        self.assertEqual(rueckblick.plays_between(user, *span)[0], Counter({"s": 4}))

    def test_backup_leaves_out_rebuildable_files(self):
        from app import backup
        for name in ("liedtexte.db", "liedtexte.db-wal", "watch_files.json", "deezer.json.defekt-2026"):
            (config.STATE_DIR / name).write_text("x")
            self.addCleanup((config.STATE_DIR / name).unlink, missing_ok=True)
        names = {arc for _, arc in backup._files()}
        self.assertFalse({"state/liedtexte.db", "state/liedtexte.db-wal", "state/watch_files.json",
                          "state/deezer.json.defekt-2026"} & names)

    def test_status_picks_only_active_mixes(self):
        from app import playlists
        cfg = base_config()
        cfg["playlists"] = [{"id": "m", "person": "familie", "welt": "kinder", "stil": "*", "type": "mix", "status": "pausiert"}]
        lib = Library([song(f"s{k}", genres=["Children"]) for k in range(5)])
        with mock.patch.object(mixer, "pick", side_effect=AssertionError("not needed")):
            row = playlists.status(cfg, BuildContext(lib))["playlists"][0]
        self.assertEqual(row["count"], 5)


if __name__ == "__main__":
    unittest.main()
