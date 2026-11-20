"""Band knowledge: similar bands and tags – for radio, suggestions, "You might still be missing", the mood of the sound
filters and the classification of new bands. Free and without a key:

* ListenBrainz: similar bands from what its listeners play one after another (labs.api.listenbrainz.org) and the
  band's tags from MusicBrainz (api.listenbrainz.org/1/metadata/artist). Both by the band's MusicBrainz ID – from
  Navidrome (Lidarr and Picard write it into the files), otherwise a MusicBrainz search for the exact name.
* Deezer: similar bands ("related artists") – strong for German music, children's songs and Schlager too. The band is
  found by its exact name (the one with the most fans if several share it).
* Last.fm (lastfm.py) only with an own key – Last.fm gives working keys only with a Pro subscription. What it has
  delivered stays in use.

artist(name) merges them: every tag and every similar band with its strongest value from any source. Fetched data is
cached for 30 days (state/bands.json) – after the first pass a run hardly costs any requests.
"""
import http.client
import json
import re
import threading
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter

from . import lastfm, progress
from .config import STATE_DIR, load_env, read_text, write_atomic
from .i18n import _s, _sn
from .version import VERSION

STATE_FILE = STATE_DIR / "bands.json"
TTL = 30 * 86400
SOURCES = ("listenbrainz", "deezer")
NAMES = {"listenbrainz": "ListenBrainz", "deezer": "Deezer"}   # names of services
SETTING = {"listenbrainz": "listenbrainz", "deezer": "deezerSimilar"}   # settings.analysis.<key>: on/off
# ListenBrainz and MusicBrainz ask for a name, a version and a contact – the project page (sent as it is, HTTP header)
USER_AGENT = f"Tuttiphon/{VERSION} ( https://github.com/seluce/tuttiphon )"
LB_SIMILAR = "https://labs.api.listenbrainz.org/similar-artists/json"
LB_ALGORITHM = "session_based_days_7500_session_300_contribution_5_threshold_10_limit_100_filter_True_skip_30"
LB_META = "https://api.listenbrainz.org/1/metadata/artist/"
MB_SEARCH = "https://musicbrainz.org/ws/2/artist"
DZ_SEARCH = "https://api.deezer.com/search/artist"
DZ_RELATED = "https://api.deezer.com/artist/{id}/related"
LB_WEIGHT = 0.8     # ListenBrainz counts a little less: its lists lean towards bands that very many people play
DZ_STEP = 0.04      # Deezer gives an order without values: the first 1.0, each further one 0.04 less (at least 0.2)
MAX_TAGS, MAX_SIMILAR = 30, 60
GIVE_UP = 5         # this many failures in a row: the source is left out for the rest of the run

_lock = threading.Lock()
_mem = {"stamp": None, "data": None}
_view = {"v": (None, {})}   # (stamps of both caches, merged data)


class BandError(Exception):
    """A source did not answer (not reachable, errors) – the band is asked again in the next run."""


class _Pace:
    """At most one request per interval to one service; a service asking for a pause pushes the next one back."""

    def __init__(self, interval):
        self.interval, self._next, self._lock = interval, 0.0, threading.Lock()

    def wait(self):
        with self._lock:
            now = time.time()
            wait = self._next - now
            self._next = max(now, self._next) + self.interval
        if wait > 0:
            time.sleep(wait)

    def later(self, seconds):
        with self._lock:
            self._next = max(self._next, time.time() + seconds)


# MusicBrainz: one request per second; ListenBrainz: 30 per 10 seconds; Deezer: 50 per 5 seconds
PACE = {"mb": _Pace(1.1), "lb": _Pace(0.4), "dz": _Pace(0.15)}


