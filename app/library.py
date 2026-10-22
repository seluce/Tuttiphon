"""Cache the song list from Navidrome (for preview, matrix, suggestions and writing).

After 15 minutes it is reloaded in the background – until then the previous one applies, nobody waits. After a scan,
new stars or credentials (invalidate()), however, the next request waits for the fresh list.
"""
import ctypes
import threading
import time

from .config import load_env
from .i18n import _
from .navidrome import Navidrome
from .rules import Library

MAX_AGE = 15 * 60


def album_meta(env):
    """Album ID -> (has a cover?, main color) from Navidrome's own API (Subsonic does not know this)."""
    from .navidrome import NavidromeError, native_session
    try:
        native = native_session(env["NAV_URL"], env.get("NAV_ADMIN_USER"), env.get("NAV_ADMIN_PASS"))
        albums = native._request("GET", "/api/album?_start=0&_end=100000")
    except (NavidromeError, KeyError, ValueError):
        return {}
    return {a["id"]: (bool(a.get("imageHash")), a.get("dominantColor")) for a in albums}


def artist_meta(env):
    """Artist ID -> has an image? (otherwise Navidrome delivers a star as a placeholder)."""
    from .navidrome import NavidromeError, native_session
    try:
        native = native_session(env["NAV_URL"], env.get("NAV_ADMIN_USER"), env.get("NAV_ADMIN_PASS"))
        artists = native._request("GET", "/api/artist?_start=0&_end=100000")
    except (NavidromeError, KeyError, ValueError):
        return {}
    return {a["id"]: bool(a.get("imageHash")) for a in artists}


def real_paths(env):
    """-> (song ID -> real file path relative to the library, song ID -> embedded lyrics). Subsonic only delivers a path
    built from tags; for .m3u mixes Navidrome needs the real one. Takes a few seconds – only when needed."""
    from .navidrome import NavidromeError, native_session
    from .liedtext import embedded_text
    paths, embedded, page, start = {}, {}, 2000, 0
    try:
        native = native_session(env["NAV_URL"], env.get("NAV_ADMIN_USER"), env.get("NAV_ADMIN_PASS"))
        while True:   # page by page: a single request for all songs took over 150 MB that Python does not give back
            songs = native._request("GET", f"/api/song?_start={start}&_end={start + page}&_sort=id&_order=ASC")
            for s in songs:
                if s.get("path") and not s.get("missing"):
                    paths[s["id"]] = s["path"]
                if s.get("lyrics") not in (None, "", "[]"):   # lyrics embedded in the file (text for the lyrics search)
                    embedded[s["id"]] = embedded_text(s["lyrics"])
            if len(songs) < page:
                break
            start += page
    except (NavidromeError, KeyError, ValueError) as e:   # do not return empty – that would create empty mixes
        raise RuntimeError(_("Could not read file paths from Navidrome: {error}", error=e))
    return paths, embedded


def release_memory():
    """Give freed memory back to the system (glibc). Otherwise Python often keeps it for good – e.g. after reloading the
    song list. Without glibc (another system) nothing happens."""
    try:
        ctypes.CDLL("libc.so.6").malloc_trim(0)
    except (OSError, AttributeError):
        pass


def _load():
    """Song list fresh from Navidrome -> (Library, account of the stars or None). The shared list is neutral: read as
    the Navidrome administrator with the average rating – a person's own view (their stars, plays) is
    stats.songs_for(), mixer.person_lib()."""
    env = load_env()
    nav = Navidrome(env["NAV_URL"], env.get("NAV_ADMIN_USER"), env.get("NAV_ADMIN_PASS"))
    lib = Library(nav.all_songs(), ratings_exact=False, user=None)
    lib.album_meta = album_meta(env)
    lib.artist_meta = artist_meta(env)
    lib.path_loader = lambda env=env: real_paths(env)
    return lib, None


class LibraryCache:
    def __init__(self):
        self._lock = threading.Lock()
        self._lib = None
        self._at = 0.0
        self._gen = 0            # counts every new list and every invalidate() – an outdated reload is dropped
        self._refreshing = False
        self.source = None

    def get(self, force=False):
        with self._lock:
            if self._lib is not None and self._at and not force:
                if time.time() - self._at > MAX_AGE:
                    self._refresh_soon()
                return self._lib
            self._lib, self.source = _load()
            self._at = time.time()
            self._gen += 1
            lib = self._lib
        release_memory()   # the previous list is free now
        return lib

    def _refresh_soon(self):
        """Reload in the background (called under self._lock)."""
        if self._refreshing:
            return
        self._refreshing = True
        gen = self._gen

        def run():
            try:
                lib, source = _load()
            except Exception:   # noqa: BLE001 – Navidrome briefly away: the previous list still applies
                lib = source = None
            with self._lock:
                self._refreshing = False
                if lib is not None and self._gen == gen:
                    self._lib, self.source, self._at = lib, source, time.time()
                    self._gen += 1
                elif lib is None and self._gen == gen:
                    self._at = time.time() - MAX_AGE + 60   # try again in a minute
            del lib
            release_memory()
        threading.Thread(target=run, daemon=True, name="songliste").start()

    def invalidate(self):
        with self._lock:
            self._at = 0.0
            self._gen += 1

    @property
    def loaded_at(self):
        return self._at


CACHE = LibraryCache()
