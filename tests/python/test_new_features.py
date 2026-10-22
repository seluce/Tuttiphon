"""Version 0.5: lyrics search and child protection, new from favourite bands, family mix, good-night mix with a fixed
length, recap playlist, library check, notifications. No network, no real data."""
from tests.python import env  # noqa: F401  (before app.*)

import copy
import datetime as dt
import json
import unittest
from collections import Counter
from unittest import mock

from app import auth, classify, config, liedtext, mixer, notify, pflege, rueckblick, rules, suggest, taste
from app.rules import Library, BuildContext
from tests.python.factory import base_config, iso_days_ago, song

ADMIN = {"user": "niklas", "role": "admin", "own": None, "local": False}
JONAS = {"user": "Jonas", "role": "user", "own": "jonas", "local": False}


class LyricsTest(unittest.TestCase):
    def setUp(self):
        env.reset_caches()
        liedtext.DB_FILE.unlink(missing_ok=True)
        liedtext._derb_cache.update(stamp=None, ids=frozenset())
        self.addCleanup(liedtext.DB_FILE.unlink, missing_ok=True)
        folder = env.MUSIC / "Band A" / "Album"
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "s1.lrc").write_text("[ar: Band A]\n[00:01.00]Wir fahren mit dem Bus nach Hause\n[00:05.20]la la la\n",
                                       encoding="utf-8")
        (folder / "s2.txt").write_text("Das ist doch alles Scheiße\nund nochmal Scheiße\n", encoding="utf-8")
        (folder / "s3.txt").write_text("Ganz brav und leise\n", encoding="utf-8")
        songs = [song("s1", "Busfahrt"), song("s2", "Wut"), song("s3", "Leise"), song("s4", "Ohne Text")]
        self.lib = Library(songs)
        self.lib.path_loader = lambda: ({s["id"]: f"Band A/Album/{s['id']}.opus" for s in songs},
                                        {"s4": "Eingebettet: Sterne über der Stadt"})

    def test_plain_and_embedded(self):
        self.assertEqual(liedtext.plain("[ti: X]\n[00:01.00]Hallo <00:01.50>Welt\n\n"), "Hallo Welt")
        raw = json.dumps([{"lang": "deu", "line": [{"start": 0, "value": "Erste Zeile"}, {"value": "Zweite"}], "synced": True}])
        self.assertEqual(liedtext.embedded_text(raw), "Erste Zeile\nZweite")

    def test_rude_needs_strong_word_or_two_mild(self):
        self.assertFalse(liedtext.rude("So ein Mist, Scheiße"))
        self.assertTrue(liedtext.rude("Scheiße, nochmal Scheiße"))
        self.assertTrue(liedtext.rude("what the fuck"))
        self.assertFalse(liedtext.rude("Wir marschieren im Marsch"))   # only at the start of a word

    def test_update_search_and_rude(self):
        changed, gone = liedtext.update(self.lib, base_config())
        self.assertEqual((changed, gone), (4, 0))
        hits = liedtext.search("mit dem bus")
        self.assertEqual(hits[0]["song"], "s1")
        self.assertIn("Bus", hits[0]["line"])
        self.assertEqual(liedtext.search("sterne über")[0]["song"], "s4")   # embedded lyrics count too
        self.assertEqual(liedtext.search("la"), [])                          # too short: matches almost everywhere
        self.assertEqual(liedtext.derb(), frozenset({"s2"}))
        self.assertEqual(liedtext.derb(["s2"]), frozenset())                  # allowed by the administrator
        self.assertEqual(liedtext.update(self.lib, base_config()), (0, 0))  # nothing changed: nothing read again

    def test_clean_person_excludes_rude_titles(self):
        liedtext.update(self.lib, base_config())
        cfg = base_config()
        cfg["welten"][0]["artists"] = ["Band A"]
        p = {"id": "k", "person": "jonas", "welt": "kinder", "stil": "*"}
        ctx = BuildContext(self.lib)
        self.assertNotIn({"isNot": {"title": "Wut"}}, rules.build_nsp(cfg, p, ctx)["all"])
        cfg["personen"][1]["clean"] = True
        nsp = rules.build_nsp(cfg, p, ctx)
        self.assertIn({"isNot": {"title": "Wut"}}, nsp["all"])
        self.assertNotIn(self.lib.index_of()["s2"], self.lib.match(nsp))
        cfg["settings"]["kinderschutz"] = {"allow": ["s2"]}
        self.assertNotIn({"isNot": {"title": "Wut"}}, rules.build_nsp(cfg, p, ctx)["all"])


