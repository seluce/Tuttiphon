"""Sound similarity for Navidrome – what the Tuttiphon plugin (navidrome-plugin/) asks for: songs that sound like a
song, an album or a band (Instant Mix, "similar songs", song and artist radio in Symfonium), similar bands, and a
path of songs from one song to another, each step sounding close to the last.

Answers come from the sound vectors of the AI sound analysis (similar.py); a song without one falls back to the radio
(Last.fm's similar bands and genres, classify.radio_artists()) ordered by the features we measured. Songs are
Navidrome's own ids, so the plugin can hand them on as they are.

Navidrome does not say who asks. So the songs come from the whole library as for the shared person: "All" (without
the separate worlds such as children's music and audio plays – unless the song asked for is in one of them), without
the shared person's dislikes, without live recordings and the like (settings.excludeTitles, minDuration) – and
without explicit songs as soon as a profile is kid-safe. But Tuttiphon knows from the live plays (listen.py) who is
playing what: if the song asked about (or a song of the band or album) is playing on exactly one account – or only
one account is playing at all – the answer is for that person (_listener()): their "All" and dislikes, without what
they heard in the last hours or rated 1 star by hand, songs they skip further down. Kid-safe stays as for the
family – never loosened on a guess.

The plugin signs in with its own key (Settings → Navidrome, card "Navidrome plugin"): only its SHA-256 is stored
(state/plugin_key.json),
the key itself is shown once.
"""
import datetime as dt
import hashlib
import heapq
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
MAX_COUNT = 200        # never more songs per answer
RADIO_BONUS = 0.1      # a band Last.fm counts as similar moves up this much (artist radio)
RUN_MAX = 2            # the smart queue: after this many songs of one band in a row, other bands come first …
RUN_FACTOR = 0.2       # … (that band's scores times this)
HOUR_FACTOR = 0.85     # a band heard several times in the last hour: times this for every further song of it
_lock = threading.Lock()
_memo = {}
_seen = {"at": None, "calls": 0, "for": None}   # the last call of the plugin (for the settings page)
_stars = {}   # account (lower case) -> (time, song ids rated 1 star by hand) – loaded in the background (_rated_one())
STARS_AGE = 3600
_FAMILY = (None, frozenset(), {})   # (person id, indices to leave out, {index: factor}): an answer for the family
_last = threading.local()


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


def has_key():
    """Is the plugin set up (a key created)?"""
    return _stored() is not None


def check_key(key):
    """Is this the plugin's key? (constant time)"""
    stored = _stored()
    if not stored or not isinstance(key, str) or not key:
        return False
    return hmac.compare_digest(hashlib.sha256(key.encode()).hexdigest(), stored["sha256"])


def plugin_file():
    """The plugin to download (tuttiphon.ndp), or None if this installation has none."""
    return next((f for f in PLUGIN_FILES if f.is_file()), None)


def status():
    """For the settings page: is there a key, when did the plugin last ask, how many songs have a sound vector."""
    stored = _stored()
    return {"key": bool(stored), "keyAt": (stored or {}).get("at"), "lastCall": _seen["at"], "calls": _seen["calls"],
            "lastFor": _seen["for"], "vectors": similar.count()}


# ---------------------------------------------------------------------------- the songs that may come

def _view(cfg, pid=None):
    """The configuration as the plugin sees the library: the person listening (pid) or the shared person – kid-safe as
    soon as any profile is a child profile or has kid-safe mode on. Without a shared person a stand-in without
    dislikes. -> (configuration, person id)"""
    default = pid or cfg["settings"].get("defaultPerson")
    clean = any(p.get("child") or p.get("clean") for p in cfg.get("personen", []))
    personen = [dict(p) for p in cfg.get("personen", [])]
    me = next((p for p in personen if p["id"] == default), None)
    if me is None:
        me = {"id": "_sonic", "name": "", "user": ""}
        personen.append(me)
    if clean:
        me["clean"] = True
    return {**cfg, "personen": personen}, me["id"]


