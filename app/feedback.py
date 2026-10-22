"""Mixes learn from listening – locally, per Navidrome account.

* Skipped: Tuttiphon remembers what a mix contained in each period (state/mix_history.json). Once a period is over, it
  compares with the account's daily play increments (recap, state/plays/). If at least MIN_HEARD songs of the mix were
  played – and in order (up to the last one played at least SEQUENTIAL of the positions; shuffle or single songs from
  albums say nothing) –, the songs that stood before the last one played but did not play count as skipped. Such
  songs come less often: the weight drops per skip (SKIP_FACTOR, at most one mark per song and week) and recovers over
  time (half-life HALF_LIFE days). Plays from a mix partly make up for skips.
* 1 star given by hand (e.g. in Symfonium): the song no longer goes into this person's mixes. "By hand" means: the
  account's star differs from the one the Deezer rating last set (state/deezer.json).

Result per account: state/feedback/<account>.json = {song ID: {"s": [days on which it was skipped], "p": plays from mixes}}
* Live plays (the Navidrome plugin, listen.py): a song left within the first seconds counts as skipped there and then,
  every play partly makes up for skips – for every song, not only in mixes. For a mix period with live plays of the
  account the guess from the mix history above is left out, so nothing counts twice. A family mix heard on a person's
  own account (recognized by its order, listen._runs()) teaches the family, not the person.
With the setting settings.mixLearn = false none of this has an effect (the history is still kept).
"""
import calendar
import datetime as dt
import json
import os
import threading
import time

from .config import STATE_DIR, read_text, slug, write_atomic
from .i18n import _s, _sn

HISTORY = STATE_DIR / "mix_history.json"
FEEDBACK_DIR = STATE_DIR / "feedback"
DEEZER_STATE = STATE_DIR / "deezer.json"
MIN_HEARD = 3          # this many songs of the mix must have been played, otherwise the period says nothing
SKIP_FACTOR = 0.55     # weight per (fresh) skip
MAX_SKIPS = 4          # no stronger downgrade than this (0.55⁴ ≈ 0.09 – only 1 star should make a song disappear)
HALF_LIFE = 60         # days after which a skip only counts half
SEQUENTIAL = 0.5       # share of the positions up to the last one played that must have played (otherwise: shuffled)
KEEP_PERIODS = 12      # remember this many past periods per mix (the family's: listen.KEEP_DAYS days – record())
_lock = threading.Lock()
_cache = {}


def _load(path, default):
    try:
        data = json.loads(read_text(path))
        return data if isinstance(data, type(default)) else default
    except (OSError, ValueError):
        return default


def _load_to_write(path, default):
    """For a file that is written again right after (what was learned, the mix history): a damaged one is set aside
    (<name>.defekt-<time>.json) instead of being overwritten; briefly not readable (NAS): OSError, nothing is written."""
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
    events.say(_s("⚠ Mixes learn: {file} was damaged – set aside as {name}.", file=path.name, name=broken.name))
    return default


def _cached(path, default, convert=lambda x: x, extra=None):
    """Read a file; from memory as long as it does not change (deezer.json is a few MB).
    extra: further part of the key (e.g. the day that is computed for)."""
    try:
        st = os.stat(path)
        key = (st.st_mtime_ns, st.st_size, extra)
    except OSError:
        return convert(default)
    hit = _cache.get(str(path))
    if hit and hit[0] == key:
        return hit[1]
    value = convert(_load(path, default))
    _cache[str(path)] = (key, value)
    return value


def _feedback_file(user):
    return FEEDBACK_DIR / f"{slug(user)}.json"


def period_end(every, start):
    if every == "week":
        return start + dt.timedelta(days=6)
    if every == "month":
        return start.replace(day=calendar.monthrange(start.year, start.month)[1])
    return start


# ---------------------------------------------------------------------------- History

def history():
    """The mix history {playlist id: [{"day", "every", "user", "ids", "done"?}, …]} – read only."""
    return _cached(HISTORY, {})


