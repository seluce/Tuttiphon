"""Lean Subsonic API client for Navidrome (standard library only)."""
import gzip
import hashlib
import json
import secrets
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

from .i18n import _, _s

CLIENT = "tuttiphon"


# Song fields Tuttiphon uses (rules, preview, statistics, mixes, maintenance). Everything else in the Subsonic answer
# (channels, ReplayGain, contributors, size, comment …) is dropped while loading.
SONG_FIELDS = frozenset(("id", "title", "album", "albumId", "artist", "artistId", "artists", "albumArtists",
                         "displayArtist", "displayAlbumArtist", "genre", "genres", "year", "duration", "created", "path",
                         "suffix", "userRating", "averageRating", "starred", "playCount", "played", "track",
                         "discNumber", "bitRate", "explicitStatus"))
# Texts many songs share (album, band, genre …): only once in memory
SHARED_TEXT = frozenset(("album", "albumId", "artist", "artistId", "displayArtist", "displayAlbumArtist", "genre",
                         "suffix", "explicitStatus"))
_shared = {}


def _one(key, make):
    """Shared object for key – artist and genre entries with their lists exist only once for all songs this way.
    They are never changed anywhere (only read)."""
    v = _shared.get(key)
    if v is None:
        if len(_shared) > 200_000:   # upper limit in case the collection changes a lot over the years
            _shared.clear()
        v = _shared[key] = make()
    return v


def _artist(a):
    i, n = a.get("id"), a.get("name")
    return _one(("a", i, n), lambda: {"id": sys.intern(i) if isinstance(i, str) else i,
                                      "name": sys.intern(n) if isinstance(n, str) else n})


def _genre(g):
    n = g.get("name")
    return _one(("g", n), lambda: {"name": sys.intern(n) if isinstance(n, str) else n})


def _slim(song):
    """Only the fields from SONG_FIELDS; artists only with name and ID, genres only with name. Repeated values are
    shared by all songs – this way the song list takes about a third of the memory."""
    out = {}
    for k, v in song.items():
        if k not in SONG_FIELDS:
            continue
        if k in SHARED_TEXT and isinstance(v, str):
            v = sys.intern(v)
        elif k in ("artists", "albumArtists") and v:
            v = _one(("A", tuple((a.get("id"), a.get("name")) for a in v)), lambda v=v: [_artist(a) for a in v])
        elif k == "genres" and v:
            v = _one(("G", tuple(g.get("name") for g in v)), lambda v=v: [_genre(g) for g in v])
        out[k] = v
    return out


class NavidromeError(Exception):
    """code: the Subsonic error code when Navidrome answered with an error (40 = wrong username or password) –
    check it instead of the message, which is translated."""

    def __init__(self, message="", code=None):
        super().__init__(message)
        self.code = code


def _check_url(url):
    if not url:
        raise NavidromeError(_("Navidrome address missing – Settings → Navidrome"))
    if not url.lower().startswith(("http://", "https://")):
        raise NavidromeError(_("Navidrome address invalid ({url}) – it starts with http:// or https://", url=url))


