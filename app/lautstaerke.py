"""Even out loudness (ReplayGain 2.0) – so that a quiet children's song and loudly mastered metal sound equally loud
in a mix. Symfonium does the leveling (turn on "ReplayGain" there).

* Measure: integrated loudness (LUFS) and true peak of every song with ffmpeg (filter ebur128) – during the night
  analysis, several songs at a time, until the time window ends. Progress in state/lautstaerke.json.
* Album: once every song of an album is measured, the album loudness follows (mean of the energy weighted by length)
  – for albums that are listened to in one go.
* Write: REPLAYGAIN_TRACK_GAIN/_PEAK and REPLAYGAIN_ALBUM_GAIN/_PEAK (reference −18 LUFS) as tags into the file – with
  mutagen, never re-encoded. Always into a copy next to the file first, check the copy (values there, same length),
  then replace the original in one step (permissions and owner as before; ID3 stays in its version, e.g. v2.3). So a
  cancellation never damages a file.
* Files with a second name (hard link – e.g. Lidarr imported a download the torrent program still shares) stay
  untouched: a copy would take the space twice, writing into the file would change the shared download. Their values
  follow once the link is gone.
* Files that already have ReplayGain values that do not come from Tuttiphon stay untouched.
* Only with settings.loudness.enabled (Settings → FLAC → Opus) and when mutagen is installed (in the Docker image).
"""
import json
import math
import os
import re
import shutil
import subprocess
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from .config import STATE_DIR, read_text, temp_copy, write_atomic
from .i18n import _, _s, _sn

STATE_FILE = STATE_DIR / "lautstaerke.json"
LINK_RETRY = 7 * 86400   # a hard-linked file (left unchanged) only makes the night analysis due again after a week
REFERENCE = -18.0   # LUFS – reference level of ReplayGain 2.0
TAGS = ("REPLAYGAIN_TRACK_GAIN", "REPLAYGAIN_TRACK_PEAK", "REPLAYGAIN_ALBUM_GAIN", "REPLAYGAIN_ALBUM_PEAK")
_lock = threading.Lock()
_RE_I = re.compile(r"^\s*I:\s*(-?[\d.]+|-inf)\s*LUFS", re.M)
_RE_PEAK = re.compile(r"^\s*Peak:\s*(-?[\d.]+|-inf)\s*dBFS", re.M)


def settings(cfg):
    return {"enabled": False, "album": True, **(cfg["settings"].get("loudness") or {})}


def available():
    """-> (ok, reason) – needs ffmpeg and mutagen."""
    if not shutil.which("ffmpeg"):
        return False, _("ffmpeg missing")
    try:
        import mutagen  # noqa: F401
    except ImportError:
        return False, _("not installed")
    return True, ""


def load():
    try:
        data = json.loads(read_text(STATE_FILE))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def save(data):
    try:
        write_atomic(STATE_FILE, json.dumps(data, separators=(",", ":")))
    except OSError:
        pass


# ---------------------------------------------------------------------------- Measuring and computing

def parse_ebur128(text):
    """Summary of ffmpeg ebur128 -> (loudness LUFS, peak dBFS) or None."""
    i, p = _RE_I.findall(text or ""), _RE_PEAK.findall(text or "")
    if not i or i[-1] == "-inf":
        return None
    return float(i[-1]), (float(p[-1]) if p and p[-1] != "-inf" else -60.0)


def measure(path, track=None, timeout=600):
    """Loudness and true peak of a file -> (LUFS, dBFS) or None."""
    cmd = ["ffmpeg", "-nostdin", "-hide_banner", "-v", "info", "-i", str(path), "-map", "0:a:0",
           "-af", "ebur128=peak=true:framelog=quiet", "-f", "null", "-"]
    nice = shutil.which("nice")
    if nice:   # low priority like the other analyses – the NAS stays responsive
        cmd = [nice, "-n", "19", *cmd]
    # own process group: "Cancel" ends ffmpeg right away (TaskRunner.cancel)
    proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, stdin=subprocess.DEVNULL, text=True,
                            errors="replace", start_new_session=True)
    if track:
        track(proc, True)
    try:
        _, err = proc.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.communicate()
        return None
    finally:
        if track:
            track(proc, False)
    return parse_ebur128(err) if proc.returncode == 0 else None


def album_loudness(items):
    """[(LUFS, peak dBFS, seconds)] -> (album LUFS, album peak): energy averaged, weighted by length."""
    total = sum(max(d, 1) for _, _, d in items)
    energy = sum(max(d, 1) * 10 ** (lufs / 10) for lufs, _, d in items) / total
    return 10 * math.log10(energy), max(p for _, p, _ in items)


def tag_values(track, album=None):
    """(LUFS, peak dBFS) of the song and possibly the album -> tag values as other programs write them."""
    def gain(lufs):
        return f"{REFERENCE - lufs:+.2f} dB"

    def peak(db):
        return f"{10 ** (db / 20):.6f}"
    out = {"REPLAYGAIN_TRACK_GAIN": gain(track[0]), "REPLAYGAIN_TRACK_PEAK": peak(track[1])}
    if album:
        out.update(REPLAYGAIN_ALBUM_GAIN=gain(album[0]), REPLAYGAIN_ALBUM_PEAK=peak(album[1]))
    return out


