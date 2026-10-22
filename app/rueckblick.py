"""Recap: Navidrome only stores "how often" and "last" per song. So that there is still "played this week" and a
year in review, Tuttiphon regularly remembers the play counters and saves the increments per day:

  state/plays/<account>/baseline.json   last state of all counters
  state/plays/<account>/<YYYY-MM-DD>.json   increments (song ID -> count), assigned to the listening day
  state/plays/<account>/first.json      when a song was counted for the first time (for "newly discovered")

An increment noticed e.g. at 05:30 mostly belongs to the day before – so the listening day is
"time minus 6 hours".
"""
import datetime as dt
import json
import os
import threading
import time
from collections import Counter, OrderedDict, defaultdict

from . import rules
from .config import STATE_DIR, load_config, read_text, slug, write_atomic
from .i18n import _, _s
from .rules import ALL, BuildContext

PLAYS_DIR = STATE_DIR / "plays"
_lock = threading.Lock()


def _dir(user):
    return PLAYS_DIR / slug(user or "unbekannt")   # i18n-ignore – folder name (data)


def _load(path, default):
    try:
        return json.loads(read_text(path))
    except (OSError, ValueError):
        return default


def _load_to_write(path, default):
    """For a file that is written again right after: a damaged one is set aside (<name>.defekt-<time>.json) instead
    of being overwritten – the counts in it stay; a file that is briefly not readable (NAS) stops the snapshot
    (OSError) instead of starting the recording over."""
    try:
        data = json.loads(read_text(path))
    except FileNotFoundError:
        return default
    except ValueError:
        data = None
    if isinstance(data, type(default)):
        return data
    broken = path.with_name(f"{path.stem}.defekt-{time.strftime('%Y%m%d-%H%M%S')}.json")   # file name: data
    os.replace(path, broken)
    from . import events
    events.say(_s("⚠ Recap: {file} was damaged – set aside as {name}.", file=f"{path.parent.name}/{path.name}",
                  name=broken.name))
    return default


def snapshot(user, songs, now=None):
    """Record the counter state. -> number of new plays (None the very first time)."""
    now = now or dt.datetime.now()
    counts = {s["id"]: int(s.get("playCount") or 0) for s in songs if s.get("playCount")}
    folder = _dir(user)
    with _lock:
        folder.mkdir(parents=True, exist_ok=True)
        base = _load_to_write(folder / "baseline.json", {})
        if not base or not isinstance(base.get("counts", {}), dict):
            write_atomic(folder / "baseline.json", json.dumps({"since": now.isoformat(timespec="seconds"),
                                                               "at": now.isoformat(timespec="seconds"), "counts": counts}))
            return None
        old = base.get("counts", {})
        delta = {sid: c - old.get(sid, 0) for sid, c in counts.items() if c > old.get(sid, 0)}
        if delta:
            # the plays happened somewhere since the last state – they count for the day in the middle of that span
            # (state at 05:30 or 07:00: the day before; a second state in the afternoon: today)
            try:
                last = dt.datetime.fromisoformat(base.get("at") or "")
            except ValueError:
                last = None
            mid = last + (now - last) / 2 if last and last < now else now - dt.timedelta(hours=6)
            day = mid.date().isoformat()
            path = folder / f"{day}.json"
            cur = _load_to_write(path, {})
            for sid, n in delta.items():
                cur[sid] = cur.get(sid, 0) + n
            write_atomic(path, json.dumps(cur))
            first = _load_to_write(folder / "first.json", {})
            new = {sid: day for sid in delta if old.get(sid, 0) == 0 and sid not in first}
            if new:
                first.update(new)
                write_atomic(folder / "first.json", json.dumps(first))
            from . import listenclock
            try:   # listening clock: when these plays happened (the last one of each song) – never at the cost of the recap
                listenclock.record(user, songs, set(delta), now)
            except (OSError, ValueError):
                pass
        base.update(at=now.isoformat(timespec="seconds"), counts=counts)
        write_atomic(folder / "baseline.json", json.dumps(base))
        return sum(delta.values())


def last_snapshot(user):
    base = _load(_dir(user) / "baseline.json", None)
    return base and {"since": base.get("since"), "at": base.get("at")}


_ever = {}   # folder -> (signature of baseline.json and first.json, song ids)


def played_ever(user):
    """Song IDs this account has ever played as far as Tuttiphon counted: the counters of the last state
    (baseline.json) and the first plays (first.json – also those that came live). Kept until the two files change.
    Empty if nothing was ever counted for the account."""
    folder = _dir(user)
    sig = []
    for name in ("baseline.json", "first.json"):
        try:
            st = (folder / name).stat()
            sig.append((st.st_size, st.st_mtime_ns))
        except OSError:
            sig.append(None)
    sig = tuple(sig)
    with _lock:
        hit = _ever.get(str(folder))
    if hit and hit[0] == sig:
        return hit[1]
    base = _load(folder / "baseline.json", {})
    counts = (base.get("counts") if isinstance(base, dict) else None) or {}
    first = _load(folder / "first.json", {}) or {}
    ids = frozenset([sid for sid, n in counts.items() if n] if isinstance(counts, dict) else []) \
        | frozenset(first if isinstance(first, dict) else ())
    with _lock:
        if len(_ever) > 200:
            _ever.clear()
        _ever[str(folder)] = (sig, ids)
    return ids


_between = OrderedDict()   # (folder, state, start, end) -> result; taste, mixes and recap often ask the same