def _cfg_key(cfg):
    parts = [cfg.get("welten"), cfg.get("stile"), cfg.get("settings"),
             [(p.get("id"), p.get("clean"), p.get("child"), p.get("dislikes")) for p in cfg.get("personen", [])]]
    return hashlib.sha1(json.dumps(parts, sort_keys=True, default=str).encode()).hexdigest()


def _remember(kind, key, value, keep=16):
    """Into the memory of this kind – the entries of another song list go (the list is reloaded now and then)."""
    with _lock:
        box = _memo.setdefault(kind, {})
        for k in [k for k in box if k[0] != key[0]]:
            del box[k]
        if len(box) >= keep:
            box.pop(next(iter(box)))
        box[key] = value
    return value


def _recall(kind, key):
    with _lock:
        return _memo.get(kind, {}).get(key)


def _pool(cfg, lib, worlds=(), pid=None):
    """Indices of the songs that may come: "All" for the person listening (pid) or the shared person (minimum rating
    0) – plus the separate worlds `worlds` (those of the song asked for)."""
    key = (ml.lib_key(lib), _cfg_key(cfg), tuple(sorted(worlds)), pid)
    hit = _recall("pool", key)
    if hit is not None:
        return hit
    view, person = _view(cfg, pid)
    base = {"id": "_sonic", "person": person, "welt": rules.ALL, "stil": rules.ALL, "minRating": 0}
    ctx = rules.BuildContext(lib)
    ids = set(lib.match(rules.build_nsp(view, base, ctx)))
    if worlds:
        ids |= set(lib.match(rules.build_nsp(view, {**base, "welt": sorted(worlds)}, ctx)))
    return _remember("pool", key, frozenset(ids))


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


def _listener(cfg, ids):
    """The person listening to one of these songs right now (listen.listener()) – the person of that account; if the
    shared person uses the account too ("Family" on a parent's account), the account's own person. None if that is
    unclear."""
    from . import listen
    from .config import slug
    folder = listen.listener(ids)
    if not folder:
        return None
    people = [p for p in cfg.get("personen", []) if p.get("user") and slug(p["user"]) == folder]
    if len(people) > 1:
        people = [p for p in people if p["id"] != cfg["settings"].get("defaultPerson")]
    if len(people) != 1 or not listen.allowed(cfg, people[0]["user"]):
        return None
    return people[0]


def _rated_one(lib, user):
    """Song ids this account rated 1 star by hand (feedback.manual_dislikes) – from the song list of the account,
    loaded in the background (it takes a while; until then none) and again after STARS_AGE."""
    from . import feedback
    if (getattr(lib, "user", None) or "").lower() == user.lower():
        return feedback.manual_dislikes(lib, user)
    low = user.lower()
    with _lock:
        hit = _stars.get(low)
        load = not hit or time.time() - hit[0] > STARS_AGE
        if load:
            _stars[low] = (time.time(), hit[1] if hit else frozenset())   # loading – not again meanwhile

    def fetch():
        from . import stats
        try:
            got = frozenset(feedback.manual_dislikes(stats.songs_for(user, lib), user))
        except Exception:   # noqa: BLE001 – no password for the account, Navidrome gone: no 1 stars then
            return
        with _lock:
            _stars[low] = (time.time(), got)
    if load:
        threading.Thread(target=fetch, daemon=True).start()
    return hit[1] if hit else frozenset()


def _bands(lib):
    """Main artist -> song indices (per song list)."""
    key = (ml.lib_key(lib),)
    hit = _recall("bands", key)
    if hit is None:
        hit = {}
        for i, s in enumerate(lib.songs):
            hit.setdefault(lib._main_artist(s), []).append(i)
        _remember("bands", key, hit, keep=2)
    return hit


