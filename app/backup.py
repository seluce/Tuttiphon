"""Built-in backup: configuration, credentials and the important state as a ZIP.

* Once a day (from the time of the daily refresh on) and at the push of a button (Settings → Backup).
* Contents: config.json, .env, state/ (without image cache, sessions, locks) and backup/ (backed-up original
  playlists *.nsp/*.m3u). Not the logs (logs/) – they are only
  for reading up. Never earlier backups: nothing from the backup folder and no file named like a backup – otherwise
  a backup folder inside the data folder would make every ZIP contain all the earlier ones.
* Location: settings.backup.dir – empty = <data folder>/sicherungen. Better a folder on another device (another disk,
  an externally backed-up folder), then the backup also survives a disk failure. Relative paths are relative to the
  Navidrome folder (TUTTIPHON_BASE). Not inside state/ or backup/ of the data folder (the setting refuses it).
* The newest settings.backup.keep backups are kept (default 14).
* The file contains credentials – it is written with the permissions 600 and only delivered to administrators.

Restoring (deliberately by hand, Tuttiphon must be stopped for it): stop the container/program, unpack the ZIP into
the data folder (overwrites config.json, .env, state/ …), start again.
"""
import datetime as dt
import os
import re
import secrets
import time
import zipfile
from pathlib import Path

from .config import BACKUP_DIR, BASE, CONFIG_FILE, DATA_DIR, ENV_FILE, STATE_DIR, load_config
from .i18n import _, _sn

PREFIX = "tuttiphon-sicherung-"   # file name (data)
NAME = re.compile(rf"^{PREFIX}(\d{{4}}-\d{{2}}-\d{{2}}_\d{{6}})\.zip$")
# cache, logins and locks do not belong in a backup – nor the id of the installation (a restored copy elsewhere is
# another installation, see instances.install_id)
SKIP_STATE = ("cache", "sessions.json", "task.lock", "install_id")
# can be rebuilt at any time (lyrics index, file states for the folder watch, audio fingerprints – large, renewed at
# night by themselves) or was put aside as broken
SKIP_NAMES = re.compile(r"^(liedtexte\.db.*|watch_files\.json|fingerprints\.json)$|\.defekt-")
# what belongs in backup/: backed-up original playlists
KEEP_BACKUP = re.compile(r"\.(nsp|m3u)$", re.I)
_items = {"key": None, "list": []}


def settings(cfg=None):
    return {"enabled": True, "keep": 14, "dir": "", **((cfg or load_config())["settings"].get("backup") or {})}


def folder(cfg=None):
    """Backup folder: the setting, otherwise BACKUP_DIR (docker-compose, e.g. /backup on another disk), otherwise in
    the data folder."""
    d = str(settings(cfg).get("dir") or os.environ.get("BACKUP_DIR") or "").strip()
    if not d:
        return DATA_DIR / "sicherungen"
    return Path(d) if os.path.isabs(d) else BASE / d


def _files(target=None):
    """(path, name in the ZIP) for everything that is backed up. target: the backup folder – if it lies in state/ or
    backup/, nothing from it (and never a ZIP: Tuttiphon keeps none there – it can only be an earlier backup)."""
    target = os.path.realpath(target) if target else None
    for path, arc in ((CONFIG_FILE, "config.json"), (ENV_FILE, ".env")):
        if path.is_file():
            yield path, arc
    for root, top in ((STATE_DIR, "state"), (BACKUP_DIR, "backup")):
        if not root.is_dir():
            continue
        for path in sorted(root.rglob("*")):
            rel = path.relative_to(root)
            if not path.is_file() or path.name.lower().endswith((".tmp", ".zip")) or path.name.startswith("."):
                continue
            if (target and target != os.path.realpath(root)
                    and (os.path.realpath(path.parent) + os.sep).startswith(target + os.sep)):
                continue   # the backup folder is a subfolder here: what lies in it does not go into the next backup
            if top == "state" and (rel.parts[0] in SKIP_STATE or path.name.startswith("instance-") or SKIP_NAMES.search(path.name)):
                continue
            if top == "backup" and not KEEP_BACKUP.search(path.name):
                continue
            yield path, f"{top}/{rel.as_posix()}"


def create(cfg=None, log=print):
    """Write a backup and remove old ones. -> {"name", "size", "files"}"""
    cfg = cfg or load_config()
    target = folder(cfg)
    target.mkdir(parents=True, exist_ok=True)
    name = f"{PREFIX}{dt.datetime.now():%Y-%m-%d_%H%M%S}.zip"
    tmp = target / f".{name}.{os.getpid()}.{secrets.token_hex(4)}.tmp"
    count = 0
    try:
        # contains credentials – 0600 from the start; O_EXCL/O_NOFOLLOW: always a new file of its own
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0), 0o600)
        with os.fdopen(fd, "wb") as raw, zipfile.ZipFile(raw, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as z:
            for path, arc in _files(target):
                try:
                    z.write(path, arc)
                    count += 1
                except OSError as e:   # a file being replaced right now (NFS) must not prevent the backup …
                    if arc in ("config.json", ".env"):   # … but without settings or credentials it is no backup
                        raise
                    log(f"  ⚠ {arc}: {e}")
        os.chmod(tmp, 0o600)   # contains credentials
        os.replace(tmp, target / name)
    finally:
        tmp.unlink(missing_ok=True)
    prune(cfg)
    size = (target / name).stat().st_size
    log(_sn(count, "Backup {name}: {n} file, {size} KB.", "Backup {name}: {n} files, {size} KB.", name=name, size=size // 1024))
    return {"name": name, "size": size, "files": count}


def items(cfg=None):
    """Existing backups, newest first. Cached until the folder changes (the schedule asks every minute)."""
    target = folder(cfg)
    try:
        key = (str(target), target.stat().st_mtime_ns)
    except OSError:
        return []
    if _items["key"] == key:
        return list(_items["list"])
    out = []
    try:
        for p in target.iterdir():
            if NAME.match(p.name):
                st = p.stat()
                out.append({"name": p.name, "size": st.st_size, "time": dt.datetime.fromtimestamp(st.st_mtime).isoformat(timespec="minutes")})
    except OSError:
        return []
    out.sort(key=lambda x: NAME.match(x["name"]).group(1), reverse=True)
    _items.update(key=key, list=out)
    return list(out)


def prune(cfg=None):
    keep = max(1, int(settings(cfg).get("keep") or 14))
    for old in items(cfg)[keep:]:
        try:
            (folder(cfg) / old["name"]).unlink()
        except OSError:
            pass


def path_of(name, cfg=None):
    """File of a backup (only valid names – nothing outside the folder)."""
    if not NAME.match(name or ""):
        raise ValueError(_("Unknown backup"))
    p = folder(cfg) / name
    if not p.is_file():
        raise ValueError(_("Unknown backup"))
    return p


def done_today(cfg=None):
    today = f"{dt.date.today():%Y-%m-%d}_"
    return any(NAME.match(x["name"]).group(1).startswith(today) for x in items(cfg))


def status(cfg=None):
    cfg = cfg or load_config()
    target = folder(cfg)
    lst = items(cfg)
    return {**settings(cfg), "path": str(target), "exists": target.is_dir(),
            "writable": os.access(target if target.is_dir() else target.parent, os.W_OK),
            "items": lst, "last": lst[0] if lst else None, "checked": time.time()}
