"""Long-term maintenance – so Tuttiphon stays lean even after years. Once a week at the start of a run
(tasks.TaskRunner, never in a dry run), while nobody else writes the files:

* Trash: playlists that have been in it for 30 days and are no longer in Navidrome are removed for good.
* Vanished songs: Navidrome gives a file a new ID when it moves or is converted (FLAC → Opus). Entries for IDs that
  have not existed for 30 days drop out of deezer.json, audio.json, ml.json, lyrics.json, sound_vectors.json,
  lautstaerke.json, what the mixes learned (feedback/) and the first plays of the recap (plays/<account>/first.json).
  Never when the song list is noticeably
  smaller than usual (say, because the music folder is not mounted right now).
* Mixes learn: skip marks older than two years drop out – they hardly count any more anyway.
* Hidden suggestions: come back after half a year (if they still fit then) – so “Discover” never runs dry. Deleted
  music worlds („scene|…“) stay hidden.
* Lyrics index: compact once a month.

State in state/langzeit.json: {"at", "compacted", "maxSongs", "missing": {song ID: since}}.
"""
import datetime as dt
import json

from .config import STATE_DIR, load_config, read_text, update_config, write_atomic
from .i18n import _s, _sn

STATE_FILE = STATE_DIR / "langzeit.json"
EVERY_DAYS = 7
TRASH_DAYS = 30
GONE_DAYS = 30
MARKS_DAYS = 730
COMPACT_DAYS = 30
HEALTHY = 0.8   # song list at least this share of the usual size – otherwise forget nothing
DISMISS_DAYS = 180


def _load():
    try:
        data = json.loads(read_text(STATE_FILE))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def _days(since, today):
    try:
        return (today - dt.date.fromisoformat(since[:10])).days
    except (TypeError, ValueError):
        return 0


def due(today=None):
    today = today or dt.date.today()
    last = _load().get("at")
    return not last or _days(last, today) >= EVERY_DAYS


