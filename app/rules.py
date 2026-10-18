"""Build smart playlist rules and evaluate them locally (preview, song counts, suggestions).

A playlist is the combination of
  * music world – WHO: curated artists + typical bands of a scene, album series, genres
                  ("*" = all, without separated worlds such as kids; or a list = several worlds)
  * vibe        – WHAT: genres, keywords in album/title, season, decade, rating … ("*" = everything)
  * person      – FOR WHOM: owner in Navidrome (whose stars/favorites count), visibility, dislikes
Internally music worlds are called "welten" and vibes "stile".
"""
import datetime as dt
import itertools
import json
import math
import random
import re
import threading
import weakref
from collections import Counter, OrderedDict, defaultdict, deque

from . import scenes
from .config import MARKER
from .i18n import N_, _, _n, _s

ALL = "*"
MULTI_FIELDS = {"artist", "albumartist", "genre"}   # multi-valued in Navidrome (tags/roles)
SORTS = {"random": "random", "neu": "-dateadded", "beliebt": "-rating", "vergessen": "lastplayed"}   # i18n-ignore: stored values


# --------------------------------------------------------------------------- helpers

def _find(items, item_id):
    for item in items:
        if item["id"] == item_id:
            return item
    raise KeyError(item_id)


def _dedupe(items):
    seen, out = set(), []
    for item in items:
        key = json.dumps(item, sort_keys=True, ensure_ascii=False)
        if key not in seen:
            seen.add(key)
            out.append(item)
    return out


def welt_ids(playlist):
    w = playlist.get("welt", ALL)
    if isinstance(w, list):
        return list(w)
    return [] if w in (None, ALL) else [w]


def season_active(season, today=None):
    if not season:
        return False
    md = (today or dt.date.today()).strftime("%m-%d")
    if md == "02-29":
        md = "02-28"   # leap day counts as the 28th – otherwise e.g. winter ("until 02-28") would end a day early
    start, end = season
    return start <= md <= end if start <= end else (md >= start or md <= end)


