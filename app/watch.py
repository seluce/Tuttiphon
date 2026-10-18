"""Folder watch (optional): detect new music in the music folder and process it right away –
convert to Opus or AAC, search lyrics, let Navidrome scan, rate with Deezer.

Works by looking regularly (not via file system events) – this also works over NFS/SMB and in the container.
New = the file was created or moved after the last look (ctime), has been unchanged for a few minutes (Lidarr may
still be writing) and was not under this path at the last look (state/watch_files.json) – so changing permissions
or tags does not turn the whole library into “new music”. Opus files that Tuttiphon itself has just created
(opus.RECENT) do not count as new.

Only what has changed is read: for every folder Tuttiphon remembers the modification time, the audio files and the
subfolders (state/watch_files.json). A new, deleted or renamed file changes the time of its folder – all other
folders are only glanced at, their files not checked one by one.
"""
import json
import os
import time
from pathlib import Path

from .config import STATE_DIR, load_config, paths, read_text, write_atomic
from .i18n import _sn
from .lyrics import AUDIO
from .opus import EXTENSIONS, RECENT, SKIP_DIRS

STATE_FILE = STATE_DIR / "watch.json"
FILES_FILE = STATE_DIR / "watch_files.json"   # folders with time, audio files and subfolders from the last look
SETTLE = 120   # seconds without change before a file counts as finished


def state():
    try:
        data = json.loads(read_text(STATE_FILE))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def _save(data):
    try:
        write_atomic(STATE_FILE, json.dumps(data))
    except OSError:
        pass


def _load_files():
    """-> (known paths or None, folder states or None). Also reads the older form (only a list of the paths)."""
    try:
        data = json.loads(read_text(FILES_FILE))
    except (OSError, ValueError):
        return None, None
    if isinstance(data, list):
        return set(data), None
    dirs = data.get("dirs") if isinstance(data, dict) else None
    if not isinstance(dirs, dict):
        return None, None
    return _paths(dirs), dirs


def _paths(dirs):
    return {f"{d}/{n}" if d else n for d, entry in dirs.items() for n in entry[1]}


def _known():
    return _load_files()[0]


def find_new(root, since, until, known=None):
    """-> (new files, all finished files relative to root). known: paths from last time (None = do not check)."""
    new, seen, _ = scan(root, since, until, known)
    return new, seen


def scan(root, since, until, known=None, dirs=None):
    """-> (new files, all finished files relative to root, folder states).

    dirs: folder states from last time – {folder relative to root: [modification time in ns or None, [audio files],
    [subfolders]]}. If the time of a folder stayed the same, its entries from back then apply. A time is only
    remembered when everything in the folder was finished and it was not changed just now – otherwise it is read
    again next time."""
    lossless = tuple(e for exts in EXTENSIONS.values() for e in exts)
    base = str(root)
    out, seen, now = [], set(), {}
    stack = [""]
    while stack:
        rel_dir = stack.pop()
        full = os.path.join(base, rel_dir) if rel_dir else base
        try:
            mtime = os.stat(full).st_mtime_ns
        except OSError:
            continue
        join = (lambda n: f"{rel_dir}/{n}") if rel_dir else (lambda n: n)
        old = (dirs or {}).get(rel_dir)
        if old and old[0] is not None and old[0] == mtime:   # unchanged: do not read again
            now[rel_dir] = old
            seen.update(join(n) for n in old[1])
            stack.extend(join(d) for d in old[2])
            continue
        try:
            with os.scandir(full) as it:
                entries = list(it)
        except OSError:
            continue
        names, subdirs, complete = [], [], True
        for e in entries:
            name = e.name
            try:
                if e.is_dir():
                    if not e.is_symlink() and not name.startswith(SKIP_DIRS):
                        subdirs.append(name)
                    continue
            except OSError:
                complete = False
                continue
            low = name.lower()
            if name.startswith((".", "._")) or not (low.endswith(AUDIO) or low.endswith(lossless)):
                continue
            path = Path(full) / name
            if str(path) in RECENT:   # just converted by Tuttiphon itself – known, not new music
                names.append(name)
                seen.add(join(name))
                continue
            try:
                st = e.stat()
            except OSError:
                complete = False
                continue
            changed = max(st.st_ctime, st.st_mtime)
            if changed > until:
                complete = False
                continue   # may still be being written – next time
            names.append(name)
            seen.add(join(name))
            if since < changed and (known is None or join(name) not in known):
                out.append(path)
        names.sort()
        subdirs.sort()
        now[rel_dir] = [mtime if complete and mtime / 1e9 < until else None, names, subdirs]
        stack.extend(join(d) for d in subdirs)
    return sorted(out), seen, now