def record(playlist_id, user, every, start, song_ids):
    """Remember the selection of a mix period (when writing the .m3u) – KEEP_PERIODS of them; of the family's mixes all
    of the days the live plays are kept, so that they are recognized there (listen._runs())."""
    if not user or not song_ids:
        return
    from . import listen
    cutoff = (start - dt.timedelta(days=listen.KEEP_DAYS)).isoformat() if listen.is_family(user) else "9999"
    with _lock:
        try:
            data = _load_to_write(HISTORY, {})
        except OSError:
            return
        entries = [e for e in data.get(playlist_id, []) if e.get("day") != start.isoformat()]
        entries.append({"day": start.isoformat(), "every": every, "user": user, "ids": list(song_ids)})
        entries = sorted(entries, key=lambda e: e["day"])
        data[playlist_id] = [e for k, e in enumerate(entries) if k >= len(entries) - KEEP_PERIODS or e["day"] >= cutoff]
        try:
            write_atomic(HISTORY, json.dumps(data))
        except OSError:
            pass


def forget_removed(playlist_ids):
    """Remove the history of deleted playlists."""
    with _lock:
        try:
            data = _load_to_write(HISTORY, {})
        except OSError:
            return
        kept = {k: v for k, v in data.items() if k in playlist_ids}
        if kept != data:
            try:
                write_atomic(HISTORY, json.dumps(kept))
            except OSError:
                pass


# ---------------------------------------------------------------------------- Usage

def usage(playlist_ids=None, today=None):
    """How much of the past editions of each mix was played – from the mix history and the recap counters, read only.
    -> {playlist id: {"every", "periods": finished editions the counters cover, "heard": editions with at least
    MIN_HEARD of their songs played in their period, "songs", "played": songs in them / of those played, "days": days
    covered, "last": first day of the last heard edition (ISO) or None}} – mixes without such an edition are missing.
    Songs played elsewhere in the period (album, artist) count too; for the family's mixes also where they were heard
    on a person's own account (listen.family_summary())."""
    from . import listen, rueckblick
    today = today or dt.date.today()
    data = _cached(HISTORY, {}, extra=today)
    snaps, plays_memo, out = {}, {}, {}
    for pid, entries in data.items():
        if playlist_ids is not None and pid not in playlist_ids:
            continue
        res = {"every": None, "periods": 0, "heard": 0, "songs": 0, "played": 0, "days": 0, "last": None}
        for e in entries[-KEEP_PERIODS:] if isinstance(entries, list) else []:
            try:
                start = dt.date.fromisoformat(e["day"])
            except (KeyError, TypeError, ValueError):
                continue
            every, user = e.get("every", "day"), e.get("user")
            end = period_end(every, start)
            if end >= today or not user:
                continue   # still running
            if user not in snaps:
                snaps[user] = rueckblick.last_snapshot(user)
            snap = snaps[user]
            # counted from the start, and the plays of the last day are known (as in learn())
            if not snap or (snap.get("since") or "") > start.isoformat() or \
                    (snap.get("at") or "") < f"{end + dt.timedelta(days=1)}T04:00":
                continue
            key = (user, start, end)
            if key not in plays_memo:
                plays_memo[key] = rueckblick.plays_between(user, start, end)[0]
                if listen.is_family(user):   # its mixes heard on the people's accounts count too
                    plays_memo[key] = {**listen.family_summary(start, end)[1], **plays_memo[key]}
            ids = e.get("ids") or []
            n = sum(1 for sid in ids if plays_memo[key].get(sid))
            res.update(every=every, periods=res["periods"] + 1, songs=res["songs"] + len(ids),
                       played=res["played"] + n, days=res["days"] + (end - start).days + 1)
            if n >= MIN_HEARD:
                res["heard"] += 1
                res["last"] = max(res["last"] or "", e["day"])
        if res["periods"]:
            out[pid] = res
    return out


# ---------------------------------------------------------------------------- Learning

