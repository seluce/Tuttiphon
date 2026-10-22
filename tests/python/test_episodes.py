"""“Next episode” (mixer.episode_order): for every audio play series an account listened to lately, the episode that
comes next – the rest of the one begun, otherwise the next one never heard, by episode number; the suggestion for it."""
from tests.python import env  # noqa: F401  (before app.*)

import datetime as dt
import shutil
import time
import unittest

from app import config, listen, mixer, rueckblick, rules, suggest
from app.rules import Library
from tests.python.factory import base_config, song

TODAY = dt.date.today()


def library():
    def ep(sid, album, artist, track=1, year=2000):
        s = song(sid, title=f"{album} – Teil {track}", artist=artist, album=album, album_id=f"al-{album}", year=year,
                 genres=["Hörspiel"], duration=1500)
        s["track"] = track
        return s
    return Library([
        ep("d10", "Folge 10: und der Feuerteufel", "Die drei ???"),
        ep("d1a", "Folge 1: und der Super-Papagei", "Die drei ???", 1), ep("d1b", "Folge 1: und der Super-Papagei", "Die drei ???", 2),
        ep("d2b", "Folge 2: und der Phantomsee", "Die drei ???", 2), ep("d2a", "Folge 2: und der Phantomsee", "Die drei ???", 1),
        ep("d3", "Folge 3: und der Karpatenhund", "Die drei ???"),
        ep("t1", "001/Die Jagd nach den Millionendieben", "TKKG"), ep("t2", "002/Der blinde Hellseher", "TKKG"),
        ep("b1", "Bibi und die Hexen", "Bibi Blocksberg", year=1980),
        song("m1", artist="Iron Test", genres=["Metal"]),
    ])


def configured():
    cfg = base_config()
    cfg["welten"].append({"id": "hoerspiel", "name": "Hörspiele", "artists": ["Die drei ???", "TKKG", "Bibi Blocksberg"],
                          "genres": ["Hörspiel"], "separate": True, "scene": rules.SPOKEN_SCENE, "minRating": 0})
    cfg["settings"]["allMinRating"] = 0
    return cfg


class EpisodeTest(unittest.TestCase):
    def setUp(self):
        self.clean()
        self.addCleanup(self.clean)
        self.cfg, self.lib = configured(), library()
        self.p = {"id": "next-jonas", "person": "jonas", "welt": ["hoerspiel"], "stil": rules.ALL, "type": "mix",
                  "episodes": True, "mix": {"every": "day"}}

    def clean(self):
        shutil.rmtree(rueckblick._dir("Jonas"), ignore_errors=True)
        listen._seen["pruned"].clear()
        rueckblick._ever.clear()
        mixer.MIX_STATE.unlink(missing_ok=True)

    def begin(self, sid, hours_ago):
        listen.record("Jonas", "start", sid, position=0, now=time.time() - hours_ago * 3600)

    def finish(self, sid, hours_ago):
        t = time.time() - hours_ago * 3600
        listen.record("Jonas", "start", sid, position=0, now=t)
        listen.record("Jonas", "play", sid, t=t, now=t + 1500)

    def next_ids(self):
        nsp = rules.build_nsp(self.cfg, self.p, rules.BuildContext(self.lib))
        order, n = mixer.episode_order(self.cfg, self.lib, self.lib, self.p, nsp, TODAY)
        return [self.lib.songs[i]["id"] for i in order], n

    def test_episode_numbers(self):
        for album, n in (("Folge 12: und der Fluch", 12), ("012/Der Super-Papagei", 12), ("Episode 3", 3),
                         ("Vol. 4 – Abenteuer", 4), ("Die drei ??? - 125 - Feuermond", 125), ("Fall #7", 7),
                         ("Bibi und die Hexen", None), ("", None)):
            self.assertEqual(mixer.episode_number(album), n, album)

    def test_the_next_episode_of_every_series(self):
        self.assertEqual(self.next_ids(), ([], 0))                 # nothing heard: nothing to go on with
        self.finish("t2", 30)                                      # TKKG 002 finished yesterday …
        self.finish("d1a", 5)
        self.finish("d1b", 4)
        self.begin("d2a", 3)                                       # … Die drei ??? 2 begun three hours ago
        ids, n = self.next_ids()
        self.assertEqual(n, 2)
        self.assertEqual(ids, ["d2a", "d2b", "t1"])                # on with 2 (in track order), TKKG from the start
        self.finish("d2a", 2)
        self.finish("d2b", 1)
        self.assertEqual(self.next_ids()[0], ["d3", "t1"])         # 3 comes after 2 – not 10
        self.finish("d3", 0.5)
        self.finish("d10", 0.2)                                    # jumped ahead to 10, the last one
        self.assertEqual(self.next_ids()[0], ["t1"])               # all of Die drei ??? heard: nothing left of it

    def test_as_a_mix_and_a_suggestion(self):
        self.finish("d1a", 5)
        self.finish("d1b", 4)
        order, n = mixer.pick(self.cfg, self.lib, self.p, rules.build_nsp(self.cfg, self.p, rules.BuildContext(self.lib)), TODAY)
        self.assertEqual(([self.lib.songs[i]["id"] for i in order], n), (["d2a", "d2b"], 1))
        got = [x for x in suggest.suggestions(self.cfg, self.lib, only_person="jonas") if x.get("playlist", {}).get("episodes")]
        self.assertEqual(len(got), 1)
        self.assertEqual((got[0]["count"], got[0]["playlist"]["welt"], got[0]["name"]),
                         (1, ["hoerspiel"], "Jonas · Next episode"))
        cfg = {**self.cfg, "playlists": [{**self.p, "status": "aktiv"}]}
        config.validate_config(cfg)
        with self.assertRaises(ValueError):
            config.validate_config({**cfg, "playlists": [{**self.p, "type": None}]})   # only as a mix

    def test_new_songs_setting_is_checked(self):
        cfg = configured()
        for ok in (0, 3, 5):
            cfg["personen"][1]["newEvery"] = ok
            config.validate_config(cfg)
        for bad in (True, 4, "5", -1):
            cfg["personen"][1]["newEvery"] = bad
            with self.assertRaises(ValueError):
                config.validate_config(cfg)


if __name__ == "__main__":
    unittest.main()
