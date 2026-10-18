"""app/rules.py: local evaluation of the rules (Library), build_nsp(), summary()."""
from tests.python import env  # noqa: F401  (before app.*)

import copy
import datetime as dt
import random
import unittest

from app import rules
from app.navidrome import SONG_FIELDS
from app.rules import BuildContext, Library, build_nsp
from tests.python.factory import ARTISTS, GENRES, WORDS, base_config, iso_days_ago, random_songs, song

OCT = dt.date(2026, 10, 12)    # no season of the test configuration active
XMAS = dt.date(2026, 12, 24)   # Christmas active


def ids_of(lib, rule):
    return {lib.songs[i]["id"] for i in lib.ids(rule)}


# --------------------------------------------------------------------------- naive reference evaluation
# Written independently of Library, following the description in the handbook (docs/04-playlists.md, local
# evaluation) and Navidrome's SQL logic: multi-valued fields = EXISTS/NOT EXISTS, columns with NULL = no match,
# text case-insensitive, missing rating = 0. For the duration the reference knows the real length with
# decimals (as in Navidrome's database), the song list only the truncated one (as the API).

MULTI = {"artist", "albumartist", "genre"}


def ref_value(s, field, real_duration):
    if field == "artist":
        return [a["name"] for a in s.get("artists") or []] or [s.get("artist", "")]
    if field == "albumartist":
        return [a["name"] for a in s.get("albumArtists") or []] or [s.get("displayAlbumArtist", "")]
    if field == "genre":
        return [g["name"] for g in s.get("genres") or []]
    if field == "duration":
        return real_duration[s["id"]]
    return {"album": s.get("album"), "title": s.get("title"), "year": s.get("year") or 0,
            "rating": s.get("userRating") or 0, "loved": bool(s.get("starred")), "playcount": s.get("playCount") or 0,
            "lastplayed": s.get("played"), "dateadded": s.get("created"), "missing": False}[field]


def days_ago(iso):
    return (dt.date.today() - dt.date.fromisoformat(iso[:10])).days


def ref_match(s, rule, real_duration):
    if "all" in rule:
        return all(ref_match(s, r, real_duration) for r in rule["all"])
    if "any" in rule:
        return any(ref_match(s, r, real_duration) for r in rule["any"])
    ((op, body),) = rule.items()
    ((field, value),) = body.items()
    v = ref_value(s, field, real_duration)
    if op in ("contains", "notContains", "startsWith", "endsWith"):
        want = value.lower()
        test = {"contains": lambda x: want in x.lower(), "notContains": lambda x: want in x.lower(),
                "startsWith": lambda x: x.lower().startswith(want), "endsWith": lambda x: x.lower().endswith(want)}[op]
        if field in MULTI:
            hit = any(test(x) for x in v)
            return not hit if op == "notContains" else hit
        if v is None:
            return False   # LIKE / NOT LIKE with NULL
        return (not test(v)) if op == "notContains" else test(v)
    if op in ("is", "isNot"):
        if field in MULTI:
            hit = any(x == value for x in v)
            return not hit if op == "isNot" else hit
        if v is None:
            return False
        return (v == value) if op == "is" else (v != value)
    if op == "gt":
        return v > value
    if op == "lt":
        return v < value
    if op == "inTheRange":
        return value[0] <= v <= value[1]
    if op == "inTheLast":
        return v is not None and days_ago(v) < value
    if op == "notInTheLast":
        return v is None or days_ago(v) > value
    raise AssertionError(op)


DATE_DAYS = (10, 100)   # n of the date rules; their boundary days do not occur in the random data
AVOID = {d + k for d in DATE_DAYS for k in (-1, 0, 1)}