def check(runner, log=lambda *_: None):
    """Look once; starts a run when there is new music. -> number of new files (or None when it is not due)."""
    cfg = load_config()
    wt = cfg["settings"].get("watch") or {}
    data = state()
    if not wt.get("enabled"):
        if data.get("last"):   # turned off: when turned on again, watch from then on, not retroactively
            _save({})
        return None
    now = time.time()
    if not data.get("last"):   # just turned on: watch from now on, not the whole library
        _save({**data, "last": now - SETTLE, "checked": now, "found": 0})
        return 0
    if now - data.get("checked", 0) < (wt.get("interval") or 15) * 60 or runner.running():
        return None
    for k in [k for k, t in list(RECENT.items()) if now - t > 86400]:   # only remember the last 24 h
        RECENT.pop(k, None)
    root = paths(cfg)["music"]
    until = now - SETTLE
    if not root.is_dir():
        return None
    known, dirs = _load_files()
    new, seen, now_dirs = scan(root, data["last"] - 5, until, known, dirs)
    if known is None:
        new = []   # first look with a path list: only remember what is there
    data.update(checked=now)

    def remember():   # remember only when the files are processed – otherwise they would not count as new next time
        if now_dirs == dirs:   # nothing changed: do not rewrite the file (a few MB) every 15 minutes
            return
        try:
            write_atomic(FILES_FILE, json.dumps({"v": 2, "dirs": now_dirs}, ensure_ascii=False, separators=(",", ":")))
        except OSError:
            pass
    if not new:
        remember()
        data.update(last=until)
        _save(data)
        return 0
    lossless = tuple(e for exts in EXTENSIONS.values() for e in exts)
    steps = []
    if wt.get("convert", True) and (cfg["settings"].get("opus") or {}).get("enabled", True) and any(p.name.lower().endswith(lossless) for p in new):
        steps.append("flac")
    if wt.get("lyrics", True):
        steps.append("lyrics")
    steps.append("scan")
    an = cfg["settings"].get("analysis") or {}
    if an.get("enabled", True):
        # sound of the new songs (after the scan, when Navidrome knows them) – only theirs (new_files): the backlog of
        # the library waits for the regular runs, the playlists after it do not
        steps.append("analyse")
        if an.get("classify", "suggest") == "auto" or (an.get("classify", "suggest") == "suggest" and an.get("autoNew", True)):
            steps += ["playlists", "scan"]   # newly classified bands go into the playlists of the music world right away
    if wt.get("deezer", True):
        steps.append("deezer")
    try:   # hand over the new files directly: they have been unchanged for SETTLE seconds (otherwise Opus would wait minAgeMinutes)
        runner.start(steps, name=_sn(len(new), "Process new music ({n} file)", "Process new music ({n} files)"),
                     lyrics_files=[str(p) for p in new], flac_files=[str(p) for p in new if p.name.lower().endswith(lossless)],
                     new_files=[str(p) for p in new], deezer_mode="new")
    except RuntimeError:
        return None   # something is running right now -> next time (path list and time window stay as they are)
    remember()
    data.update(last=until, found=len(new), lastRun=time.strftime("%d.%m.%Y %H:%M"))
    _save(data)
    log(_sn(len(new), "{n} new file found", "{n} new files found"))
    return len(new)
