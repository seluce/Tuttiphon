"""Live plays from Navidrome – what the Tuttiphon plugin passes on as Navidrome's scrobbler (navidrome-plugin/):

  start   a song starts (Navidrome's "now playing"; the time is when it arrives). Navidrome also sends one with every
          player's report, further into the song – only those near the beginning (START_SECONDS) are kept
  play    a song was played (Navidrome's scrobble; the time is when it started – also later, from offline phones)
  report  a player's report (playing, paused, stopped … with the position and the player)

Only for accounts that have a person in Tuttiphon and are not blocked (allowed()). Kept per account and day in
state/plays/<account>/live-<YYYY-MM-DD>.jsonl (one event per line, permissions 0640), KEEP_DAYS days.

What comes of it:
* exact listening times – the listening clock (listenclock.moments) takes every play (moments()), also the second
  play of a song on the same day (Navidrome itself keeps only the last one per song);
* real skips (skips()) – a song that gave way to another one before SKIP_SECONDS (or, for a short track, before its
  last 5 seconds) without having been scrobbled counts as skipped – per player from its reports (the position
  reached or the time until the next song), otherwise from the starts of the account. Not a skip: a moment of
  another song in between (cross-fade, a report arriving late), going back to the song before (the "previous"
  button), the first song after a pause of IDLE_SECONDS (a car resuming yesterday's queue). The mixes learn from them
  (feedback.factors); for mix periods with live starts or reports the coarse guess from the mix history is left out
  (feedback.learn);
* plays without a stored password – as long as an account has no counter snapshots (rueckblick, baseline.json), its
  plays go into the recap from here (the day files rueckblick.snapshot writes); with the first snapshot that stops, so
  nothing counts twice. A play that arrives twice (Navidrome retrying it) is kept once;
* who is listening right now (listener(), heard()) – Navidrome does not say who asks the plugin for similar songs;
  sonic.py answers for the person playing the song asked about.
"""
import datetime as dt
import json
import os
import threading
import time
from collections import defaultdict

from .config import read_text
from .i18n import _

KEEP_DAYS = 120
SKIP_SECONDS = 30
START_SECONDS = 15   # a "now playing" further into the song is the same play going on
SAME_PLAY = 60       # a start and the scrobble of the same song this close together are one play
SHORT_PIECE = 5      # a moment of another song between two parts of the same song: not a change of song
IDLE_SECONDS = 1800  # the first song after this long a pause on a player never counts as skipped
LISTENER_SONG = 900       # the song asked about played on exactly one account this recently: that account listens
LISTENER_ACTIVE = 600     # otherwise: the one account playing anything right now (its last event this recent)
HEARD_SECONDS = 3 * 3600  # what the listener heard this recently does not come again at once (sonic.py)
KINDS = ("start", "play", "report")
STATES = ("starting", "playing", "paused", "stopped", "expired")
_lock = threading.Lock()
_seen = {"at": None, "events": 0, "accounts": set(), "pruned": {}}
_versions = defaultdict(int)   # per account: changes with every event kept (for caches)
_days = {}                     # path -> ((size, mtime), rows) – a day file is parsed again only when it changed


def _folder(user):
    from .rueckblick import _dir
    return _dir(user)


def _file(user, day):
    return _folder(user) / f"live-{day}.jsonl"


def _local(t):
    return dt.datetime.fromtimestamp(t)


def allowed(cfg, user):
    """Plays are kept only for accounts with a person in Tuttiphon that are not blocked."""
    low = user.lower()
    if not any((p.get("user") or "").lower() == low for p in cfg.get("personen", [])):
        return False
    return ((cfg.get("accounts") or {}).get(low) or {}).get("role") != "none"


def _number(x, top=86400):
    return isinstance(x, (int, float)) and not isinstance(x, bool) and 0 <= x <= top