@env.german   # checks the German output of existing installations
class PlaylistKindsTest(unittest.TestCase):
    def setUp(self):
        env.reset_caches()
        taste._memo.clear()
        self.cfg = base_config()
        songs = [song(f"n{k}", f"Neu {k}", artist="Band A", album="Frisch", created=iso_days_ago(5), duration=200)
                 for k in range(6)]
        songs += [song(f"o{k}", f"Alt {k}", artist="Band A", album="Alt", created=iso_days_ago(300)) for k in range(6)]
        songs += [song(f"b{k}", f"Andere {k}", artist="Band B", created=iso_days_ago(5)) for k in range(6)]
        self.lib = Library(songs)
        patches = [mock.patch.object(taste, "profile", return_value=None),
                   mock.patch.object(classify, "song_features", return_value={})]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)

    def test_fav_takes_new_songs_of_favorite_bands(self):
        self.cfg["personen"][1]["likes"]["artists"] = ["Band A"]
        p = {"id": "f", "person": "jonas", "welt": "*", "stil": "*", "fav": {"days": 60}, "minRating": 0, "sort": "neu"}
        config.validate_config({**self.cfg, "playlists": [p]})
        ids = self.lib.match(rules.build_nsp(self.cfg, p, BuildContext(self.lib)))
        self.assertEqual({self.lib.songs[i]["id"] for i in ids}, {f"n{k}" for k in range(6)})
        self.assertIn("Lieblingsbands", rules.summary(self.cfg, p, BuildContext(self.lib))[0])

    def test_fav_without_favorites_stays_empty(self):
        p = {"id": "f", "person": "niklas", "welt": "*", "stil": "*", "fav": {"days": 60}, "minRating": 0}
        self.assertEqual(self.lib.match(rules.build_nsp(self.cfg, p, BuildContext(self.lib))), frozenset())

    def test_together_uses_nogos_of_all(self):
        p = {"id": "t", "person": "familie", "welt": ["kinder"], "stil": "*", "type": "mix", "together": ["jonas", "oma"]}
        config.validate_config({**self.cfg, "playlists": [p]})
        nsp = rules.build_nsp(self.cfg, p, BuildContext(self.lib))
        for band in ("Band X", "Nordwind", "Iron Test"):   # family, Jonas and grandma
            self.assertIn({"isNot": {"artist": band}}, nsp["all"])
        with self.assertRaises(ValueError):
            config.validate_config({**self.cfg, "playlists": [{**p, "together": ["jonas"]}]})

    def test_minutes_fill_the_time(self):
        p = {"id": "g", "person": "familie", "welt": ["kinder"], "stil": "*", "type": "mix",
             "mix": {"minutes": 10, "perArtist": 0, "perAlbum": 0}}
        config.validate_config({**self.cfg, "playlists": [p]})
        order = mixer.select(self.lib, frozenset(range(len(self.lib.songs))), p, dt.date(2026, 10, 13))
        total = sum(self.lib.songs[i]["duration"] for i in order)
        self.assertGreaterEqual(total, 600)
        self.assertLess(total - self.lib.songs[order[-1]]["duration"], 600)   # no more than needed

    def test_calm_down_ends_without_vocals(self):
        lib = Library([song(f"s{k}", artist=f"Band {k}") for k in range(6)])
        feats = {k: {"arousal": 0.9 - k * 0.1, "inst": 0.9 if k in (0, 1) else 0.1} for k in range(6)}
        order = mixer.calm_down(lib, list(range(6)), feats, quiet_end=2)
        self.assertEqual(order[-2:], [0, 1])
        self.assertEqual(order[:4], [2, 3, 4, 5])

    def test_review_takes_top_songs_of_last_month(self):
        p = {"id": "r", "person": "jonas", "welt": "*", "stil": "*", "type": "mix", "review": {"period": "month"},
             "mix": {"size": 5, "every": "month"}}
        config.validate_config({**self.cfg, "playlists": [p]})
        plays = Counter({"o1": 9, "o2": 4, "b3": 7, "weg": 20})
        with mock.patch.object(rueckblick, "plays_between", return_value=(plays, {})) as pb:
            order, n = mixer.pick(self.cfg, self.lib, p, {}, dt.date(2026, 11, 2))
        self.assertEqual(pb.call_args[0][1:], (dt.date(2026, 10, 1), dt.date(2026, 10, 31)))
        self.assertEqual([self.lib.songs[i]["id"] for i in order], ["o1", "b3", "o2"])
        self.assertEqual(rules.review_name(self.cfg, p, dt.date(2026, 11, 2)), "Jonas · Dein Oktober 2026")
        self.assertEqual(rules.review_name(self.cfg, {**p, "person": "familie", "review": {"period": "year"}},
                                           dt.date(2027, 1, 5)), "Unser Jahr 2026")

    def test_suggestions_offer_new_kinds(self):
        self.cfg["personen"][1]["likes"]["artists"] = ["Band A"]
        plays = Counter({f"o{k}": 3 for k in range(6)} | {f"n{k}": 2 for k in range(6)} | {f"b{k}": 1 for k in range(6)}
                        | {f"x{k}": 1 for k in range(10)})
        lib = Library(self.lib.songs + [song(f"x{k}", artist="Band B") for k in range(10)])
        with mock.patch.object(rueckblick, "plays_between", return_value=(plays, {})):
            out = suggest.suggestions(self.cfg, lib, only_person="jonas")
        keys = {s["key"] for s in out}
        self.assertIn("jonas|*|*||fav", keys)
        self.assertIn("jonas|*|*||mix|review:month", keys)