# ---------------------------------------------------------------------------- Reading and writing tags

def _read(f):
    """ReplayGain values of a file opened with mutagen -> {tag: value}."""
    from mutagen.id3 import ID3
    from mutagen.mp4 import MP4
    out = {}
    tags = f.tags
    if tags is None:
        return out
    if isinstance(tags, ID3):
        for frame in tags.getall("TXXX"):
            if frame.desc.upper() in TAGS and frame.text:
                out[frame.desc.upper()] = str(frame.text[0])
    elif isinstance(f, MP4):
        for k in TAGS:
            v = tags.get(f"----:com.apple.iTunes:{k}")
            if v:
                out[k] = bytes(v[0]).decode("utf-8", "replace")
    else:   # Ogg (Opus, Vorbis), FLAC: Vorbis comments
        for k in TAGS:
            v = tags.get(k) or tags.get(k.lower())
            if v:
                out[k] = str(v[0])
    for k in ("R128_TRACK_GAIN", "R128_ALBUM_GAIN"):   # the Opus-specific value also counts as "already present"
        try:
            if tags.get(k):
                out[k] = str(tags.get(k)[0])
        except (TypeError, ValueError, KeyError):
            pass
    return out


def read_tags(path):
    import mutagen
    f = mutagen.File(str(path))
    return _read(f) if f is not None else {}


def _set(f, values):
    from mutagen.id3 import ID3, TXXX
    from mutagen.mp4 import MP4, MP4FreeForm
    if f.tags is None:
        f.add_tags()
    if isinstance(f.tags, ID3):
        for k, v in values.items():
            f.tags.delall(f"TXXX:{k}")
            f.tags.add(TXXX(encoding=3, desc=k, text=[v]))
        # keep the version of the file: some players (and Windows) read only ID3v2.3
        f.save(v2_version=3 if f.tags.version[:2] <= (2, 3) else 4)
        return
    elif isinstance(f, MP4):
        for k, v in values.items():
            f.tags[f"----:com.apple.iTunes:{k}"] = [MP4FreeForm(v.encode("utf-8"))]
    else:
        for k, v in values.items():
            f.tags[k] = [v]
    f.save()


def linked(path):
    """Has the file a second name (hard link)? Then it is left as it is (see above)."""
    return os.stat(path).st_nlink > 1


def _keep_owner(tmp, st, owner):
    """Owner and permissions of the original for the new file. If the owner cannot be set (not allowed without root),
    the owner from the settings like for new files."""
    try:
        os.chown(tmp, st.st_uid, st.st_gid)
    except OSError:
        from .opus import _own
        _own(tmp, owner, st.st_mode & 0o7777)
    try:
        os.chmod(tmp, st.st_mode & 0o7777)   # after chown: that may clear special bits
    except OSError:
        pass


def write_tags(path, values, owner=None):
    """Write the values into a copy, check it, then replace the original. -> True or an error text."""
    import mutagen
    path = Path(path)
    tmp = None
    try:
        st = os.stat(path)
        if st.st_nlink > 1:
            return _s("the file has a second name (hard link) – left unchanged")
        before = mutagen.File(str(path))
        if before is None:
            return _s("unknown format")
        length = before.info.length
        tmp = temp_copy(path, path, "tuttiphon-rg")   # a new file under a unique name – never through a link
        f = mutagen.File(str(tmp))
        _set(f, values)
        check = mutagen.File(str(tmp))
        got = _read(check)
        if any(got.get(k) != v for k, v in values.items()):
            return _s("values not readable after writing")
        if abs(check.info.length - length) > 0.5:
            return _s("length has changed")
        _keep_owner(tmp, st, owner)
        os.replace(tmp, path)
        return True
    except Exception as e:   # noqa: BLE001 – one file must not stop the run; the original stays
        return str(e) or type(e).__name__
    finally:
        if tmp is not None:
            tmp.unlink(missing_ok=True)


# ---------------------------------------------------------------------------- Run

def pending(cfg, lib):
    """How many songs are still to be measured or written (0 if turned off or not possible)."""
    if not settings(cfg)["enabled"] or not available()[0]:
        return 0
    songs = load().get("songs") or {}
    n = 0
    for i, s in enumerate(lib.songs):
        e = songs.get(s["id"])
        if e is None:
            n += bool(lib.real_path(i))   # without a file path nothing can be measured
        elif e.get("l") is not None and not e.get("w") and not e.get("x") and time.time() - e.get("h", 0) > LINK_RETRY:
            n += 1
    return n


