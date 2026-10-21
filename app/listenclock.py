"""Listening clock per Navidrome account: when someone listens (time of day, weekday) and how long at a stretch – so
that suggestions for a daily routine only come when the habit is there ("Good morning" only for people who listen in
the morning), with the length of their usual round and the sound of what they play at that time.

Navidrome keeps per account and song only the time of the last play ("played", UTC). Two sources, together:
* the song list of the account right now – the last play of every song, so the clock works from the first day on
  with the plays of the past weeks,
* moments recorded by the recap snapshots (rueckblick.snapshot -> record()): the last play of every song with new plays,
  in state/plays/<account>/moments.json – so a song played again later does not erase its earlier moment,
* with the Navidrome plugin every start and play as it happens (listen.py) – exact, also several plays a day.
Times count in the local time zone (TZ of the container).

Sessions: plays less than SESSION_GAP apart belong together; a session lasts from its first to its last play plus one
song. A morning counts if a session of at least two songs starts between MORNING[0] and MORNING[1] o'clock; the habit
is there with MIN_DAYS such mornings in the last DAYS days, spread over MIN_WEEKS weeks.
"""
import datetime as dt
import json
import math
import statistics
import threading
from collections import Counter

from .config import read_text, write_atomic

DAYS = 42                    # the last six weeks decide
KEEP_DAYS = 120              # recorded moments are kept this long
MAX_MOMENTS = 30000
SESSION_GAP = dt.timedelta(minutes=20)
SONG_MINUTES = 3.5           # a session lasts until its last song has played
MORNING = (5, 10)            # a session starting from 05:00 to 09:59 is a morning one
MIN_DAYS, MIN_WEEKS = 6, 3
MINUTES = (15, 60)           # length of the morning mix: the usual round, within these limits
LIVE_TOLERANCE = 120         # Navidrome's last play this close to a live one is the same play
_lock = threading.Lock()
_memo = {}


def _file(user):
    from .rueckblick import _dir
    return _dir(user) / "moments.json"


