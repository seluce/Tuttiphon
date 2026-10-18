"""Deezer popularity -> Navidrome stars – so that Symfonium sorts a band's top tracks correctly.

Remembers in state/deezer.json which songs have been rated already.
  new     only new songs (seconds)
  missing try again the songs not found on Deezer so far
  refresh the songs unchecked the longest (first those rated with the old search) – at night in small portions
  full    check all songs again – resumable: when stopped, the next run continues where it left off
  recalc  recalculate stars from the saved ranks (after the levels changed) – without asking Deezer
Stars changed by hand stay, unless overwriting them is explicitly allowed.
The levels (rank -> stars) can be adjusted under Settings → Deezer stars; the levels themselves are those of dztnr.py.

Search (version 2, entry "v": 2): a hit only counts if band and title match (spellings, bracketed additions and
"feat." are tolerated) – before, the search took the most popular of the first three hits, no matter by whom. If the
search finds nothing, the file's MusicBrainz ID (from Lidarr) leads via MusicBrainz to the ISRC and thus exactly to the
song on Deezer ("i"). If a song got stars with the old search and the new one does not find it, it loses them again
(only if they still come from Tuttiphon).
Top tracks ("b"): if many songs of a band share its highest star count, up to three clearly most popular ones get one
star more – otherwise Symfonium could not tell them apart from the rest (settings.deezer.topBoost).
"""
import difflib
import unicodedata
from collections import defaultdict
import datetime as dt
import json
import os
import re
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor

from .config import LEGACY_LOG_DIR, STATE_DIR, load_config, rating_users, read_text, user_password, write_atomic
from .i18n import _, _s, _sn
from .navidrome import Navidrome, NavidromeError

STATE_FILE = STATE_DIR / "deezer.json"
API = "https://api.deezer.com/search"
RATE = 9.0          # requests per second (Deezer allows 50 per 5 s)
WORKERS = 4


DEFAULT_THRESHOLDS = [10000, 100000, 300000, 600000, 850000]   # like get_rating_from_rank() in dztnr.py


def rank_to_stars(rank, thresholds=None):
    """Deezer rank (0 … ~1 million, higher = more popular) -> 0–5 stars. thresholds[k] = k+1 stars from here on."""
    rank = int(rank)
    for stars, limit in enumerate(thresholds or DEFAULT_THRESHOLDS):
        if rank < limit:
            return stars
    return 5


REFRESH_PER_RUN = 1500   # songs checked per "refresh" run (at night) – every song gets its turn about every 15 nights


def settings(cfg=None):
    return {"thresholds": DEFAULT_THRESHOLDS, "users": None, "overwriteManual": False, "pipelineMode": "new", "rate": RATE,
            "topBoost": True, "refresh": True, **((cfg or load_config())["settings"].get("deezer") or {})}


