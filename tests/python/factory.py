"""Synthetic song lists and configurations for the tests (no Navidrome queries).

Songs have the same fields as the song list from Navidrome (app/navidrome.py SONG_FIELDS, after _slim()).
"""
from tests.python import env  # noqa: F401  (before app.*)

import copy
import datetime as dt
import random

from app import config

ARTISTS = ["Band A", "Band B", "Band X", "Iron Test", "Spielleute", "Die Ärzte-Test", "The Testers", "Solo Sänger",
           "Kinderchor", "Nordwind"]
GENRES = ["Rock", "Metal", "Children", "Christmas", "Folk", "Pop", "Medieval", "Hörspiel-Genre", "Indie Rock"]
WORDS = ["Tanz", "Party", "Weihnacht", "Jingle Bell", "Sommer", "Nacht", "(Live", "Karaoke", "Lied", "Regen",
         "Hörspiel", "Mittelaltermarkt", "Feuer", "Instrumental", "Sonne"]


def iso_days_ago(days, hour=12):
    """Point in time `days` days ago (local date, noon) in the Subsonic API format."""
    d = dt.date.today() - dt.timedelta(days=days)
    return f"{d.isoformat()}T{hour:02d}:00:00Z"


def song(sid, title="Lied", artist="Band A", album="Album", album_id=None, album_artist=None, genres=(),
         year=2000, duration=200, rating=None, avg=None, starred=False, plays=0, played=None, created=None,
         path=None, artists=None, album_artists=None):
    """A song as delivered by Navidrome. artists/album_artists: list of names (several artists/roles)."""
    names = list(artists) if artists is not None else [artist]
    aa_names = list(album_artists) if album_artists is not None else [album_artist or artist]
    s = {
        "id": sid, "title": title, "album": album, "albumId": album_id or f"al-{album}",
        "artist": " & ".join(names), "artistId": f"ar-{names[0]}" if names else None,
        "artists": [{"id": f"ar-{n}", "name": n} for n in names],
        "albumArtists": [{"id": f"ar-{n}", "name": n} for n in aa_names],
        "displayArtist": " & ".join(names), "displayAlbumArtist": " & ".join(aa_names),
        "genre": genres[0] if genres else None, "genres": [{"name": g} for g in genres],
        "year": year, "duration": duration, "created": created or iso_days_ago(400),
        "path": path or f"{aa_names[0] if aa_names else 'X'}/{album}/{sid}.opus", "suffix": "opus",
        "playCount": plays,
    }
    if rating is not None:
        s["userRating"] = rating
    if avg is not None:
        s["averageRating"] = avg
    if starred:
        s["starred"] = "2024-01-01T00:00:00Z"
    if played:
        s["played"] = played
    return {k: v for k, v in s.items() if v is not None}


def random_songs(n, seed=1, avoid_days=()):
    """Random but reproducible library. avoid_days: day offsets that do not occur in date fields
    (the boundary days of the date rules – see test_rules)."""
    rnd = random.Random(seed)
    days = [d for d in range(0, 500) if d not in set(avoid_days)]
    out = []
    for i in range(n):
        k = rnd.choice([1, 1, 1, 2, 2, 3])
        arts = rnd.sample(ARTISTS, k) if rnd.random() < 0.95 else []
        aa = [rnd.choice(arts)] if arts and rnd.random() < 0.8 else rnd.sample(ARTISTS, 1)
        title = " ".join(rnd.sample(WORDS, rnd.choice([1, 2]))).swapcase() if rnd.random() < 0.2 else \
            " ".join(rnd.sample(WORDS, rnd.choice([1, 2])))
        album = None if rnd.random() < 0.05 else " ".join(rnd.sample(WORDS, rnd.choice([1, 2])))
        s = song(f"s{i:04d}", title=title, album=album or "x", artists=arts, album_artists=aa,
                 genres=rnd.sample(GENRES, rnd.choice([0, 1, 1, 2, 3])),
                 year=rnd.choice([None, 1975, 1980, 1985, 1989, 1990, 2001, 2015]),
                 duration=rnd.choice([30, 44, 45, 46, 90, 119, 120, 121, 300]),
                 rating=rnd.choice([None, None, 1, 2, 3, 4, 5]), starred=rnd.random() < 0.2,
                 plays=rnd.choice([0, 0, 1, 5, 20]),
                 played=None if rnd.random() < 0.3 else iso_days_ago(rnd.choice(days)),
                 created=iso_days_ago(rnd.choice(days)))
        if album is None:
            s.pop("album")
        if not arts:   # song without artist roles: Navidrome then only delivers the display name
            s["artist"] = "Unbekannt"
        out.append(s)
    return out


