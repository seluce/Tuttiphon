"""Sound similarity for Navidrome – what the Tuttiphon plugin (navidrome-plugin/) asks for: songs that sound like a
song, an album or a band (Instant Mix, "similar songs", song and artist radio in Symfonium), similar bands, and a
path of songs from one song to another, each step sounding close to the last.

Answers come from the sound vectors of the AI sound analysis (similar.py); a song without one falls back to the radio
(Last.fm's similar bands and genres, classify.radio_artists()) ordered by the features we measured. Songs are
Navidrome's own ids, so the plugin can hand them on as they are.

Navidrome does not say who is listening. So the songs come from the whole library as for the shared person: "All"
(without the separate worlds such as children's music and audio plays – unless the song asked for is in one of them),
without the shared person's dislikes, without live recordings and the like (settings.excludeTitles, minDuration) –
and without explicit songs as soon as there is a child profile.

The plugin signs in with its own key (Settings → Navidrome plugin): only its SHA-256 is stored (state/plugin_key.json),
the key itself is shown once.
"""
import datetime as dt
import hashlib
import hmac
import json
import random
import re
import secrets
import threading
import time
from collections import Counter
from pathlib import Path

from . import classify, ml, rules, similar, taste
from .config import STATE_DIR, read_text, write_atomic

KEY_FILE = STATE_DIR / "plugin_key.json"
_ROOT = Path(__file__).resolve().parent.parent
PLUGIN_FILES = (_ROOT / "plugin" / "tuttiphon.ndp",                     # in the Docker image
                _ROOT / "navidrome-plugin" / "dist" / "tuttiphon.ndp")   # built here (tools/build-plugin.sh)
NEIGHBORS = 400        # nearest songs looked at per song (cached in similar.Index)
MAX_COUNT = 200        # never more songs per answer
RADIO_BONUS = 0.1      # a band Last.fm counts as similar moves up this much (artist radio)
_lock = threading.Lock()
_memo = {}
_seen = {"at": None, "calls": 0}   # the last call of the plugin (for the settings page)


# ---------------------------------------------------------------------------- the plugin's key

def _stored():
    try:
        data = json.loads(read_text(KEY_FILE))
        return data if isinstance(data, dict) and isinstance(data.get("sha256"), str) else None
    except (OSError, ValueError):
        return None


def new_key():
    """A new key for the plugin – the old one stops working. -> the key (shown once, only its hash is stored)."""
    key = "tp_" + secrets.token_urlsafe(32)
    KEY_FILE.parent.mkdir(parents=True, exist_ok=True)
    write_atomic(KEY_FILE, json.dumps({"sha256": hashlib.sha256(key.encode()).hexdigest(),
                                       "at": dt.datetime.now().isoformat(timespec="seconds")}))
    return key


def remove_key():
    KEY_FILE.unlink(missing_ok=True)


def check_key(key):
    """Is this the plugin's key? (constant time)"""
    stored = _stored()
    if not stored or not isinstance(key, str) or not key:
        return False
    ok = hmac.compare_digest(hashlib.sha256(key.encode()).hexdigest(), stored["sha256"])
    if ok:
        with _lock:
            _seen["at"] = dt.datetime.now().isoformat(timespec="seconds")
            _seen["calls"] += 1
    return ok


def plugin_file():
    """The plugin to download (tuttiphon.ndp), or None if this installation has none."""
    return next((f for f in PLUGIN_FILES if f.is_file()), None)


def status():
    """For the settings page: is there a key, when did the plugin last ask, how many songs have a sound vector."""
    stored = _stored()
    return {"key": bool(stored), "keyAt": (stored or {}).get("at"), "lastCall": _seen["at"], "calls": _seen["calls"],
            "vectors": similar.count()}


# ---------------------------------------------------------------------------- the songs that may come

def _view(cfg):
    """The configuration as the plugin sees the library: the shared person, with kid-safe mode as soon as there is
    a child profile (Navidrome does not say who is listening)."""
    default = cfg["settings"].get("defaultPerson")
    child = any(p.get("child") for p in cfg.get("personen", []))
    personen = [{**p, "clean": True} if p["id"] == default and child else p for p in cfg.get("personen", [])]
    return {**cfg, "personen": personen}, default


