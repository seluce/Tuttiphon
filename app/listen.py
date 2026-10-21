"""Live plays from Navidrome – what the Tuttiphon plugin passes on as Navidrome's scrobbler (navidrome-plugin/):

  start   a song starts (Navidrome's "now playing"; the time is when it arrives)
  play    a song was played (Navidrome's scrobble; the time is when it started – also later, from offline phones)
  report  a player's report (playing, paused, stopped … with the position and the player)

Kept per account and day in state/plays/<account>/live-<YYYY-MM-DD>.jsonl (one event per line), KEEP_DAYS days.

What comes of it:
* exact listening times – the listening clock (listenclock.moments) takes every start and play, also the second play
  of a song on the same day (Navidrome itself keeps only the last one per song);
* real skips (skips()) – a song that gave way to another one within SKIP_SECONDS without having been played counts as
  skipped: per player from its reports (the position reached), otherwise from the starts of the account. The mixes
  learn from them (feedback.factors); for mix periods with live plays the coarse guess from the mix history is left
  out (feedback.learn);
* plays without a stored password – as long as an account has no counter snapshots (rueckblick), its plays go into
  the recap from here (the day files rueckblick.snapshot writes); with the first snapshot that stops, so nothing
  counts twice.
"""
import datetime as dt
import json
import threading
import time
from collections import defaultdict

from .config import read_text
from .i18n import _

KEEP_DAYS = 120
SKIP_SECONDS = 30
KINDS = ("start", "play", "report")
STATES = ("starting", "playing", "paused", "stopped", "expired")
_lock = threading.Lock()
_seen = {"at": None, "events": 0, "accounts": set(), "pruned": {}}


def _folder(user):
    from .rueckblick import _dir
    return _dir(user)


def _file(user, day):
    return _folder(user) / f"live-{day}.jsonl"


def _local(t):
    return dt.datetime.fromtimestamp(t)


def record(user, kind, song_id, t=None, position=None, state=None, player=None, now=None):
    """One event of the plugin. t: Unix seconds (play: when the song started; otherwise now), position: seconds.
    -> True if kept (ValueError for an event that makes no sense)."""
    now_t = (now or time.time())
    if not isinstance(user, str) or not user.strip() or len(user) > 200:
        raise ValueError(_("invalid request"))
    if kind not in KINDS:
        raise ValueError(_("invalid request"))
    if not isinstance(song_id, str) or not song_id or len(song_id) > 100:
        raise ValueError(_("invalid request"))
    if kind == "play" and isinstance(t, (int, float)) and not isinstance(t, bool):
        if t > now_t + 3600 or t < now_t - KEEP_DAYS * 86400:
            return False   # from the future or older than what is kept
    else:
        t = now_t
    row = {"t": int(t), "k": kind, "id": song_id}
    if isinstance(position, (int, float)) and not isinstance(position, bool) and 0 <= position <= 86400:
        row["pos"] = round(float(position), 1)
    if state in STATES:
        row["st"] = state
    if isinstance(player, str) and player:
        row["pl"] = player[:100]
    day = _local(t).date().isoformat()
    with _lock:
        path = _file(user, day)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(row) + "\n")
        _seen["at"] = dt.datetime.fromtimestamp(now_t).isoformat(timespec="seconds")
        _seen["events"] += 1
        _seen["accounts"].add(user)
    if kind == "play":
        _count(user, song_id, t)
    _prune(user, now_t)
    return True


def _count(user, song_id, t):
    """A play into the recap – only while the account has no counter snapshots (those count it then)."""
    from . import rueckblick
    from .config import write_atomic
    if rueckblick.last_snapshot(user):
        return
    day = (_local(t) - dt.timedelta(hours=6)).date().isoformat()   # the listening day, as in the recap
    folder = _folder(user)
    try:
        with rueckblick._lock:
            folder.mkdir(parents=True, exist_ok=True)
            cur = rueckblick._load_to_write(folder / f"{day}.json", {})
            cur[song_id] = cur.get(song_id, 0) + 1
            write_atomic(folder / f"{day}.json", json.dumps(cur))
            first = rueckblick._load_to_write(folder / "first.json", {})
            if song_id not in first:
                first[song_id] = day
                write_atomic(folder / "first.json", json.dumps(first))
    except OSError:
        pass   # briefly not readable: this one play is missing in the recap


