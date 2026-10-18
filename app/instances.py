"""Detect several Tuttiphon instances (PC and Docker container) and lock runs against each other.

PC and container do not necessarily share the data folder (PC: data/, container: /config) – but they surely share
the playlist folder on the NAS share that Navidrome reads. So the announcement and the lock live in a hidden
subfolder there: <playlist folder>/.tuttiphon/ (Navidrome skips hidden folders). If .navitool/ already exists there
(from the time when Tuttiphon was called NaviTool), that folder stays in use – so old and new instances still see
each other.

* Every instance writes its own file instance-<id>.json every minute with a timestamp and “is a run going on?”.
* Each installation (data folder) has its own random id (state/install_id). Reports with the own installation id come
  from the same installation – e.g. the container before an update with another host name, or a run from the command
  line – and are not "a second Tuttiphon".
* Before a run, Tuttiphon checks these announcements and takes a lock on .tuttiphon/task.lock (tasks._InstanceLock).

TUTTIPHON_SHARED_DIR sets the folder (test servers – they must not touch the real playlist folder). If the playlist
folder is not writable, Tuttiphon falls back to state/ (then only instances with a shared data folder see each other).
"""
import json
import os
import re
import secrets
import socket
import time
from pathlib import Path

from .config import STATE_DIR, env_var, load_config, read_text, write_atomic

IN_DOCKER = os.path.exists("/.dockerenv") or env_var("DOCKER") == "1"
# one entry per computer/container (without process id) – a restart is not a "second instance".
# Runs from the command line (tuttiphon.py run) announce themselves with their own id (use_cli_id), otherwise they
# would overwrite the announcement of the server on the same computer.
INSTANCE_ID = f"{'docker' if IN_DOCKER else 'pc'}:{socket.gethostname()}"
FRESH = 180   # seconds: an announcement counts as “still running” for this long
_state = {"running": False, "dir": None, "at": 0.0, "install": None}


def install_id():
    """Random id of this installation, kept in its data folder – the same across restarts, updates and a new host
    name. Not part of backups: a copy elsewhere is another installation."""
    if _state.get("install"):
        return _state["install"]
    path = STATE_DIR / "install_id"
    try:
        value = read_text(path, attempts=2).strip()
    except FileNotFoundError:
        value = ""
    except OSError:   # briefly unreadable: no new id (that would look like another installation) – try again later
        return ""
    if not re.fullmatch(r"[0-9a-f]{16}", value):
        value = secrets.token_hex(8)
        try:
            write_atomic(path, value + "\n", mode=0o644)
        except OSError:
            pass
    _state["install"] = value
    return value


def _named(parent):
    """<playlist folder>/.tuttiphon – or .navitool, as long as only the old folder exists."""
    new, old = parent / ".tuttiphon", parent / ".navitool"
    return old if old.is_dir() and not new.exists() else new


def shared_dir():
    """Folder for announcement and lock (created, writable for all instances). Remembered for one minute."""
    if _state["dir"] is not None and time.time() - _state["at"] < 60:
        return _state["dir"]
    target = env_var("SHARED_DIR")
    if target:
        folder = Path(target)
    else:
        from .playlists import playlist_dir
        try:
            folder = _named(playlist_dir(load_config()))
        except Exception:   # settings broken or similar – then locally
            folder = STATE_DIR
    try:
        if folder.is_symlink():   # a link instead of the folder: someone else's doing – do not follow it
            raise PermissionError(str(folder))
        folder.mkdir(parents=True, exist_ok=True)
        try:
            # PC and container may run as different users – through the opened folder, never through a link
            fd = os.open(folder, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0))
            try:
                os.fchmod(fd, 0o777)
            finally:
                os.close(fd)
        except OSError:
            pass
        if not os.access(folder, os.W_OK):
            raise PermissionError(str(folder))
    except OSError:
        folder = STATE_DIR
    _state.update(dir=folder, at=time.time())
    return folder


def use_cli_id():
    """For tuttiphon.py run: own id with process id (the file is removed at the end of the run)."""
    global INSTANCE_ID
    INSTANCE_ID = f"{INSTANCE_ID}:run-{os.getpid()}"
    _state["cli"] = True


def _file(instance_id):
    return shared_dir() / ("instance-" + re.sub(r"[^\w.-]", "_", instance_id) + ".json")


def heartbeat(running=None):
    """Write the own announcement. running: True/False when it changes right now (start/end of a run)."""
    if running is not None:
        _state["running"] = running
    if _state.get("cli") and running is False:   # command line: run over -> announcement gone
        try:
            _file(INSTANCE_ID).unlink()
        except OSError:
            pass
        return
    try:
        write_atomic(_file(INSTANCE_ID), json.dumps({"id": INSTANCE_ID, "ts": time.time(), "host": socket.gethostname(),
                                                      "docker": IN_DOCKER, "running": _state["running"],
                                                      "install": install_id()}), mode=0o666)
    except OSError:
        pass


def others(max_age=FRESH, foreign_only=False):
    """Other instances that announced themselves in the last max_age seconds. foreign_only: only other installations
    (for the notice "running twice") – without reports of the own installation under another id."""
    now = time.time()
    own = install_id() if foreign_only else None
    out = []
    try:
        files = list(shared_dir().glob("instance-*.json"))
    except OSError:
        return []
    for path in files:
        try:
            data = json.loads(read_text(path, attempts=2))
        except (OSError, ValueError):
            continue
        if not isinstance(data, dict) or data.get("id") == INSTANCE_ID or (own and data.get("install") == own):
            continue
        ts = data.get("ts")
        if not isinstance(ts, (int, float)) or isinstance(ts, bool):   # broken or foreign file
            continue
        age = now - ts
        if age < max_age:
            out.append({"host": data.get("host"), "docker": bool(data.get("docker")), "running": bool(data.get("running"))})
        elif age > 7 * 86400:
            try:
                path.unlink()   # instance gone long ago
            except OSError:
                pass
    return out


def busy_elsewhere():
    """Is another instance working on a run right now?"""
    return any(o["running"] for o in others())