def record(user, kind, song_id, t=None, position=None, state=None, player=None, duration=None, cfg=None, now=None):
    """One event of the plugin. t: Unix seconds (play: when the song started; otherwise now), position and duration:
    seconds. cfg: the configuration (only accounts that are allowed()). -> True if kept (ValueError for an event that
    makes no sense)."""
    now_t = now or time.time()
    if not isinstance(user, str) or not user.strip() or len(user) > 100 or not user.isprintable():
        raise ValueError(_("invalid request"))
    try:
        user.encode("utf-8")
    except UnicodeEncodeError:
        raise ValueError(_("invalid request")) from None
    if kind not in KINDS or not isinstance(song_id, str) or not song_id or len(song_id) > 100:
        raise ValueError(_("invalid request"))
    if cfg is not None and not allowed(cfg, user):
        return False
    if kind == "start" and _number(position) and position > START_SECONDS:
        return False   # the same play going on
    if kind == "play" and _number(t, float("inf")):
        if t > now_t + 3600 or t < now_t - KEEP_DAYS * 86400:
            return False   # from the future or older than what is kept
    else:
        t = now_t
    row = {"t": int(t), "k": kind, "id": song_id}
    if _number(position):
        row["pos"] = round(float(position), 1)
    if _number(duration) and duration > 0:
        row["dur"] = round(float(duration), 1)
    if state in STATES:
        row["st"] = state
    if isinstance(player, str) and player:
        row["pl"] = player[:100]
    day = _local(t).date().isoformat()
    with _lock:
        path = _file(user, day)
        if kind == "play" and any(r["k"] == "play" and r["id"] == song_id and r["t"] == row["t"] for r in _rows(path)):
            return True   # the same play once more (Navidrome retrying it)
        path.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o640)
        try:
            os.fchmod(fd, 0o640)   # also on a share where new files would otherwise get other permissions
            text = json.dumps(row) + "\n"
            if os.fstat(fd).st_size and not _ends_with_newline(path):
                text = "\n" + text   # a line cut off before: do not glue this one to it
            os.write(fd, text.encode("utf-8"))
        finally:
            os.close(fd)
        _versions[user.lower()] += 1
        _seen["at"] = dt.datetime.fromtimestamp(now_t).isoformat(timespec="seconds")
        _seen["events"] += 1
        _seen["accounts"].add(user)
    if kind == "play":
        _count(user, song_id, t)
    try:
        _prune(user, now_t)
    except OSError:
        pass   # next time
    return True


def _ends_with_newline(path):
    try:
        with open(path, "rb") as f:
            f.seek(-1, os.SEEK_END)
            return f.read(1) == b"\n"
    except OSError:
        return True


def _count(user, song_id, t):
    """A play into the recap – only while the account has no counter snapshots (those count it then)."""
    from . import rueckblick
    from .config import write_atomic
    folder = _folder(user)
    try:
        if (folder / "baseline.json").exists():
            return
        day = (_local(t) - dt.timedelta(hours=6)).date().isoformat()   # the listening day, as in the recap
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
        pass   # not readable just now: this one play is missing in the recap rather than counted twice


def _prune(user, now_t):
    """Remove days older than KEEP_DAYS – at most once a day per account (all accounts: prune_all())."""
    today = dt.date.fromtimestamp(now_t)
    if _seen["pruned"].get(user.lower()) == today:
        return
    _seen["pruned"][user.lower()] = today
    cutoff = (today - dt.timedelta(days=KEEP_DAYS)).isoformat()
    for path in _folder(user).glob("live-*.jsonl"):
        if path.stem[5:] < cutoff:
            path.unlink(missing_ok=True)
            _days.pop(str(path), None)


def prune_all(now=None):
    """Old days of every account – also of accounts that stopped playing (the long-term maintenance)."""
    from .rueckblick import PLAYS_DIR
    now_t = now or time.time()
    cutoff = (dt.date.fromtimestamp(now_t) - dt.timedelta(days=KEEP_DAYS)).isoformat()
    for path in PLAYS_DIR.glob("*/live-*.jsonl"):
        if path.stem[5:] < cutoff:
            path.unlink(missing_ok=True)
            _days.pop(str(path), None)