class Navidrome:
    def __init__(self, url, user, password):
        _check_url(url)
        if not user or not password:
            raise NavidromeError(_("Credentials incomplete for user '{user}'", user=user or "?"))
        self.url, self.user, self._password = url.rstrip("/"), user, password

    def call(self, endpoint, timeout=60, post=False, **params):
        salt = secrets.token_hex(8)
        query = {
            "u": self.user,
            "t": hashlib.md5((self._password + salt).encode()).hexdigest(),
            "s": salt,
            "v": "1.16.1",
            "c": CLIENT,
            "f": "json",
        }
        query.update({k: v for k, v in params.items() if v is not None})
        encoded = urllib.parse.urlencode(query, doseq=True)   # lists -> songId=a&songId=b
        if post:   # long parameter lists (e.g. 100 song IDs) as a form
            req = urllib.request.Request(f"{self.url}/rest/{endpoint}", data=encoded.encode(),
                                         headers={"Content-Type": "application/x-www-form-urlencoded"})
        else:
            req = f"{self.url}/rest/{endpoint}?{encoded}"
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except urllib.error.URLError as e:
            raise NavidromeError(_("Navidrome not reachable ({url}): {reason}", url=self.url,
                                   reason=e.reason if hasattr(e, "reason") else e))
        except ValueError:
            raise NavidromeError(_("The answer from Navidrome is not JSON"))
        body = data.get("subsonic-response", {})
        if body.get("status") != "ok":
            err = body.get("error", {})
            raise NavidromeError(_("Navidrome error {code}: {message} (user {user})", code=err.get("code", "?"),
                                   message=err.get("message", _("unknown")), user=self.user), code=err.get("code"))
        return body

    def ping(self):
        return self.call("ping")

    def all_songs(self, page=500):
        """All songs incl. rating/listening statistics as this user sees them (~4 s for 22k songs).
        Only the fields Tuttiphon needs (_slim())."""
        return list(self.iter_songs(page))

    def iter_songs(self, page=500):
        """Like all_songs(), but page by page – so the whole answer never has to be in memory at once."""
        offset = 0
        while True:
            result = self.call("search3", query="", songCount=page, songOffset=offset,
                               artistCount=0, albumCount=0).get("searchResult3", {})
            chunk = result.get("song", [])
            for s in chunk:
                yield _slim(s)
            if len(chunk) < page:
                return
            offset += page

    def scan_status(self):
        return self.call("getScanStatus").get("scanStatus", {})

    def start_scan(self, full=False):
        return self.call("startScan", fullScan="true" if full else None).get("scanStatus", {})

    def wait_for_scan(self, log=print, stop=None, timeout=4 * 3600):
        start = time.time()
        time.sleep(2)
        last_count = None
        while time.time() - start < timeout:
            if stop is not None and stop.is_set():
                log(_s("Stopped waiting for the scan (the scan continues in Navidrome)."))
                return False
            status = self.scan_status()
            if not status.get("scanning"):
                return True
            count = status.get("count")
            if count != last_count and count is not None:
                log(_s("  … scan running, {count} files processed", count=count))
                last_count = count
            time.sleep(3)
        log(_s("The scan is taking unusually long – not waiting any longer."))
        return False

    def set_rating(self, song_id, rating):
        return self.call("setRating", id=song_id, rating=int(rating))

    def stream(self, song_id, fmt="raw", max_bitrate=192, byte_range=None):
        """Audio of a song for a preview (open answer – the caller reads it piece by piece and closes it).
        fmt "raw": the file as it is (seeking via Range); "mp3": for browsers without Opus. Does not count as a play."""
        salt = secrets.token_hex(8)
        query = {"u": self.user, "t": hashlib.md5((self._password + salt).encode()).hexdigest(), "s": salt,
                 "v": "1.16.1", "c": CLIENT, "id": song_id, "format": fmt}
        if fmt != "raw":
            query["maxBitRate"] = max_bitrate
        req = urllib.request.Request(f"{self.url}/rest/stream?{urllib.parse.urlencode(query)}",
                                     headers={"Range": byte_range} if byte_range else {})
        try:
            resp = urllib.request.urlopen(req, timeout=30)
        except urllib.error.HTTPError as e:
            if e.code == 416:
                raise NavidromeError(_("Range not available"))
            raise NavidromeError(_("Song not playable ({code})", code=e.code))
        except urllib.error.URLError as e:
            raise NavidromeError(_("Navidrome not reachable ({url}): {reason}", url=self.url,
                                   reason=e.reason if hasattr(e, "reason") else e))
        ctype = resp.headers.get("Content-Type", "")
        if ctype.startswith(("application/json", "text/xml", "application/xml")):   # Subsonic error instead of audio
            resp.close()
            raise NavidromeError(_("Song not playable"))
        return resp

    def cover_art(self, cover_id, size=None):
        """Raw image (bytes, content type) – getCoverArt does not answer with JSON. Without a size: the image as it is
        (for a playlist: the uploaded file itself)."""
        salt = secrets.token_hex(8)
        query = {"u": self.user, "t": hashlib.md5((self._password + salt).encode()).hexdigest(), "s": salt,
                 "v": "1.16.1", "c": CLIENT, "id": cover_id, **({"size": size} if size else {})}
        try:
            with urllib.request.urlopen(f"{self.url}/rest/getCoverArt?{urllib.parse.urlencode(query)}", timeout=30) as resp:
                return resp.read(), resp.headers.get("Content-Type", "")
        except urllib.error.URLError as e:
            raise NavidromeError(_("Image not available: {error}", error=e))