def base_config():
    """Default configuration (app/default_config.json) with a manageable set of test worlds, directions and persons."""
    cfg = copy.deepcopy(config.default_config())
    cfg.setdefault("version", config.CONFIG_VERSION)
    S = cfg["settings"]
    S["excludeTitles"] = ["(Live", "Instrumental", "Karaoke"]
    S["minDuration"] = 120
    S["allMinRating"] = 3
    S["limit"] = 100
    S["defaultPerson"] = "familie"
    S["allName"] = "Alle"   # the test data is a German family installation
    cfg["welten"] = [
        {"id": "kinder", "name": "Kinder", "artists": ["Band A", "Band B"], "genres": ["Children"], "separate": True,
         "minDuration": 45, "minRating": 0, "excludeTitles": ["(Kapitel"], "excludeAlbums": ["Hörspiel"]},
        {"id": "metal", "name": "Metal", "artists": ["Iron Test"], "genres": ["Metal"], "minRating": 2},
        {"id": "mittelalter", "name": "Mittelalter", "artists": ["Spielleute"], "albums": ["Mittelaltermarkt"],
         "minDuration": 90},
    ]
    cfg["stile"] = [
        {"id": "tanzen", "name": "Tanzen & Toben", "albums": ["Tanz", "Party"], "titles": ["Tanz"]},
        {"id": "weihnachten", "name": "Weihnachten", "season": ["11-25", "01-06"], "albums": ["Weihnacht"],
         "titles": ["Jingle Bell"], "genres": ["Christmas"],
         "excludeElsewhere": {"albums": ["Weihnacht"], "titles": ["Jingle Bell"], "genres": ["Christmas"]}},
        {"id": "sommer", "name": "Sommer", "season": ["06-01", "08-31"], "titles": ["Sommer"]},
        {"id": "jahreszeit", "name": "Passend zur Jahreszeit", "kind": "season"},
        {"id": "80er", "name": "80er", "filters": {"years": [1980, 1989]}},
        {"id": "tophits", "name": "Top-Hits", "filters": {"minRating": 4}},
        {"id": "neu", "name": "Neu dazugekommen", "filters": {"addedDays": 60}},
        {"id": "lieblinge", "name": "Lieblingssongs", "filters": {"loved": True}},
        {"id": "klang-ruhig", "name": "Ruhig", "sound": {"moods": ["ruhig"]}},
    ]
    cfg["personen"] = [
        {"id": "familie", "name": "Familie", "user": "", "public": True, "prefix": "",
         "likes": {"welten": [], "stile": [], "artists": []}, "dislikes": {"artists": ["Band X"], "genres": []}},
        {"id": "jonas", "name": "Jonas", "user": "Jonas", "public": False, "prefix": "Jonas · ",
         "likes": {"welten": ["kinder"], "stile": [], "artists": []},
         "dislikes": {"artists": ["Nordwind"], "genres": ["Metal"]}},
        {"id": "niklas", "name": "Niklas", "user": "niklas", "prefix": "",   # without "public" -> private
         "likes": {"welten": [], "stile": [], "artists": []}, "dislikes": {"artists": [], "genres": []}},
        {"id": "oma", "name": "Oma", "user": "oma", "public": True, "prefix": "Oma · ", "color": "#aa0000",
         "likes": {"welten": ["mittelalter"], "stile": [], "artists": ["Spielleute"]},
         "dislikes": {"artists": ["Iron Test"], "genres": []}},
    ]
    cfg["playlists"] = []
    cfg["dismissed"], cfg["ignored"] = [], []
    return cfg