def learn(today=None, log=lambda *_: None):
    """Evaluate finished mix periods (once per period). -> {"periods": n, "skips": k, "plays": m}"""
    from . import rueckblick
    today = today or dt.date.today()
    out = {"periods": 0, "skips": 0, "plays": 0}
    with _lock:
        try:
            data = _load_to_write(HISTORY, {})
        except OSError:   # briefly not readable: next time
            return out
        changed = False
        per_user = {}
        for entries in data.values():
            for e in entries:
                if e.get("done"):
                    continue
                start = dt.date.fromisoformat(e["day"])
                end = period_end(e.get("every", "day"), start)
                if end >= today:
                    continue   # period still running
                from . import listen
                if listen.has_live(e["user"], start, end):   # live plays know the skips exactly (factors())
                    e["done"] = True
                    changed = True
                    out["periods"] += 1
                    continue
                snap = rueckblick.last_snapshot(e["user"])
                if not snap or (snap.get("since") or "") > start.isoformat():
                    if (today - end).days > 14:   # never counted (no password or the like) – do not carry it along forever
                        e["done"] = True
                        changed = True
                    continue
                # the plays of the last day are only known after the next counter snapshot – the daily one comes at the
                # time of the refresh (default 05:30); what is played until 04:00 still counts for the day before
                if (snap.get("at") or "") < f"{end + dt.timedelta(days=1)}T04:00":
                    continue
                plays, _ = rueckblick.plays_between(e["user"], start, end)
                ids = e.get("ids") or []
                heard = [i for i, sid in enumerate(ids) if plays.get(sid)]
                e["done"] = True
                changed = True
                out["periods"] += 1
                if len(heard) < MIN_HEARD:
                    continue
                last = max(heard)
                if len(heard) < SEQUENTIAL * (last + 1):
                    continue   # shuffled or only single songs played: skips cannot be recognized
                if e["user"] not in per_user:
                    try:
                        per_user[e["user"]] = _load_to_write(_feedback_file(e["user"]), {})
                    except OSError:   # briefly not readable: evaluate this period next time
                        e["done"] = False
                        out["periods"] -= 1
                        continue
                fb = per_user[e["user"]]
                for i, sid in enumerate(ids[:last]):
                    if not plays.get(sid):
                        item = fb.setdefault(sid, {"s": [], "p": 0})
                        marks = item.get("s", [])
                        if marks and (end - dt.date.fromisoformat(marks[-1])).days < 7:
                            continue   # at most one mark per week (Daily Mixes repeat songs)
                        item["s"] = (marks + [end.isoformat()])[-10:]
                        out["skips"] += 1
                for i in heard:
                    item = fb.setdefault(ids[i], {"s": [], "p": 0})
                    item["p"] = item.get("p", 0) + 1
                    out["plays"] += 1
        for user, fb in per_user.items():
            try:
                FEEDBACK_DIR.mkdir(parents=True, exist_ok=True)
                write_atomic(_feedback_file(user), json.dumps(fb))
            except OSError:
                pass
        if changed:
            try:
                write_atomic(HISTORY, json.dumps(data))
            except OSError:
                pass
    if out["periods"]:
        log(_sn(out['periods'], "Mixes learn: {n} period evaluated – {skips}× skipped, {plays}× played.",
                "Mixes learn: {n} periods evaluated – {skips}× skipped, {plays}× played.",
                skips=out['skips'], plays=out['plays']))
    return out


# ---------------------------------------------------------------------------- Applying

def _effect(fb, today):
    """Song ID -> how strongly it counts as skipped: every skip mark halves with HALF_LIFE, every play from a mix
    makes up for half a skip."""
    out = {}
    for sid, item in fb.items():
        eff = 0.0
        for day in item.get("s", []):
            try:
                age = (today - dt.date.fromisoformat(day)).days
            except ValueError:
                continue
            eff += 0.5 ** (max(age, 0) / HALF_LIFE)
        out[sid] = eff - 0.5 * item.get("p", 0)
    return out


_live_memo = {}