def random_rule(rnd, songs, depth=0):
    if depth < 3 and rnd.random() < 0.35:
        return {rnd.choice(["all", "any"]): [random_rule(rnd, songs, depth + 1) for _ in range(rnd.randint(1, 4))]}
    kind = rnd.random()
    if kind < 0.35:
        field = rnd.choice(["title", "album", "genre", "artist", "albumartist"])
        pool = {"genre": GENRES, "artist": ARTISTS, "albumartist": ARTISTS}.get(field, WORDS)
        word = rnd.choice(pool)
        a = rnd.randrange(len(word))
        part = word[a:a + rnd.randint(1, 5)]
        part = part.upper() if rnd.random() < 0.3 else part
        return {rnd.choice(["contains", "notContains", "startsWith", "endsWith"]): {field: part}}
    if kind < 0.55:
        field = rnd.choice(["artist", "albumartist", "genre", "title", "loved", "playcount"])
        value = {"artist": lambda: rnd.choice(ARTISTS), "albumartist": lambda: rnd.choice(ARTISTS),
                 "genre": lambda: rnd.choice(GENRES), "title": lambda: rnd.choice(songs)["title"],
                 "loved": lambda: rnd.choice([True, False]), "playcount": lambda: 0}[field]()
        return {rnd.choice(["is", "isNot"]): {field: value}}
    if kind < 0.8:
        field, values = rnd.choice([("duration", [44, 45, 90, 120]), ("rating", [0, 2, 3, 4]),
                                    ("year", [1980, 1990]), ("playcount", [0, 4])])
        return {rnd.choice(["gt", "lt"]): {field: rnd.choice(values)}}
    if kind < 0.87:
        return {"inTheRange": {"year": rnd.choice([[1980, 1989], [1990, 2020]])}}
    return {rnd.choice(["inTheLast", "notInTheLast"]): {rnd.choice(["dateadded", "lastplayed"]): rnd.choice(DATE_DAYS)}}


class TestFactory(unittest.TestCase):
    def test_synthetic_songs_only_use_navidrome_fields(self):
        for s in random_songs(50) + [song("x", starred=True, rating=3, avg=2.5, played=iso_days_ago(1))]:
            self.assertLessEqual(set(s), SONG_FIELDS)


# --------------------------------------------------------------------------- Library: single operators