class PermissionsTest(unittest.TestCase):
    def test_what_everyone_likes_is_the_family_s(self):
        cfg = base_config()
        cfg["playlists"] = [{"id": "t", "person": "familie", "welt": ["kinder"], "stil": "*", "type": "mix",
                             "together": ["niklas", "oma", "familie", "gibtsnicht"]}]
        incoming = copy.deepcopy(cfg)
        incoming["playlists"][0]["together"] = ["jonas", "niklas", "oma"]
        incoming["playlists"].append({"id": "u", "person": "jonas", "welt": ["kinder"], "stil": "*", "type": "mix",
                                      "together": ["jonas", "oma"]})
        out = {p["id"]: p for p in auth.merge_user_changes(cfg, incoming, JONAS)["playlists"]}
        self.assertEqual(out["t"]["together"], ["niklas", "oma", "jonas"])   # people – not the family, nobody unknown
        self.assertNotIn("together", out["u"])                              # a person's own playlist: no family mix

    def test_person_fields_clean_and_push(self):
        cfg = base_config()
        cfg["personen"][1].update(clean=True, push="jonas-musik_1")
        config.validate_config(cfg)
        cfg["personen"][1]["push"] = "mit leerzeichen"
        with self.assertRaises(ValueError):
            config.validate_config(cfg)