def plays_between(user, start, end):
    """-> ({song ID: plays}, {day: plays}) for start <= day <= end. Cached until the folder changes (every new daily
    state replaces a file and thereby changes the folder)."""
    folder = _dir(user)
    try:
        key = (str(folder), folder.stat().st_mtime_ns, start, end)
    except OSError:
        return Counter(), {}
    with _lock:
        hit = _between.get(key)
        if hit:
            _between.move_to_end(key)
            return Counter(hit[0]), dict(hit[1])
    per_song, per_day = _read_between(folder, start, end)
    with _lock:
        _between[key] = (per_song, per_day)
        while len(_between) > 32:
            _between.popitem(last=False)
    return Counter(per_song), dict(per_day)


def _read_between(folder, start, end):
    per_song, per_day = Counter(), {}
    for path in folder.glob("????-??-??.json"):
        day = path.stem
        if start.isoformat() <= day <= end.isoformat():
            data = _load(path, {})
            per_song.update(data)
            per_day[day] = sum(data.values())
    return per_song, per_day


def period(kind, today=None, year=None):
    today = today or dt.date.today()
    if kind == "woche":
        return today - dt.timedelta(days=6), today, _("The last 7 days")
    if kind == "monat":
        return today - dt.timedelta(days=29), today, _("The last 30 days")
    y = int(year or today.year)
    return dt.date(y, 1, 1), min(dt.date(y, 12, 31), today), _("Your year {year}", year=y)


def summary(cfg, lib, user, kind="woche", year=None):
    start, end, title = period(kind, year=year)
    per_song, per_day = plays_between(user, start, end)
    first = _load(_dir(user) / "first.json", {})
    snap = last_snapshot(user)
    index = lib.index_of()
    songs = lib.songs
    aid = lib.artist_ids()
    plays = {index[sid]: n for sid, n in per_song.items() if sid in index}
    total = sum(plays.values())
    seconds = sum((songs[i].get("duration") or 0) * n for i, n in plays.items())

    by_artist, by_album, artist_songs = Counter(), Counter(), defaultdict(set)
    for i, n in plays.items():
        a = lib._main_artist(songs[i])
        by_artist[a] += n
        artist_songs[a].add(i)
        by_album[songs[i].get("albumId")] += n
    albums = lib.albums()

    # days / months as a time line
    series = []
    if kind == "jahr":
        months = Counter()
        for day, n in per_day.items():
            months[day[:7]] += n
        for m in range(1, 13):   # the interface labels them (month names)
            key = f"{start.year}-{m:02d}"
            series.append({"key": key, "n": months.get(key, 0)})
    else:
        d = start
        while d <= end:
            series.append({"key": d.isoformat(), "n": per_day.get(d.isoformat(), 0)})
            d += dt.timedelta(days=1)
    busiest = max(per_day.items(), key=lambda x: x[1]) if per_day else None

    # newly discovered: counted for the first time in this period
    new_ids = [index[sid] for sid, day in first.items() if start.isoformat() <= day <= end.isoformat() and sid in index]
    new_artists = Counter(lib._main_artist(songs[i]) for i in new_ids)

    # music worlds
    ctx = BuildContext(lib)
    welten = []
    if plays:
        for w in cfg["welten"]:
            ids = lib.match(rules.build_nsp(cfg, {"welt": w["id"], "stil": ALL, "person": None, "minRating": 0, "minDuration": 0}, ctx))
            n = sum(c for i, c in plays.items() if i in ids)
            if n:
                welten.append({"id": w["id"], "name": w["name"], "icon": w.get("icon"), "plays": n})
        welten.sort(key=lambda x: -x["plays"])
    decades = Counter()
    for i, n in plays.items():
        y = songs[i].get("year") or 0
        if y >= 1950:
            decades[_("{decade}s", decade=y // 10 * 10)] += n

    def song_row(i):
        d = lib.describe(i)
        d.update(plays=plays.get(i, 0), artistImg=aid.get(lib._main_artist(songs[i])))
        return d

    return {
        "kind": kind, "title": title, "from": start.isoformat(), "to": end.isoformat(), "user": user,
        "since": (snap or {}).get("since"), "lastSnapshot": (snap or {}).get("at"),
        "totals": {"plays": total, "hours": round(seconds / 3600, 1), "songs": len(plays), "artists": len(by_artist),
                   "days": sum(1 for n in per_day.values() if n), "newSongs": len(new_ids), "newArtists": len(new_artists)},
        "topArtists": [{"name": a, "plays": n, "songs": len(artist_songs[a]), "id": aid.get(a)} for a, n in by_artist.most_common(10)],
        "topSongs": [song_row(i) for i, _ in sorted(plays.items(), key=lambda x: -x[1])[:10]],
        "topAlbums": [{**albums[a], "plays": n} for a, n in by_album.most_common(8) if a in albums],
        "series": series, "busiest": {"day": busiest[0], "plays": busiest[1]} if busiest else None,
        "discoveries": [{"name": a, "songs": n, "id": aid.get(a)} for a, n in new_artists.most_common(8)],
        "welten": welten[:6], "decades": sorted(decades.items()),
    }


def snapshot_all(cfg=None, base_lib=None, log=lambda *_: None):
    """Record the counter state for every Navidrome account with a password (and the default account)."""
    from .library import CACHE
    from .stats import songs_for
    cfg = cfg or load_config()
    base = base_lib or CACHE.get()
    users = []
    for p in cfg["personen"]:
        u = (p.get("user") or "").strip()
        if u and u.lower() not in [x.lower() for x in users]:
            users.append(u)
    done = {}
    for u in users:
        try:
            lib = songs_for(u, base)
            done[u] = snapshot(u, lib.songs)
        except Exception as e:   # no password, or a file briefly not readable -> leave out this account this time
            log(_s("Recap: {user} skipped ({error})", user=u, error=e))
            continue
    return done
