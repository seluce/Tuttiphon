"""The weekly "New for you this week" notification: on Monday per person with "Discovered for you" or "Album of the
week", from the selections written for this week, once per week – the devices of an account shared by several people
once, with what is new for each of them; configuration v12 turns the event on."""
from tests.python import env  # noqa: F401  (before app.*)

import copy
import datetime as dt
import unittest
from unittest import mock

from app import config, mixer, notify, webpush
from app.rules import Library
from tests.python.factory import base_config, song

MONDAY = dt.date(2026, 10, 19)


class WeeklyTest(unittest.TestCase):
    def setUp(self):
        self.cfg = base_config()
        self.cfg["settings"]["notify"] = {"enabled": True, "events": {}}
        self.cfg["playlists"] = [
            {"id": "disc", "person": "jonas", "welt": "*", "stil": "*", "type": "mix", "unheard": True, "name": "Entdeckt für Jonas",
             "mix": {"every": "week"}},
            {"id": "alb", "person": "jonas", "welt": "*", "stil": "*", "type": "mix", "album": True, "name": "Album der Woche für Jonas",
             "mix": {"every": "week"}}]
        self.lib = Library([song(f"d{k}") for k in range(30)] + [song(f"a{k}", artist="Gast", album="Platte Z", album_artist="Gruppe Z")
                                                                for k in range(9)])
        self.state = {"disc": {"day": MONDAY.isoformat(), "ids": [f"d{k}" for k in range(30)]},
                      "alb": {"day": MONDAY.isoformat(), "ids": [f"a{k}" for k in range(9)]}}
        self.topics, self.devices, self.keys = [], [], set()
        for p in (mock.patch.object(mixer, "_load_state", lambda: self.state),
                  mock.patch.object(notify, "send", lambda topic, title, text, *a, **k: self.topics.append((topic, title, text)) or True),
                  mock.patch.object(webpush, "send_to", lambda title, text, path, **k: self.devices.append(
                      (*(k["make"]() if k.get("make") else (title, text)), k)) or True),
                  mock.patch.object(notify, "once", lambda key, go: key not in self.keys and bool(go()) and not self.keys.add(key))):
            p.start()
            self.addCleanup(p.stop)

    def run_on(self, day, person="jonas", topic=None):
        with mock.patch.object(mixer, "mix_day", lambda now=None: day):
            who = next(x for x in self.cfg["personen"] if x["id"] == person)
            return notify._weekly(self.cfg, self.lib, who, topic, day)

    @env.german
    def test_monday_once_with_both(self):
        self.assertEqual(self.run_on(MONDAY, topic="jonas-topic"), 1)
        title, text, kw = self.devices[0]
        self.assertEqual(title, "Neu für dich diese Woche")
        self.assertEqual(text, "Entdeckt für Jonas: 30 Songs, die du noch nie gehört hast · "
                               "Album der Woche für Jonas: Gruppe Z – Platte Z")   # the album artist, not a guest
        self.assertEqual((kw["accounts"], kw["tag"]), (["jonas"], "weekly-jonas"))
        self.assertEqual([t[0] for t in self.topics], ["jonas-topic"])
        self.assertEqual(self.run_on(MONDAY + dt.timedelta(days=1)), 0)   # the same week: not again

    def test_not_mid_week_and_not_before_it_is_written(self):
        self.assertEqual(self.run_on(MONDAY + dt.timedelta(days=2)), 0)
        self.state["disc"]["day"] = self.state["alb"]["day"] = (MONDAY - dt.timedelta(days=7)).isoformat()
        self.assertEqual(self.run_on(MONDAY), 0)
        self.assertEqual(self.devices, [])

    def test_only_weekly_mixes(self):
        self.cfg["playlists"][0]["mix"]["every"] = "day"   # a daily "Discovered": not "this week"
        self.run_on(MONDAY)
        self.assertNotIn("Entdeckt", self.devices[0][1])

    @env.german
    def test_shared_account_gets_one_message(self):
        family = self.cfg["personen"][0]
        family["user"] = "Jonas"   # the shared person on the same account
        self.cfg["playlists"].append({"id": "fam", "welt": "*", "stil": "*", "type": "mix", "unheard": True,   # no "person":
                                      "name": "Entdeckt für uns", "mix": {"every": "week"}})              # the default one
        self.state["fam"] = {"day": MONDAY.isoformat(), "ids": ["d1", "d2"]}
        self.run_on(MONDAY, "familie", topic="familie-topic")
        self.run_on(MONDAY, "jonas", topic="jonas-topic")
        self.assertEqual(len(self.devices), 1)   # the phone: once …
        text = self.devices[0][1]
        self.assertIn("Entdeckt für Jonas", text)   # … with what is new for both, the own person first
        self.assertTrue(text.index("Entdeckt für Jonas") < text.index("Entdeckt für uns"))
        self.assertEqual([t[0] for t in self.topics], ["familie-topic", "jonas-topic"])   # own topics: each

    def test_migration_turns_the_event_on(self):
        old = copy.deepcopy(base_config())
        old["version"] = 11
        old["settings"]["notify"] = {"enabled": True, "events": {"favorites": False}}
        new = config.migrate(old)
        self.assertEqual(new["version"], config.CONFIG_VERSION)
        self.assertEqual(new["settings"]["notify"]["events"], {"favorites": False, "weekly": True})


if __name__ == "__main__":
    unittest.main()