def rank_histogram():
    """For the settings: how many songs have which rank (buckets of 10,000)."""
    buckets = [0] * 101
    not_found = verified = top = 0
    entries = load_state().get("songs", {})
    for e in entries.values():
        r = e.get("r")
        if r:
            buckets[min(100, int(r) // 10000)] += 1
        elif "r" in e:
            not_found += 1
        verified += (e.get("v") or 1) >= 2
        top += bool(e.get("b"))
    return {"bucket": 10000, "counts": buckets, "notFound": not_found, "total": len(entries), "verified": verified,
            "top": top, "perNight": REFRESH_PER_RUN}


class DeezerClient:
    def __init__(self, rate=RATE):
        self._interval = 1.0 / rate
        self._next = 0.0
        self._lock = threading.Lock()

    def _throttle(self):
        with self._lock:
            now = time.monotonic()
            wait = self._next - now
            self._next = max(now, self._next) + self._interval
        if wait > 0:
            time.sleep(wait)

    def _get(self, query):
        for attempt in range(6):
            self._throttle()
            url = f"{API}?{urllib.parse.urlencode({'q': query})}"
            try:
                with urllib.request.urlopen(url, timeout=20) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
            except (urllib.error.URLError, TimeoutError, ValueError, ConnectionError):
                time.sleep(2 * (attempt + 1))
                continue
            if "error" in data:            # e.g. quota exceeded (code 4)
                time.sleep(5)
                continue
            return data.get("data") or []
        raise ConnectionError(_("Deezer does not respond (tried several times)"))

    def best_rank(self, song):
        """Best rank among the hits whose band and title match the song – or None."""
        artists = artist_names(song)
        title = song.get("title") or ""
        clean = _BRACKETS.sub("", title).strip() or title
        main = artists[0] if artists else ""
        queries = [f'artist:"{main}" track:"{clean}"', f"{main} {title}"]
        if clean != title:
            queries.append(f"{main} {clean}")
        queries += [f'artist:"{a}" track:"{clean}"' for a in artists[1:3]]
        for q in dict.fromkeys(queries):
            hits = [h for h in self._get(q)[:10] if matches(song, h)]
            best = max((int(h.get("rank") or 0) for h in hits), default=0)
            if best > 0:
                return best
        return None

    def rank_by_isrc(self, isrc):
        """Rank of the song with exactly this ISRC – or None."""
        self._throttle()
        try:
            with urllib.request.urlopen(f"https://api.deezer.com/track/isrc:{urllib.parse.quote(isrc)}", timeout=20) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError, ValueError, ConnectionError):
            return None
        return int(data.get("rank") or 0) or None if isinstance(data, dict) and "error" not in data else None


class MusicBrainz:
    """ISRCs of a recording via its MusicBrainz ID – at most one request per second (MusicBrainz rule)."""

    def __init__(self):
        self._lock = threading.Lock()
        self._next = 0.0

    def isrcs(self, mbid):
        if not re.fullmatch(r"[0-9a-f-]{36}", mbid or ""):
            return []
        with self._lock:
            wait = self._next - time.monotonic()
            if wait > 0:
                time.sleep(wait)
            self._next = time.monotonic() + 1.1
        from .version import VERSION
        req = urllib.request.Request(f"https://musicbrainz.org/ws/2/recording/{mbid}?inc=isrcs&fmt=json",
                                     headers={"User-Agent": f"Tuttiphon/{VERSION} (Navidrome-Helfer)", "Accept": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=20) as resp:
                return [x for x in (json.loads(resp.read().decode("utf-8")).get("isrcs") or []) if isinstance(x, str)][:3]
        except (urllib.error.URLError, TimeoutError, ValueError, ConnectionError):
            return []


# ---------------------------------------------------------------------------- matching: does a hit belong to the song?

_BRACKETS = re.compile(r"\s*[\(\[][^\)\]]*[\)\]]")
_SUFFIX = re.compile(r"\s+-\s+.*$")                      # "Song - Remastered 2011", "Song - Live"
_FEAT = re.compile(r"\s+(?:feat\.?|ft\.?|featuring)\s+.*$", re.I)
_SPLIT = re.compile(r"\s*(?:,|&|\+|/|\bfeat\.?|\bft\.?|\bfeaturing\b|\bund\b|\bx\b|\bvs\.?)\s*", re.I)   # i18n-ignore


def _fold(text):
    """Lower case, without accents, apostrophes and punctuation: “Du wirst mich niemals heulen seh’n” ≈ “… sehn”."""
    text = unicodedata.normalize("NFKD", (text or "").lower())
    text = "".join(c for c in text if not unicodedata.combining(c)).replace("&", "and").replace("ß", "ss")   # i18n-ignore
    return re.sub(r"[^a-z0-9]+", "", text)


def core_title(title):
    return _fold(_FEAT.sub("", _SUFFIX.sub("", _BRACKETS.sub("", title or ""))))


def artist_names(song):
    """All names the band could be listed under on Deezer – also just the first one of “A, B & C”."""
    names = [a.get("name") for a in song.get("artists") or []] + [a.get("name") for a in song.get("albumArtists") or []]
    names += [song.get("artist"), song.get("displayArtist")]
    out = []
    for n in names:
        if n and n != "Various Artists":
            out.append(n)
            first = _SPLIT.split(n)[0].strip()
            if first and first != n:
                out.append(first)
    return list(dict.fromkeys(out))


def _same(a, b):
    if not a or not b:
        return False
    if a == b or (min(len(a), len(b)) >= 4 and (a in b or b in a)):
        return True
    return difflib.SequenceMatcher(None, a, b).ratio() >= 0.85


def matches(song, hit):
    """Does the Deezer hit belong to this song? Band and title have to match."""
    band = _fold((hit.get("artist") or {}).get("name"))
    if not any(_same(_fold(n), band) for n in artist_names(song)):
        return False
    want = core_title(song.get("title"))
    return any(_same(want, core_title(hit.get(k))) for k in ("title", "title_short") if hit.get(k))


def main_artist(song):
    aa = song.get("albumArtists") or []
    if aa and aa[0].get("name") and aa[0]["name"] != "Various Artists":
        return aa[0]["name"]
    return song.get("artist") or song.get("displayArtist") or ""


def top_songs(songs, entries, thresholds=None):
    """Song IDs that get one star more as top tracks of their band: if at least two different songs share the band's
    highest star count (below 5), the up to three most popular ones get one star more – if they have at least 80 % of
    the leader's rank and there are still songs on the same level after them.
    The same title on several albums counts as one song."""
    by = defaultdict(list)
    for s in songs:
        r = (entries.get(s["id"]) or {}).get("r")
        if r:
            by[main_artist(s)].append((int(r), core_title(s.get("title")), s["id"]))
    out = set()
    for items in by.values():
        if len(items) < 4:
            continue
        top = max(rank_to_stars(r, thresholds) for r, _, _ in items)
        if top >= 5:
            continue
        level = [x for x in items if rank_to_stars(x[0], thresholds) == top]
        best = {}
        for r, t, _ in level:
            best[t] = max(best.get(t, 0), r)
        ranked = sorted(best.items(), key=lambda kv: -kv[1])
        if len(ranked) < 2:
            continue
        chosen = {t for t, r in ranked[:3] if r >= 0.8 * ranked[0][1]}
        if len(chosen) == len(ranked):
            continue   # all equally high up – nothing to highlight
        out |= {sid for _, t, sid in level if t in chosen}
    return out


def load_state():
    try:
        return json.loads(read_text(STATE_FILE))
    except (FileNotFoundError, ValueError):
        return {"version": 1, "songs": {}}


def save_state(state):
    write_atomic(STATE_FILE, json.dumps(state, ensure_ascii=False, separators=(",", ":")))


def _load_for_run(log):
    """Like load_state(), but a damaged file is set aside instead of being replaced by an empty state (the ranks and
    the record of the stars Tuttiphon set would be gone) – and the step stops, so that this shows."""
    try:
        data = json.loads(read_text(STATE_FILE))
    except FileNotFoundError:
        return {"version": 1, "songs": {}}
    except ValueError:
        data = None
    if isinstance(data, dict) and isinstance(data.get("songs", {}), dict):
        return data
    broken = STATE_FILE.with_name(f"deezer.defekt-{time.strftime('%Y%m%d-%H%M%S')}.json")   # file name: data
    os.replace(STATE_FILE, broken)
    log(_s("⚠ Deezer: the file with the ranks was damaged – set aside as {name}.", name=broken.name))
    raise RuntimeError(_s("The Deezer file was damaged and has been set aside as {name} – the next run starts with "
                          "fresh ranks.", name=broken.name))


def last_full_run():
    """Start time of the last full run of dztnr.py (from deezer-bewertung/logs)."""
    best = None
    if not LEGACY_LOG_DIR.exists():
        return None
    for path in LEGACY_LOG_DIR.glob("deezer-rank_*.log"):
        m = re.search(r"_(\d+)\.log$", path.name)
        if not m:
            continue
        with path.open("rb") as f:
            f.seek(0, 2)
            f.seek(max(0, f.tell() - 600))
            tail = f.read().decode("utf-8", "ignore")
        tracks = re.search(r"Tracks: (\d+)", tail)
        if tracks and int(tracks.group(1)) >= 5000:
            best = max(best or 0, int(m.group(1)))
    return best


_import_lock = threading.Lock()
_RANK_LINE = re.compile(r"^\[([^\]]+)\]\s+r:(\d+|\?\?) → ★:(\d) \| (?:\(not found\) )?(.*)$")
_ALBUM_LINE = re.compile(r"^\[[^\]]+\]\s+Album: .* \(([A-Za-z0-9]+)\)\s*$")


def import_legacy(state, songs, users, log=print):
    """Take over exact ranks from the last dztnr full run – for songs that so far only counted as
    "already rated". This lets the stars be recalculated after the levels changed."""
    entries = state.setdefault("songs", {})
    need = {k for k, v in entries.items() if v.get("seed") and "r" not in v}
    started = last_full_run()
    if not need or not started:
        return 0
    path = LEGACY_LOG_DIR / f"deezer-rank_{started}.log"
    if not path.exists():
        return 0
    by_key = {}
    for s in songs:
        if s["id"] in need:
            by_key.setdefault((s.get("albumId"), (s.get("title") or "").strip()), []).append(s["id"])
    album, n = None, 0
    for line in read_text(path).splitlines():
        m = _ALBUM_LINE.match(line)
        if m:
            album = m.group(1)
            continue
        m = _RANK_LINE.match(line)
        if not m or album is None:
            continue
        ts, rank, stars, title = m.groups()
        for sid in by_key.pop((album, title.strip()), []):
            try:
                t = int(dt.datetime.strptime(ts.split(",")[0], "%Y-%m-%d %H:%M:%S").timestamp())
            except ValueError:
                t = started
            if rank == "??":
                entries[sid] = {"r": None, "s": None, "t": t, "u": {}, "imported": True}
            else:
                entries[sid] = {"r": int(rank), "s": int(stars), "t": t, "u": {u: int(stars) for u in users}, "imported": True}
            n += 1
    if n:
        log(_sn(n, "Imported {n} exact Deezer rank from the full run of {date}.",
                "Imported {n} exact Deezer ranks from the full run of {date}.",
                date=dt.datetime.fromtimestamp(started).strftime("%d.%m.%Y")))
    return n


def ensure_ranks(songs, cfg=None, env=None):
    """Once: take over the ranks from the old full run, if that has not happened yet."""
    from .config import load_env
    with _import_lock:
        state = load_state()
        if not any(v.get("seed") and "r" not in v for v in state.get("songs", {}).values()):
            return 0
        users = rating_users(env or load_env(), cfg)
        n = import_legacy(state, songs, users, log=lambda *_: None)
        if n:
            save_state(state)
        return n


_stats_memo = {"key": None, "out": None, "ids": frozenset()}


def stats(state=None, songs=None):
    """Numbers for the interface. Without state from state/deezer.json – cached until the file changes
    (it is a few MB, and the home page, the library and "to review" ask often)."""
    if state is None:
        try:
            st = STATE_FILE.stat()
            key = (st.st_mtime_ns, st.st_size)
        except OSError:
            key = None
        memo = _stats_memo
        if key is None or memo["key"] != key:
            state = load_state()
            out = stats(state)
            memo.update(key=key, out=out, ids=frozenset(state.get("songs", {})))
        out = dict(memo["out"])
        if songs is not None:
            ids = memo["ids"]
            out["new"] = sum(1 for s in songs if s["id"] not in ids) if ids else None
        return out
    entries = state.get("songs", {})
    full = state.get("full")
    out = {
        "known": len(entries),
        "found": sum(1 for e in entries.values() if e.get("r")),
        "notFound": sum(1 for e in entries.values() if "r" in e and not e.get("r")),
        "seeded": sum(1 for e in entries.values() if e.get("seed")),
        "lastRun": state.get("lastRun"),
        "lastFull": state.get("lastFull"),
        "seededFrom": state.get("seededFrom"),
        "fullRun": None,
    }
    if full:
        done = sum(1 for e in entries.values() if (e.get("t") or 0) >= full["started"])
        out["fullRun"] = {"since": dt.datetime.fromtimestamp(full["started"]).strftime("%d.%m.%Y %H:%M"),
                          "done": done, "total": full.get("total")}
    if songs is not None:
        out["new"] = sum(1 for s in songs if s["id"] not in entries) if entries else None
    return out


def seed_state(state, songs, log, before=None):
    """First start: everything that was in Navidrome before the last dztnr full run counts as rated."""
    cutoff = before or last_full_run()
    if not cutoff:
        log(_s("No earlier full run found – all songs count as new."))
        return 0
    cutoff_iso = dt.datetime.fromtimestamp(cutoff, dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")
    n = 0
    for s in songs:
        if (s.get("created") or "9999")[:19] < cutoff_iso:
            state["songs"][s["id"]] = {"seed": True}
            n += 1
    state["seededFrom"] = dt.datetime.fromtimestamp(cutoff).strftime("%d.%m.%Y %H:%M")
    log(_sn(n, "First start: {n} song was already there at the full run of {date} and counts as rated.",
            "First start: {n} songs were already there at the full run of {date} and count as rated.",
            date=state["seededFrom"]))
    return n


def run(env, mode="new", dry_run=False, max_songs=0, log=print, stop=None, overwrite_manual=None, cfg=None):
    cfg = cfg or load_config()
    dz = settings(cfg)
    thresholds = dz["thresholds"]
    if overwrite_manual is None:
        overwrite_manual = bool(dz.get("overwriteManual"))
    admin = Navidrome(env["NAV_URL"], env.get("NAV_ADMIN_USER"), env.get("NAV_ADMIN_PASS"))
    songs = admin.all_songs()
    log(_sn(len(songs), "{n} song in Navidrome.", "{n} songs in Navidrome."))

    state = _load_for_run(log)
    if not state.get("songs") and mode in ("new", "both"):
        seed_state(state, songs, log)
        if not dry_run:
            save_state(state)
    if not dry_run and import_legacy(state, songs, rating_users(env, cfg), log):
        save_state(state)

    users = {}
    for user in rating_users(env, cfg):
        pw = user_password(env, user)
        if not pw:
            log(_s("⚠ No password for “{user}” – please enter it under Settings → Navidrome.", user=user))
            continue
        try:
            nav = Navidrome(env["NAV_URL"], user, pw)
            users[user] = (nav, {s["id"]: s.get("userRating", 0) for s in nav.all_songs()})
        except NavidromeError as e:
            log(f"⚠ {e}")
            from . import auth
            if auth.wrong_password(e):   # the interface then asks for the password again
                auth.note_password(user, False)
    if not users and not dry_run:
        if not rating_users(env, cfg):
            raise RuntimeError(_("No accounts selected for rating (Settings → Deezer stars)."))
        raise RuntimeError(_("No user available for rating – passwords are missing (Settings → Navidrome)."))

    entries = state["songs"]
    if mode == "refresh":
        todo = refresh_order(songs, entries)
        max_songs = max_songs or REFRESH_PER_RUN
    elif mode == "new":
        todo = [s for s in songs if s["id"] not in entries]
    elif mode == "recalc":
        todo = [s for s in songs if entries.get(s["id"], {}).get("r")]
    elif mode in ("missing", "both"):   # both: new ones + those not found so far (setting for "update everything")
        todo = [s for s in songs if (s["id"] in entries and "r" in entries[s["id"]] and not entries[s["id"]].get("r"))
                or (mode == "both" and s["id"] not in entries)]
    else:
        full = state.get("full")
        if not full:
            full = {"started": int(time.time()), "total": len(songs)}
            if not dry_run:
                state["full"] = full
            log(_s("Full check started – it can be stopped at any time and continued later."))
        else:
            log(_s("Continuing the full check (started {date}).",
                   date=dt.datetime.fromtimestamp(full["started"]).strftime("%d.%m.%Y %H:%M")))
        todo = [s for s in songs if (entries.get(s["id"], {}).get("t") or 0) < full["started"]]
    if max_songs:
        todo = todo[:max_songs]
    label = {"new": _s("new"), "missing": _s("not found so far"), "both": _s("new or not found so far"),
             "full": _s("not checked yet"), "recalc": _s("recalculate stars from saved ranks"),
             "refresh": _s("unchecked the longest")}[mode]
    if dry_run:
        log(_sn(len(todo), "To rate: {n} song ({label}) – dry run, nothing is saved",
                "To rate: {n} songs ({label}) – dry run, nothing is saved", label=label))
    else:
        log(_sn(len(todo), "To rate: {n} song ({label})", "To rate: {n} songs ({label})", label=label))
    result = {"processed": 0, "found": 0, "notFound": 0, "set": 0, "kept": 0, "cleared": 0, "isrc": 0, "top": 0,
              "stopped": False}

    deezer = DeezerClient(rate=float(dz.get("rate") or RATE))
    mb = MusicBrainz()
    native = None
    started = time.time()
    boost_on = bool(dz.get("topBoost", True))
    boosted = top_songs(songs, entries, thresholds) if boost_on else set()

    def mbid_of(song):   # Subsonic does not deliver the MusicBrainz ID – Navidrome's own API does
        nonlocal native
        try:
            if native is None:
                from .navidrome import native_session
                native = native_session(env["NAV_URL"], env.get("NAV_ADMIN_USER"), env.get("NAV_ADMIN_PASS"))
            d = native._request("GET", f"/api/song/{urllib.parse.quote(song['id'])}")
            return d.get("mbzRecordingID") or d.get("mbzRecordingId")
        except (NavidromeError, ValueError, KeyError, TypeError):
            return None

    def lookup(song):
        if stop is not None and stop.is_set():
            return song, "stop", None
        if mode == "recalc":   # look nothing up – take the saved rank
            return song, entries[song["id"]]["r"], None
        rank = deezer.best_rank(song)
        if rank:
            return song, rank, None
        known = (entries.get(song["id"]) or {}).get("i")   # fallback: exactly via the ISRC
        for isrc in [known] if known else mb.isrcs(mbid_of(song)):
            rank = deezer.rank_by_isrc(isrc)
            if rank:
                return song, rank, isrc
        return song, None, None

    try:
        _process(todo, pool_lookup=lookup, entries=entries, users=users, mode=mode, dry_run=dry_run,
                 overwrite_manual=overwrite_manual, result=result, log=log, state=state, started=started,
                 thresholds=thresholds, boosted=boosted)
        if boost_on and not result["stopped"]:   # top tracks after the new ranks: only what changes because of them
            boosted = top_songs(songs, entries, thresholds)
            by_id = {s["id"]: s for s in songs}
            for sid, e in list(entries.items()):
                if e.get("r") and sid in by_id and _stars(e["r"], thresholds, sid in boosted) != e.get("s"):
                    _apply(by_id[sid], e["r"], entries, users, "top", dry_run, overwrite_manual, result, log, thresholds,
                           boosted=boosted, isrc=e.get("i"))
    finally:   # also when an error stops the run: save what was done, otherwise our own stars later count as "manual"
        if not dry_run:
            save_state(state)

    now = dt.datetime.now().strftime("%d.%m.%Y %H:%M")
    state["lastRun"] = now
    if mode == "full" and not result["stopped"] and not max_songs:
        state.pop("full", None)
        state["lastFull"] = now
    if not dry_run:
        save_state(state)
    # one translated phrase per number, joined as a list
    if result["isrc"]:
        parts = [_s("{found} found ({isrc} of them via the ISRC)", found=result["found"], isrc=result["isrc"])]
    else:
        parts = [_s("{n} found", n=result["found"])]
    parts += [_s("{n} not found", n=result["notFound"]),
              _sn(result["set"], "{n} rating set", "{n} ratings set"),
              _sn(result["kept"], "{n} manual rating kept", "{n} manual ratings kept")]
    if result["cleared"]:
        parts.append(_sn(result["cleared"], "{n} wrong star removed", "{n} wrong stars removed"))
    if result["top"]:
        parts.append(_sn(result["top"], "{n} top track highlighted", "{n} top tracks highlighted"))
    log(_s("Deezer done: {details}.", details=", ".join(parts)))
    return result


def refresh_order(songs, entries):
    """Refresh: first what is still rated with the old search, then what has been unchecked the longest."""
    return sorted((s for s in songs if s["id"] in entries),
                  key=lambda s: ((entries[s["id"]].get("v") or 1) >= 2, entries[s["id"]].get("t") or 0))


def _stars(rank, thresholds, boost):
    return min(5, rank_to_stars(rank, thresholds) + (1 if boost else 0))


def _process(todo, pool_lookup, entries, users, mode, dry_run, overwrite_manual, result, log, state, started, thresholds=None,
             boosted=frozenset()):
    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        for chunk_start in range(0, len(todo), 200):
            chunk = todo[chunk_start:chunk_start + 200]
            for song, rank, isrc in pool.map(pool_lookup, chunk):
                if rank == "stop":
                    result["stopped"] = True
                    continue
                _apply(song, rank, entries, users, mode, dry_run, overwrite_manual, result, log, thresholds,
                       boosted=boosted, isrc=isrc)
            done = chunk_start + len(chunk)
            if not dry_run:
                save_state(state)
            if result["stopped"]:
                log(_s("Stopped – progress is saved."))
                break
            if len(todo) > 200:
                rate = done / max(1e-6, time.time() - started)
                log(_s("  … {done}/{total} ({rate:.1f} songs/s, about {minutes} min left)", done=done, total=len(todo),
                       rate=rate, minutes=int((len(todo) - done) / rate / 60)))


def _apply(song, rank, entries, users, mode, dry_run, overwrite_manual, result, log, thresholds=None,
           boosted=frozenset(), isrc=None):
    """mode "top": only adjust the stars to the top-track rule (rank as saved, no new check date)."""
    for k in ("cleared", "isrc", "top"):
        result.setdefault(k, 0)
    artist = song.get("artist") or song.get("displayArtist") or ""
    boost = song["id"] in boosted
    stars = _stars(rank, thresholds, boost) if rank else None
    prev = entries.get(song["id"], {})
    entry = {"r": rank, "s": stars, "t": prev.get("t") if mode == "top" else int(time.time()), "u": dict(prev.get("u", {})),
             "v": 2 if mode not in ("recalc", "top") else prev.get("v", 1)}
    if isrc or prev.get("i"):
        entry["i"] = isrc or prev["i"]
    if boost:
        entry["b"] = 1
    if mode == "top":
        result["top"] += boost
    else:
        result["processed"] += 1
        result["isrc"] += bool(isrc)
    if stars is None:
        result["notFound"] += 1
        log(_s("  ?? {artist} – {title} (not found on Deezer)", artist=artist, title=song.get("title")))
        if prev.get("s"):   # wrongly matched by the old search: remove the stars Tuttiphon set
            for user, (nav, current) in users.items():
                cur = current.get(song["id"], 0) or 0
                last_set = prev.get("u", {}).get(user, prev.get("s") if prev.get("seed") else None)
                if cur and cur == last_set and not dry_run:
                    try:
                        nav.set_rating(song["id"], 0)
                    except NavidromeError as e:
                        log(_s("  ⚠ {artist} – {title}: star for {user} not removed ({error})", artist=artist,
                               title=song.get("title"), user=user, error=e))
                        return
                    current[song["id"]] = 0
                    result["cleared"] += 1
                entry["u"].pop(user, None)
    else:
        result["found"] += mode != "top"
        notes = [_s("top track of the band") if boost else _s("no longer a top track")] if mode == "top" else []
        for user, (nav, current) in users.items():
            cur = current.get(song["id"], 0) or 0
            last_set = prev.get("u", {}).get(user)
            if last_set is None and prev.get("seed"):
                last_set = prev.get("s")   # taken over from the old log: back then the calculated star was set
            manual = cur and cur != stars and cur != last_set
            if manual and not overwrite_manual:
                result["kept"] += 1
                notes.append(_s("{user}: {stars}★ by hand, stays", user=user, stars=cur))
                continue
            if cur != stars and not dry_run:
                try:
                    nav.set_rating(song["id"], stars)
                except NavidromeError as e:   # Navidrome briefly gone: this song again in the next run
                    log(_s("  ⚠ {artist} – {title}: star for {user} not set ({error})", artist=artist,
                           title=song.get("title"), user=user, error=e))
                    return
                current[song["id"]] = stars
                result["set"] += 1
            entry["u"][user] = stars
        changed = prev.get("s") is not None and prev.get("s") != stars
        if mode not in ("full", "recalc", "refresh", "top") or changed or notes:
            # the annotations in brackets are translated one by one and appended to the line
            log(f"  {'★' * stars}{'☆' * (5 - stars)}  r:{rank:<7} {artist} – {song.get('title')}"
                + ("  " + _s("(before {stars}★)", stars=prev["s"]) if changed else "")
                + (f"  ({'; '.join(notes)})" if notes else ""))
    entries[song["id"]] = entry