def season_soon(season, today=None, days=21):
    today = today or dt.date.today()
    return any(season_active(season, today + dt.timedelta(days=d)) for d in (0, days // 2, days))


def resting(cfg, playlist, today=None):
    """Seasonal playlist outside its time (Christmas in summer)? -> day from which it is back, otherwise None.
    It is then not in Navidrome and Symfonium – that keeps the lists tidy (settings.seasonRest; "all year" per
    playlist with yearRound)."""
    if not cfg["settings"].get("seasonRest", True) or playlist.get("yearRound") or playlist.get("rules") is not None:
        return None
    stil = None if playlist.get("stil", ALL) == ALL else _find(cfg["stile"], playlist.get("stil"))
    if not stil or stil.get("kind") == "season" or not stil.get("season"):
        return None
    today = today or dt.date.today()
    if season_active(stil["season"], today):
        return None
    for d in range(1, 367):
        day = today + dt.timedelta(days=d)
        if season_active(stil["season"], day):
            return day
    return None


def active_season_stile(cfg, today=None):
    return [s for s in cfg["stile"] if s.get("kind") != "season" and season_active(s.get("season"), today)]


class BuildContext:
    """What building needs besides the configuration: the library (for scene bands and hits thresholds) and the
    date (for seasons)."""

    def __init__(self, lib=None, today=None):
        self.lib = lib
        self.today = today

    @property
    def artist_index(self):
        return self.lib.artist_index() if self.lib else None


# --------------------------------------------------------------------------- music worlds

def scene_members(welt, ctx):
    """Bands of the linked catalog world: typical bands and – with a library – the recognized ones (autowelten.py)."""
    if ctx.lib is not None:
        from .autowelten import members
        return members(welt["scene"], ctx.lib)
    return scenes.members(welt["scene"], ctx.artist_index)


def welt_artists(welt, ctx=None):
    """Manual artists + automatically recognized bands of the scene – excluded ones."""
    out = list(welt.get("artists", []))
    if welt.get("autoScene") and welt.get("scene") and ctx is not None:
        excluded = set(welt.get("excludedArtists", []))
        out += [a for a in scene_members(welt, ctx) if a not in excluded and a not in out]
    return out


def auto_artists(welt, ctx):
    manual = set(welt.get("artists", []))
    if not (welt.get("autoScene") and welt.get("scene")):
        return []
    return [a for a in scene_members(welt, ctx) if a not in manual]


def welt_block(welt, ctx=None):
    rules = []
    for a in welt_artists(welt, ctx):
        rules += [{"is": {"artist": a}}, {"is": {"albumartist": a}}]
    # "contains" as in welt_negation(): Navidrome has no "notStartsWith" – this way exactly what the separate music
    # world takes in drops out of the all-playlists
    rules += [{"contains": {"album": x}} for x in welt.get("albums", [])]
    rules += [{"contains": {"genre": g}} for g in welt.get("genres", [])]
    return rules


def welt_negation(welt, ctx=None, keep=()):
    """Rules that exclude a separate music world. keep: artists that should be included anyway (addArtists)."""
    rules = []
    for a in welt_artists(welt, ctx):
        if a in keep:
            continue
        rules += [{"isNot": {"artist": a}}, {"isNot": {"albumartist": a}}]
    rules += [{"notContains": {"album": x}} for x in welt.get("albums", [])]
    rules += [{"notContains": {"genre": g}} for g in welt.get("genres", [])]
    return rules


# --------------------------------------------------------------------------- vibes

def stil_block(stil):
    return ([{"contains": {"genre": g}} for g in stil.get("genres", [])]
            + [{"is": {"artist": a}} for a in stil.get("artists", [])]
            + [{"contains": {"album": k}} for k in stil.get("albums", [])]
            + [{"contains": {"title": k}} for k in stil.get("titles", [])])


def filter_rules(filters):
    rules = []
    if filters.get("years"):
        rules.append({"inTheRange": {"year": [int(filters["years"][0]), int(filters["years"][1])]}})
    if filters.get("loved"):
        rules.append({"is": {"loved": True}})
    if filters.get("addedDays"):
        rules.append({"inTheLast": {"dateadded": int(filters["addedDays"])}})
    if filters.get("notPlayedDays"):
        rules.append({"notInTheLast": {"lastplayed": int(filters["notPlayedDays"])}})
    if filters.get("neverPlayed"):
        rules.append({"is": {"playcount": 0}})
    return rules


# --------------------------------------------------------------------------- names

def person_of(cfg, playlist):
    pid = playlist.get("person") or cfg["settings"].get("defaultPerson")
    return next((p for p in cfg.get("personen", []) if p["id"] == pid), None)


def together_of(cfg, playlist):
    """People of a family mix whose taste may count: those visible to everyone, those with the same account as the
    playlist's person – and all of them if the playlist belongs to the shared person (the administrator looks after
    it). This way a profile that has become private no longer flows into other people's mixes."""
    ids = playlist.get("together") or []
    if not ids:
        return []
    owner = person_of(cfg, playlist) or {}
    shared = owner.get("id") == cfg["settings"].get("defaultPerson")
    out = []
    for p in cfg.get("personen", []):
        if p["id"] in ids and (shared or p.get("public") or (p.get("user") or "").lower() == (owner.get("user") or "").lower()):
            out.append(p)
    return out


MONTH_NAMES = [N_("January"), N_("February"), N_("March"), N_("April"), N_("May"), N_("June"), N_("July"),
               N_("August"), N_("September"), N_("October"), N_("November"), N_("December")]


def join_and(items):
    """"a, b and c" in the language of the request (a single item stays as it is)."""
    items = list(items)
    if len(items) > 1:
        return _("{first} and {last}", first=", ".join(items[:-1]), last=items[-1])
    return items[0] if items else ""


def favorite_artists(cfg, person, ctx=None, n=30):
    """Favorite bands of a person: chosen by hand and the most played ones (taste.py), without dislikes."""
    if not person:
        return []
    likes = list((person.get("likes") or {}).get("artists", []))
    heard = []
    lib = getattr(ctx, "lib", None)
    if lib is not None and person.get("user"):
        try:
            from . import taste
            prof = taste.profile(cfg, lib, person["user"], getattr(ctx, "today", None))
            if prof and prof.get("enough"):
                heard = [a for a, share in prof["artists"] if share >= 0.01]
        except Exception:   # noqa: BLE001 – no password or Navidrome briefly gone: only the ones chosen by hand
            heard = []
    nogo = set((person.get("dislikes") or {}).get("artists", []))
    return [a for a in dict.fromkeys(likes + heard) if a not in nogo][:n]


def review_period(kind, day):
    """Period of the recap playlist on mix day `day`: the last full month or the year up to the end of last month
    (in January the whole previous year). -> (from, to, title without "Your"/"Our"; server language)."""
    first = day.replace(day=1)
    end = first - dt.timedelta(days=1)
    if kind == "year":
        return dt.date(end.year, 1, 1), end, _s("year {year}", year=end.year)
    return end.replace(day=1), end, f"{_s(MONTH_NAMES[end.month - 1])} {end.year}"   # i18n-ignore: N_ constant


def review_name(cfg, playlist, day=None):
    from .mixer import mix_day
    person = person_of(cfg, playlist) or {}
    _start, _end, title = review_period((playlist.get("review") or {}).get("period", "month"), day or mix_day())
    if person.get("id") == cfg["settings"].get("defaultPerson"):   # the shared person: the whole family
        return person.get("prefix", "") + _s("Our {period}", period=title)
    return person.get("prefix", "") + _s("Your {period}", period=title)


def base_name(cfg, playlist):
    """Name of a smart playlist from music world × vibe. A whole world without a vibe is “All Sorts”, not “Mix”:
    “Mix” is kept for real mixes (playlist_name)."""
    welten = [_find(cfg["welten"], w) for w in welt_ids(playlist)]
    stil = None if playlist.get("stil", ALL) == ALL else _find(cfg["stile"], playlist["stil"])
    hits = playlist.get("hits")
    wname = " + ".join(w["name"] for w in welten)
    if stil is None:
        return _s("{world} · The Hits", world=wname) if hits else _s("{world} · All Sorts", world=wname)
    sname = stil["name"] + (" (Hits)" if hits else "")
    if not welten:
        return sname
    return cfg["settings"]["namePattern"].format(welt=wname, stil=sname)


def is_mix(playlist):
    return playlist.get("type") == "mix"


def playlist_name(cfg, playlist):
    if playlist.get("name"):
        return playlist["name"]
    if playlist.get("rules") is not None:
        return playlist.get("originalName") or "Playlist"
    if playlist.get("review"):   # "Your October 2026" – the name moves on with the month
        return review_name(cfg, playlist)
    person = person_of(cfg, playlist)
    prefix = person.get("prefix", "") if person else ""
    if playlist.get("radio"):
        seeds = playlist["radio"].get("seed", [])
        return prefix + "Radio · " + " & ".join(seeds[:2]) + (" …" if len(seeds) > 2 else "")
    if is_mix(playlist):
        welten = [_find(cfg["welten"], w)["name"] for w in welt_ids(playlist)]
        stil = None if playlist.get("stil", ALL) == ALL else _find(cfg["stile"], playlist["stil"])["name"]
        parts = [" + ".join(welten)] if welten else []
        if stil:
            parts.append(stil)
        from .mixer import label
        return prefix + label(playlist) + " · " + (" · ".join(parts) or _s("Everything"))
    return prefix + base_name(cfg, playlist)


def describe(cfg, playlist):
    """Description for the "comment" in Navidrome (server language)."""
    if playlist.get("rules") is not None:
        return _s("custom rules (taken over unchanged)")
    welten = [_find(cfg["welten"], w)["name"] for w in welt_ids(playlist)]
    stil = None if playlist.get("stil", ALL) == ALL else _find(cfg["stile"], playlist["stil"])["name"]
    text = f"{' + '.join(welten) or cfg['settings'].get('allName', _s('All'))} × {stil or _s('Everything')}"
    if playlist.get("radio"):
        text = _s("{bands} and similar bands", bands=" & ".join(playlist["radio"].get("seed", [])))
    if playlist.get("fav"):
        text = _s("New from the favorite bands, last {days} days", days=int(playlist["fav"].get("days") or 60))
    if playlist.get("together"):
        text = _s("What everyone likes: {text}", text=text)
    if playlist.get("review"):
        if playlist["review"].get("period") == "year":
            return _s("Recap – the most played songs of the year")
        return _s("Recap – the most played songs of last month")
    if is_mix(playlist):
        from .mixer import EVERY, options
        opt = options(playlist)
        name, how = EVERY.get(opt.get("every"), EVERY["day"])
        cap = _s("max. {n} per band", n=opt["perArtist"]) if opt.get("perArtist") else _s("no band limit")
        text = _s("{mix} – {text}, {cap}, renewed {every}", mix=name, text=text, cap=cap, every=_s(how))   # i18n-ignore: N_ constant
    return text


# --------------------------------------------------------------------------- build .nsp

def build_nsp(cfg, playlist, ctx=None):
    ctx = ctx or BuildContext()
    S = cfg["settings"]
    person = person_of(cfg, playlist)
    # Without "public" the person counts as private – as with the visibility in Tuttiphon (auth.visible_playlist)
    public = bool(person.get("public", False)) if person else bool(S.get("public", True))
    head = {
        "name": playlist_name(cfg, playlist),
        "comment": f"{MARKER}: {describe(cfg, playlist)}",
        "public": public,
    }
    if playlist.get("rules") is not None:   # taken over unchanged
        return {**head, playlist.get("rulesOp", "all"): playlist["rules"],
                "sort": playlist.get("sortRaw") or SORTS.get(playlist.get("sort"), "random"),
                **({"limit": int(playlist["limit"])} if playlist.get("limit") else {}),
                **{k: v for k, v in (playlist.get("rulesExtra") or {}).items()   # e.g. "order", "offset"
                   if k not in ("name", "comment", "public", "all", "any", "sort", "limit")}}

    welten = [_find(cfg["welten"], w) for w in welt_ids(playlist)]
    stil = None if playlist.get("stil", ALL) == ALL else _find(cfg["stile"], playlist["stil"])
    rules = []

    # WHO
    extra = [r for a in playlist.get("addArtists", []) for r in ({"is": {"artist": a}}, {"is": {"albumartist": a}})]
    radio = playlist.get("radio")
    fav = playlist.get("fav")
    if fav and not radio:   # new from the favorite bands: bands chosen by hand and most played, freshly added
        arts = favorite_artists(cfg, person, ctx)
        rules.append({"any": _dedupe([r for a in arts for r in ({"is": {"artist": a}}, {"is": {"albumartist": a}})] + extra)
                      or [{"is": {"title": _s("– no favorite bands yet –")}}]})   # matches nothing
        rules.append({"inTheLast": {"dateadded": int(fav.get("days") or 60)}})
    elif radio:   # radio: seed band(s) + similar bands that are in the library (Last.fm, otherwise genres)
        if ctx.lib is not None:
            from .classify import radio_artists
            arts = radio_artists(radio.get("seed", []), ctx.lib, limit=int(radio.get("bands") or 25))
        else:
            arts = list(radio.get("seed", []))
        rules.append({"any": _dedupe([r for a in arts for r in ({"is": {"artist": a}}, {"is": {"albumartist": a}})] + extra)})
    elif welten:
        rules.append({"any": _dedupe([r for w in welten for r in welt_block(w, ctx)] + extra)})
    else:   # all: the whole library without separate music worlds – additionally chosen artists stay in anyway
        keep = set(playlist.get("addArtists", []))
        for w in cfg["welten"]:
            if w.get("separate"):
                rules += welt_negation(w, ctx, keep)

    # WHAT
    seasonal = []
    if stil:
        if stil.get("kind") == "season":
            seasonal = active_season_stile(cfg, ctx.today)
            block = [rule for s in seasonal for rule in stil_block(s)]
            if not block:   # no season active right now -> the playlist stays empty instead of "everything"
                block = [{"is": {"title": _s("– no season active –")}}]   # matches nothing
        else:
            block = stil_block(stil)
        if block:
            rules.append({"any": _dedupe(block)})
        rules += filter_rules(stil.get("filters") or {})

    # hide seasonal/topic content (Christmas, lantern songs, lullabies …) everywhere else
    own = shown_vibes(cfg, playlist, stil, seasonal)
    for s in cfg["stile"]:
        if s["id"] in own:
            continue
        ex = s.get("excludeElsewhere") or {}
        rules += [{"notContains": {"album": k}} for k in ex.get("albums", [])]
        rules += [{"notContains": {"title": k}} for k in ex.get("titles", [])]
        rules += [{"notContains": {"genre": k}} for k in ex.get("genres", [])]

    # Dislikes of the person and the playlist – in the family mix ("What everyone likes") those of everyone involved
    # (private ones too: protection comes first; only taste needs consent, rules.together_of())
    together = [x for x in cfg.get("personen", []) if x["id"] in (playlist.get("together") or [])]
    nogo_artists, nogo_genres = list(playlist.get("excludeArtists", [])), []
    for x in [person or {}] + together:
        nogo_artists += (x.get("dislikes") or {}).get("artists", [])
        nogo_genres += (x.get("dislikes") or {}).get("genres", [])
    for a in dict.fromkeys(nogo_artists):
        rules += [{"isNot": {"artist": a}}, {"isNot": {"albumartist": a}}]
    rules += [{"notContains": {"genre": g}} for g in dict.fromkeys(nogo_genres)]

    # clean up: live, instrumental, karaoke, too short …
    w0 = welten[0] if len(welten) == 1 else None
    titles = list(S.get("excludeTitles", [])) + [t for w in welten for t in w.get("excludeTitles", [])]
    rules += [{"notContains": {"title": t}} for t in titles]
    rules += [{"notContains": {"album": a}} for w in welten for a in w.get("excludeAlbums", [])]
    min_duration = playlist.get("minDuration")
    if min_duration is None:
        min_duration = w0.get("minDuration") if w0 and w0.get("minDuration") is not None else S.get("minDuration")
        if len(welten) > 1:
            min_duration = min((w.get("minDuration") if w.get("minDuration") is not None else S.get("minDuration") or 0)
                               for w in welten)
    if min_duration:
        rules.append({"gt": {"duration": int(min_duration)}})

    # rating: minimum rating or "only the hits" – each OR marked as favorite
    min_rating = _min_rating(S, playlist, welten, stil)
    if playlist.get("hits"):
        min_rating = hits_threshold(cfg, rules, ctx, floor=min_rating)
    if min_rating > 0:
        rules.append({"any": [{"gt": {"rating": min_rating - 1}}, {"is": {"loved": True}}]})
    if playlist.get("notPlayedDays"):
        rules.append({"notInTheLast": {"lastplayed": int(playlist["notPlayedDays"])}})

    desc = describe(cfg, playlist)
    if seasonal:
        desc = _s("{text} (currently: {seasons})", text=desc, seasons=", ".join(s["name"] for s in seasonal))
    head["comment"] = f"{MARKER}: {desc}"
    # Files Navidrome lists as missing (e.g. the old FLAC after the conversion to Opus) would otherwise count in
    # Navidrome: the playlist would be shorter than its limit in Symfonium
    rules.append({"is": {"missing": False}})
    if any(x.get("clean") for x in [person or {}] + together):
        rules += clean_rules(cfg, rules, ctx)
    return {**head, "all": _dedupe(rules), "sort": SORTS.get(playlist.get("sort"), "random"),
            "limit": int(playlist.get("limit") or S.get("limit") or 100)}


def clean_rules(cfg, rules, ctx):
    """Kid-safe mode: take songs with explicit lyrics (liedtext.py) out of the selection – as one rule per title,
    because Navidrome evaluates smart playlists itself and does not know the lyrics detection."""
    if ctx is None or ctx.lib is None:
        return []
    from . import liedtext
    allow = set((cfg["settings"].get("kinderschutz") or {}).get("allow", []))
    rude = liedtext.derb(allow)
    lib = ctx.lib

    def bad(s):   # recognized by the lyrics – or marked "explicit" in the file
        return s["id"] in rude or (s.get("explicitStatus") in ("explicit", "e") and s["id"] not in allow)

    # Pool without rules on stars, favorites and plays – Navidrome evaluates those with the person's account, here the
    # song list of another account would be used (an explicit favorite song of the child would otherwise slip through)
    pool = lib.match({"all": _account_free(rules)})
    titles = sorted({lib.songs[i].get("title") for i in pool if bad(lib.songs[i]) and lib.songs[i].get("title")})
    return [{"isNot": {"title": t}} for t in titles]


ACCOUNT_FIELDS = {"rating", "loved", "playcount", "lastplayed", "dateloved", "daterated"}


def _account_free(rules):
    """Rules without account-dependent fields – the selection only gets bigger, never smaller (safe for protection)."""
    out = []
    for r in rules:
        (op, arg), = r.items() if isinstance(r, dict) and len(r) == 1 else ((None, None),)
        if op == "all":
            inner = _account_free(arg)
            if inner:
                out.append({"all": inner})
        elif op == "any":   # an OR block would be narrower without one of its options – then it is dropped entirely
            inner = _account_free(arg)
            if inner and len(inner) == len(arg):
                out.append({"any": inner})
        elif isinstance(arg, dict) and set(arg) & ACCOUNT_FIELDS:
            continue
        else:
            out.append(r)
    return out


def hits_threshold(cfg, rules, ctx, floor=0):
    """Star threshold for "The hits": roughly the most popular third of what would otherwise be in it.
    Always above the normal minimum rating (floor), as long as enough songs remain."""
    if not ctx.lib:
        return max(floor + 1, 3)
    ids = ctx.lib.ids({"all": rules}) if rules else frozenset(range(len(ctx.lib.songs)))
    ratings = ctx.lib.field_values("rating")
    loved = ctx.lib.field_values("loved")

    def at_least(t):   # -0.25: round averages (e.g. 2.67) generously
        return sum(1 for i in ids if (ratings[i] or 0) >= t - 0.25 or loved[i])

    base = at_least(floor) if floor else len(ids)
    if not base:
        return floor
    share = float(cfg["settings"].get("hitsShare", 0.3))
    need = max(min(25, base), share * base)
    for t in range(5, floor, -1):
        if at_least(t) >= need:
            return t
    # hardly any stars: still only rated songs (or favorites) – "the hits" must never simply be everything
    return floor + 1


# --------------------------------------------------------------------------- local evaluation

_BIT_OFFSETS = [tuple(k for k in range(8) if b >> k & 1) for b in range(256)]


def _indices(bits):
    """Bit mask -> frozenset of the set bit numbers."""
    data = bits.to_bytes((bits.bit_length() + 7) // 8, "little")
    offsets = _BIT_OFFSETS
    return frozenset([j << 3 | k for j, b in enumerate(data) if b for k in offsets[b]])


def _mask(groups, n):
    """Song numbers (each entry a number or a list of numbers, as in _add) -> bit mask of all of them
    (n = number of songs)."""
    total = 0
    for idx in groups:
        total += 1 if idx.__class__ is int else len(idx)
    if not total:
        return 0
    if total * 8 < n:   # few songs: set single bits
        buf = bytearray((n + 7) >> 3)
        for idx in groups:
            if idx.__class__ is int:
                buf[idx >> 3] |= 1 << (idx & 7)
                continue
            for i in idx:
                buf[i >> 3] |= 1 << (i & 7)
        return int.from_bytes(buf, "little")
    buf = bytearray(b"0") * n   # many: one character per song, read as a binary number
    for idx in groups:
        if idx.__class__ is int:
            buf[idx] = 49
            continue
        for i in idx:
            buf[i] = 49
    buf.reverse()
    return int(buf, 2)


def _add(index, key, i):
    """index[key]: song number i – one number or, from the second song on, a list (saves memory for unique values)."""
    cur = index.get(key)
    if cur is None:
        index[key] = i
    elif cur.__class__ is int:
        if cur != i:
            index[key] = [cur, i]
    elif cur[-1] != i:
        cur.append(i)


def _scan(test, values):
    """Bit mask of the songs whose value passes the test – song by song."""
    return int("".join("1" if test(v) else "0" for v in reversed(values)) or "0", 2)


# Fields whose values do not depend on the account (and not on Navidrome's file paths): song lists with the same songs
# in the same order share what is computed from them (_Shared)
SHARED_FIELDS = frozenset({"artist", "albumartist", "genre", "album", "title", "year", "duration", "dateadded",
                           "missing"})
TEXT_OPS = ("contains", "notContains", "startsWith", "endsWith")
_shared_ids = itertools.count(1)
# keys of shared caches whose song lists are gone: caches of other modules drop their entries for them (ml.gone()) –
# otherwise e.g. the sound features of every reloaded song list would stay until their cache is full
RELEASED = deque(maxlen=512)


class _Shared:
    """What a song list computes from SHARED_FIELDS: values, value index, lowercased values, rule results (bit masks).
    The song list of an account uses the one of the default list when it has the same songs in the same order
    (stats.songs_for) – the music worlds are then evaluated once instead of once per account."""

    def __init__(self, keyed=False):
        self.key = next(_shared_ids)   # for caches of other modules (ml.songs_key)
        if keyed:   # only remembers the number (no lock: may run in the middle of anything, during garbage collection)
            weakref.finalize(self, RELEASED.append, self.key)
        self.bits, self.values, self.groups, self.lowered, self.present = {}, {}, {}, {}, {}
        self.artist_index = None


class Library:
    """Evaluates .nsp rules locally against the song list (preview, song counts, suggestions).

    Mirrors the SQL logic of Navidrome 0.64 (persistence/criteria_sql.go): tags/roles are multi-valued, negations
    are NOT EXISTS, LIKE is case-insensitive, a missing rating = 0.

    A rule part is evaluated once per song list and cached as a bit mask. Text rules do not look at every song but at
    an index of the distinct values (value -> songs, lowercased text -> songs), built in one pass per field – a band
    rule ("is artist X") costs microseconds instead of milliseconds.
    """

    def __init__(self, songs, ratings_exact=True, user=None):
        self.songs = songs
        self.ratings_exact = ratings_exact   # False: average rating as an approximation
        self.user = user
        self._cache = {}       # rule results of fields that depend on the account or the file paths
        self._own = _Shared()  # values, index … of these fields
        self._shared = _Shared(keyed=True)

    def share_with(self, other):
        """Use the account-independent caches of another song list with the same songs in the same order (the caller
        checks that, stats.songs_for). Only right after creating the list."""
        if len(self.songs) == len(other.songs):
            self._shared = other._shared

    def songs_key(self):
        """Key of the song list for caches that only depend on the songs and their account-independent fields
        (sound features, band styles, sound index): the same for lists that share their caches."""
        return self._shared.key

    def artist_index(self):
        """normalized name -> exact names in Navidrome (track and album artists)."""
        shared = self._shared
        if shared.artist_index is None:
            idx = defaultdict(set)
            for s in self.songs:
                for a in (s.get("artists") or []) + (s.get("albumArtists") or []):
                    idx[scenes.norm(a["name"])].add(a["name"])
            shared.artist_index = dict(idx)
        return shared.artist_index

    def field_values(self, field):
        return self._field(field)

    def _store(self, field):
        return self._shared if field in SHARED_FIELDS else self._own

    def _field(self, field):
        field = field.lower()
        store = self._store(field)
        if field in store.values:
            return store.values[field]
        getter = {
            "artist": lambda s: [a["name"] for a in s.get("artists") or []] or [s.get("artist", "")],
            "albumartist": lambda s: [a["name"] for a in s.get("albumArtists") or []] or [s.get("displayAlbumArtist", "")],
            "genre": lambda s: [g["name"] for g in s.get("genres") or []],
            "album": lambda s: s.get("album"),
            "title": lambda s: s.get("title"),
            "filepath": lambda s: s.get("path"),
            "year": lambda s: s.get("year") or 0,
            "duration": lambda s: s.get("duration") or 0,
            "rating": (lambda s: s.get("userRating") or 0) if self.ratings_exact
                      else (lambda s: s.get("userRating") or s.get("averageRating") or 0),
            "loved": lambda s: bool(s.get("starred")),
            "playcount": lambda s: s.get("playCount") or 0,
            "lastplayed": lambda s: s.get("played"),
            "dateadded": lambda s: s.get("created"),
            "missing": lambda s: False,   # the song list from Navidrome only contains existing files
        }.get(field.lower())
        if getter is None:
            raise ValueError(_("Field '{field}' is not supported in the preview", field=field))
        if field == "filepath":   # like Navidrome: the real file path (Subsonic only returns one built from tags)
            try:
                self._load_paths()
                real = self._real_paths
            except RuntimeError:   # Navidrome not reachable right now: then the built path as an approximation
                real = {}
            getter = lambda s: real.get(s.get("id")) or s.get("path")   # noqa: E731
        values = [getter(s) for s in self.songs]
        store.values[field] = values
        return values

    def _groups(self, field):
        """Distinct values of a field -> the song with it (number) or the songs (list of numbers); multi-valued fields:
        each of their values. Values that are not text are kept apart by type (1, 1.0 and True stay three).
        None if a value cannot be a dict key (then evaluate song by song)."""
        store = self._store(field)
        if field in store.groups:
            return store.groups[field]
        values = self._field(field)
        out = {}
        try:
            if field in MULTI_FIELDS:
                for i, v in enumerate(values):
                    for x in v:
                        _add(out, x, i)
            else:
                for i, v in enumerate(values):
                    _add(out, v if v is None or v.__class__ is str else (v.__class__, repr(v), v), i)
        except TypeError:
            out = None
        store.groups[field] = out
        return out

    def _lowered(self, field):
        """Lowercased text of a field -> song number(s), for contains & co. (songs without a value are missing)."""
        store = self._store(field)
        if field in store.lowered:
            return store.lowered[field]
        values = self._field(field)
        out = {}
        if field in MULTI_FIELDS:
            for i, v in enumerate(values):
                for x in v:
                    _add(out, x.lower(), i)
        else:
            for i, v in enumerate(values):
                if v is not None:
                    _add(out, (v if v.__class__ is str else str(v)).lower(), i)
        store.lowered[field] = out
        return out

    def _present(self, field):
        """Bit mask of the songs that have a value in this (single-valued) field."""
        store = self._store(field)
        if field not in store.present:
            values = self._field(field)
            store.present[field] = ((1 << len(values)) - 1) ^ _mask([[i for i, v in enumerate(values) if v is None]],
                                                                      len(values))
        return store.present[field]

    def ids(self, rule):
        """Indices of the songs a rule matches."""
        return _indices(self._bits(rule))

    def _bits(self, rule):
        """Matches of a rule as a bit mask (bit i = song i). In the cache that is ~3 KB per rule – as a set it would
        be over 1 MB for rules like "not this artist" that match almost everything."""
        return self._eval(rule)[0]

    def _eval(self, rule):
        """-> (bit mask, does it only depend on SHARED_FIELDS?) – such results go into the shared cache."""
        key = json.dumps(rule, sort_keys=True, ensure_ascii=False)
        shared = self._shared.bits
        hit = shared.get(key)
        if hit is not None:
            return hit, True
        hit = self._cache.get(key)
        if hit is not None:
            return hit, False
        if "all" in rule:
            result, free = (1 << len(self.songs)) - 1, True
            for r in rule["all"]:   # evaluate all (do not stop early) – otherwise errors in rules would go unnoticed
                bits, f = self._eval(r)
                result &= bits
                free = free and f
        elif "any" in rule:
            result, free = 0, True
            for r in rule["any"]:
                bits, f = self._eval(r)
                result |= bits
                free = free and f
        else:
            ((op, body),) = rule.items()
            ((field, value),) = body.items()
            field = field.lower()
            result = self._leaf(op, field, value)
            # "in the last n days" depends on today: stays with this list (it is reloaded regularly)
            free = field in SHARED_FIELDS and op not in ("inTheLast", "notInTheLast")
        (shared if free else self._cache)[key] = result
        return result, free

    def _leaf(self, op, field, value):
        """Bit mask of one rule part – from the value index where possible, otherwise song by song (_scan). Both give
        exactly the same result as the predicate applied to every song."""
        test = self._predicate(op, field, value)   # unknown operator: error before the field is looked at
        values = self._field(field)
        n = len(values)
        full = (1 << n) - 1
        multi = field in MULTI_FIELDS
        if op in TEXT_OPS and isinstance(value, str):
            low = value.lower()
            items = self._lowered(field).items()
            if op == "startsWith":
                hit = [idx for text, idx in items if text.startswith(low)]
            elif op == "endsWith":
                hit = [idx for text, idx in items if text.endswith(low)]
            else:
                hit = [idx for text, idx in items if low in text]
            bits = _mask(hit, n)
            if op != "notContains":
                return bits
            # tag/role: NOT EXISTS (a song without any value passes);  column: NOT LIKE (NULL -> no match)
            return (full if multi else self._present(field)) & ~bits
        if multi and op not in ("is", "isNot"):
            return _scan(test, values)
        groups = self._groups(field)
        if groups is None:
            return _scan(test, values)
        if op in ("is", "isNot") and (multi or isinstance(value, str)):   # exact value: look it up (text never
            # equals a number or None)
            try:
                idx = groups.get(value)
            except TypeError:   # e.g. a list: equal to no value
                idx = None
            bits = _mask([] if idx is None else [idx], n)
            if op == "is":
                return bits
            return (full if multi else self._present(field)) & ~bits
        hit, miss, n_hit, n_miss = [], [], 0, 0
        for k, idx in groups.items():
            count = 1 if idx.__class__ is int else len(idx)
            if test(k[2] if k.__class__ is tuple else k):
                hit.append(idx)
                n_hit += count
            else:
                miss.append(idx)
                n_miss += count
        return _mask(hit, n) if n_hit <= n_miss else full ^ _mask(miss, n)

    def _predicate(self, op, field, value):
        multi = field in MULTI_FIELDS
        low = value.lower() if isinstance(value, str) else value

        def strings(v):
            if multi:
                return [x.lower() for x in v]
            return None if v is None else [str(v).lower()]

        if op in ("contains", "notContains", "startsWith", "endsWith"):
            check = {"contains": lambda x: low in x, "notContains": lambda x: low in x,
                     "startsWith": lambda x: x.startswith(low), "endsWith": lambda x: x.endswith(low)}[op]
            if op == "notContains":
                # tag/role: NOT EXISTS;  column: NOT LIKE (NULL -> no match)
                return lambda v: (strings(v) is not None) and not any(check(x) for x in strings(v))
            return lambda v: strings(v) is not None and any(check(x) for x in strings(v))
        if op in ("is", "isNot"):
            def eq(v):
                if multi:
                    return any(x == value for x in v)
                if isinstance(value, bool):
                    return bool(v) == value
                return v == value
            if op == "isNot":
                return lambda v: (multi or v is not None) and not eq(v)
            return eq
        if op == "gt" and field == "duration":
            # Navidrome stores seconds with decimals, the API returns them truncated
            return lambda v: v is not None and v + 0.999 > value
        if op == "gt":
            return lambda v: v is not None and v > value
        if op == "lt":
            return lambda v: v is not None and v < value
        if op == "inTheRange":
            lo, hi = value
            return lambda v: v is not None and lo <= v <= hi
        if op in ("inTheLast", "notInTheLast"):
            since = (dt.datetime.now() - dt.timedelta(days=int(value))).strftime("%Y-%m-%d")
            if op == "inTheLast":   # like Navidrome: timestamp > 'YYYY-MM-DD' – the boundary day is included
                return lambda v: bool(v) and v[:10] >= since
            return lambda v: not v or v[:10] < since
        raise ValueError(_("Operator '{op}' is not supported in the preview", op=op))

    def match(self, nsp):
        key = "all" if "all" in nsp else "any"
        return self.ids({key: nsp.get(key, [])})

    def _main_artist(self, s):
        """Artist a song is shown under (for compilations the performer)."""
        aa = s.get("albumArtists") or []
        if aa and aa[0].get("name") != "Various Artists":
            return aa[0]["name"]
        return s.get("artist") or s.get("displayArtist")

    def top_artists(self, ids, n=6):
        return Counter(self._main_artist(self.songs[i]) for i in ids).most_common(n)

    def artist_ids(self, all=False):
        """Artist name -> Navidrome ID. Default: only artists with a real picture (for /img/ar-<id>);
        all=True: all of them (e.g. for biographies)."""
        if getattr(self, "_artist_ids_all", None) is None:
            ids = {}
            for s in self.songs:
                for a in (s.get("albumArtists") or []) + (s.get("artists") or []):
                    if a.get("name") and a.get("id"):
                        ids.setdefault(a["name"], a["id"])
            meta = getattr(self, "artist_meta", None) or {}
            self._artist_ids_all = ids
            self._artist_ids = {n: i for n, i in ids.items() if meta.get(i, not meta)}
        return self._artist_ids_all if all else self._artist_ids

    def artist_rows(self, ids, n=8):
        """[[name, songs, artistId], …] for lists with pictures."""
        aid = self.artist_ids()
        return [[a, c, aid.get(a)] for a, c in self.top_artists(ids, n)]

    def albums(self):
        if getattr(self, "_albums", None) is None:
            albums = {}
            for s in self.songs:
                a = albums.get(s.get("albumId"))
                if a is None:
                    a = albums[s.get("albumId")] = {
                        "id": s.get("albumId"), "name": s.get("album"), "artist": s.get("displayAlbumArtist"),
                        "year": s.get("year"), "cover": f"al-{s.get('albumId')}", "created": s.get("created") or "",
                        "songs": 0, "artistId": ((s.get("albumArtists") or [{}])[0]).get("id"),
                        "hasArt": self.has_art(s.get("albumId")), "color": self.color(s.get("albumId"))}
                a["songs"] += 1
                c = s.get("created") or ""
                if c and (not a["created"] or c < a["created"]):   # the earliest known day
                    a["created"] = c
            self._albums = albums
        return self._albums

    def real_path(self, idx):
        """Real file path of a song (for .m3u). Loaded once when first needed
        (if loading fails, it is tried again next time)."""
        self._load_paths()
        return self._real_paths.get(self.songs[idx]["id"])

    def _load_paths(self):
        if getattr(self, "_real_paths", None) is None:
            loader = getattr(self, "path_loader", None)
            data = loader() if loader else {}
            self._real_paths, self._embedded = data if isinstance(data, tuple) else (data, set())

    def embedded_lyrics(self):
        """Songs with lyrics embedded in the file (Navidrome already shows them): song ID -> text
        (or only the IDs if the loader returns no texts)."""
        self._load_paths()
        return self._embedded

    def index_of(self):
        """Song ID -> index in self.songs."""
        if getattr(self, "_index_of", None) is None:
            self._index_of = {s["id"]: i for i, s in enumerate(self.songs)}
        return self._index_of

    def has_art(self, album_id):
        return getattr(self, "album_meta", {}).get(album_id, (True, None))[0]

    def color(self, album_id):
        return getattr(self, "album_meta", {}).get(album_id, (True, None))[1]

    def covers(self, ids, n=4):
        """Covers of the albums most songs come from (for mosaics) – only real covers."""
        c = Counter(self.songs[i].get("albumId") for i in ids)
        return [f"al-{a}" for a, _ in c.most_common() if a and self.has_art(a)][:n]

    def main_color(self, ids):
        c = Counter(self.songs[i].get("albumId") for i in ids)
        return next((self.color(a) for a, _ in c.most_common(12) if self.has_art(a) and self.color(a)), None)

    def new_albums(self, n=16):
        return sorted(self.albums().values(), key=lambda a: a["created"], reverse=True)[:n]

    def describe(self, idx):
        s = self.songs[idx]
        return {
            "id": s.get("id"), "title": s.get("title"), "artist": s.get("displayArtist") or s.get("artist"),
            "artistId": ((s.get("artists") or [{}])[0]).get("id"),
            "album": s.get("album"), "year": s.get("year"),
            "cover": f"al-{s.get('albumId')}" if self.has_art(s.get("albumId")) else None,
            "duration": s.get("duration"),
            "genres": [g["name"] for g in s.get("genres") or []],
            "rating": s.get("userRating") or (None if self.ratings_exact else s.get("averageRating")),
        }


def preview(cfg, lib, playlist, sample=15, today=None):
    ctx = BuildContext(lib, today)
    nsp = build_nsp(cfg, playlist, ctx)
    ids = lib.match(nsp)
    if is_mix(playlist):   # mix: show exactly today's selection
        from .mixer import pick
        order, pool = pick(cfg, lib, playlist, nsp, today)
        chosen = frozenset(order)
        return {"name": nsp["name"], "count": len(order), "pool": pool, "limit": len(order), "nsp": nsp, "mix": True,
                "topArtists": lib.artist_rows(chosen, 12), "artistCount": len({lib._main_artist(lib.songs[i]) for i in chosen}),
                "covers": lib.covers(chosen), "color": lib.main_color(chosen),
                "sample": _with_sound(lib, order if sample >= 25 else order[:sample]), "summary": summary(cfg, playlist, ctx)}
    ids = apply_sound(cfg, lib, playlist, ids)
    picks = random.sample(sorted(ids), min(sample, len(ids)))
    return {"name": nsp["name"], "count": len(ids), "limit": nsp.get("limit"), "nsp": nsp,
            "topArtists": lib.artist_rows(ids, 12), "artistCount": len({lib._main_artist(lib.songs[i]) for i in ids}),
            "covers": lib.covers(ids), "color": lib.main_color(ids), "sample": _with_sound(lib, picks),
            "summary": summary(cfg, playlist, ctx)}


def _with_sound(lib, idx):
    """Song info + sound (tempo, moods), as far as already analyzed."""
    from .audio import moods
    from .classify import song_features
    feats = song_features(lib)
    out = []
    for i in idx:
        d = lib.describe(i)
        f = feats.get(i)
        if f:
            d.update(bpm=round(f["bpm"]) if f.get("bpm") else None, energy=f.get("energy"), moods=moods(f))
        out.append(d)
    return out


def _min_rating(S, playlist, welten, stil):
    """Minimum rating: the playlist's own, otherwise inherited (world or "all" setting, filter of the vibe)."""
    min_rating = playlist.get("minRating")
    if min_rating is None:
        base = min(w.get("minRating", 0) or 0 for w in welten) if welten else S.get("allMinRating", 0)
        min_rating = max(base or 0, ((stil or {}).get("filters") or {}).get("minRating") or 0)
    return int(min_rating or 0)


def summary(cfg, playlist, ctx=None):
    """The rules of a playlist in everyday language (for the detail view)."""
    if playlist.get("rules") is not None:
        return [_("Custom rules, taken over unchanged from the handmade .nsp file.")]
    S = cfg["settings"]
    lines = []
    welten = [_find(cfg["welten"], w) for w in welt_ids(playlist)]
    stil = None if playlist.get("stil", ALL) == ALL else _find(cfg["stile"], playlist["stil"])
    if playlist.get("review"):
        from .mixer import mix_day, options
        start, end, _title = review_period(playlist["review"].get("period", "month"), mix_day())
        # the dates are formatted by the text itself: {start:%d.%m.} in German, {start:%b %-d} in English
        return [_("Recap: the {n} most played songs from {start:%b %-d} to {end:%b %-d, %Y}, most played first",
                  n=options(playlist)["size"], start=start, end=end),
                _("Changes by itself on the first of the month – it always stays one playlist")]
    if playlist.get("radio"):
        lines.append(_("Radio: {seeds} – plus up to {n} similar bands from your library (according to Last.fm, otherwise "
                       "by genres)", seeds=" & ".join(playlist["radio"].get("seed", [])), n=playlist["radio"].get("bands") or 25))
    if playlist.get("fav"):
        arts = favorite_artists(cfg, person_of(cfg, playlist), ctx)
        days = int(playlist["fav"].get("days") or 60)
        if arts:
            lines.append(_("New from the favorite bands in the last {days} days: {bands}", days=days,
                           bands=", ".join(arts[:5]) + (" …" if len(arts) > 5 else "")))
        else:
            lines.append(_("New from the favorite bands in the last {days} days – no favorite bands known yet", days=days))
    together = [x["name"] for x in together_of(cfg, playlist)]
    if together:
        lines.append(_("Prefers what {names} like to hear – everyone’s dislikes count", names=join_and(together)))
    snd = sound_of(cfg, playlist)
    if snd:
        from .audio import MOODS
        from .ml import INSTRUMENTS, THEMES
        parts = [_(MOODS.get(m, m)) for m in snd.get("moods", [])]   # i18n-ignore: N_ constants
        parts += [_(INSTRUMENTS[x]) for x in snd.get("instruments", []) if x in INSTRUMENTS]   # i18n-ignore: N_ constants
        parts += [_(THEMES[x]) for x in snd.get("themes", []) if x in THEMES]   # i18n-ignore: N_ constants
        for key, text, scale in (("approachable", N_("Easy to listen to {lo}–{hi} %"), 100),
                                 ("engaging", N_("For close listening {lo}–{hi} %"), 100),
                                 ("energy", N_("Energy {lo}–{hi} %"), 100), ("bpm", N_("Tempo {lo}–{hi} BPM"), 1),
                                 ("dance", N_("Danceability {lo}–{hi} %"), 100),
                                 ("arousal", N_("Liveliness {lo}–{hi} %"), 100)):
            if snd.get(key):
                lo, hi = snd[key]
                parts.append(_(text, lo=f"{lo * scale:.0f}", hi=f"{hi * scale:.0f}"))   # i18n-ignore: N_ constants
        lines.append(_("Sound: {parts} (from the sound analysis)", parts=", ".join(parts)))
    if playlist.get("fav"):
        pass
    elif welten:
        n = sum(len(welt_artists(w, ctx)) for w in welten)
        lines.append(_n(n, "Bands from {worlds} ({n} band)", "Bands from {worlds} ({n} bands)",
                        worlds=" + ".join(w["name"] for w in welten)))
    else:
        sep = [w["name"] for w in cfg["welten"] if w.get("separate")]
        lines.append(_("The whole library – without {worlds}", worlds=", ".join(sep)) if sep else _("The whole library"))
    if stil:
        if stil.get("kind") == "season":
            act = ", ".join(s["name"] for s in active_season_stile(cfg, ctx.today if ctx else None))
            lines.append(_("Matching the season right now: {styles}", styles=act) if act
                         else _("Matching the season right now: no season active"))
        else:
            what = []
            if stil.get("genres"):
                what.append(_("genres like {genres}", genres=", ".join(stil["genres"][:4]) + (" …" if len(stil["genres"]) > 4 else "")))
            if stil.get("albums") or stil.get("titles"):
                what.append(_("keywords like {words}", words=", ".join(
                    _("“{word}”", word=k) for k in (stil.get("albums", []) + stil.get("titles", []))[:3])))
            if stil.get("artists"):
                what.append(", ".join(stil["artists"][:3]))
            f = stil.get("filters") or {}
            if f.get("years"):
                what.append(_("from {start}–{end}", start=f["years"][0], end=f["years"][1]))
            if f.get("addedDays"):
                what.append(_("added in the last {days} days", days=f["addedDays"]))
            if f.get("loved"):
                what.append(_("marked as favorite"))
            lines.append(f"{stil['name']}: " + "; ".join(what) if what else stil["name"])
    if playlist.get("hits"):
        lines.append(_("Only the hits – the most popular songs by Deezer stars"))
    elif _min_rating(S, playlist, welten, stil):
        lines.append(_("From {stars} (or marked as favorite)", stars="★" * _min_rating(S, playlist, welten, stil)))
    if playlist.get("addArtists"):
        lines.append(_("Also included: {artists}", artists=", ".join(playlist["addArtists"])))
    person = person_of(cfg, playlist)
    nogo = list((person or {}).get("dislikes", {}).get("artists", [])) + list(playlist.get("excludeArtists", []))
    if nogo:
        lines.append(_("Never included: {artists}", artists=", ".join(nogo)))
    shown = shown_vibes(cfg, playlist, stil, active_season_stile(cfg, ctx.today if ctx else None)
                        if stil and stil.get("kind") == "season" else [])
    hidden = [s["name"] for s in cfg["stile"] if s["id"] not in shown
              and any((s.get("excludeElsewhere") or {}).get(k) for k in ("albums", "titles", "genres"))]
    if hidden:
        lines.append(_("Hidden: {styles}", styles=", ".join(hidden)))
    without = _title_filters_text(list(S.get("excludeTitles", [])) + [t for w in welten for t in w.get("excludeTitles", [])])
    if without:
        lines.append(without)
    sort = {"neu": _("newest first"), "beliebt": _("most popular first"),   # i18n-ignore: stored values
            "vergessen": _("longest unplayed first")}   # i18n-ignore: stored value
    if is_mix(playlist):
        from .mixer import EVERY, FLAVORS, options
        o = options(playlist)
        name, how = EVERY.get(o.get("every"), EVERY["day"])
        caps = ", ".join(x for x in (_("at most {n} per band", n=o["perArtist"]) if o.get("perArtist") else "",
                                     _("{n} per album", n=o["perAlbum"]) if o.get("perAlbum") else "") if x) or _("no band limit")
        amount = _("about {n} minutes", n=o["minutes"]) if o.get("minutes") else _n(o["size"], "{n} song", "{n} songs")
        flavor = _(FLAVORS.get(o["flavor"], o["flavor"]))   # i18n-ignore: N_ constants
        if o.get("avoidRecent"):
            lines.append(_("{mix}: {amount}, {caps}, {flavor}, recently played songs (last {days} days) only rarely",
                           mix=name, amount=amount, caps=caps, flavor=flavor, days=o["avoidRecent"]))
        else:
            lines.append(_("{mix}: {amount}, {caps}, {flavor}", mix=name, amount=amount, caps=caps, flavor=flavor))
        # {every} mid-sentence, {Every} at the start of a sentence (German)
        every = _(how)   # i18n-ignore: N_ constant
        if o.get("perArtist"):
            lines.append(_("Rebuilt {every}, the list stays the same in between (ideal for offline in Symfonium) – never "
                           "the same band twice in a row", every=every, Every=every.capitalize()))
        else:
            lines.append(_("Rebuilt {every}, the list stays the same in between (ideal for offline in Symfonium)",
                           every=every, Every=every.capitalize()))
        if S.get("mixLearn", True):
            lines.append(_("Learns as you listen: skipped songs come up less often, songs rated 1 star by hand not at all"))
    else:
        lines.append(_("Up to {n} songs, {order}", n=playlist.get("limit") or S.get("limit", 100),
                       order=sort[playlist["sort"]] if playlist.get("sort") in sort else _("reshuffled on every load")))
    person = person_of(cfg, playlist) or {}
    if person.get("clean") or any(x.get("clean") for x in cfg.get("personen", []) if x["id"] in (playlist.get("together") or [])):
        lines.append(_("Kid-safe mode: songs with explicit lyrics stay out"))
    return lines


# Excluded versions in summaries: whole phrases, the German compounds ("Unplugged- und Karaoke-Versionen") differ
VERSION_TEXTS = {
    ("Unplugged",): N_("unplugged versions"),
    ("Instrumental",): N_("instrumental versions"),
    ("Karaoke",): N_("karaoke versions"),
    ("Unplugged", "Instrumental"): N_("unplugged and instrumental versions"),
    ("Unplugged", "Karaoke"): N_("unplugged and karaoke versions"),
    ("Instrumental", "Karaoke"): N_("instrumental and karaoke versions"),
    ("Unplugged", "Instrumental", "Karaoke"): N_("unplugged, instrumental and karaoke versions"),
}


def _title_filters_text(titles):
    """Excluded title keywords in everyday language: "(Live", "Karaoke" … ->
    "Without live recordings, unplugged, instrumental and karaoke versions"."""
    low = [t.lower() for t in titles]

    def hit(key, t):   # "live" as a word of its own – "Olive" is not a live recording
        return re.search(rf"(?<![a-zäöüß]){key}(?![a-zäöüß])", t) is not None   # i18n-ignore: matches titles

    has = lambda *keys: any(hit(k, t) for t in low for k in keys)   # noqa: E731
    known = ("live", "unplugged", "instrumental", "karaoke", "playback")
    other = [t for t in titles if not any(hit(k, t.lower()) for k in known)]
    words = []
    if other:
        words.append(_("titles with {words}", words=", ".join(_("“{word}”", word=t) for t in other[:3])
                       + (" …" if len(other) > 3 else "")))
    if has("live"):
        words.append(_("live recordings"))
    versions = tuple(v for v, keys in (("Unplugged", ("unplugged",)), ("Instrumental", ("instrumental",)),
                                       ("Karaoke", ("karaoke", "playback"))) if has(*keys))
    if versions:   # "unplugged, instrumental and karaoke versions" – one phrase, it already has its own "and"
        last = _(VERSION_TEXTS[versions])   # i18n-ignore: N_ constants
        if not words:
            return _("Without {items}", items=last)
        if len(versions) > 1:
            return _("Without {items}, {last}", items=", ".join(words), last=last)
        return _("Without {items} and {last}", items=", ".join(words), last=last)
    if not words:
        return ""
    if len(words) > 1:
        return _("Without {items} and {last}", items=", ".join(words[:-1]), last=words[-1])
    return _("Without {items}", items=words[0])


def shown_vibes(cfg, playlist, stil=None, seasonal=()):
    """Vibes whose content (excludeElsewhere: Christmas, lantern songs …) the playlist may contain: its own vibe, the
    active seasons of "Right for the season" (seasonal) and the vibes linked to a theme its sound filter asks for
    (ml.THEME_VIBES: the AI theme “Christmas” may find the Christmas songs)."""
    from .ml import THEME_VIBES
    own = {stil["id"]} if stil else set()
    own |= {s["id"] for s in seasonal}
    own |= {THEME_VIBES[x] for x in (sound_of(cfg, playlist) or {}).get("themes", []) if x in THEME_VIBES}
    return own


def sound_of(cfg, playlist):
    """Sound filter of a playlist (its own or that of its vibe) – or None."""
    stil = next((s for s in cfg["stile"] if s["id"] == playlist.get("stil")), None)
    return playlist.get("sound") or (stil or {}).get("sound") or None


def apply_sound(cfg, lib, playlist, ids):
    """Only songs whose sound matches the filter (sound analysis + Last.fm mood)."""
    snd = sound_of(cfg, playlist)
    if not snd:
        return ids
    if not ids:
        return frozenset()
    fits = _sound_matches(lib, snd)
    return frozenset(i for i in ids if i in fits)


_sound_memo = OrderedDict()   # (song list, measurements, filter) -> songs that fit
_sound_lock = threading.Lock()


def _sound_matches(lib, snd):
    """All songs of the list that fit a sound filter – once per filter and state of the measurements (the suggestions
    ask for the same filters hundreds of times)."""
    from . import audio, lastfm, ml
    from .classify import song_features
    feats = song_features(lib)
    stamps = (audio._cache["stamp"], ml.stamp(), lastfm._mem["stamp"])
    key = (ml.songs_key(lib), stamps, json.dumps(snd, sort_keys=True, ensure_ascii=False))
    with _sound_lock:
        hit = _sound_memo.get(key)
        if hit is not None:
            _sound_memo.move_to_end(key)
            return hit
    fits = frozenset(i for i, f in feats.items() if audio.matches(f, snd))
    with _sound_lock:
        for k in [k for k in _sound_memo if k[1] != stamps or ml.gone(k[0])]:   # older measurements, lists gone
            del _sound_memo[k]
        _sound_memo[key] = fits
        while len(_sound_memo) > 64:
            _sound_memo.popitem(last=False)
    return fits


def count(cfg, lib, playlist, ctx):
    return len(apply_sound(cfg, lib, playlist, lib.match(build_nsp(cfg, playlist, ctx))))


def matrix(cfg, lib, today=None):
    ctx = BuildContext(lib, today)
    welten = [ALL] + [w["id"] for w in cfg["welten"]]
    stile = [ALL] + [s["id"] for s in cfg["stile"]]
    counts = {}
    for w in welten:
        for s in stile:
            if w == ALL and s == ALL:
                continue
            counts[f"{w}|{s}"] = count(cfg, lib, {"welt": w, "stil": s, "person": None}, ctx)
    return {"counts": counts, "activeSeason": [s["id"] for s in active_season_stile(cfg, today)]}


# --------------------------------------------------------------------------- library info

def artist_stats(songs):
    """Per album artist: song count, genre distribution, songs without a genre, first added."""
    count, genres, untagged, first = Counter(), defaultdict(Counter), Counter(), {}
    for s in songs:
        artist = s.get("displayAlbumArtist") or s.get("artist")
        if not artist or artist == "Various Artists":
            continue
        count[artist] += 1
        names = [g["name"] for g in s.get("genres") or []]
        genres[artist].update(names)
        if not names:
            untagged[artist] += 1
        created = (s.get("created") or "")[:10]
        if created and (artist not in first or created < first[artist]):
            first[artist] = created
    return count, genres, untagged, first


def similar_artists(cfg, songs, ctx, limit=10, threshold=0.35):
    """Artists that are not in any world yet but fit a world by their genres.

    TF-IDF cosine: rare genres (Medieval, Children's Music) count a lot, everyday genres (Pop, Rock) little –
    otherwise every pop band would end up with the kids' songs.
    """
    count, genres, untagged, _ = artist_stats(songs)
    assigned = {a for w in cfg["welten"] for a in welt_artists(w, ctx)}
    excluded = {a for w in cfg["welten"] for a in w.get("excludedArtists", [])}
    doc_freq = Counter(g for a in genres for g in genres[a])
    idf = {g: math.log(len(genres) / d) for g, d in doc_freq.items()}

    def vector(shares):
        v = {g: share * idf.get(g, 0) for g, share in shares.items()}
        norm = math.sqrt(sum(x * x for x in v.values())) or 1.0
        return {g: x / norm for g, x in v.items()}

    result = {}
    for w in cfg["welten"]:
        members = [a for a in welt_artists(w, ctx) if genres.get(a)]
        shares = Counter()
        for a in members:
            shares.update({g: c / count[a] for g, c in genres[a].items()})
        wv = vector(shares)
        keys = [g.lower() for g in w.get("genres", [])]
        scored = []
        for artist, n in count.items():
            if artist in assigned or artist in excluded or n < 5 or not genres[artist]:
                continue
            av = vector({g: c / n for g, c in genres[artist].items()})
            score = sum(wv.get(g, 0) * x for g, x in av.items())
            if keys and any(k in g.lower() for g in av for k in keys):
                score = max(score, 0.9)
            if score >= threshold:
                scored.append({"artist": artist, "score": round(score, 2), "songs": n,
                               "genres": [g for g, _ in genres[artist].most_common(3)]})
        scored.sort(key=lambda x: -x["score"])
        result[w["id"]] = scored[:limit]
    return result


def untagged_artists(cfg, songs):
    count, _, untagged, _ = artist_stats(songs)
    in_stil = defaultdict(list)
    for s in cfg["stile"]:
        for a in s.get("artists", []):
            in_stil[a].append(s["id"])
    return [{"artist": a, "songs": n, "stile": in_stil.get(a, [])}
            for a, n in count.most_common() if n >= 5 and untagged[a] / n >= 0.8]


def library_index(songs):
    artists = Counter()
    for s in songs:
        for a in s.get("artists") or []:
            artists[a["name"]] += 1
        for a in s.get("albumArtists") or []:
            if a["name"] not in artists:
                artists[a["name"]] += 0
    genres = Counter(g["name"] for s in songs for g in s.get("genres") or [])
    albums = Counter(s.get("album") for s in songs if s.get("album"))
    suffix = Counter(s.get("suffix") for s in songs)
    mp3_albums = sorted({f"{s.get('displayAlbumArtist')} – {s.get('album')}" for s in songs if s.get("suffix") == "mp3"})
    return {
        "artists": sorted(artists.items(), key=lambda x: x[0].lower()),
        "genres": genres.most_common(),
        "albums": len(albums),
        "songs": len(songs),
        "suffix": dict(suffix),
        "mp3Albums": mp3_albums,
        "loved": sum(1 for s in songs if s.get("starred")),
        "played": sum(1 for s in songs if s.get("playCount")),
    }