def run(lib, log=print, today=None, force=False):
    """-> {"trash", "songs", "marks", "compacted"} or None (not due yet)."""
    today = today or dt.date.today()
    st = _load()
    if not force and st.get("at") and _days(st["at"], today) < EVERY_DAYS:
        return None
    out = {"trash": expire_trash(today), "songs": 0, "marks": 0, "compacted": None, "dismissed": expire_dismissed(today)}
    try:   # live plays of the Navidrome plugin older than they are kept – also of accounts that stopped playing
        from . import listen
        listen.prune_all()
    except OSError:
        pass
    n = len(lib.songs)
    usual = int(st.get("maxSongs") or 0)
    missing = st.get("missing") if isinstance(st.get("missing"), dict) else {}
    if n and n >= HEALTHY * usual:
        current = {s["id"] for s in lib.songs}
        stores = _stores()
        known = set().union(*(set(ids()) for ids, _ in stores))
        for sid in known - current:
            missing.setdefault(sid, today.isoformat())
        missing = {sid: d for sid, d in missing.items() if sid in known and sid not in current}
        gone = {sid for sid, d in missing.items() if _days(d, today) >= GONE_DAYS}
        if gone:
            for _, forget in stores:
                forget(gone)
            missing = {sid: d for sid, d in missing.items() if sid not in gone}
            out["songs"] = len(gone)
    elif usual:
        log(_s("Long-term maintenance: with {n} songs the song list is clearly smaller than usual ({usual}) – vanished "
               "songs are not forgotten this time.", n=n, usual=usual))
    out["marks"] = _age_marks(today)
    if _days(st.get("compacted") or "", today) >= COMPACT_DAYS or not st.get("compacted"):
        from . import liedtext
        out["compacted"] = liedtext.compact()
        if out["compacted"]:
            st["compacted"] = today.isoformat()
    # the usual size slowly follows a collection that got smaller (3 % per week)
    st.update(at=today.isoformat(), maxSongs=max(n, int(usual * 0.97)), missing=missing)
    try:
        write_atomic(STATE_FILE, json.dumps(st))
    except OSError:
        pass
    parts = []   # independent clauses, listed with "; "
    if out["trash"]:
        parts.append(_sn(len(out["trash"]), "{n} playlist removed from the trash ({names})",
                         "{n} playlists removed from the trash ({names})",
                         names=", ".join(out["trash"][:5]) + (" …" if len(out["trash"]) > 5 else "")))
    if out["songs"]:
        parts.append(_sn(out["songs"], "{n} vanished song forgotten", "{n} vanished songs forgotten"))
    if out["dismissed"]:
        parts.append(_sn(out["dismissed"], "{n} hidden suggestion allowed again after half a year",
                         "{n} hidden suggestions allowed again after half a year"))
    if out["marks"]:
        parts.append(_sn(out["marks"], "{n} old skip mark removed", "{n} old skip marks removed"))
    if out["compacted"]:
        before, after = out["compacted"]
        parts.append(_s("Lyrics index compacted ({before} → {after} MB)", before=before // 1024 // 1024,
                        after=after // 1024 // 1024))
    if parts:
        log(_s("Long-term maintenance: {items}.", items="; ".join(parts)))
    return out


# ---------------------------------------------------------------------------- trash

def expire_trash(today):
    """Remove playlists for good that have been in the trash for TRASH_DAYS days – only when their file is no longer in
    the playlist folder (so it is no longer in Navidrome either). Without a date: count from today. -> [name]"""
    from .playlists import plain_playlist_file, playlist_dir
    from .rules import playlist_name
    cfg = load_config()
    trash = [p for p in cfg["playlists"] if p.get("status") == "papierkorb"]
    if not trash:
        return []
    folder = playlist_dir(cfg)

    def still_there(p):
        f = p.get("file")
        try:
            return bool(f) and plain_playlist_file(f) and (folder / f).exists()
        except OSError:
            return True   # when in doubt, keep
    old = {p["id"] for p in trash if p.get("deletedAt") and _days(p["deletedAt"], today) >= TRASH_DAYS and not still_there(p)}
    undated = {p["id"] for p in trash if not p.get("deletedAt")}
    if not old and not undated:
        return []
    names = [playlist_name(cfg, p) for p in trash if p["id"] in old]

    def apply(fresh):
        keep = []
        for p in fresh["playlists"]:
            if p.get("status") == "papierkorb":
                if p["id"] in old and p.get("deletedAt"):
                    continue
                if not p.get("deletedAt"):
                    p["deletedAt"] = today.isoformat()
            keep.append(p)
        fresh["playlists"] = keep
    update_config(apply)
    return names


# ---------------------------------------------------------------------------- hidden suggestions

def expire_dismissed(today):
    """Allow suggestions again that have been hidden for DISMISS_DAYS days – for the administrator (dismissed) and for
    every account (accounts.<account>.dismissed). „scene|…“ (deleted music worlds) stays. -> count"""
    from .config import stamp_dismissed

    def expired(holder):
        at = holder.get("dismissedAt") if isinstance(holder.get("dismissedAt"), dict) else {}
        return [k for k in holder.get("dismissed", []) if isinstance(k, str) and not k.startswith("scene|")
                and at.get(k) and _days(at[k], today) >= DISMISS_DAYS]

    def holders(cfg):
        return [cfg] + [a for a in (cfg.get("accounts") or {}).values() if isinstance(a, dict)]
    cfg = load_config()
    todo = sum(len(expired(h)) for h in holders(cfg))
    undated = any(set(h.get("dismissed", [])) - set(h.get("dismissedAt") or {}) for h in holders(cfg))
    if not todo and not undated:
        return 0
    n = 0

    def apply(fresh):
        nonlocal n
        for h in holders(fresh):
            if not h.get("dismissed") and "dismissedAt" not in h:
                continue
            gone = set(expired(h))
            n += len(gone)
            h["dismissed"] = [k for k in h.get("dismissed", []) if k not in gone]
            stamp_dismissed(h, h.get("dismissedAt"))   # older entries without a date count from today
    update_config(apply)
    return n


# ---------------------------------------------------------------------------- vanished songs

def _json(path):
    try:
        data = json.loads(read_text(path))
        return data if isinstance(data, dict) else None
    except (OSError, ValueError):
        return None


def _stores():
    """[(deliver IDs, forget IDs -> count)] for every file with entries per song."""
    from . import audio, deezer, feedback, lautstaerke, lyrics, ml, rueckblick, similar
    out = []

    def nested(path, key, save):   # {key: {song ID: …}} – deezer.json, audio.json, ml.json, lyrics.json
        def ids():
            data = _json(path)
            return (data.get(key) or {}).keys() if data else ()

        def forget(gone):
            data = _json(path)
            songs = (data or {}).get(key)
            if not isinstance(songs, dict):
                return 0
            hit = [sid for sid in songs if sid in gone]
            for sid in hit:
                del songs[sid]
            if hit:
                save(data)
            return len(hit)
        out.append((ids, forget))
    nested(deezer.STATE_FILE, "songs", deezer.save_state)
    nested(audio.STATE_FILE, "songs", audio.save)
    nested(ml.STATE_FILE, "songs", ml.save)
    nested(lyrics.STATE_FILE, "songs", lyrics.save_state)
    # sound vectors of the AI ({"v", "dim", "songs"}) and loudness ({"songs"}): written back whole (version stays)
    nested(similar.STATE_FILE, "songs", lambda data: write_atomic(similar.STATE_FILE, json.dumps(data, separators=(",", ":"))))
    nested(lautstaerke.STATE_FILE, "songs", lautstaerke.save)

    def flat(path):   # {song ID: …} – feedback/<account>.json, plays/<account>/first.json
        def ids():
            return (_json(path) or {}).keys()

        def forget(gone):
            data = _json(path)
            hit = [sid for sid in (data or {}) if sid in gone]
            for sid in hit:
                del data[sid]
            if hit:
                write_atomic(path, json.dumps(data))
            return len(hit)
        out.append((ids, forget))
    for path in sorted(feedback.FEEDBACK_DIR.glob("*.json")) if feedback.FEEDBACK_DIR.is_dir() else ():
        if ".defekt-" not in path.name:   # set aside after damage: stays as it is
            flat(path)
    for path in sorted(rueckblick.PLAYS_DIR.glob("*/first.json")) if rueckblick.PLAYS_DIR.is_dir() else ():
        flat(path)
    return out


def _age_marks(today):
    """Remove skip marks older than MARKS_DAYS from what the mixes learned; empty entries entirely. -> count"""
    from . import feedback
    if not feedback.FEEDBACK_DIR.is_dir():
        return 0
    cutoff = (today - dt.timedelta(days=MARKS_DAYS)).isoformat()
    total = 0
    for path in sorted(feedback.FEEDBACK_DIR.glob("*.json")):
        data = _json(path)
        if not data:
            continue
        n = 0
        for sid in list(data):
            item = data[sid]
            if not isinstance(item, dict):
                continue
            marks = item.get("s") or []
            fresh = [m for m in marks if isinstance(m, str) and m >= cutoff]
            n += len(marks) - len(fresh)
            if fresh != marks:
                item["s"] = fresh
            if not item.get("s") and not item.get("p"):
                del data[sid]
        if n:
            write_atomic(path, json.dumps(data))
            total += n
    return total