def _rows(path):
    """The events of one day file – parsed again only when the file changed."""
    try:
        st = path.stat()
    except OSError:
        return []
    sig = (st.st_size, st.st_mtime_ns)
    hit = _days.get(str(path))
    if hit and hit[0] == sig:
        return hit[1]
    try:
        text = read_text(path)
    except OSError:
        return hit[1] if hit else []
    rows = []
    for line in text.splitlines():
        try:
            row = json.loads(line)
        except ValueError:
            continue   # a line cut off while writing
        if isinstance(row, dict) and isinstance(row.get("t"), int) and row.get("k") in KINDS and row.get("id"):
            rows.append(row)
    if len(_days) > 2000:
        _days.clear()
    _days[str(path)] = (sig, rows)
    return rows


def events(user, start, end):
    """The events of these days (dates, both included), oldest first."""
    out = []
    folder = _folder(user)
    day = start
    while day <= end:
        out.extend(_rows(folder / f"live-{day.isoformat()}.jsonl"))
        day += dt.timedelta(days=1)
    out.sort(key=lambda r: r["t"])
    return out


def stamp(user):
    """Changes with every event kept for the account (for caches; in this process)."""
    return _versions[user.lower()]


def moments(user, since):
    """[(local time, song id)] of the plays since `since` (datetime) – for the listening clock: a start near the
    beginning of the song or a scrobble, a start and its scrobble once (SAME_PLAY), a song played again later twice."""
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


def _recent(folder, since, now_t):
    """The events of one account folder from `since` to `now_t` (Unix seconds), oldest first."""
    days = sorted({_local(since).date().isoformat(), _local(now_t).date().isoformat()})
    rows = [r for d in days for r in _rows(folder / f"live-{d}.jsonl") if since <= r["t"] <= now_t]
    rows.sort(key=lambda r: r["t"])
    return rows


def listener(ids, now=None):
    """Who is listening – the account folder (config.slug of the account) or None if that is unclear. `ids`: the
    song asked about (or the songs of the band or album asked about). The account that played one of them in the
    last LISTENER_SONG seconds – if it is exactly one; if none did, the one account playing anything right now (its
    last event at most LISTENER_ACTIVE seconds ago and not "stopped")."""
    from .rueckblick import PLAYS_DIR
    now_t = now or time.time()
    try:
        folders = [f for f in PLAYS_DIR.iterdir() if f.is_dir()]
    except OSError:
        return None
    recent = {f.name: _recent(f, now_t - LISTENER_SONG, now_t) for f in folders}
    hit = [a for a, rows in recent.items() if any(r["id"] in ids for r in rows)]
    if hit:
        return hit[0] if len(hit) == 1 else None
    playing = [a for a, rows in recent.items()
               if rows and rows[-1]["t"] >= now_t - LISTENER_ACTIVE and rows[-1].get("st") not in ("stopped", "expired")]
    return playing[0] if len(playing) == 1 else None


def heard(user, seconds=HEARD_SECONDS, now=None):
    """Song ids this account started, played or reported in the last `seconds`."""
    now_t = now or time.time()
    return {r["id"] for r in _recent(_folder(user), now_t - seconds, now_t)}


def has_live(user, start, end):
    """Did starts or reports of this account arrive for these listening days (time minus 6 hours, as in the recap)?
    Then the skips are known exactly – the mix history need not guess them."""
    for r in events(user, start, end + dt.timedelta(days=1)):
        if r["k"] in ("start", "report") and start <= (_local(r["t"]) - dt.timedelta(hours=6)).date() <= end:
            return True
    return False


