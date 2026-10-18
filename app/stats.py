"""Listening statistics per person – from Navidrome's play counters (Symfonium reports every play).

Navidrome only stores "how often" and "last" per song, no complete history. That is enough to show a lot (top bands,
top songs, music worlds, forgotten favorites), but no time series.
"""
import datetime as dt
import threading
import time
from collections import Counter, defaultdict

from . import rules
from .config import load_env, user_password
from .i18n import _
from .navidrome import Navidrome, NavidromeError
from .rules import ALL, BuildContext, Library

_cache = {}
_lock = threading.Lock()
_user_locks = {}   # per account: two simultaneous requests load the song list only once
MAX_AGE = 10 * 60
USER_FIELDS = ("userRating", "starred", "playCount", "played")   # what differs per account


def purge():
    """Release the song lists of other accounts when they have not been needed for a while."""
    with _lock:
        old = [k for k, (t, _) in _cache.items() if time.time() - t > MAX_AGE]
        for k in old:
            del _cache[k]
    if old:
        from .library import release_memory
        release_memory()


def overlay(base_lib, songs):
    """Song list of another account based on the default list: songs with the same stars, favorites and plays are the
    same entries, the others copies with this account's values (they keep sharing titles, bands, genres). Instead of
    a second full list an account only costs what differs for it."""
    index = base_lib.index_of()
    base = base_lib.songs
    out = []
    for s in songs:
        i = index.get(s["id"])
        if i is None:   # new since the default list was last loaded
            out.append(s)
            continue
        b = base[i]
        if all(s.get(k) == b.get(k) for k in USER_FIELDS):
            out.append(b)
            continue
        d = {k: v for k, v in b.items() if k not in USER_FIELDS}
        for k in USER_FIELDS:
            if k in s:
                d[k] = s[k]
        out.append(d)
    return out


def songs_for(user, base_lib):
    """Song list from a user's point of view (their plays, stars, favorites)."""
    if base_lib.user and base_lib.user.lower() == (user or "").lower():
        return base_lib
    env = load_env()
    pw = user_password(env, user)
    if not pw:
        raise ValueError(_("No password is stored for “{user}” – personal statistics need one.", user=user))
    with _lock:
        hit = _cache.get(user.lower())
        if hit and time.time() - hit[0] < MAX_AGE:
            return hit[1]
        mine = _user_locks.setdefault(user.lower(), threading.Lock())
    with mine:
        with _lock:   # loaded by another request in the meantime?
            hit = _cache.get(user.lower())
            if hit and time.time() - hit[0] < MAX_AGE:
                return hit[1]
        try:
            songs = overlay(base_lib, Navidrome(env["NAV_URL"], user, pw).iter_songs())
        except NavidromeError as e:
            raise ValueError(str(e))
        lib = Library(songs, ratings_exact=True, user=user)
        for attr in ("album_meta", "artist_meta"):
            setattr(lib, attr, getattr(base_lib, attr, {}))
        base = base_lib.songs
        if len(songs) == len(base) and all(a["id"] == b["id"] for a, b in zip(songs, base)):
            # same songs in the same order: bands, genres, titles … are those of the default list (overlay) – its
            # evaluated rules (music worlds), sound features and index count for this account as well
            lib.share_with(base_lib)
        with _lock:
            _cache[user.lower()] = (time.time(), lib)
        return lib


def _since(iso):
    if not iso:
        return None
    try:
        return (dt.datetime.now(dt.timezone.utc) - dt.datetime.fromisoformat(iso.replace("Z", "+00:00"))).days
    except ValueError:
        return None


def compute(cfg, lib):
    songs = lib.songs
    played = [i for i, s in enumerate(songs) if s.get("playCount")]
    plays = {i: songs[i]["playCount"] for i in played}
    total = sum(plays.values())
    seconds = sum((songs[i].get("duration") or 0) * n for i, n in plays.items())
    aid = lib.artist_ids()

    by_artist, songs_by_artist = Counter(), defaultdict(int)
    for i, n in plays.items():
        a = lib._main_artist(songs[i])
        by_artist[a] += n
        songs_by_artist[a] += 1
    by_album = Counter()
    for i, n in plays.items():
        by_album[songs[i].get("albumId")] += n
    albums = lib.albums()

    top_songs = sorted(played, key=lambda i: -plays[i])[:15]
    recent = sorted((i for i, s in enumerate(songs) if s.get("played")), key=lambda i: songs[i]["played"], reverse=True)[:20]

    # music worlds: share of the plays
    ctx = BuildContext(lib)
    welten = []
    for w in cfg["welten"]:
        ids = lib.match(rules.build_nsp(cfg, {"welt": w["id"], "stil": ALL, "person": None, "minRating": 0,
                                              "minDuration": 0}, ctx))
        p = sum(plays.get(i, 0) for i in ids)
        never = sum(1 for i in ids if not songs[i].get("playCount"))
        welten.append({"id": w["id"], "name": w["name"], "icon": w.get("icon"), "plays": p, "songs": len(ids),
                       "neverPlayed": never})
    welten.sort(key=lambda x: -x["plays"])

    decades = Counter()
    for i, n in plays.items():
        y = songs[i].get("year") or 0
        if y >= 1950:
            decades[_("{decade}s", decade=y // 10 * 10)] += n
    genres = Counter()
    for i, n in plays.items():
        for g in songs[i].get("genres") or []:
            genres[g["name"]] += n

    # forgotten favorites: favorites or well-liked hits that have not played for 90 days
    def long_ago(s):
        d = _since(s.get("played"))
        return d is None or d > 90   # never played or not for more than 90 days

    forgotten = [i for i, s in enumerate(songs)
                 if (s.get("starred") or ((s.get("userRating") or 0) >= 4 and s.get("playCount"))) and long_ago(s)]
    forgotten.sort(key=lambda i: (not songs[i].get("starred"), -(songs[i].get("userRating") or 0)))

    def song_row(i):
        d = lib.describe(i)
        d.update(plays=plays.get(i, 0), played=songs[i].get("played"), artistImg=aid.get(lib._main_artist(songs[i])))
        return d

    return {
        "user": lib.user,
        "totals": {"plays": total, "hours": round(seconds / 3600, 1), "songsPlayed": len(played), "songs": len(songs),
                   "loved": sum(1 for s in songs if s.get("starred")),
                   "rated": sum(1 for s in songs if s.get("userRating")),
                   "artists": len(by_artist)},
        "topArtists": [{"name": a, "plays": n, "songs": songs_by_artist[a], "id": aid.get(a)} for a, n in by_artist.most_common(15)],
        "topSongs": [song_row(i) for i in top_songs],
        "topAlbums": [{**albums[a], "plays": n} for a, n in by_album.most_common(12) if a in albums],
        "recent": [song_row(i) for i in recent],
        "welten": welten,
        "decades": sorted(decades.items()),
        "genres": genres.most_common(10),
        "forgotten": {"count": len(forgotten), "sample": [song_row(i) for i in forgotten[:12]]},
        "neverPlayed": sum(1 for s in songs if not s.get("playCount")),
    }
