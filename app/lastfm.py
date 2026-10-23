"""Last.fm (free, own API key): similar artists and tags.

* artist.getSimilar  -> "Similar to …" radio, better suggestions, bands you are missing
* artist.getTopTags  -> genres/moods for the automatic classification of new bands
Everything is cached for 30 days (state/lastfm.json) – after the first run it hardly costs any requests.
Enter the key under Settings → Intelligence (or LASTFM_API_KEY in docker-compose).
"""
import http.client
import json
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

from . import progress
from .config import STATE_DIR, load_env, read_text, write_atomic
from .i18n import _, _s, _sn

API = "https://ws.audioscrobbler.com/2.0/"
STATE_FILE = STATE_DIR / "lastfm.json"
TTL = 30 * 86400
USER_AGENT = "Tuttiphon/1.0 (Navidrome-Helfer)"   # sent as it is (HTTP header)
_lock = threading.Lock()
_mem = {"stamp": None, "data": None}


class LastfmError(Exception):
    def __init__(self, message, bad_key=False):
        super().__init__(message)
        self.bad_key = bad_key   # key missing or invalid: no further request can work


def api_key(env=None):
    return (env or load_env()).get("LASTFM_API_KEY", "").strip()


def load():
    try:
        st = STATE_FILE.stat()
        stamp = (st.st_mtime_ns, st.st_size)
    except OSError:
        return {"artists": {}}
    if _mem["stamp"] != stamp:
        try:
            data = json.loads(read_text(STATE_FILE))
        except (OSError, ValueError):
            data = {}
        data.setdefault("artists", {})
        _mem.update(stamp=stamp, data=data)
    return _mem["data"]


def save(data):
    try:
        write_atomic(STATE_FILE, json.dumps(data, ensure_ascii=False, separators=(",", ":")))
    except OSError:
        pass


class Client:
    def __init__(self, key, rate=4.0):
        if not key:
            raise LastfmError(_("No Last.fm key entered (Settings → Intelligence)."), bad_key=True)
        self.key = key
        self._interval = 1.0 / rate
        self._next = 0.0
        self._tlock = threading.Lock()

    def call(self, method, **params):
        with self._tlock:   # Last.fm allows about 5 requests per second
            wait = self._next - time.time()
            self._next = max(time.time(), self._next) + self._interval
        if wait > 0:
            time.sleep(wait)
        q = urllib.parse.urlencode({"method": method, "api_key": self.key, "format": "json", "autocorrect": 1, **params})
        req = urllib.request.Request(f"{API}?{q}", headers={"User-Agent": USER_AGENT})
        for attempt in range(3):
            try:
                with urllib.request.urlopen(req, timeout=20) as res:
                    data = json.loads(res.read().decode("utf-8"))
                break
            except urllib.error.HTTPError as e:
                try:
                    data = json.loads(e.read().decode("utf-8"))
                except ValueError:
                    data = {"error": e.code, "message": str(e)}
                if e.code in (429, 500, 502, 503) and attempt < 2:
                    time.sleep(3 * (attempt + 1))
                    continue
                break
            except (urllib.error.URLError, http.client.HTTPException, OSError, ValueError) as e:
                # not reachable, timeout, broken off or broken answer (e.g. HTML instead of JSON)
                if attempt < 2:
                    time.sleep(2 * (attempt + 1))
                    continue
                raise LastfmError(_("Last.fm not reachable: {error}", error=e))
        if isinstance(data, dict) and data.get("error"):
            code = data.get("error")
            if code in (10, 26):
                raise LastfmError(_("The Last.fm key is invalid."), bad_key=True)
            if code == 6:   # artist/title unknown
                return None
            raise LastfmError(f"Last.fm: {data.get('message') or code}")
        return data


def _tags(data):
    tags = ((data or {}).get("toptags") or {}).get("tag") or []
    if isinstance(tags, dict):
        tags = [tags]
    return [[t.get("name", "").strip().lower(), int(t.get("count") or 0)] for t in tags if t.get("name")][:30]


def _similar(data):
    arts = ((data or {}).get("similarartists") or {}).get("artist") or []
    if isinstance(arts, dict):
        arts = [arts]
    return [[a.get("name", ""), round(float(a.get("match") or 0), 3)] for a in arts if a.get("name")][:60]


def fetch_artist(client, name):
    """Tags + similar artists of an artist (two requests)."""
    tags = _tags(client.call("artist.gettoptags", artist=name))
    sim = _similar(client.call("artist.getsimilar", artist=name, limit=60))
    return {"t": int(time.time()), "tags": tags, "similar": sim}


def artist(name):
    """Cached data or None."""
    return load()["artists"].get(name)


def test(key):
    try:
        res = Client(key).call("artist.gettoptags", artist="Nightwish")
        return {"ok": True, "tags": [t[0] for t in _tags(res)[:5]]}
    except LastfmError as e:
        return {"ok": False, "error": str(e)}


def refresh(names, log=print, stop=None, budget=None, everything=False):
    """Load missing/expired artists. budget in minutes (0/None = no limit)."""
    client = Client(api_key())
    with _lock:
        data = json.loads(json.dumps(load()))   # copy
    arts = data.setdefault("artists", {})
    now = time.time()
    todo = [n for n in names if everything or n not in arts or now - arts[n].get("t", 0) > TTL]
    deadline = now + budget * 60 if budget else None
    if budget:
        log(_s("Last.fm: {current} bands up to date, {todo} to load (at most {minutes} min).",
               current=len(names) - len(todo), todo=len(todo), minutes=budget))
    else:
        log(_s("Last.fm: {current} bands up to date, {todo} to load.", current=len(names) - len(todo), todo=len(todo)))
    done = later = 0
    progress.part("lastfm", len(todo), until=deadline)
    try:
        for k, name in enumerate(todo, 1):
            progress.at(k - 1)
            if stop is not None and stop.is_set():
                break
            if deadline and time.time() > deadline:
                later = len(todo) - k + 1
                break
            try:
                arts[name] = fetch_artist(client, name)
                done += 1
            except LastfmError as e:
                if e.bad_key:
                    raise
                log(f"  ⚠ {name}: {e}")
            if k % 100 == 0:
                log(f"  … {k}/{len(todo)}")
                with _lock:
                    save(data)
    finally:
        data["lastRun"] = time.strftime("%d.%m.%Y %H:%M")
        with _lock:
            save(data)
    if later:
        log(_sn(done, "Last.fm: {n} band updated, {later} follow in the next run.",
                "Last.fm: {n} bands updated, {later} follow in the next run.", later=later))
    else:
        log(_sn(done, "Last.fm: {n} band updated.", "Last.fm: {n} bands updated."))
    return {"artists": done, "later": later}


def stats():
    data = load()
    arts = data.get("artists", {})
    return {"artists": len(arts), "withTags": sum(1 for a in arts.values() if a.get("tags")),
            "lastRun": data.get("lastRun"), "key": bool(api_key())}