def _get(url, pace, attempts=3):
    """JSON of url, None if there is nothing (404). BandError if the service does not answer."""
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    for attempt in range(attempts):
        pace.wait()
        try:
            with urllib.request.urlopen(req, timeout=20) as res:
                left, reset = res.headers.get("X-RateLimit-Remaining"), res.headers.get("X-RateLimit-Reset-In")
                if left and left.isdigit() and int(left) <= 1 and reset and reset.isdigit():
                    pace.later(min(30, int(reset) + 1))   # ListenBrainz: the window is used up
                return json.loads(res.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            if e.code in (429, 500, 502, 503, 504) and attempt < attempts - 1:
                reset = e.headers.get("X-RateLimit-Reset-In") or e.headers.get("Retry-After") or ""
                pace.later(min(30, int(reset) + 1) if reset.isdigit() else 3 * (attempt + 1))
                continue
            raise BandError(f"HTTP {e.code}") from None
        except (urllib.error.URLError, http.client.HTTPException, OSError, ValueError) as e:
            # not reachable, timeout, broken off or broken answer (e.g. HTML instead of JSON)
            if attempt < attempts - 1:
                pace.later(2 * (attempt + 1))
                continue
            raise BandError(str(getattr(e, "reason", None) or e)) from None
    raise BandError("HTTP 503")


def _key(name):
    """Comparable form of a band name: lower case, no diacritics, no punctuation, no leading "the", "&" = "and"."""
    s = unicodedata.normalize("NFKD", (name or "").casefold())
    s = "".join(c for c in s if not unicodedata.combining(c)).replace("&", " and ")
    s = re.sub(r"^\s*the\s+", "", s)   # i18n-ignore: data
    return re.sub(r"[\W_]+", "", s)


# ---------------------------------------------------------------------------- the sources

def _mb_find(name):
    """MusicBrainz ID of a band by its exact name – None if MusicBrainz has none of that name."""
    query = 'artist:"{}"'.format(name.replace("\\", "\\\\").replace('"', '\\"'))
    data = _get(f"{MB_SEARCH}?" + urllib.parse.urlencode({"query": query, "fmt": "json", "limit": 5}), PACE["mb"])
    want = _key(name)
    for a in (data or {}).get("artists") or []:
        if _key(a.get("name")) == want and str(a.get("score") or 0).isdigit() and int(a.get("score")) >= 90:
            return a.get("id")
    return None


def _lb_similar(mbid):
    """Similar bands by ListenBrainz: [[name, 0–1]], the most similar first."""
    data = _get(f"{LB_SIMILAR}?" + urllib.parse.urlencode({"artist_mbids": mbid, "algorithm": LB_ALGORITHM}), PACE["lb"])
    if isinstance(data, list) and data and isinstance(data[0], dict) and isinstance(data[0].get("data"), list):
        data = data[0]["data"]   # the older answer of the labs API: the rows inside "data"
    rows = [r for r in data or [] if isinstance(r, dict) and r.get("name") and r.get("artist_mbid") != mbid]
    scores = [float(r.get("score") or 0) for r in rows]
    top = max(scores, default=0)
    if top <= 0:
        return []
    return [[r["name"], round(LB_WEIGHT * s / top, 3)] for r, s in zip(rows, scores) if s > 0][:MAX_SIMILAR]


def _lb_tags(mbid):
    """The band's tags at MusicBrainz: [[tag, 0–100]] – the most named one 100, like Last.fm."""
    data = _get(f"{LB_META}?" + urllib.parse.urlencode({"artist_mbids": mbid, "inc": "tag"}), PACE["lb"])
    rows = data if isinstance(data, list) else list(data.values()) if isinstance(data, dict) else []
    counts = {}
    for row in rows:
        for t in ((row or {}).get("tag") or {}).get("artist") or []:
            name, n = (t.get("tag") or "").strip().lower(), int(t.get("count") or 0)
            if name and n > 0:
                counts[name] = max(counts.get(name, 0), n)
    top = max(counts.values(), default=0)
    return [[t, round(100 * n / top)] for t, n in sorted(counts.items(), key=lambda x: -x[1])][:MAX_TAGS]


def _dz(url):
    """Deezer answers errors with status 200 and {"error": …}: a pause at its quota, None if it has nothing."""
    for attempt in range(3):
        data = _get(url, PACE["dz"])
        err = data.get("error") if isinstance(data, dict) else None
        if not err:
            return data
        if err.get("code") == 4 and attempt < 2:   # quota exceeded
            PACE["dz"].later(5)
            continue
        if err.get("code") == 800:   # no data
            return None
        raise BandError(f"Deezer: {err.get('message') or err.get('code')}")
    return None


def _dz_find(name):
    """Deezer ID of a band by its exact name (the one with the most fans) – None without one."""
    data = _dz(f"{DZ_SEARCH}?" + urllib.parse.urlencode({"q": name, "limit": 10}))
    want = _key(name)
    hits = [a for a in (data or {}).get("data") or [] if a.get("id") and _key(a.get("name")) == want]
    best = max(hits, key=lambda a: a.get("nb_fan") or 0, default=None)
    return int(best["id"]) if best else None


def _dz_similar(dz):
    """Similar bands by Deezer: [[name, 0.2–1]] in Deezer's order."""
    data = _dz(DZ_RELATED.format(id=int(dz)) + "?limit=50")
    names = [a["name"] for a in (data or {}).get("data") or [] if a.get("name")]
    return [[n, round(max(0.2, 1 - k * DZ_STEP), 3)] for k, n in enumerate(names)][:MAX_SIMILAR]


def navidrome_ids():
    """Band name -> MusicBrainz ID as Navidrome knows it (getArtists – Lidarr and Picard write it into the files).
    {} if Navidrome does not answer: the MusicBrainz search finds the bands then."""
    from .navidrome import Navidrome, NavidromeError
    env = load_env()
    try:
        res = Navidrome(env.get("NAV_URL", ""), env.get("NAV_ADMIN_USER"), env.get("NAV_ADMIN_PASS")).call("getArtists")
    except (NavidromeError, OSError, ValueError):
        return {}
    out = {}
    for index in (res.get("artists") or {}).get("index") or []:
        for a in index.get("artist") or []:
            if a.get("name") and a.get("musicBrainzId"):
                out.setdefault(a["name"], a["musicBrainzId"])
    return out


# ---------------------------------------------------------------------------- cache and merged view

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
        if not isinstance(data, dict) or not isinstance(data.get("artists"), dict):
            data = {"artists": {}}
        _mem.update(stamp=stamp, data=data)
    return _mem["data"]


def save(data):
    try:
        write_atomic(STATE_FILE, json.dumps(data, ensure_ascii=False, separators=(",", ":")))
    except OSError:
        pass


def stamp():
    """State of the band knowledge (both caches) – for memos that depend on it."""
    lastfm.load()
    load()
    return (lastfm._mem["stamp"], _mem["stamp"])


def _merge(lists, cap):
    """[[name, value]] lists -> one list: every name (case ignored) with its strongest value, the strongest first."""
    best = {}
    for rows in lists:
        for row in rows or []:
            if not (isinstance(row, (list, tuple)) and len(row) == 2 and isinstance(row[0], str)
                    and isinstance(row[1], (int, float))):
                continue
            k = row[0].lower()
            if k not in best or row[1] > best[k][1]:
                best[k] = [best[k][0] if k in best else row[0], row[1]]
    return sorted(best.values(), key=lambda x: -x[1])[:cap]


def _merged():
    key = stamp()
    seen, data = _view["v"]
    if seen != key:
        own, lf = load()["artists"], lastfm.load()["artists"]
        data = {}
        for name in own.keys() | lf.keys():
            a, b = own.get(name) or {}, lf.get(name) or {}
            data[name] = {"tags": _merge([a.get("tags"), b.get("tags")], MAX_TAGS),
                          "similar": _merge([a.get("listenbrainz"), a.get("deezer"), b.get("similar")], MAX_SIMILAR)}
        _view["v"] = (key, data)
    return data


def artist(name):
    """{"tags": [[tag, 0–100]], "similar": [[band, 0–1]]} from every source, or None if no source was asked yet."""
    return _merged().get(name)


def sources(an):
    """The sources turned on in settings.analysis (both by default)."""
    return [s for s in SOURCES if (an or {}).get(SETTING[s], True) is not False]


# ---------------------------------------------------------------------------- fetching

def refresh(names, use, log=print, stop=None, budget=None, everything=False, ids=None):
    """Fetch the bands that are missing, expired or still lack a source turned on. use: the sources (sources()),
    budget in minutes (0/None = no limit), ids: band -> MusicBrainz ID (default: Navidrome's)."""
    with _lock:
        data = json.loads(json.dumps(load()))   # copy
    arts = data.setdefault("artists", {})
    now = time.time()
    want = [s for s in SOURCES if s in use]

    def due(name):
        a = arts.get(name)
        return everything or not a or now - a.get("t", 0) > TTL or not set(want) <= set(a.get("src") or [])

    todo = [n for n in names if due(n)]
    if not want:
        return {"artists": 0, "later": 0}
    deadline = now + budget * 60 if budget else None
    if budget:
        log(_s("Similar bands: {current} bands up to date, {todo} to load (at most {minutes} min).",
               current=len(names) - len(todo), todo=len(todo), minutes=budget))
    else:
        log(_s("Similar bands: {current} bands up to date, {todo} to load.", current=len(names) - len(todo), todo=len(todo)))
    if not todo:
        return {"artists": 0, "later": 0}
    if ids is None:
        ids = navidrome_ids() if "listenbrainz" in want else {}
    fails, off = Counter(), set()
    done = later = 0
    progress.part("bands", len(todo), until=deadline)
    try:
        for k, name in enumerate(todo, 1):
            progress.at(k - 1)
            if stop is not None and stop.is_set():
                break
            if deadline and time.time() > deadline:
                later = len(todo) - k + 1
                break
            old = arts.get(name) or {}
            entry = {"t": int(time.time()), "src": []}
            for src in want:
                if src in off:
                    continue
                try:
                    if src == "listenbrainz":
                        mbid = ids.get(name) or old.get("mbid") or _mb_find(name)
                        entry.update(mbid=mbid or "", tags=_lb_tags(mbid) if mbid else [],
                                     listenbrainz=_lb_similar(mbid) if mbid else [])
                    else:
                        dz = old.get("dz") or _dz_find(name)
                        entry.update(dz=dz or 0, deezer=_dz_similar(dz) if dz else [])
                    entry["src"].append(src)
                    fails[src] = 0
                except BandError as e:
                    fails[src] += 1
                    if fails[src] >= GIVE_UP:
                        off.add(src)
                        log(_s("⚠ {source} does not answer – left out for this run: {error}", source=NAMES[src], error=e))
            if not entry["src"]:   # no source answered: what was there stays, the band comes again in the next run
                if off >= set(want):
                    later = len(todo) - k + 1
                    break
                continue
            for field, src in (("mbid", "listenbrainz"), ("tags", "listenbrainz"), ("listenbrainz", "listenbrainz"),
                               ("dz", "deezer"), ("deezer", "deezer")):
                if src not in entry["src"] and field in old and src in want:
                    entry[field] = old[field]   # a source that failed this time: its data so far stays
            arts[name] = entry
            done += 1
            if k % 100 == 0:
                log(f"  … {k}/{len(todo)}")
                with _lock:
                    save(data)
    finally:
        data["lastRun"] = time.strftime("%d.%m.%Y %H:%M")
        with _lock:
            save(data)
    if later:
        log(_sn(done, "Similar bands: {n} band updated, {later} follow in the next run.",
                "Similar bands: {n} bands updated, {later} follow in the next run.", later=later))
    else:
        log(_sn(done, "Similar bands: {n} band updated.", "Similar bands: {n} bands updated."))
    return {"artists": done, "later": later}


def stats():
    own = load()
    arts = own.get("artists", {})
    merged = _merged()
    return {"artists": len(merged), "withTags": sum(1 for a in merged.values() if a["tags"]),
            "withSimilar": sum(1 for a in merged.values() if a["similar"]),
            "listenbrainz": sum(1 for a in arts.values() if a.get("mbid")),
            "deezer": sum(1 for a in arts.values() if a.get("dz")), "lastRun": own.get("lastRun")}