def _cfg_key(cfg):
    parts = [cfg.get("welten"), cfg.get("stile"), cfg.get("settings"),
             [(p.get("id"), p.get("clean"), p.get("child"), p.get("dislikes")) for p in cfg.get("personen", [])]]
    return hashlib.sha1(json.dumps(parts, sort_keys=True, default=str).encode()).hexdigest()


def _pool(cfg, lib, worlds=()):
    """Indices of the songs that may come: "All" for the shared person (minimum rating 0) – plus the separate worlds
    `worlds` (those of the song asked for)."""
    key = ("pool", ml.lib_key(lib), _cfg_key(cfg), tuple(sorted(worlds)))
    with _lock:
        if key in _memo:
            return _memo[key]
    view, default = _view(cfg)
    base = {"id": "_sonic", "person": default, "welt": rules.ALL, "stil": rules.ALL, "minRating": 0}
    ctx = rules.BuildContext(lib)
    ids = set(lib.match(rules.build_nsp(view, base, ctx)))
    if worlds:
        ids |= set(lib.match(rules.build_nsp(view, {**base, "welt": sorted(worlds)}, ctx)))
    out = frozenset(ids)
    with _lock:
        if len(_memo) > 16:
            _memo.clear()
        _memo[key] = out
    return out


def _worlds_of(cfg, lib, indices):
    """The separate music worlds these songs are in."""
    out = set()
    for w in cfg["welten"]:
        if w.get("separate") and taste.excluded_ids(cfg, lib, (w["id"],)) & set(indices):
            out.add(w["id"])
    return out


def _all_batch():
    """All sound vectors as one batch (similar.Batch) – kept until the vectors change. -> (song ids, Batch) or None"""
    stamp = similar.stamp()
    with _lock:
        hit = _memo.get("batch")
    if hit and hit[0] == stamp:
        return hit[1]
    out = similar.batch()
    with _lock:
        _memo["batch"] = (stamp, out)
    return out


def _closest(lib, vec, allowed, exclude=frozenset()):
    """[(index, score)] of the allowed songs with a vector, by closeness to the unit vector vec, best first."""
    got = _all_batch()
    if not got or vec is None:
        return []
    sids, b = got
    index = lib.index_of()
    scored = []
    for sid, sc in zip(sids, b.closeness(vec)):
        i = index.get(sid)
        if i is not None and i in allowed and i not in exclude:
            scored.append((i, sc))
    scored.sort(key=lambda x: -x[1])
    return scored


_PAREN = re.compile(r"\s*[\(\[].*?[\)\]]")


def _same_song(s):
    """Key of a recording regardless of edition – "Song (Remastered)" and "Song" are the same."""
    return (_PAREN.sub("", (s.get("title") or "").lower()).strip(), (s.get("artist") or "").lower())


