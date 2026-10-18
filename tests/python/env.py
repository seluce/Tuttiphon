"""Test environment – must be loaded BEFORE any import of app.* (`from tests.python import env`).

app/config.py already reads TUTTIPHON_DATA, TUTTIPHON_BASE etc. on import. This module
* creates a fresh temp folder: data/ (data folder), navidrome/ (TUTTIPHON_BASE with Music/00_SmartPlaylists
  and Archiv/) and shared/ (TUTTIPHON_SHARED_DIR for instance registration and run lock),
* removes credentials and storage locations from the environment (NAV_*, TUTTIPHON_*, old NAVITOOL_*, MUSIC_DIR, PLAYLIST_DIR, ARCHIVE_DIR …),
* blocks network access (Navidrome, Deezer, Last.fm, LRCLIB) – a mistake fails immediately instead of sending anything,
* checks after importing app.config that the temp folder is really used, and removes it at the end.
"""
import atexit
import copy
import os
import shutil
import socket
import sys
import tempfile
from pathlib import Path

if any(name == "app" or name.startswith("app.") for name in sys.modules):
    raise RuntimeError("tests.python.env must be loaded before any import of app.* – otherwise the paths "
                       "point to the real data.")

ROOT = Path(tempfile.mkdtemp(prefix="tuttiphon-test-"))
DATA = ROOT / "data"
BASE = ROOT / "navidrome"
MUSIC = BASE / "Music"
PLAYLISTS = MUSIC / "00_SmartPlaylists"
ARCHIVE = BASE / "Archiv"
SHARED = ROOT / "shared"
for _d in (DATA, PLAYLISTS, ARCHIVE, SHARED):
    _d.mkdir(parents=True, exist_ok=True)

_DROP = ("MUSIC_DIR", "PLAYLIST_DIR", "ARCHIVE_DIR", "RATING_USERS", "LASTFM_API_KEY", "NTFY_TOKEN")
for _key in list(os.environ):
    if _key.startswith(("NAV_", "TUTTIPHON_", "NAVITOOL_")) or _key in _DROP:
        del os.environ[_key]
os.environ.update(TUTTIPHON_DATA=str(DATA), TUTTIPHON_BASE=str(BASE), TUTTIPHON_SHARED_DIR=str(SHARED),
                  TUTTIPHON_NO_SCHEDULER="1", TUTTIPHON_WEB=str(ROOT / "web"))


# --------------------------------------------------------------------------- no network

class NetworkBlocked(OSError):
    pass


def _blocked(*args, **kwargs):
    raise NetworkBlocked("Network access is blocked in the tests")


_real_connect = socket.socket.connect
_real_connect_ex = socket.socket.connect_ex


def _guard_connect(self, address):
    if self.family in (socket.AF_INET, socket.AF_INET6):
        _blocked()
    return _real_connect(self, address)


def _guard_connect_ex(self, address):
    if self.family in (socket.AF_INET, socket.AF_INET6):
        _blocked()
    return _real_connect_ex(self, address)


socket.getaddrinfo = _blocked
socket.create_connection = _blocked
socket.socket.connect = _guard_connect
socket.socket.connect_ex = _guard_connect_ex


# --------------------------------------------------------------------------- load and check app

from app import config  # noqa: E402

if config.DATA_DIR != DATA or config.BASE != BASE:
    raise RuntimeError(f"app.config does not use the test folder ({config.DATA_DIR}) – aborting.")
_err = config.ensure_dirs()
if _err:
    raise RuntimeError(_err)


def _cleanup():
    shutil.rmtree(ROOT, ignore_errors=True)


atexit.register(_cleanup)


# --------------------------------------------------------------------------- helpers for the tests

def german(target):
    """Run a test (class) with German as the server language. Such tests check the German texts existing installations
    see – logs, messages, playlist names – exactly as they were before the interface became bilingual."""
    from unittest import mock
    return mock.patch("app.i18n.server_lang", new=lambda: "de")(target)


def reset_caches():
    """Clear the modules' caches (configuration, .env, sessions, accounts, instance folder)."""
    config._env_cache.update(key=None, env=None)
    config._cfg_cache.update(key=None, cfg=None)
    for name, attr, value in (("app.auth", "_users", {"at": 0.0, "list": []}),
                              ("app.auth", "_sessions_cache", {"key": None, "data": {}})):
        mod = sys.modules.get(name)
        if mod is not None:
            getattr(mod, attr).clear()
            getattr(mod, attr).update(copy.deepcopy(value))
    inst = sys.modules.get("app.instances")
    if inst is not None:
        inst._state.update(dir=None, at=0.0, install=None)


def clear_dir(path):
    """Empty a test folder (only inside the temp folder)."""
    path = Path(path)
    if ROOT not in path.parents:
        raise RuntimeError(f"{path} is not inside the test folder")
    if path.is_dir():
        for child in path.iterdir():
            if child.is_dir() and not child.is_symlink():
                shutil.rmtree(child)
            else:
                child.unlink()