class TestLibraryOperators(unittest.TestCase):
    def setUp(self):
        self.lib = Library([
            song("multi", title="Tanz der Vampire", artists=["Band A", "Band B"], album_artist="Band A",
                 genres=["Rock", "Metal"], album="Party Mix", duration=45, year=1985, rating=4,
                 created=iso_days_ago(5), played=iso_days_ago(3), plays=2),
            song("solo", title="Der Tanz", artist="Band C", genres=["Pop"], album="Sommer", duration=44,
                 year=1989, starred=True, created=iso_days_ago(100)),
            song("nogenre", title="Regen", artist="Band A", genres=[], album="Ohne", duration=46, year=None,
                 rating=1, created=iso_days_ago(40), played=iso_days_ago(100), plays=7),
        ])
        self.noalbum = song("noalbum", title="Ohne Album", artist="Band D", genres=["Folk"])
        self.noalbum.pop("album")
        self.lib.songs.append(self.noalbum)

    def test_contains_on_multi_valued_genre(self):
        self.assertEqual(ids_of(self.lib, {"contains": {"genre": "metal"}}), {"multi"})
        self.assertEqual(ids_of(self.lib, {"contains": {"genre": "ROC"}}), {"multi"})

    def test_not_contains_on_multi_valued_field_is_not_exists(self):
        # one matching value among several excludes; a song without any genre passes the negation
        self.assertEqual(ids_of(self.lib, {"notContains": {"genre": "metal"}}), {"solo", "nogenre", "noalbum"})

    def test_is_and_is_not_on_multiple_artists(self):
        self.assertEqual(ids_of(self.lib, {"is": {"artist": "Band B"}}), {"multi"})
        # NOT EXISTS: the song with Band A & Band B drops out for "isNot Band B", although Band A ≠ Band B
        self.assertEqual(ids_of(self.lib, {"isNot": {"artist": "Band B"}}), {"solo", "nogenre", "noalbum"})
        self.assertEqual(ids_of(self.lib, {"isNot": {"albumartist": "Band A"}}), {"solo", "noalbum"})

    def test_is_is_exact_but_contains_ignores_case(self):
        self.assertEqual(ids_of(self.lib, {"is": {"artist": "band a"}}), set())
        self.assertEqual(ids_of(self.lib, {"contains": {"artist": "band a"}}), {"multi", "nogenre"})

    def test_missing_column_value_matches_neither_contains_nor_negation(self):
        self.assertNotIn("noalbum", ids_of(self.lib, {"contains": {"album": "o"}}))
        self.assertNotIn("noalbum", ids_of(self.lib, {"notContains": {"album": "Party"}}))
        self.assertNotIn("noalbum", ids_of(self.lib, {"isNot": {"album": "Party Mix"}}))
        self.assertEqual(ids_of(self.lib, {"notContains": {"album": "Party"}}), {"solo", "nogenre"})

    def test_starts_with_and_ends_with(self):
        self.assertEqual(ids_of(self.lib, {"startsWith": {"title": "tanz"}}), {"multi"})
        self.assertEqual(ids_of(self.lib, {"endsWith": {"title": "TANZ"}}), {"solo"})
        self.assertEqual(ids_of(self.lib, {"startsWith": {"artist": "band c"}}), {"solo"})

    def test_gt_duration_accounts_for_truncated_seconds(self):
        # The API returns 45 for a file with 45.x seconds – in Navidrome it is longer than 45
        self.assertEqual(ids_of(self.lib, {"gt": {"duration": 45}}), {"multi", "nogenre", "noalbum"})
        self.assertNotIn("solo", ids_of(self.lib, {"gt": {"duration": 45}}))   # 44.x
        self.assertEqual(ids_of(self.lib, {"lt": {"duration": 45}}), {"solo"})

    def test_in_the_range_is_inclusive_and_missing_year_never_matches(self):
        self.assertEqual(ids_of(self.lib, {"inTheRange": {"year": [1985, 1989]}}), {"multi", "solo"})
        self.assertEqual(ids_of(self.lib, {"inTheRange": {"year": [1986, 1988]}}), set())
        self.assertNotIn("nogenre", ids_of(self.lib, {"inTheRange": {"year": [1, 3000]}}))   # missing = 0

    def test_in_the_last_and_not_in_the_last(self):
        self.assertEqual(ids_of(self.lib, {"inTheLast": {"dateadded": 30}}), {"multi"})
        self.assertEqual(ids_of(self.lib, {"inTheLast": {"lastplayed": 30}}), {"multi"})
        # never played counts as "not in the last n days"
        self.assertEqual(ids_of(self.lib, {"notInTheLast": {"lastplayed": 30}}), {"solo", "nogenre", "noalbum"})

    def test_is_loved_and_rating_defaults(self):
        self.assertEqual(ids_of(self.lib, {"is": {"loved": True}}), {"solo"})
        self.assertEqual(ids_of(self.lib, {"is": {"loved": False}}), {"multi", "nogenre", "noalbum"})
        self.assertEqual(ids_of(self.lib, {"lt": {"rating": 1}}), {"solo", "noalbum"})   # missing = 0
        self.assertEqual(ids_of(self.lib, {"is": {"playcount": 0}}), {"solo", "noalbum"})

    def test_average_rating_only_when_ratings_are_not_exact(self):
        songs = [song("a", rating=None, avg=4.0), song("b", rating=2, avg=5.0)]
        self.assertEqual(ids_of(Library(songs), {"gt": {"rating": 3}}), set())
        self.assertEqual(ids_of(Library(songs, ratings_exact=False), {"gt": {"rating": 3}}), {"a"})

    def test_nested_all_any(self):
        rule = {"all": [
            {"any": [{"contains": {"title": "tanz"}}, {"is": {"loved": True}}, {"contains": {"genre": "folk"}}]},
            {"any": [{"isNot": {"artist": "Band B"}}, {"gt": {"rating": 3}}]},
            {"notContains": {"title": "Vampire"}},
        ]}
        self.assertEqual(ids_of(self.lib, rule), {"solo", "noalbum"})
        self.assertEqual(self.lib.match({"any": [{"is": {"artist": "Band C"}}, {"is": {"artist": "Band D"}}]}),
                         self.lib.ids({"any": [{"is": {"artist": "Band C"}}, {"is": {"artist": "Band D"}}]}))

    def test_unknown_operator_or_field_raises(self):
        with self.assertRaises(ValueError):
            self.lib.ids({"matches": {"title": "x"}})
        with self.assertRaises(ValueError):
            self.lib.ids({"is": {"bitrate": 320}})

    def test_filepath_uses_real_path_from_loader(self):
        lib = Library([song("p1", path="Band A/Album/p1.opus"), song("p2", path="Band A/Album/p2.opus")])
        calls = []

        def loader():
            calls.append(1)
            return {"p1": "Musik/Echte Ordner/01 Lied.flac"}, {"p2"}
        lib.path_loader = loader
        self.assertEqual(ids_of(lib, {"contains": {"filepath": "echte ordner"}}), {"p1"})
        # without a real path the path built from the API counts
        self.assertEqual(ids_of(lib, {"startsWith": {"filepath": "band a/album/p2"}}), {"p2"})
        self.assertEqual(lib.real_path(0), "Musik/Echte Ordner/01 Lied.flac")
        self.assertEqual(lib.embedded_lyrics(), {"p2"})
        self.assertEqual(len(calls), 1)

    def test_filepath_falls_back_when_navidrome_is_unreachable(self):
        lib = Library([song("p1", path="Band A/Album/p1.opus")])

        def loader():
            raise RuntimeError("Navidrome unreachable")
        lib.path_loader = loader
        self.assertEqual(ids_of(lib, {"contains": {"filepath": "album/p1"}}), {"p1"})

    def test_in_the_last_and_not_in_the_last_are_complementary_on_the_boundary_day(self):
        # Navidrome compares the timestamp with the date n days ago ("dateadded > 'YYYY-MM-DD'" or
        # "< 'YYYY-MM-DD' OR NULL") – every song belongs to exactly one of the two rules, a song from the boundary
        # day (exactly n days ago, at any time of day) counts towards inTheLast. Library has to see it the same way.
        lib = Library([song("grenze", created=iso_days_ago(30, hour=12), played=iso_days_ago(30, hour=20))])
        for field in ("dateadded", "lastplayed"):
            inside = ids_of(lib, {"inTheLast": {field: 30}})
            outside = ids_of(lib, {"notInTheLast": {field: 30}})
            self.assertEqual(inside | outside, {"grenze"}, field)
            self.assertEqual(inside & outside, set(), field)


