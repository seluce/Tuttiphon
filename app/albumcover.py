"""Fetch missing album covers – only where there really is none.

* Candidates: albums for which Navidrome knows no image at all (neither a file in the folder nor one in the music
  files), whose songs are in exactly one folder that contains only this album and in which there is still no image
  file now (cover/folder/front/album.*).
* Lidarr saves covers itself when importing – so an album has to be in Navidrome for at least two days.
* Source: Cover Art Archive via the album's MusicBrainz ID (the same source as Lidarr), otherwise Deezer.
* Saved as cover.jpg (or cover.png) next to the music, with the permissions and the owner from the Opus settings;
  existing images are never overwritten. Navidrome reads the cover at the next scan.
* Covers not found are only tried again after 30 days (state/covers.json).
"""
import datetime as dt
import json
import os
import re
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import defaultdict

from .config import STATE_DIR, read_text, write_atomic
from .i18n import _s, _sn

STATE_FILE = STATE_DIR / "covers.json"
GRACE_DAYS = 2
RETRY_DAYS = 30
MAX_PER_RUN = 60
MIN_BYTES = 8000
_lock = threading.Lock()


def _ua():
    from .version import VERSION
    return f"Tuttiphon/{VERSION} (Musikverwaltung fuer Navidrome)"   # sent as it is (HTTP header)


def load_state():
    try:
        data = json.loads(read_text(STATE_FILE))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def save_state(data):
    write_atomic(STATE_FILE, json.dumps(data))


def due(days=7):
    """Time for the weekly search at night? (state/covers.json is written again after every run.)"""
    try:
        return time.time() - STATE_FILE.stat().st_mtime > days * 86400
    except OSError:
        return True