def run(cfg, lib, log=print, stop=None, budget=None, until=None, track=None, dry_run=False):
    """Measure what is missing, then write tags where something changed. -> {"measured", "written", "skipped", "errors"}"""
    st = settings(cfg)
    out = {"measured": 0, "written": 0, "skipped": 0, "errors": 0, "linked": 0}
    if not st["enabled"]:
        return out
    ok, why = available()
    if not ok:
        log(_s("Even out loudness: {reason} – skipped.", reason=why))
        return out
    from .opus import music_dir
    root = music_dir(cfg=cfg)
    an = cfg["settings"].get("analysis") or {}
    minutes = an.get("budgetMinutes", 10) if budget is None else budget
    deadline = time.time() + minutes * 60 if minutes else None
    if until:
        deadline = min(deadline or until, until)
    workers = max(1, int(an.get("workers") or max(1, (os.cpu_count() or 2) // 2)))
    with _lock:
        data = load()
        songs = data.setdefault("songs", {})
        index = {}
        for i, s in enumerate(lib.songs):
            rel = lib.real_path(i)
            if rel:
                index[s["id"]] = (i, rel)
        todo = [sid for sid, (_, rel) in index.items() if (songs.get(sid) or {}).get("path") != rel]
        if deadline and todo:
            log(_s("Loudness: {done} songs measured, {open} pending (until {time}).", done=len(index) - len(todo),
                   open=len(todo), time=time.strftime("%H:%M", time.localtime(deadline))))
        else:
            log(_s("Loudness: {done} songs measured, {open} pending.", done=len(index) - len(todo), open=len(todo)))
        last_save = time.time()

        def one(sid):
            if (stop and stop()) or (deadline and time.time() > deadline):
                return sid, "later"
            i, rel = index[sid]
            return sid, measure(root / rel, track=track)

        with ThreadPoolExecutor(max_workers=workers) as pool:
            for sid, res in pool.map(one, todo):
                if res == "later":
                    continue
                i, rel = index[sid]
                if res is None:
                    out["errors"] += 1
                    songs[sid] = {"path": rel, "err": 1}
                else:
                    out["measured"] += 1
                    songs[sid] = {"path": rel, "l": round(res[0], 2), "p": round(res[1], 2),
                                  "d": int(lib.songs[i].get("duration") or 0)}
                if time.time() - last_save > 60 and not dry_run:
                    save(data)
                    last_save = time.time()
        if out["measured"] or out["errors"]:
            if out["errors"]:
                log(_s("  {measured} measured, {errors} not measurable.", measured=out["measured"], errors=out["errors"]))
            else:
                log(_s("  {measured} measured.", measured=out["measured"]))
        if not (stop and stop()):
            _write_all(lib, root, songs, index, st, cfg, out, log, stop, deadline, dry_run)
        if not dry_run:
            save(data)
    if out["written"]:
        log(_s("Loudness: ReplayGain values added to {n} songs – Navidrome reads them at the next scan.", n=out["written"]))
    if out["linked"]:
        log(_sn(out["linked"], "Loudness: {n} song has a second name (hard link, e.g. a download that is still being "
                               "shared) – it gets its values once the link is gone.",
                "Loudness: {n} songs have a second name (hard link, e.g. a download that is still being shared) – they "
                "get their values once the link is gone."))
    return out


def _write_all(lib, root, songs, index, st, cfg, out, log, stop, deadline, dry_run):
    """Write the tags for every fully measured album (or every song when album values are off)."""
    owner = (cfg["settings"].get("opus") or {}).get("owner")
    albums = {}
    for sid, (i, _) in index.items():
        albums.setdefault(lib.songs[i].get("albumId") or sid, []).append(sid)
    shown = 0
    for album_id, ids in albums.items():
        if (stop and stop()) or (deadline and time.time() > deadline):
            break
        measured = [songs[sid] for sid in ids if (songs.get(sid) or {}).get("l") is not None]
        if not measured or len(measured) + sum(1 for sid in ids if (songs.get(sid) or {}).get("err")) < len(ids):
            continue   # album not fully measured yet
        album = album_loudness([(e["l"], e["p"], e.get("d") or 0) for e in measured]) if st.get("album", True) else None
        for sid in ids:
            e = songs.get(sid) or {}
            if e.get("l") is None or e.get("x"):
                continue
            values = tag_values((e["l"], e["p"]), album)
            sig = values["REPLAYGAIN_TRACK_GAIN"] + "|" + values.get("REPLAYGAIN_ALBUM_GAIN", "")
            if e.get("w") == sig:
                continue
            path = root / index[sid][1]
            try:
                present = read_tags(path)
            except Exception:   # noqa: BLE001 – file not readable right now: next time
                continue
            if present and not e.get("w"):   # values from another source (e.g. set on import) – do not touch
                e["x"] = 1
                out["skipped"] += 1
                continue
            try:
                if linked(path):   # e.g. a download still being shared: later, once the link is gone
                    e["h"] = int(time.time())
                    out["linked"] += 1
                    continue
            except OSError:
                continue
            if dry_run:
                out["written"] += 1
                continue
            res = write_tags(path, values, owner)
            if res is True:
                e["w"] = sig
                e.pop("h", None)
                out["written"] += 1
            else:
                out["errors"] += 1
                if shown < 10:
                    shown += 1
                    log(_s("  ⚠ {path}: {error} – file unchanged.", path=index[sid][1], error=res))