def _variety(lib, user, seed):
    """{index: factor} so that the smart queue does not stay with one band: Symfonium asks about every new song and
    takes the most similar – mostly of the same band. After RUN_MAX songs of the band in a row (the song asked about
    included) its songs come after the others (RUN_FACTOR); a band heard several times in the last hour comes a
    little later (HOUR_FACTOR for every further song of it)."""
    from . import listen
    index = lib.index_of()
    seq = [index[s] for s in listen.sequence(user) if s in index]
    if not seq or seq[-1] != seed:
        seq.append(seed)
    band = lib._main_artist(lib.songs[seed])
    run = 0
    for i in reversed(seq):
        if lib._main_artist(lib.songs[i]) != band:
            break
        run += 1
    members = _bands(lib)
    out = {}
    for b, n in Counter(lib._main_artist(lib.songs[i]) for i in seq).items():
        if n > 1:
            for j in members.get(b, ()):
                out[j] = HOUR_FACTOR ** (n - 1)
    if run >= RUN_MAX:
        for j in members.get(band, ()):
            out[j] = out.get(j, 1.0) * RUN_FACTOR
    return out


def _who(cfg, lib, ids, personal, seed=None):
    """For whom the answer is: (person id, indices to leave out, {index: factor}) of the person listening to one of
    these song ids – what they heard in the last hours (listen.heard()) or rated 1 star by hand stays out, what they
    skip comes further down (feedback.factors(), with "Mixes that learn" on); for the songs like `seed` (the smart
    queue) also variety between bands (_variety()). _FAMILY if not asked or unclear."""
    _last.person = None
    person = _listener(cfg, ids) if personal else None
    if not person:
        return _FAMILY
    from . import feedback, listen
    _last.person = person.get("name") or person["id"]
    user = person["user"]
    index = lib.index_of()
    leave = frozenset(index[s] for s in listen.heard(user) | _rated_one(lib, user) if s in index)
    factor = {}
    if cfg["settings"].get("mixLearn", True):
        factor = {index[s]: f for s, f in feedback.factors(user).items() if s in index}
    if seed is not None:
        for j, f in _variety(lib, user, seed).items():
            factor[j] = factor.get(j, 1.0) * f
    return person["id"], leave, factor


def _favour(scored, factor):
    """Scores times the person's factors (skipped songs < 1), best first again."""
    if not factor:
        return scored
    return sorted(((i, sc * factor.get(i, 1.0)) for i, sc in scored), key=lambda x: -x[1])


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


def _albums(lib):
    """Album id -> song indices (per song list)."""
    key = (ml.lib_key(lib),)
    hit = _recall("albums", key)
    if hit is None:
        hit = {}
        for i, s in enumerate(lib.songs):
            hit.setdefault(s.get("albumId"), []).append(i)
        _remember("albums", key, hit, keep=2)
    return hit


def _sound(lib, idx, i):
    """The sound of song i as a unit vector: its own – or, while the AI has not analysed it yet, the mean sound of its
    album, otherwise of its band. None without anything."""
    if idx is None:
        return None
    own = idx.centered(i)
    if own is not None:
        return similar.unit(own)
    album = [v for v in (idx.centered(j) for j in _albums(lib).get(lib.songs[i].get("albumId"), ()) if j != i)
             if v is not None]
    if album:
        return similar.mean_unit(album)
    return idx.centroid(lib._main_artist(lib.songs[i]))


_PAREN = re.compile(r"\s*[\(\[](?![^\)\]]*\d)[^\)\]]*[\)\]]")   # “(Remastered)”, “[Live]” – not “(Part 2)”, “(2011)”


class _Seen:
    """Every recording once: the same title and band with about the same length (± 4 s) is the same recording –
    “Song (Remastered)” and “Song”; “Intro” of two albums or “Teil 1”/“Teil 2” are not."""

    def __init__(self):
        self.lengths = {}

    def add(self, s):
        """-> False if this recording was taken already."""
        key = (_PAREN.sub("", (s.get("title") or "").lower()).strip(), (s.get("artist") or "").lower())
        d = s.get("duration") or 0
        known = self.lengths.setdefault(key, [])
        if any(not d or not x or abs(d - x) <= 4 for x in known):
            return False
        known.append(d)
        return True