def _get(url, timeout=20):
    req = urllib.request.Request(url, headers={"User-Agent": _ua(), "Accept": "*/*"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read(), r.headers.get("Content-Type", "")


def _image(data):
    """-> ".jpg"/".png" for a usable image, otherwise None (too small, no image, below 250 pixels)."""
    if not data or len(data) < MIN_BYTES:
        return None
    ext = ".jpg" if data[:3] == b"\xff\xd8\xff" else ".png" if data[:8] == b"\x89PNG\r\n\x1a\n" else None
    if not ext:
        return None
    try:
        import io
        from PIL import Image
        with Image.open(io.BytesIO(data)) as im:
            if min(im.size) < 250:
                return None
    except ImportError:
        pass   # without Pillow: the file size has to do
    except Exception:   # noqa: BLE001 – broken image
        return None
    return ext


def _norm(text):
    text = re.sub(r"[\(\[][^\)\]]*[\)\]]", "", (text or "").lower())
    return re.sub(r"[^0-9a-zäöüß]+", " ", text).strip()   # i18n-ignore


def from_caa(album):
    for kind, mbid in (("release", album.get("mbz")), ("release-group", album.get("rg"))):
        if not mbid or not re.fullmatch(r"[0-9a-f-]{36}", mbid):
            continue
        try:
            data, _ = _get(f"https://coverartarchive.org/{kind}/{mbid}/front-500")
        except (urllib.error.URLError, OSError, ValueError):
            continue
        ext = _image(data)
        if ext:
            return data, ext, "Cover Art Archive"
    return None


def from_deezer(album):
    q = f'artist:"{album["artist"]}" album:"{album["name"]}"'
    try:
        data, _ = _get("https://api.deezer.com/search/album?" + urllib.parse.urlencode({"q": q, "limit": 5}))
        hits = json.loads(data).get("data") or []
    except (urllib.error.URLError, OSError, ValueError):
        return None
    want, artist = _norm(album["name"]), _norm(album["artist"])
    for h in hits:
        if _norm(h.get("title")) == want and _norm((h.get("artist") or {}).get("name")) == artist and h.get("cover_xl"):
            try:
                img, _ = _get(h["cover_xl"])
            except (urllib.error.URLError, OSError, ValueError):
                return None
            ext = _image(img)
            return (img, ext, "Deezer") if ext else None
    return None


def candidates(lib, root, albums_meta, state=None, today=None):
    """Albums without any image that Tuttiphon may fill. -> [{id, name, artist, folder, mbz, rg}]"""
    from .opus import _folder_has_cover
    today = today or dt.date.today()
    state = state or {}
    folders, albums_in = defaultdict(set), defaultdict(set)
    for i, s in enumerate(lib.songs):
        p = lib.real_path(i)
        if p and s.get("albumId"):
            folders[s["albumId"]].add(os.path.dirname(p))
            albums_in[os.path.dirname(p)].add(s["albumId"])
    out = []
    for a in albums_meta:
        if a.get("imageHash") or a.get("missing") or len(folders.get(a["id"], ())) != 1:
            continue
        if len(albums_in[next(iter(folders[a["id"]]))]) > 1:
            continue   # folder with several albums (singles, loose files): one cover.jpg would apply to all of them
        created = (a.get("createdAt") or "")[:10]
        if not created or created > (today - dt.timedelta(days=GRACE_DAYS)).isoformat():
            continue   # give Lidarr time to save its own cover
        last = state.get(a["id"])
        if last and last.get("t", 0) > time.time() - RETRY_DAYS * 86400:
            continue
        folder = root / next(iter(folders[a["id"]]))
        try:   # only folders that really are inside the music folder (no links leading out)
            if root.resolve() not in folder.resolve().parents:
                continue
        except OSError:
            continue
        if _folder_has_cover(folder):
            continue
        out.append({"id": a["id"], "name": a.get("name") or "", "artist": a.get("albumArtist") or "",
                    "folder": folder, "mbz": a.get("mbzAlbumId"), "rg": a.get("mbzReleaseGroupId")})
    return out


def run(cfg, lib, log=print, stop=None, dry_run=False):
    """Fetch missing covers. -> {"checked", "saved", "notFound", "skipped"}"""
    from .config import load_env
    from .navidrome import native_session
    from .opus import _folder_has_cover, _own, music_dir
    st = cfg["settings"].get("covers") or {}
    if not st.get("enabled", True):
        log(_s("Fetching missing covers is turned off."))
        return {"checked": 0, "saved": 0, "notFound": 0, "skipped": True}
    env = load_env()
    native = native_session(env["NAV_URL"], env.get("NAV_ADMIN_USER"), env.get("NAV_ADMIN_PASS"))
    meta = native._request("GET", "/api/album?_start=0&_end=100000")
    with _lock:
        state = load_state()
        todo = candidates(lib, music_dir(cfg=cfg), meta, state)
        if len(todo) > MAX_PER_RUN:
            log(_s("Albums without any cover: {n} – taking the first {max}.", n=len(todo), max=MAX_PER_RUN))
        else:
            log(_s("Albums without any cover: {n}", n=len(todo)))
        saved = missing = 0
        owner = (cfg["settings"].get("opus") or {}).get("owner")
        for a in todo[:MAX_PER_RUN]:
            if stop and stop():
                break
            got = from_caa(a) or from_deezer(a)
            time.sleep(1)   # go easy on both services
            if not got:
                missing += 1
                state[a["id"]] = {"t": int(time.time()), "ok": False}
                log(_s("  · {artist} – {album}: no cover found", artist=a["artist"], album=a["name"]))
                continue
            data, ext, source = got
            dst = a["folder"] / f"cover{ext}"
            if dry_run:
                log(_s("  (dry run) {artist} – {album}: cover from {source}", artist=a["artist"], album=a["name"],
                       source=source))
                continue
            if _folder_has_cover(a["folder"]):   # meanwhile someone (Lidarr) saved one
                continue
            try:
                write_atomic(dst, data, 0o644)
                _own(dst, owner, 0o644)
            except OSError as e:
                log(f"  ⚠ {a['artist']} – {a['name']}: {e}")
                continue
            saved += 1
            state[a["id"]] = {"t": int(time.time()), "ok": True, "src": source}
            log(_s("  ✓ {artist} – {album}: cover from {source}", artist=a["artist"], album=a["name"], source=source))
        if not dry_run:
            try:
                save_state(state)
            except OSError:
                pass
    if saved:
        log(_sn(saved, "{n} cover saved – Navidrome shows it after the next scan.",
                "{n} covers saved – Navidrome shows them after the next scan."))
    return {"checked": len(todo), "saved": saved, "notFound": missing}