def _live_effect(user, today):
    """The same from the live plays (listen.py): skips on their days, every play makes up for half a skip. The family:
    also its mixes heard on the people's accounts (listen.family_summary())."""
    from . import listen
    family = listen.is_family(user)
    key = (user.lower(), today, listen.stamp_all() if family else listen.stamp(user), listen.family_key())
    hit = _live_memo.get(key)
    if hit is not None:
        return hit
    start = today - dt.timedelta(days=listen.KEEP_DAYS)
    skipped, played = listen.family_summary(start, today) if family else listen.summary(user, start, today)
    out = {}
    for sid, days in skipped.items():
        out[sid] = sum(0.5 ** (max((today - dt.date.fromisoformat(d)).days, 0) / HALF_LIFE) for d in days)
    for sid, n in played.items():
        out[sid] = out.get(sid, 0.0) - 0.5 * n
    if len(_live_memo) > 16:
        _live_memo.clear()
    _live_memo[key] = out
    return out


_factors_memo = {}
_NO_EFFECT = {}   # one object for "no feedback file", so that the memo below recognizes it


def factors(user, today=None):
    """Song ID -> weight factor (< 1 for skipped songs) for the mixes of this account – the same object as long as
    neither the feedback file nor the live plays change (mixes ask often)."""
    if not user:
        return {}
    today = today or dt.date.today()
    base = _cached(_feedback_file(user), {}, lambda fb: _effect(fb, today), extra=today) or _NO_EFFECT
    live = _live_effect(user, today)
    key = (user.lower(), today)
    hit = _factors_memo.get(key)
    if hit and hit[0] is base and hit[1] is live:
        return hit[2]
    eff = dict(base)
    for sid, value in live.items():
        eff[sid] = eff.get(sid, 0.0) + value
    out = {sid: SKIP_FACTOR ** min(e, MAX_SKIPS) for sid, e in eff.items() if e > 0.05}
    if len(_factors_memo) > 32:
        _factors_memo.clear()
    _factors_memo[key] = (base, live, out)
    return out


def deezer_stars(user):
    """Song ID -> star the Deezer rating last set for this account (only entries with "u").
    A star of the account that differs from it was given by hand."""
    low = (user or "").lower()

    def convert(entries):
        out = {}
        for sid, e in entries.items():
            for k, v in (e.get("u") or {}).items():
                if k.lower() == low:
                    out[sid] = v
        return out
    entries = _cached(DEEZER_STATE, {}, lambda d: d.get("songs", {}) if isinstance(d, dict) else {})
    key = ("stars", low, (_cache.get(str(DEEZER_STATE)) or (None,))[0])   # recompute when the file changes
    hit = _cache.get(key)
    if hit is None:
        for k in [k for k in list(_cache) if isinstance(k, tuple) and k[:2] == ("stars", low)]:   # copy: other threads write too
            _cache.pop(k, None)
        hit = _cache[key] = convert(entries)
    return hit


def manual_dislikes(lib, user):
    """Song IDs this account rated with 1 star by hand. Only if lib has the stars of exactly this account."""
    if not user or (getattr(lib, "user", None) or "").lower() != user.lower() or not getattr(lib, "ratings_exact", False):
        return set()
    entries = _cached(DEEZER_STATE, {}, lambda d: d.get("songs", {}) if isinstance(d, dict) else {})
    out = set()
    low = user.lower()
    for s in lib.songs:
        if s.get("userRating") != 1:
            continue
        entry = entries.get(s["id"])
        if entry is None:   # Deezer never rated the song -> the star was given by hand
            out.add(s["id"])
            continue
        given = {k.lower(): v for k, v in (entry.get("u") or {}).items()}
        # By hand if the Deezer rating did not set 1 for this account (or did not rate it at all).
        # Entries without accounts in "u" do not say who got which star – there the star counts as automatic,
        # otherwise machine-given 1 stars could drop out of the mixes for good.
        if given and given.get(low) != 1:
            out.add(s["id"])
    return out


def stats(user):
    """For the interface: how many songs currently come less often."""
    return {"seltener": len(factors(user))}