@env.german   # checks the German output of existing installations
class LibraryCheckTest(unittest.TestCase):
    def test_report(self):
        songs = [song("a1", "Lied", album="X"), song("a2", "Lied", album="X"), song("a3", "Lied (Playback)", album="X"),
                 song("b1", "Kurz", album="Y", duration=5), song("c1", "Hit (Remastered 2011)", album="Single"),
                 song("c2", "Hit", album="Album 2")]
        songs[0]["suffix"], songs[1]["suffix"] = "flac", "opus"
        for k, t in enumerate((1, 2, 4)):
            songs.append(song(f"t{k}", f"Track {k}", album="Lücke"))
            songs[-1]["track"] = t
        songs.append({**song("m1", "Alt", album="Z"), "suffix": "mp3", "bitRate": 96})
        report = {c["id"]: c for c in pflege.report(base_config(), Library(songs))["checks"]}
        self.assertEqual(report["doppelt"]["count"], 1)
        self.assertIn("FLAC und OPUS", report["doppelt"]["items"][0]["detail"])
        self.assertEqual(report["mehrfach"]["count"], 1)
        self.assertEqual(report["luecken"]["items"][0]["detail"], "es fehlt 3")
        self.assertEqual(report["kurz"]["count"], 1)
        self.assertEqual(report["qualitaet"]["count"], 1)
        self.assertEqual(report["genre"]["count"], len(songs))


@env.german   # checks the German output of existing installations
class NotifyTest(unittest.TestCase):
    def setUp(self):
        env.reset_caches()
        notify.SENT_FILE.unlink(missing_ok=True)
        self.addCleanup(notify.SENT_FILE.unlink, missing_ok=True)
        self.cfg = base_config()
        self.cfg["settings"]["notify"] = {"enabled": True, "server": "https://ntfy.example", "topic": "admin-x",
                                          "url": "https://tuttiphon.example", "events": {"newMusic": False}}

    def test_send_posts_json(self):
        sent = []

        class Resp:
            status = 200

            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

        def fake(req, timeout=0):
            sent.append((req.full_url, json.loads(req.data)))
            return Resp()
        with mock.patch("urllib.request.urlopen", fake):
            self.assertTrue(notify.send("thema", "Titel – mit Umlaut ä", "Text", ("cd",), "#/verlauf", self.cfg))
        url, body = sent[0]
        self.assertEqual(url, "https://ntfy.example")
        self.assertEqual(body["click"], "https://tuttiphon.example/#/verlauf")
        self.assertEqual(body["topic"], "thema")

    def test_once(self):
        self.assertTrue(notify.once("x"))
        self.assertFalse(notify.once("x"))

    def test_after_run_respects_events(self):
        with mock.patch.object(notify, "send", return_value=True) as send:
            notify.after_run({"name": "Process new music (2 files)", "results": {"scan": "ok"},
                              "summary": {"analyse": {"assignedBands": [["Band A", "kinder"]]}}}, self.cfg)
        titles = [c.args[1] for c in send.call_args_list]
        self.assertEqual(len(titles), 1)                       # new music is switched off
        self.assertIn("eingeordnet", titles[0])
        self.assertIn("Band A → Kinder", send.call_args_list[0].args[2])
        with mock.patch.object(notify, "send", return_value=True) as send:
            notify.after_run({"name": "Alles aktualisieren", "results": {"scan": "fehler"}, "summary": {}}, self.cfg)
        self.assertIn("fehlgeschlagen", send.call_args.args[1])

    def test_favorites_once_per_album(self):
        self.cfg["personen"][1].update(push="jonas-x")
        self.cfg["personen"][1]["likes"]["artists"] = ["Band A"]
        lib = Library([song("n1", album="Neues Album", artist="Band A", created=iso_days_ago(1)),
                       song("o1", album="Altes", artist="Band A", created=iso_days_ago(100))])
        with mock.patch.object(taste, "profile", return_value=None), \
                mock.patch.object(notify, "send", return_value=True) as send:
            self.assertEqual(notify.for_persons(self.cfg, lib), 1)
            self.assertEqual(notify.for_persons(self.cfg, lib), 0)
        self.assertEqual(send.call_args.args[0], "jonas-x")


if __name__ == "__main__":
    unittest.main()