def _prune(user, now_t):
    """Remove days older than KEEP_DAYS – at most once a day per account."""
    today = dt.date.fromtimestamp(now_t)
    if _seen["pruned"].get(user) == today:
        return
    _seen["pruned"][user] = today
    cutoff = (today - dt.timedelta(days=KEEP_DAYS)).isoformat()
    for path in _folder(user).glob("live-*.jsonl"):
        if path.stem[5:] < cutoff:
            path.unlink(missing_ok=True)


def events(user, start, end):
    """The events of these days (dates, both included), oldest first."""
    out = []
    folder = _folder(user)
    day = start
    while day <= end:
        path = folder / f"live-{day.isoformat()}.jsonl"
        if path.exists():
            try:
                text = read_text(path)
            except OSError:
                text = ""
            for line in text.splitlines():
                try:
                    row = json.loads(line)
                except ValueError:
                    continue   # a line cut off while writing
                if isinstance(row, dict) and isinstance(row.get("t"), int) and row.get("k") in KINDS and row.get("id"):
                    out.append(row)
        day += dt.timedelta(days=1)
    out.sort(key=lambda r: r["t"])
    return out


def stamp(user):
    """Changes when live events of the account arrive (for caches)."""
    try:
        return tuple(sorted((p.name, p.stat().st_size) for p in _folder(user).glob("live-*.jsonl"))[-3:])
    except OSError:
        return ()


START_SECONDS = 15   # a "now playing" further into the song is the same play going on (Navidrome sends one per report)
SAME_PLAY = 600      # a start and the scrobble of the same song this close together are one play


def moments(user, since):
    """[(local time, song id)] of the plays since `since` (datetime) – for the listening clock: a start near the
    beginning of the song or a scrobble, each play once."""
    out, last = [], {}
    for r in events(user, since.date(), dt.date.today()):
        if r["k"] not in ("start", "play") or (r["k"] == "start" and (r.get("pos") or 0) > START_SECONDS):
            continue
        if r["id"] in last and abs(r["t"] - last[r["id"]]) < SAME_PLAY:
            continue
        last[r["id"]] = r["t"]
        if _local(r["t"]) >= since:
            out.append((_local(r["t"]), r["id"]))
    return out


def has_plays(user, start, end):
    """Did plays of this account arrive live on these days? (Then the mix history need not guess the skips.)"""
    return any(r["k"] == "play" for r in events(user, start, end))


def skips(user, start, end):
    """Songs skipped live: {song id: [days]} – each song at most once a day. Per player from its reports (the
    position reached before another song came); without reports from the starts of the account (a phone and a
    tablet playing at the same time on one account can look like a skip there – one skip weighs little)."""
    rows = events(user, start - dt.timedelta(days=1), end + dt.timedelta(days=1))
    played = defaultdict(list)
    for r in rows:
        if r["k"] == "play":
            played[r["id"]].append(r["t"])

    def heard(sid, a, b):
        return any(a - 5 <= t <= b + 5 for t in played.get(sid, ()))

    out = defaultdict(set)

    def mark(sid, t):
        day = _local(t).date()
        if start <= day <= end:
            out[sid].add(day.isoformat())

    reports = [r for r in rows if r["k"] == "report" and r.get("pl")]
    if reports:   # per player: song after song, the furthest position reached
        by_player = defaultdict(list)
        for r in reports:
            by_player[r["pl"]].append(r)
        for seq in by_player.values():
            cur = None   # [song id, first time, furthest position]
            for r in seq:
                if cur and r["id"] != cur[0]:
                    # how far it got: the furthest position reported or the time until the next song (a player may
                    # report only when something changes)
                    if max(cur[2], r["t"] - cur[1]) < SKIP_SECONDS and not heard(cur[0], cur[1], r["t"]):
                        mark(cur[0], cur[1])
                    cur = None
                if cur is None:
                    cur = [r["id"], r["t"], 0.0]
                cur[2] = max(cur[2], r.get("pos") or 0.0)
    else:
        starts = [r for r in rows if r["k"] == "start"]
        for a, b in zip(starts, starts[1:]):
            if a["id"] != b["id"] and b["t"] - a["t"] < SKIP_SECONDS and not heard(a["id"], a["t"], b["t"]):
                mark(a["id"], a["t"])
    return {sid: sorted(days) for sid, days in out.items()}


def plays(user, start, end):
    """{song id: plays that arrived live} on these days."""
    out = defaultdict(int)
    for r in events(user, start, end):
        if r["k"] == "play":
            out[r["id"]] += 1
    return dict(out)


def status():
    """Since Tuttiphon started: the last event, how many, from which accounts."""
    with _lock:
        return {"lastEvent": _seen["at"], "events": _seen["events"], "accounts": sorted(_seen["accounts"], key=str.lower)}