def _segments(rows):
    """Song after song: [{"id", "t0", "t1", "pos", "dur"}] – parts of the same song with only a moment of another song
    in between become one (SHORT_PIECE)."""
    segs = []
    for r in rows:
        if segs and segs[-1]["id"] == r["id"]:
            seg = segs[-1]
            seg["t1"] = r["t"]
        else:
            seg = {"id": r["id"], "t0": r["t"], "t1": r["t"], "pos": 0.0, "dur": None}
            segs.append(seg)
        seg["pos"] = max(seg["pos"], r.get("pos") or 0.0)
        seg["dur"] = r.get("dur") or seg["dur"]
        if len(segs) >= 3 and segs[-1]["id"] == segs[-3]["id"]:
            mid = segs[-2]
            if max(mid["pos"], mid["t1"] - mid["t0"]) < SHORT_PIECE:   # A, a moment of B, A again: still A
                last = segs.pop()
                segs.pop()
                segs[-1]["t1"], segs[-1]["pos"] = last["t1"], max(segs[-1]["pos"], last["pos"])
    return segs


def _skipped(segs, heard):
    """The segments that count as skipped: [(song id, time)]."""
    out = []
    for k in range(len(segs) - 1):
        seg, nxt = segs[k], segs[k + 1]
        prev = segs[k - 1] if k else None
        if prev is None or seg["t0"] - prev["t1"] >= IDLE_SECONDS:
            continue   # the first song after a pause (a resumed queue) – no judgement
        if nxt["id"] == prev["id"]:
            continue   # back to the song before ("previous")
        limit = SKIP_SECONDS
        if seg["dur"]:
            limit = min(limit, max(3.0, seg["dur"] - 5))   # a short track: only if left well before its end
        if max(seg["pos"], nxt["t0"] - seg["t0"]) < limit and not heard(seg["id"], seg["t0"], nxt["t0"]):
            out.append((seg["id"], seg["t0"]))
    return out


def summary(user, start, end):
    """Skips and plays of these days, read once: ({song id: [days skipped]}, {song id: plays}). Per player from its
    reports; without reports from the account's starts near the beginning of a song (two devices playing at once on
    one account can look like a skip there – one skip weighs little)."""
    rows = events(user, start - dt.timedelta(days=1), end + dt.timedelta(days=1))
    played = defaultdict(list)
    plays_ = defaultdict(int)
    for r in rows:
        if r["k"] == "play":
            played[r["id"]].append(r["t"])
            if start <= _local(r["t"]).date() <= end:
                plays_[r["id"]] += 1

    def heard(sid, a, b):   # scrobbled: its start time lies around the start of this part
        return any(a - SAME_PLAY <= t <= b + 5 for t in played.get(sid, ()))

    reports = [r for r in rows if r["k"] == "report" and r.get("pl")]
    if reports:
        by_player = defaultdict(list)
        for r in reports:
            by_player[r["pl"]].append(r)
        found = [x for seq in by_player.values() for x in _skipped(_segments(seq), heard)]
    else:
        starts = [r for r in rows if r["k"] == "start" and (r.get("pos") or 0) <= START_SECONDS]
        found = _skipped(_segments(starts), heard)
    skipped = defaultdict(set)
    for sid, t in found:
        day = _local(t).date()
        if start <= day <= end:
            skipped[sid].add(day.isoformat())
    return {sid: sorted(days) for sid, days in skipped.items()}, dict(plays_)


def skips(user, start, end):
    """Songs skipped live: {song id: [days]} – each song at most once a day (summary())."""
    return summary(user, start, end)[0]


def plays(user, start, end):
    """{song id: plays that arrived live} on these days."""
    return summary(user, start, end)[1]


def status():
    """Since Tuttiphon started: the last event, how many, from which accounts."""
    with _lock:
        return {"lastEvent": _seen["at"], "events": _seen["events"], "accounts": sorted(_seen["accounts"], key=str.lower)}