class NativeApi:
    """Navidrome's own REST API (like its web interface) – for things Subsonic cannot do:
    change owner/name/visibility of playlists, upload covers, album/artist information.

    Navidrome limits logins (HTTP 429). Therefore: reuse one session per user (native_session),
    log in again once when the token has expired, wait briefly on 429."""

    def __init__(self, url, user, password):
        _check_url(url)
        if not user or not password:
            raise NavidromeError(_("Navidrome admin access missing – Settings → Navidrome"))
        self.url = url.rstrip("/")
        self._user, self._password = user, password
        self.token = None
        self._login()

    def _login(self):
        body = self._raw("POST", "/auth/login", {"username": self._user, "password": self._password}, auth=False)
        self.token = body["token"]

    def _raw(self, method, path, body=None, auth=True, data=None, content_type="application/json"):
        headers = {"Content-Type": content_type, "Accept-Encoding": "gzip"}
        if auth:
            headers["X-ND-Authorization"] = f"Bearer {self.token}"
        payload = data if data is not None else (json.dumps(body).encode("utf-8") if body is not None else None)
        for attempt in range(4):
            req = urllib.request.Request(self.url + path, data=payload, method=method, headers=headers)
            try:
                with urllib.request.urlopen(req, timeout=60) as resp:
                    fresh = resp.headers.get("X-ND-Authorization")
                    if auth and fresh:   # Navidrome extends the token with every answer
                        self.token = fresh.replace("Bearer ", "")
                    raw = resp.read()
                    if resp.headers.get("Content-Encoding") == "gzip":
                        raw = gzip.decompress(raw)
                    raw = raw.decode("utf-8")
                return json.loads(raw) if raw.strip() else {}
            except urllib.error.HTTPError as e:
                if e.code == 429 and attempt < 3:
                    time.sleep(int(e.headers.get("Retry-After") or 0) or 5 * (attempt + 1))
                    continue
                raise NavidromeError(_("Navidrome API {method} {path}: HTTP {code}", method=method, path=path, code=e.code),
                                     code=e.code)
            except urllib.error.URLError as e:
                raise NavidromeError(_("Navidrome not reachable: {reason}", reason=e.reason))
        raise NavidromeError(_("Navidrome API {method} {path}: too many requests", method=method, path=path))

    def _request(self, method, path, body=None, **kw):
        try:
            return self._raw(method, path, body, **kw)
        except NavidromeError as e:
            if "HTTP 401" not in str(e):
                raise
            self._login()   # token expired -> log in again once
            return self._raw(method, path, body, **kw)

    def users(self):
        return self._request("GET", "/api/user")

    def playlists(self):
        return self._request("GET", "/api/playlist?_start=0&_end=5000&_sort=name&_order=ASC")

    def playlist_count(self, playlist_id):
        """Song count of a playlist as Navidrome stored it (for mixes/.m3u). Navidrome evaluates smart playlists fresh only
        for their owner – so the self-check counts them as the owner (selfcheck.owner_count)."""
        self._request("GET", f"/api/playlist/{playlist_id}/tracks?_start=0&_end=1")
        return int(self._request("GET", f"/api/playlist/{playlist_id}").get("songCount") or 0)

    def update_playlist(self, playlist_id, fields):
        # Only the fields sent are changed (rules etc. stay)
        return self._request("PUT", f"/api/playlist/{playlist_id}", fields)

    def delete_playlist(self, playlist_id):
        return self._request("DELETE", f"/api/playlist/{playlist_id}")

    def upload_playlist_image(self, playlist_id, data, filename="cover.jpg", ctype="image/jpeg"):
        boundary = "----tuttiphon" + secrets.token_hex(8)
        body = (f"--{boundary}\r\nContent-Disposition: form-data; name=\"image\"; filename=\"{filename}\"\r\n"
                f"Content-Type: {ctype}\r\n\r\n").encode() + data + f"\r\n--{boundary}--\r\n".encode()
        return self._request("POST", f"/api/playlist/{playlist_id}/image", data=body,
                             content_type=f"multipart/form-data; boundary={boundary}")

    def delete_playlist_image(self, playlist_id):
        return self._request("DELETE", f"/api/playlist/{playlist_id}/image")

    def playlist_image(self, playlist_id):
        """The image Navidrome has for a playlist, byte for byte as uploaded (getCoverArt without a size)."""
        return Navidrome(self.url, self._user, self._password).cover_art(f"pl-{playlist_id}")[0]


_sessions = {}
_sessions_lock = threading.Lock()


def native_session(url, user, password):
    """Reusable session (avoids Navidrome's login limit)."""
    key = (url, user, hashlib.sha256((password or "").encode()).hexdigest())
    with _sessions_lock:
        sess = _sessions.get(key)
        if sess is None:
            sess = _sessions[key] = NativeApi(url, user, password)
        return sess