def _diverse(lib, scored, count, seeds=(), seed_share=0.25):
    """The best `count` of scored [(index, score)] – at most a few per band (the seed bands a bit more), every recording
    once, none of the seeds."""
    songs = lib.songs
    seed_artists = {lib._main_artist(songs[i]) for i in seeds}
    taken = {_same_song(songs[i]) for i in seeds}
    per = Counter()
    cap_other = max(2, count // 12)
    cap_seed = max(cap_other, round(count * seed_share))
    out = []
    for i, sc in scored:
        if i in seeds:
            continue
        s = songs[i]
        a = lib._main_artist(s)
        same = _same_song(s)
        if same in taken or per[a] >= (cap_seed if a in seed_artists else cap_other):
            continue
        taken.add(same)
        per[a] += 1
        out.append((i, max(0.0, min(1.0, round(sc, 4)))))
        if len(out) >= count:
            break
    return out


def _radio(cfg, lib, i, allowed, exclude):
    """Without a sound vector: songs of the band and similar bands (radio) ordered by how much they sound like song i
    (our features), with falling scores."""
    artist = lib._main_artist(lib.songs[i])
    bands = set(classify.radio_artists([artist], lib, limit=25))
    cands = [j for j in allowed if j not in exclude and lib._main_artist(lib.songs[j]) in bands]
    ranked = classify.rank_like(lib, i, cands, random.Random(lib.songs[i]["id"]))
    idx = similar.index(lib)
    out = []
    for k, j in enumerate(ranked):
        c = idx.cos(i, j) if idx is not None else None
        out.append((j, c if c is not None else max(0.05, 0.5 - 0.45 * k / max(1, len(ranked)))))
    return out


def _clamp(count, default=50):
    try:
        return max(1, min(MAX_COUNT, int(count)))
    except (TypeError, ValueError):
        return default


# ---------------------------------------------------------------------------- answers

def similar_songs(cfg, lib, song_id, count=50):
    """Songs that sound like this one (Instant Mix, song radio): [(index, similarity 0–1)]."""
    count = _clamp(count)
    i = lib.index_of().get(song_id)
    if i is None:
        return []
    allowed = _pool(cfg, lib, _worlds_of(cfg, lib, [i]))
    idx = similar.index(lib)
    scored = []
    if idx is not None and idx.has(i):
        scored = [(j, sc) for j, sc in idx.neighbors(i, NEIGHBORS) if j in allowed]
    out = _diverse(lib, scored, count, seeds=[i])
    if len(out) < count:   # no vector (yet) or too few near ones: the radio fills up
        have = {j for j, _sc in out} | {i}
        out = _diverse(lib, out + _radio(cfg, lib, i, allowed, have), count, seeds=[i])
    return out


def _artist_songs(lib, name=None, artist_id=None):
    """Songs of a band – by Navidrome's artist id or its name, as main artist, among the artists or as album artist
    (Navidrome asks for every artist, also one who only takes part) – and the band as Tuttiphon counts it: the main
    artist of most of them. -> (indices, band name)"""
    songs = lib.songs
    low = (name or "").lower()

    def hit(s):
        people = (s.get("artists") or []) + (s.get("albumArtists") or [])
        if artist_id and (s.get("artistId") == artist_id or any(a.get("id") == artist_id for a in people)):
            return True
        return bool(low) and ((lib._main_artist(s) or "").lower() == low or any((a.get("name") or "").lower() == low
                                                                               for a in people))
    found = [i for i, s in enumerate(songs) if hit(s)]
    if not found:
        return [], name
    main = Counter(lib._main_artist(songs[i]) for i in found).most_common(1)[0][0]
    return found, main


def songs_like_artist(cfg, lib, name=None, artist_id=None, count=50):
    """Artist radio: songs that sound like the band – its own, of bands that sound like it and of those Last.fm counts
    as similar (RADIO_BONUS); without vectors the radio's bands, shuffled by the day."""
    count = _clamp(count)
    own, artist = _artist_songs(lib, name, artist_id)
    if not own:
        return []
    allowed = _pool(cfg, lib, _worlds_of(cfg, lib, own))
    bands = set(classify.radio_artists([artist], lib, limit=25))
    idx = similar.index(lib)
    centre = idx.centroid(artist) if idx is not None else None
    if centre is not None:
        scored = [(i, sc + (RADIO_BONUS if lib._main_artist(lib.songs[i]) in bands else 0))
                  for i, sc in _closest(lib, centre, allowed)]
        scored.sort(key=lambda x: -x[1])
    else:
        rnd = random.Random(f"{artist}|{dt.date.today()}")
        cands = [i for i in allowed if lib._main_artist(lib.songs[i]) in bands]
        rnd.shuffle(cands)
        scored = [(i, 0.5) for i in cands]
    return _diverse_with_own(lib, scored, count, artist)


def _diverse_with_own(lib, scored, count, artist):
    """As _diverse(), the band itself with up to a third of the songs."""
    songs = lib.songs
    per, taken, out = Counter(), set(), []
    cap_other, cap_own = max(2, count // 12), max(2, count // 3)
    for i, sc in scored:
        a = lib._main_artist(songs[i])
        same = _same_song(songs[i])
        if same in taken or per[a] >= (cap_own if a == artist else cap_other):
            continue
        taken.add(same)
        per[a] += 1
        out.append((i, max(0.0, min(1.0, round(sc, 4)))))
        if len(out) >= count:
            break
    return out


def songs_like_album(cfg, lib, album_id=None, name=None, artist=None, count=50):
    """Songs that sound like an album (its mean sound) – not from the album itself."""
    count = _clamp(count)
    songs = lib.songs
    own = [i for i, s in enumerate(songs) if album_id and s.get("albumId") == album_id]
    if not own and name:
        own = [i for i, s in enumerate(songs) if (s.get("album") or "").lower() == name.lower()
               and (not artist or artist.lower() in ((s.get("displayAlbumArtist") or s.get("artist") or "").lower()))]
    if not own:
        return []
    allowed = _pool(cfg, lib, _worlds_of(cfg, lib, own))
    idx = similar.index(lib)
    vec = similar.mean_unit([v for v in (idx.centered(i) for i in own) if v is not None]) if idx is not None else None
    if vec is not None:
        return _diverse(lib, _closest(lib, vec, allowed, exclude=set(own)), count, seeds=own)
    return songs_like_artist(cfg, lib, name=lib._main_artist(songs[own[0]]), count=count)


def similar_artists(cfg, lib, name=None, artist_id=None, limit=20):
    """Bands that sound like this one or count as similar (radio): [(name, artist id or None)] – only bands that are in
    the library, never the band itself."""
    limit = _clamp(limit, 20)
    own, artist = _artist_songs(lib, name, artist_id)
    if not artist:
        return []
    ids = {}
    for s in lib.songs:
        a = lib._main_artist(s)
        if a and a not in ids:
            ids[a] = ((s.get("artists") or [{}])[0]).get("id") or s.get("artistId")
    return [(a, ids.get(a)) for a in classify.radio_artists([artist], lib, limit=limit + 1) if a != artist][:limit]


def path(cfg, lib, start_id, end_id, count=25):
    """A path from one song to another: `count` songs (with both ends), each step sounding close to the last – at
    every step the song nearest to the point between the two sounds. [(index, similarity to that point)]; empty
    without sound vectors for both."""
    count = max(2, _clamp(count, 25))
    index = lib.index_of()
    a, b = index.get(start_id), index.get(end_id)
    idx = similar.index(lib)
    if a is None or b is None or idx is None:
        return []
    va, vb = idx.centered(a), idx.centered(b)
    va, vb = similar.unit(va) if va is not None else None, similar.unit(vb) if vb is not None else None
    if va is None or vb is None:
        return []
    allowed = _pool(cfg, lib, _worlds_of(cfg, lib, [a, b]))
    got = _all_batch()
    if not got:
        return []
    sids, batch = got
    rows = [(index.get(sid), k) for k, sid in enumerate(sids)]
    rows = [(i, k) for i, k in rows if i is not None and i in allowed]
    used = {a, b}
    taken = {_same_song(lib.songs[a]), _same_song(lib.songs[b])}
    out = [(a, 1.0)]
    for step in range(1, count - 1):
        t = step / (count - 1)
        target = similar.unit([(1 - t) * x + t * y for x, y in zip(va, vb)])
        if target is None:
            continue
        scores = batch.closeness(target)
        best = None
        for i, k in rows:
            if i in used or (best is not None and scores[k] <= best[1]):
                continue
            if _same_song(lib.songs[i]) in taken:
                continue
            best = (i, scores[k])
        if best is None:
            break
        used.add(best[0])
        taken.add(_same_song(lib.songs[best[0]]))
        out.append((best[0], max(0.0, min(1.0, round(best[1], 4)))))
    out.append((b, 1.0))
    return out


def as_songs(lib, scored):
    """[(index, similarity)] -> what the plugin hands to Navidrome."""
    out = []
    for i, sc in scored:
        s = lib.songs[i]
        out.append({"id": s["id"], "title": s.get("title") or "", "artist": lib._main_artist(s) or s.get("artist") or "",
                    "album": s.get("album") or "", "durationMs": int((s.get("duration") or 0) * 1000),
                    "similarity": sc})
    return out


def answer(cfg, lib, what, query):
    """One request of the plugin: what = similar | artist | album | artists | path. -> JSON-able dict"""
    started = time.time()
    if what == "similar":
        out = {"songs": as_songs(lib, similar_songs(cfg, lib, query.get("id", ""), query.get("count", 50)))}
    elif what == "artist":
        out = {"songs": as_songs(lib, songs_like_artist(cfg, lib, query.get("name"), query.get("id"), query.get("count", 50)))}
    elif what == "album":
        out = {"songs": as_songs(lib, songs_like_album(cfg, lib, query.get("id"), query.get("name"), query.get("artist"),
                                                       query.get("count", 50)))}
    elif what == "artists":
        out = {"artists": [{"name": n, "id": a or ""} for n, a in similar_artists(cfg, lib, query.get("name"), query.get("id"),
                                                                                  query.get("count", 20))]}
    elif what == "path":
        out = {"songs": as_songs(lib, path(cfg, lib, query.get("from", ""), query.get("to", ""), query.get("count", 25)))}
    else:
        raise KeyError(what)
    out["ms"] = round((time.time() - started) * 1000)
    return out