# --------------------------------------------------------------------------- Library against the reference

class TestLibraryAgainstReference(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.songs = random_songs(240, seed=7, avoid_days=AVOID)
        rnd = random.Random(11)
        cls.real_duration = {s["id"]: s["duration"] + rnd.uniform(0.05, 0.95) for s in cls.songs}
        cls.lib = Library(cls.songs)

    def expected(self, rule):
        return {s["id"] for s in self.songs if ref_match(s, rule, self.real_duration)}

    def test_random_rules_match_reference(self):
        rnd = random.Random(2026)
        checked = nonempty = 0
        for _ in range(400):
            rule = random_rule(rnd, self.songs)
            got = ids_of(self.lib, rule)
            self.assertEqual(got, self.expected(rule), rule)
            checked += 1
            nonempty += bool(got) and len(got) < len(self.songs)
        self.assertGreater(nonempty, checked // 4)   # the rules really do separate

    def test_built_playlists_match_reference(self):
        cfg = base_config()
        cases = [{"welt": "kinder", "stil": "tanzen"}, {"welt": "*", "stil": "80er", "hits": True},
                 {"welt": "*", "stil": "neu", "person": "jonas"}, {"welt": ["kinder", "metal"], "stil": "*"},
                 {"welt": "*", "stil": "lieblinge", "addArtists": ["Band A"], "notPlayedDays": 100},
                 {"welt": "metal", "stil": "tophits", "excludeArtists": ["Band B"]},
                 {"welt": "*", "stil": "jahreszeit"}]
        for p in cases:
            nsp = build_nsp(cfg, {"id": "t", **p}, BuildContext(self.lib, OCT))
            got = {self.songs[i]["id"] for i in self.lib.match(nsp)}
            self.assertEqual(got, self.expected({"all": nsp["all"]}), p)


# --------------------------------------------------------------------------- build_nsp

@env.german   # checks the German output of existing installations
class TestBuildNsp(unittest.TestCase):
    def setUp(self):
        self.cfg = base_config()

    def nsp(self, today=OCT, lib=None, **playlist):
        return build_nsp(self.cfg, {"id": "t", **playlist}, BuildContext(lib, today))

    def test_world_times_direction_as_documented(self):
        # example from docs/04-playlists.md (structure of an .nsp)
        nsp = self.nsp(welt="kinder", stil="tanzen", person="familie")
        self.assertEqual(nsp, {
            "name": "Kinder · Tanzen & Toben", "comment": "Tuttiphon: Kinder × Tanzen & Toben", "public": True,
            "all": [
                {"any": [{"is": {"artist": "Band A"}}, {"is": {"albumartist": "Band A"}},
                         {"is": {"artist": "Band B"}}, {"is": {"albumartist": "Band B"}},
                         {"contains": {"genre": "Children"}}]},
                {"any": [{"contains": {"album": "Tanz"}}, {"contains": {"album": "Party"}},
                         {"contains": {"title": "Tanz"}}]},
                {"notContains": {"album": "Weihnacht"}}, {"notContains": {"title": "Jingle Bell"}},
                {"notContains": {"genre": "Christmas"}},
                {"isNot": {"artist": "Band X"}}, {"isNot": {"albumartist": "Band X"}},
                {"notContains": {"title": "(Live"}}, {"notContains": {"title": "Instrumental"}},
                {"notContains": {"title": "Karaoke"}}, {"notContains": {"title": "(Kapitel"}},
                {"notContains": {"album": "Hörspiel"}},
                {"gt": {"duration": 45}},
                {"is": {"missing": False}},
            ],
            "sort": "random", "limit": 100})

    def test_all_playlist_negates_separate_worlds_as_documented(self):
        nsp = self.nsp(welt="*", stil="80er", hits=True, sort="beliebt")
        self.assertEqual(nsp["name"], "80er (Hits)")
        self.assertEqual(nsp["comment"], "Tuttiphon: Alle × 80er")
        self.assertEqual(nsp["sort"], "-rating")
        self.assertEqual(nsp["all"], [
            {"isNot": {"artist": "Band A"}}, {"isNot": {"albumartist": "Band A"}},
            {"isNot": {"artist": "Band B"}}, {"isNot": {"albumartist": "Band B"}},
            {"notContains": {"genre": "Children"}},
            {"inTheRange": {"year": [1980, 1989]}},
            {"notContains": {"album": "Weihnacht"}}, {"notContains": {"title": "Jingle Bell"}},
            {"notContains": {"genre": "Christmas"}},
            {"isNot": {"artist": "Band X"}}, {"isNot": {"albumartist": "Band X"}},
            {"notContains": {"title": "(Live"}}, {"notContains": {"title": "Instrumental"}},
            {"notContains": {"title": "Karaoke"}},
            {"gt": {"duration": 120}},
            {"any": [{"gt": {"rating": 3}}, {"is": {"loved": True}}]},
            {"is": {"missing": False}},
        ])
        # worlds that are not separate (Metal, Mittelalter) are not excluded
        self.assertNotIn({"isNot": {"artist": "Iron Test"}}, nsp["all"])

    def test_add_artists_survive_negation_but_genre_exclusion_stays(self):
        rules_ = self.nsp(welt="*", stil="*", addArtists=["Band A"], radio=None)["all"]
        self.assertNotIn({"isNot": {"artist": "Band A"}}, rules_)
        self.assertNotIn({"isNot": {"albumartist": "Band A"}}, rules_)
        self.assertIn({"isNot": {"artist": "Band B"}}, rules_)
        self.assertIn({"notContains": {"genre": "Children"}}, rules_)

    def test_add_artists_join_the_world_block(self):
        who = self.nsp(welt="metal", stil="*", addArtists=["Band C"])["all"][0]["any"]
        self.assertIn({"is": {"artist": "Band C"}}, who)
        self.assertIn({"is": {"artist": "Iron Test"}}, who)

    def test_several_worlds_form_one_or_block(self):
        nsp = self.nsp(welt=["kinder", "mittelalter"], stil="*")
        who = nsp["all"][0]["any"]
        self.assertIn({"contains": {"album": "Mittelaltermarkt"}}, who)
        self.assertIn({"contains": {"genre": "Children"}}, who)
        self.assertEqual(nsp["name"], "Kinder + Mittelalter · Querbeet")

    def test_season_collection_without_active_season_stays_empty(self):
        nsp = self.nsp(welt="*", stil="jahreszeit", today=OCT)
        self.assertIn({"any": [{"is": {"title": "– keine Saison aktiv –"}}]}, nsp["all"])
        lib = Library(random_songs(60, seed=3))
        self.assertEqual(lib.match(nsp), frozenset())

    def test_season_collection_with_active_season(self):
        nsp = self.nsp(welt="*", stil="jahreszeit", today=XMAS)
        self.assertEqual(nsp["all"][5], {"any": [{"contains": {"genre": "Christmas"}}, {"contains": {"album": "Weihnacht"}},
                                                 {"contains": {"title": "Jingle Bell"}}]})
        # the currently active season is not hidden here at the same time
        self.assertNotIn({"notContains": {"genre": "Christmas"}}, nsp["all"])
        self.assertTrue(nsp["comment"].endswith("(gerade: Weihnachten)"))

    def test_season_active_wraps_around_new_year(self):
        season = ["11-25", "01-06"]
        for day, active in ((dt.date(2026, 12, 24), True), (dt.date(2027, 1, 6), True), (dt.date(2027, 1, 7), False),
                            (dt.date(2026, 11, 24), False), (dt.date(2026, 11, 25), True)):
            self.assertEqual(rules.season_active(season, day), active, day)
        self.assertFalse(rules.season_active(None, XMAS))

    def test_default_winter_season_covers_leap_day(self):
        # Winter ends on "02-28" – the leap day counts like the 28th, otherwise 29 February would have no winter.
        from app import config
        winter = next(s for s in config.default_config()["stile"] if s["id"] == "winter")
        self.assertTrue(rules.season_active(winter["season"], dt.date(2028, 2, 29)))

    def test_person_no_gos_and_playlist_exclusions(self):
        all_ = self.nsp(welt="*", stil="*", person="jonas", excludeArtists=["Band C"], radio=None)["all"]
        for a in ("Nordwind", "Band C"):
            self.assertIn({"isNot": {"artist": a}}, all_)
            self.assertIn({"isNot": {"albumartist": a}}, all_)
        self.assertIn({"notContains": {"genre": "Metal"}}, all_)
        self.assertNotIn({"isNot": {"artist": "Band X"}}, all_)   # no-go of another person

    def test_default_person_when_playlist_has_none(self):
        all_ = self.nsp(welt="metal", stil="*")["all"]
        self.assertIn({"isNot": {"artist": "Band X"}}, all_)   # no-go of the default person "familie"

    def test_exclude_titles_from_settings_and_all_chosen_worlds(self):
        self.cfg["welten"][2]["excludeTitles"] = ["Dudelsack-Solo"]
        self.cfg["welten"][2]["excludeAlbums"] = ["Best of"]
        all_ = self.nsp(welt=["kinder", "mittelalter"], stil="*")["all"]
        for t in ("(Live", "Instrumental", "Karaoke", "(Kapitel", "Dudelsack-Solo"):
            self.assertIn({"notContains": {"title": t}}, all_)
        for a in ("Hörspiel", "Best of"):
            self.assertIn({"notContains": {"album": a}}, all_)
        # all playlist: only the setting, no world exclusions
        all_ = self.nsp(welt="*", stil="80er")["all"]
        self.assertNotIn({"notContains": {"title": "(Kapitel"}}, all_)

    def test_min_rating_is_any_with_loved(self):
        def rating_rules(**p):
            return [r for r in self.nsp(**p)["all"] if "any" in r and {"is": {"loved": True}} in r["any"]]
        self.assertEqual(rating_rules(welt="metal", stil="*"),
                         [{"any": [{"gt": {"rating": 1}}, {"is": {"loved": True}}]}])
        self.assertEqual(rating_rules(welt="*", stil="tophits"),           # max(allMinRating 3, filter 4)
                         [{"any": [{"gt": {"rating": 3}}, {"is": {"loved": True}}]}])
        self.assertEqual(rating_rules(welt=["kinder", "metal"], stil="*"), [])   # minimum of the worlds: 0
        self.assertEqual(rating_rules(welt="metal", stil="*", minRating=0), [])  # explicitly 0 = none
        self.assertEqual(rating_rules(welt="kinder", stil="*", minRating=5),
                         [{"any": [{"gt": {"rating": 4}}, {"is": {"loved": True}}]}])
        # hits without a library: minimum rating + 1, at least 3
        self.assertEqual(rating_rules(welt="kinder", stil="*", hits=True),
                         [{"any": [{"gt": {"rating": 2}}, {"is": {"loved": True}}]}])

    def test_min_duration(self):
        def duration(**p):
            return [r["gt"]["duration"] for r in self.nsp(**p)["all"] if "gt" in r and "duration" in r["gt"]]
        self.assertEqual(duration(welt="kinder", stil="*"), [45])          # value of the world
        self.assertEqual(duration(welt="metal", stil="*"), [120])          # setting
        self.assertEqual(duration(welt="*", stil="80er"), [120])
        self.assertEqual(duration(welt=["mittelalter", "metal"], stil="*"), [90])   # minimum over the worlds
        self.assertEqual(duration(welt="kinder", stil="*", minDuration=30), [30])  # playlist beats everything
        self.assertEqual(duration(welt="kinder", stil="*", minDuration=0), [])
        self.cfg["welten"][1]["minDuration"] = 0
        self.assertEqual(duration(welt="metal", stil="*"), [])

    def test_public_defaults(self):
        self.assertTrue(self.nsp(welt="metal", stil="*", person="familie")["public"])
        self.assertFalse(self.nsp(welt="metal", stil="*", person="jonas")["public"])
        self.assertFalse(self.nsp(welt="metal", stil="*", person="niklas")["public"])   # "public" missing -> private
        self.assertTrue(self.nsp(welt="metal", stil="*", person="gibtsnicht")["public"])   # settings.public
        self.cfg["settings"]["public"] = False
        self.assertFalse(self.nsp(welt="metal", stil="*", person="gibtsnicht")["public"])

    def test_filters_sort_limit_and_not_played(self):
        nsp = self.nsp(welt="*", stil="neu", sort="neu", limit=25, notPlayedDays=30)
        self.assertIn({"inTheLast": {"dateadded": 60}}, nsp["all"])
        self.assertEqual(nsp["all"][-2:], [{"notInTheLast": {"lastplayed": 30}}, {"is": {"missing": False}}])
        self.assertEqual((nsp["sort"], nsp["limit"]), ("-dateadded", 25))
        self.assertIn({"is": {"loved": True}}, self.nsp(welt="*", stil="lieblinge")["all"])

    def test_takeover_rules_pass_through(self):
        nsp = self.nsp(rules=[{"is": {"loved": True}}], rulesOp="any", sortRaw="title", limit=7,
                       rulesExtra={"order": "desc", "name": "fremd", "all": [], "public": False}, originalName="Alt",
                       person="jonas")
        self.assertEqual(nsp, {"name": "Alt", "comment": "Tuttiphon: eigene Regeln (unverändert übernommen)",
                               "public": False, "any": [{"is": {"loved": True}}], "sort": "title", "limit": 7,
                               "order": "desc"})

    def test_radio_without_library_uses_seeds(self):
        nsp = self.nsp(welt="*", stil="*", radio={"seed": ["Band C", "Nordwind"]}, type="mix")
        self.assertEqual(nsp["all"][0], {"any": [{"is": {"artist": "Band C"}}, {"is": {"albumartist": "Band C"}},
                                                 {"is": {"artist": "Nordwind"}}, {"is": {"albumartist": "Nordwind"}}]})

    def test_no_duplicate_rules(self):
        self.cfg["welten"][0]["excludeTitles"] = ["(Live"]   # already in the settings
        all_ = self.nsp(welt="kinder", stil="*", excludeArtists=["Band X"])["all"]
        self.assertEqual(len(all_), len({repr(r) for r in all_}))


# --------------------------------------------------------------------------- summary

@env.german   # checks the German output of existing installations
class TestSummary(unittest.TestCase):
    def setUp(self):
        self.cfg = base_config()

    def test_all_playlist_summary(self):
        lines = rules.summary(self.cfg, {"id": "t", "welt": "*", "stil": "80er", "minRating": 3},
                              BuildContext(None, OCT))
        self.assertEqual(lines, [
            "Die ganze Bibliothek – ohne Kinder",
            "80er: aus 1980–1989",
            "Ab ★★★ (oder als Favorit markiert)",
            "Nie dabei: Band X",
            "Ausgeblendet: Weihnachten",
            "Ohne Live-Aufnahmen, Instrumental- und Karaoke-Versionen",
            "Bis zu 100 Songs, bei jedem Abruf neu gemischt",
        ])

    def test_world_playlist_summary(self):
        lines = rules.summary(self.cfg, {"id": "t", "welt": "kinder", "stil": "weihnachten", "person": "jonas",
                                         "excludeArtists": ["Band C"], "addArtists": ["Band D"], "sort": "neu",
                                         "limit": 30}, BuildContext(None, OCT))
        self.assertIn("Bands aus Kinder (2 Bands)", lines)
        self.assertIn("Zusätzlich: Band D", lines)
        self.assertIn("Nie dabei: Nordwind, Band C", lines)
        self.assertFalse(any(x.startswith("Ausgeblendet") for x in lines))   # Christmas is the playlist's own direction
        self.assertIn("Ohne Titel mit „(Kapitel“, Live-Aufnahmen, Instrumental- und Karaoke-Versionen", lines)
        self.assertEqual(lines[-1], "Bis zu 30 Songs, neueste zuerst")

    def test_season_summary_follows_active_season(self):
        p = {"id": "t", "welt": "*", "stil": "jahreszeit"}
        xmas = rules.summary(self.cfg, p, BuildContext(None, XMAS))
        self.assertIn("Gerade passend zur Jahreszeit: Weihnachten", xmas)
        self.assertFalse(any(x.startswith("Ausgeblendet") for x in xmas))
        octo = rules.summary(self.cfg, p, BuildContext(None, OCT))
        self.assertIn("Gerade passend zur Jahreszeit: keine Saison aktiv", octo)
        self.assertIn("Ausgeblendet: Weihnachten", octo)

    def test_inherited_star_minimum_is_mentioned(self):
        # build_nsp() also takes the minimum rating from settings.allMinRating (every all playlist, default
        # 3 stars), from the world's minRating or the direction's filter (top hits: 4) – summary() has to mention it.
        p = {"id": "t", "welt": "*", "stil": "80er"}
        self.assertIn({"any": [{"gt": {"rating": 2}}, {"is": {"loved": True}}]}, build_nsp(self.cfg, p)["all"])
        self.assertTrue(any("★★★" in line for line in rules.summary(self.cfg, p, BuildContext(None, OCT))))

    def test_takeover_summary(self):
        self.assertEqual(rules.summary(self.cfg, {"rules": []}),
                         ["Eigene Regeln, unverändert aus der handgemachten .nsp-Datei übernommen."])

    def test_title_filters_text(self):
        f = rules._title_filters_text
        self.assertEqual(f(["(Live", "Live at", "Unplugged", "Instrumental", "Karaoke", "Playback"]),
                         "Ohne Live-Aufnahmen, Unplugged-, Instrumental- und Karaoke-Versionen")
        self.assertEqual(f(["Karaoke"]), "Ohne Karaoke-Versionen")
        self.assertEqual(f(["Playback", "(Live"]), "Ohne Live-Aufnahmen und Karaoke-Versionen")
        self.assertEqual(f(["(Kapitel"]), "Ohne Titel mit „(Kapitel“")
        self.assertEqual(f(["Olive"]), "Ohne Titel mit „Olive“")   # "live" only as a word of its own
        self.assertEqual(f(["(Kapitel", "Intro", "Outro", "Skit", "Instrumental"]),
                         "Ohne Titel mit „(Kapitel“, „Intro“, „Outro“ … und Instrumental-Versionen")
        self.assertEqual(f([]), "")


if __name__ == "__main__":
    unittest.main()