def local_time(iso):
    """'2026-10-19T05:45:12Z' (Navidrome, UTC) -> local naive datetime, None if unreadable."""
    try:
        t = dt.datetime.fromisoformat(str(iso).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    if t.tzinfo is None:
        t = t.replace(tzinfo=dt.timezone.utc)
    return t.astimezone().replace(tzinfo=None)


def _stored(user):
    try:
        data = json.loads(read_text(_file(user)))
    except (OSError, ValueError):
        return []
    rows = data.get("moments") if isinstance(data, dict) else None
    return [r for r in rows or [] if isinstance(r, list) and len(r) == 2 and all(isinstance(x, str) for x in r)]


def record(user, songs, new_ids, now=None):
    """After a snapshot: remember the last play of the songs with new plays (called by rueckblick.snapshot under its
    lock). Old moments go after KEEP_DAYS, at most MAX_MOMENTS stay."""
    played = {s["id"]: s.get("played") for s in songs if s["id"] in new_ids and s.get("played")}
    if not played:
        return
    now = now or dt.datetime.now()
    cutoff = now - dt.timedelta(days=KEEP_DAYS)
    rows = _stored(user) + [[sid, iso] for sid, iso in played.items()]
    seen, keep = set(), []
    for sid, iso in rows:
        t = local_time(iso)
        if t is None or t < cutoff or (sid, iso[:16]) in seen:
            continue
        seen.add((sid, iso[:16]))
        keep.append([sid, iso])
    _file(user).parent.mkdir(parents=True, exist_ok=True)
    write_atomic(_file(user), json.dumps({"v": 1, "moments": keep[-MAX_MOMENTS:]}))


def moments(user, songs, now=None, days=DAYS):
    """[(local time, song id)] of the last `days` days, oldest first – recorded moments and the last play of every
    song, each moment once."""
    now = now or dt.datetime.now()
    cutoff = dt.datetime.combine(now.date() - dt.timedelta(days=days), dt.time())
    seen, out = set(), []
    from . import listen
    live = listen.moments(user, cutoff)   # live from the Navidrome plugin: every play, exact
    near = {}
    for t, sid in live:
        near.setdefault(sid, []).append(t)
    other = [(local_time(iso), sid) for sid, iso in
             _stored(user) + [[s["id"], s.get("played")] for s in songs if s.get("played")]]
    for t, sid, is_live in [(t, sid, True) for t, sid in live] + [(t, sid, False) for t, sid in other]:
        if t is None or t < cutoff or t > now + dt.timedelta(hours=1):
            continue
        if not is_live and any(abs((t - x).total_seconds()) <= LIVE_TOLERANCE for x in near.get(sid, ())):
            continue   # the same play, known exactly from the plugin
        key = (sid, t.replace(second=0, microsecond=0))
        if key not in seen:
            seen.add(key)
            out.append((t, sid))
    out.sort()
    return out


def sessions(moms):
    """Listening sessions from moments (sorted): [{"start", "end", "minutes", "songs": [song id, …]}]."""
    out, cur = [], None
    for t, sid in moms:
        if cur is not None and t - cur["end"] <= SESSION_GAP:
            cur["end"] = t
            cur["songs"].append(sid)
        else:
            cur = {"start": t, "end": t, "songs": [sid]}
            out.append(cur)
    for s in out:
        s["minutes"] = (s["end"] - s["start"]).total_seconds() / 60 + SONG_MINUTES
    return out


def _round5(minutes):
    return int(5 * round(minutes / 5))


def morning(user, songs, now=None, skip=frozenset()):
    """The morning habit of an account, or None: {"days", "weeks", "at": "06:45" (usual start), "minutes" (usual
    round, MINUTES), "weekdays": mostly Monday to Friday, "songs": {song id: plays in the morning}}.
    skip: song ids that do not count (music worlds the person keeps out of their taste, e.g. children's music)."""
    now = now or dt.datetime.now()
    moms = [m for m in moments(user, songs, now) if m[1] not in skip]
    sess = [s for s in sessions(moms) if MORNING[0] <= s["start"].hour < MORNING[1] and len(s["songs"]) >= 2]
    per_day = {}
    for s in sess:   # per morning: the longest round decides its length, the first one its time
        d = s["start"].date()
        cur = per_day.setdefault(d, {"start": s["start"], "minutes": 0.0})
        cur["minutes"] = max(cur["minutes"], s["minutes"])
    weeks = {d.isocalendar()[:2] for d in per_day}
    if len(per_day) < MIN_DAYS or len(weeks) < MIN_WEEKS:
        return None
    start = statistics.median(x["start"].hour * 60 + x["start"].minute for x in per_day.values())
    start = _round5(start)
    minutes = min(MINUTES[1], max(MINUTES[0], _round5(statistics.median(x["minutes"] for x in per_day.values()))))
    weekdays = sum(1 for d in per_day if d.weekday() < 5) / len(per_day) >= 0.8
    return {"days": len(per_day), "weeks": len(weeks), "at": f"{start // 60}:{start % 60:02d}", "minutes": minutes,
            "weekdays": weekdays, "songs": dict(Counter(sid for s in sess for sid in s["songs"]))}


def _stamp(user):
    try:
        st = _file(user).stat()
        return (st.st_mtime_ns, st.st_size)
    except OSError:
        return None


def morning_of(cfg, base, user, today=None, exclude=()):
    """morning() for an account with its own song list (needs its stored password) – cached per account, day,
    song list, recorded moments and the music worlds left out (exclude, taste.excluded(person)); None without a
    password or without the habit."""
    if not user:
        return None
    from . import ml, taste
    plib = taste._person_lib(cfg, base, user)
    if plib is None:
        return None
    today = today or dt.date.today()
    exclude = tuple(sorted(set(exclude or ())))
    from . import listen
    key = ("morning", user.lower(), today, ml.lib_key(plib), _stamp(user), listen.stamp(user), exclude)
    with _lock:
        if key in _memo:
            return _memo[key]
    now = dt.datetime.now() if today == dt.date.today() else dt.datetime.combine(today, dt.time(23, 59))
    skip = taste.excluded_ids(cfg, plib, exclude, today)
    out = morning(user, plib.songs, now, frozenset(plib.songs[i]["id"] for i in skip))
    with _lock:
        if len(_memo) > 32:
            _memo.clear()
        _memo[key] = out
    return out


def morning_taste(cfg, base, plib, user, today=None, exclude=()):
    """Sound of the account's mornings (soundtaste.SoundTaste from what it plays in the morning) for the "Good
    morning" mix, or None – no habit, no sound vectors, too few morning songs with one."""
    from . import similar, soundtaste
    info = morning_of(cfg, base, user, today, exclude)
    stamp = similar.stamp()
    if not info or stamp is None:
        return None
    today = today or dt.date.today()
    key = ("taste", user.lower(), today, stamp, tuple(sorted(set(exclude or ()))), tuple(sorted(info["songs"].items())),
           len(plib.songs))
    with _lock:
        if key in _memo:
            return _memo[key]
    index = {s["id"]: i for i, s in enumerate(plib.songs)}
    scores = {index[sid]: 1.0 + math.log1p(n) for sid, n in info["songs"].items() if sid in index}
    out = soundtaste.compute(plib, user, today, scores) if scores else None
    with _lock:
        _memo[key] = out
    return out
