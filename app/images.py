"""Fetch covers and artist images from Navidrome and cache them on disk.

The interface loads images only through Tuttiphon's /img/<id> – the Navidrome credentials stay in the server.
"""
import hashlib
import json
import re
import threading
import time
from collections import OrderedDict

from .config import STATE_DIR, load_env, read_bytes, read_text, write_atomic
from .i18n import _
from .navidrome import Navidrome, NavidromeError

CACHE_DIR = STATE_DIR / "cache" / "img"
INFO_FILE = STATE_DIR / "cache" / "artist_info.json"
SIZES = (64, 150, 300, 600)
MAX_AGE = 14 * 86400   # after that fetch fresh from Navidrome (a changed cover shows up on its own this way)
VALID_ID = re.compile(r"^[A-Za-z0-9_:.\-]{3,120}$")
_info_lock = threading.Lock()
_info = None


def _client():
    env = load_env()
    return Navidrome(env["NAV_URL"], env.get("NAV_ADMIN_USER"), env.get("NAV_ADMIN_PASS"))


def get_image(cover_id, size):
    """-> (bytes, content_type) or None if Navidrome has no image."""
    if not VALID_ID.match(cover_id or ""):
        raise ValueError(_("invalid image ID"))
    size = min(SIZES, key=lambda s: abs(s - int(size or 300)))
    key = hashlib.sha1(f"{cover_id}|{size}".encode()).hexdigest()
    folder = CACHE_DIR / key[:2]
    stale = None
    for ext in ("webp", "jpeg", "png"):
        path = folder / f"{key}.{ext}"
        if path.exists():
            try:
                data = read_bytes(path)
                fresh = time.time() - path.stat().st_mtime < MAX_AGE
            except OSError:
                break
            if fresh:
                return data, f"image/{ext}"
            stale = (data, f"image/{ext}", path)
            break
    try:
        data, ctype = _client().cover_art(cover_id, size)
    except NavidromeError:
        return stale[:2] if stale else None   # Navidrome gone right now: rather the old image
    if not data or not ctype.startswith("image/"):
        if stale:
            stale[2].unlink(missing_ok=True)   # Navidrome has no image any more
        return None
    ext = "webp" if "webp" in ctype else "png" if "png" in ctype else "jpeg"
    try:
        folder.mkdir(parents=True, exist_ok=True)
        if stale and stale[2].suffix != f".{ext}":
            stale[2].unlink(missing_ok=True)
        write_atomic(folder / f"{key}.{ext}", data)
    except OSError:
        pass   # the cache is optional
    return data, f"image/{ext}"


_live = OrderedDict()   # the playlist covers shown last (at most 200)
_live_lock = threading.Lock()   # parallel requests (ThreadingHTTPServer) change _live


def live_image(cover_id, size, version):
    """Images that change (playlist covers): not on disk, only briefly in memory – key with version."""
    if not VALID_ID.match(cover_id or "") or not cover_id.startswith("pl-"):
        raise ValueError(_("invalid image ID"))
    size = min(SIZES, key=lambda s: abs(s - int(size or 300)))
    key = (cover_id, size, version)
    with _live_lock:
        hit = _live.get(key)
        if hit is not None:
            _live.move_to_end(key)
            return hit
    try:
        data, ctype = _client().cover_art(cover_id, size)
    except NavidromeError:
        return None
    if not data or not ctype.startswith("image/"):
        return None
    with _live_lock:
        for k in [k for k in _live if k[:2] == key[:2]]:   # older versions of the same cover
            del _live[k]
        _live[key] = (data, ctype)
        while len(_live) > 200:
            _live.popitem(last=False)
    return data, ctype


def artist_info(artist_id):
    """Biography & similar artists (Navidrome fetches them from Last.fm/Deezer). Cached for a week."""
    global _info
    with _info_lock:
        if _info is None:
            try:
                _info = json.loads(read_text(INFO_FILE))
            except (OSError, ValueError):
                _info = {}
        hit = _info.get(artist_id)
    if hit and time.time() - hit.get("t", 0) < 7 * 86400:
        return hit
    try:
        raw = _client().call("getArtistInfo2", id=artist_id, count=12).get("artistInfo2", {})
    except NavidromeError:
        return hit or {}
    bio = re.sub(r"<a [^>]*>.*?</a>", "", raw.get("biography") or "").strip()
    entry = {"t": time.time(), "bio": bio, "url": raw.get("lastFmUrl"),
             "similar": [a.get("name") for a in raw.get("similarArtist", []) if a.get("name")]}
    with _info_lock:
        _info[artist_id] = entry
        try:
            INFO_FILE.parent.mkdir(parents=True, exist_ok=True)
            write_atomic(INFO_FILE, json.dumps(_info, ensure_ascii=False))
        except OSError:
            pass   # only a cache – try again next time
    return entry