def _diverse(lib, scored, count, seeds=(), seed_share=0.25, own=None, exclude=frozenset()):
    """The best `count` of scored [(index, score)] – at most a few per band (the seed bands a bit more; `own`: this
    band up to a third), every recording once, none of the seeds or `exclude`."""
    songs = lib.songs
    seed_artists = {lib._main_artist(songs[i]) for i in seeds}
    seen = _Seen()
    for i in seeds:
        seen.add(songs[i])
    per = Counter()
    cap_other = max(2, count // 12)
    cap_seed = max(cap_other, round(count * seed_share))
    cap_own = max(2, count // 3)
    out = []
    for i, sc in scored:
        if i in seeds or i in exclude:
            continue
        s = songs[i]
        a = lib._main_artist(s)
        cap = cap_own if a == own else cap_seed if a in seed_artists else cap_other
        if per[a] >= cap or not seen.add(s):
            continue
        per[a] += 1
        out.append((i, max(0.0, min(1.0, round(sc, 4)))))
        if len(out) >= count:
            break
    return out


def _radio(lib, i, allowed, exclude, count, below=0.5):
    """Without any sound: songs of the band and similar bands (radio) ordered by how much they sound like song i
    (our features). Scores fall from `below` – always under the real ones they follow – over `count` places."""
    artist = lib._main_artist(lib.songs[i])
    bands = set(classify.radio_artists([artist], lib, limit=25))
    cands = [j for j in allowed if j not in exclude and lib._main_artist(lib.songs[j]) in bands]
    ranked = classify.rank_like(lib, i, cands, random.Random(lib.songs[i]["id"]))
    top = max(0.05, min(0.5, below - 0.01))
    return [(j, max(0.01, top - (top - 0.01) * k / max(1, count))) for k, j in enumerate(ranked)]


def _clamp(count, default=50):
    try:
        return max(1, min(MAX_COUNT, int(count)))
    except (TypeError, ValueError):
        return default


# ---------------------------------------------------------------------------- answers

def similar_songs(cfg, lib, song_id, count=50, personal=False):
    """Songs that sound like this one (Instant Mix, song radio, the smart queue): [(index, similarity 0–1)], most
    similar first. personal: for the person listening to it, if that is clear (_who())."""
    count = _clamp(count)
    i = lib.index_of().get(song_id)
    if i is None:
        return []
    pid, leave, factor = _who(cfg, lib, {song_id}, personal, seed=i)
    allowed = _pool(cfg, lib, _worlds_of(cfg, lib, [i]), pid)
    key = (ml.lib_key(lib), _cfg_key(cfg), similar.stamp(), song_id, count)
    if pid is None:
        hit = _recall("similar", key)
        if hit is not None:
            return hit
    idx = similar.index(lib)
    scored = _favour(_closest(lib, _sound(lib, idx, i), allowed, exclude={i} | leave), factor)
    out = _diverse(lib, scored, count, seeds=[i])
    if len(out) < count:   # no sound at all, or too few near ones: the radio fills up – below the real ones
        have = {j for j, _sc in out} | {i} | leave
        low = out[-1][1] if out else 0.5
        out = _diverse(lib, out + _favour(_radio(lib, i, allowed, have, count, below=low), factor), count, seeds=[i])
    return out if pid else _remember("similar", key, out, keep=256)


def _artist_songs(lib, name=None, artist_id=None):
    """Songs of a band – by Navidrome's artist id or its name, as main artist, among the artists or as album artist
    (Navidrome asks for every artist, also one who only takes part) – and the band as Tuttiphon counts it: the artist
    itself where it is the main artist of some of them, otherwise the main artist of most. -> (indices, band name)"""
    songs = lib.songs
    low = (name or "").lower()
    ids = lib.artist_ids(all=True)

    def hit(s):
        people = (s.get("artists") or []) + (s.get("albumArtists") or [])
        if artist_id and (s.get("artistId") == artist_id or any(a.get("id") == artist_id for a in people)):
            return True
        return bool(low) and ((lib._main_artist(s) or "").lower() == low or any((a.get("name") or "").lower() == low
                                                                               for a in people))
    found = [i for i, s in enumerate(songs) if hit(s)]
    if not found:
        return [], name
    mains = Counter(lib._main_artist(songs[i]) for i in found)
    for a in mains:
        if (low and (a or "").lower() == low) or (artist_id and ids.get(a) == artist_id):
            return found, a
    return found, mains.most_common(1)[0][0]


def songs_like_artist(cfg, lib, name=None, artist_id=None, count=50, exclude=frozenset(), personal=False, who=None):
    """Artist radio: songs that sound like the band – its own (up to a third), of bands that sound like it and of
    those Last.fm counts as similar (they move up by RADIO_BONUS, the similarity shown stays the sound's); without
    vectors the radio's bands, shuffled by the day. personal / who: for the person listening to the band (_who())."""
    count = _clamp(count)
    own, artist = _artist_songs(lib, name, artist_id)
    if not own:
        return []
    pid, leave, factor = who or _who(cfg, lib, {lib.songs[i]["id"] for i in own}, personal)
    exclude = set(exclude) | leave
    allowed = _pool(cfg, lib, _worlds_of(cfg, lib, own), pid)
    bands = set(classify.radio_artists([artist], lib, limit=25))
    idx = similar.index(lib)
    centre = idx.centroid(artist) if idx is not None else None
    if centre is not None:
        scored = _favour(_closest(lib, centre, allowed, exclude), factor)
        ranked = sorted(scored, key=lambda x: -(x[1] + (RADIO_BONUS if lib._main_artist(lib.songs[x[0]]) in bands else 0)))
        return _diverse(lib, ranked, count, own=artist)
    rnd = random.Random(f"{artist}|{dt.date.today()}")
    cands = [i for i in allowed if i not in exclude and lib._main_artist(lib.songs[i]) in bands]
    rnd.shuffle(cands)
    scored = _favour([(i, max(0.01, 0.5 - 0.49 * k / count)) for k, i in enumerate(cands)], factor)
    return _diverse(lib, scored, count, own=artist)


def songs_like_album(cfg, lib, album_id=None, name=None, artist=None, count=50, personal=False):
    """Songs that sound like an album (its mean sound) – never from the album itself. personal: for the person
    listening to it (_who())."""
    count = _clamp(count)
    songs = lib.songs
    own = list(_albums(lib).get(album_id, ())) if album_id else []
    if not own and name:
        own = [i for i, s in enumerate(songs) if (s.get("album") or "").lower() == name.lower()
               and (not artist or artist.lower() in ((s.get("displayAlbumArtist") or s.get("artist") or "").lower()))]
    if not own:
        return []
    who = _who(cfg, lib, {songs[i]["id"] for i in own}, personal)
    pid, leave, factor = who
    allowed = _pool(cfg, lib, _worlds_of(cfg, lib, own), pid)
    idx = similar.index(lib)
    vec = similar.mean_unit([v for v in (idx.centered(i) for i in own) if v is not None]) if idx is not None else None
    if vec is None and idx is not None:
        vec = idx.centroid(lib._main_artist(songs[own[0]]))
    if vec is not None:
        return _diverse(lib, _favour(_closest(lib, vec, allowed, exclude=set(own) | leave), factor), count, seeds=own)
    return songs_like_artist(cfg, lib, name=lib._main_artist(songs[own[0]]), count=count, exclude=set(own), who=who)


def similar_artists(cfg, lib, name=None, artist_id=None, limit=20):
    """Bands that sound like this one or count as similar (radio): [(name, Navidrome's artist id or None)] – only
    bands with songs that may come for this band (separate worlds only for a band of them, kid-safe as the rest),
    never the band itself."""
    limit = _clamp(limit, 20)
    own, artist = _artist_songs(lib, name, artist_id)
    if not own:
        return []
    allowed = _pool(cfg, lib, _worlds_of(cfg, lib, own))
    present = {lib._main_artist(lib.songs[i]) for i in allowed}
    ids = lib.artist_ids(all=True)
    out = [a for a in classify.radio_artists([artist], lib, limit=limit * 3) if a != artist and a in present]
    return [(a, ids.get(a)) for a in out[:limit]]


def path(cfg, lib, start_id, end_id, count=25):
    """A path from one song to another: `count` songs (with both ends), each step sounding close to the last – at
    every step the song nearest to the point between the two sounds, at most a few per band. Songs without a vector
    of their own take the sound of their album or band; without any sound: the first half from the similar songs of
    the start, the second from those of the end. [(index, similarity to that point)]"""
    count = max(2, _clamp(count, 25))
    index = lib.index_of()
    a, b = index.get(start_id), index.get(end_id)
    if a is None or b is None:
        return []
    if a == b:   # from a song to itself: the song and what sounds like it
        return [(a, 1.0)] + similar_songs(cfg, lib, start_id, count - 1)
    idx = similar.index(lib)
    va, vb = _sound(lib, idx, a), _sound(lib, idx, b)
    allowed = _pool(cfg, lib, _worlds_of(cfg, lib, [a, b]))
    got = _all_batch()
    if va is None or vb is None or not got:
        first = similar_songs(cfg, lib, start_id, count)
        last = similar_songs(cfg, lib, end_id, count)
        middle, used = [], {a, b}
        for k in range(count - 2):
            pool = first if k < (count - 2 + 1) // 2 else last
            pick = next(((j, sc) for j, sc in (pool if pool is first else reversed(pool)) if j not in used), None)
            if pick is None:
                continue
            used.add(pick[0])
            middle.append(pick)
        return [(a, 1.0)] + middle + [(b, 1.0)]
    sids, batch = got
    rows = [(index.get(sid), k) for k, sid in enumerate(sids)]
    rows = [(i, k) for i, k in rows if i is not None and i in allowed]
    used = {a, b}
    seen = _Seen()
    seen.add(lib.songs[a])
    seen.add(lib.songs[b])
    per = Counter()
    cap = max(2, round(count / 8))
    out = [(a, 1.0)]
    for step in range(1, count - 1):
        t = step / (count - 1)
        target = similar.unit([(1 - t) * x + t * y for x, y in zip(va, vb)])
        if target is None:
            continue
        scores = batch.closeness(target)
        near = heapq.nlargest(64, rows, key=lambda r: scores[r[1]])   # nearly always the pick is among these
        for cands in (near, sorted(rows, key=lambda r: -scores[r[1]])):
            pick = None
            for i, k in cands:
                band = lib._main_artist(lib.songs[i])
                if i in used or per[band] >= cap or not seen.add(lib.songs[i]):
                    continue
                pick = (i, k, band)
                break
            if pick:
                i, k, band = pick
                used.add(i)
                per[band] += 1
                out.append((i, max(0.0, min(1.0, round(scores[k], 4)))))
                break
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
    with _lock:   # for the settings page: the last question (plays do not count here)
        _seen["at"] = dt.datetime.now().isoformat(timespec="seconds")
        _seen["calls"] += 1
    _last.person = None
    if what == "similar":
        out = {"songs": as_songs(lib, similar_songs(cfg, lib, query.get("id", ""), query.get("count", 50), personal=True))}
    elif what == "artist":
        out = {"songs": as_songs(lib, songs_like_artist(cfg, lib, query.get("name"), query.get("id"), query.get("count", 50),
                                                        personal=True))}
    elif what == "album":
        out = {"songs": as_songs(lib, songs_like_album(cfg, lib, query.get("id"), query.get("name"), query.get("artist"),
                                                       query.get("count", 50), personal=True))}
    elif what == "artists":
        out = {"artists": [{"name": n, "id": a or ""} for n, a in similar_artists(cfg, lib, query.get("name"), query.get("id"),
                                                                                  query.get("count", 20))]}
    elif what == "path":
        out = {"songs": as_songs(lib, path(cfg, lib, query.get("from", ""), query.get("to", ""), query.get("count", 25)))}
    else:
        raise KeyError(what)
    if what in ("similar", "artist", "album"):   # whom the last song answer was for (None: the family)
        with _lock:
            _seen["for"] = getattr(_last, "person", None)
    out["ms"] = round((time.time() - started) * 1000)
    return out
