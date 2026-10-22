"""Understanding music – locally and free of charge:

* Classify bands automatically: which music world (and which vibe) fits a band that is nowhere yet? Four weighted
  signals: Last.fm tags, similar bands (Last.fm) in a world, genres in the files, scene catalog. Result with a match
  score 0–1 and a reason.
* Radio: bands that resemble a seed band and are in the library.
* Still missing: similar bands that are not in the library.
* Mood: AI sound analysis (ml.py) and Last.fm tags (happy, sad, chill …) refine the sound estimate.
* Without Last.fm data: the music styles of the AI sound analysis (averaged per band) replace the tags.
* Sound similarity (similar.py, AI sound vectors): one more signal for the classification, bands that sound alike
  for the radio and the artist window, and "More like this" ranked by sound.
"""
import datetime as dt
import json
import math
import re
import threading
import unicodedata
from collections import Counter, OrderedDict, defaultdict

from . import audio, lastfm, ml, rules, scenes, similar
from .config import STATE_DIR, read_text, write_atomic
from .i18n import _

# Last.fm tags that say nothing about the music; tag word lists (data, partly German tags)
# i18n-ignore-start
NOISE = {"seen live", "favorites", "favourite", "favorite", "my favorite", "awesome", "love", "beautiful", "albums i own",
         "german", "deutsch", "germany", "male vocalists", "female vocalists", "spotify", "under 2000 listeners", "all",
         "good", "best", "cool", "amazing", "epic"}
POSITIVE = {"happy", "upbeat", "fun", "feel good", "feelgood", "party", "cheerful", "uplifting", "joyful", "positive", "sunny",
            "summer", "funny", "good mood", "gute laune", "dance", "kinderlieder", "children's music", "kids", "spass"}
NEGATIVE = {"sad", "melancholic", "melancholy", "dark", "depressive", "depressing", "gloomy", "sorrow", "heartbreak",
            "doom", "gothic", "melancholisch", "traurig", "darkwave", "emotional"}
# i18n-ignore-end
_memo = OrderedDict()   # song_features() per song list
_lock = threading.Lock()
SOUNDS_LIKE_MIN = 0.35   # band centroids from here on "sound alike" (measured: same scene ≈ 0.45, unrelated ≈ −0.05)
RADIO_SOUND_MIN = 0.4    # radio: bands that sound like the seed band from here on
SOUND_WEIGHT = 0.15      # share of the sound similarity in the match rate of the classification


def _norm(s):
    return re.sub(r"[^a-z0-9]+", "", (s or "").lower())


def _tags(name):
    a = lastfm.artist(name)
    return {t: c for t, c in (a or {}).get("tags", []) if t not in NOISE and c >= 5}


def tag_valence(name):
    """Basic mood from Last.fm tags: 0 (sad) … 1 (happy), or None if there is nothing to go on."""
    tags = _tags(name)
    pos = sum(c for t, c in tags.items() if t in POSITIVE)
    neg = sum(c for t, c in tags.items() if t in NEGATIVE)
    if pos + neg < 20:
        return None
    return pos / (pos + neg)


def song_features(lib):
    """Index -> features (own measurement + AI sound analysis + Last.fm mood per band). Cached.

    The one place where tempo, key and instruments come together: "bpm" is the AI tempo when its windows agree
    (ml.TEMPO_AGREE, or our own measurement found none) – then "bsrc": "ml" and danceability, arousal and mood follow
    it (audio.with_tempo) –, otherwise our own estimate from ffmpeg. With the AI also "camelot" (key on the Camelot
    wheel, from ml.KEY_MIN strength), "instr" ({instrument: strength}), "themes" ({theme: strength}, only the offered
    themes from their strength ml.THEME_PRESENT) and "approachable"/"engaging" (0–1, only with the AI from VERSION 3 –
    a song without them never fits a sound filter on these values)."""
    feats = audio.features()
    mlf = ml.features()
    tempo, keys, instr, scores, themes = ml.tempo(), ml.keys(), ml.instruments(), ml.scores(), ml.themes()
    stamps = (audio._cache["stamp"], ml.stamp(), lastfm._mem["stamp"])
    key = ("feat", ml.songs_key(lib), *stamps)
    with _lock:
        if key in _memo:
            _memo.move_to_end(key)
            return _memo[key]
    out, val_cache, codes = {}, {}, {}
    for i, s in enumerate(lib.songs):
        sid = s["id"]
        f = feats.get(sid)
        if not f:
            continue
        artist = lib._main_artist(s)
        if artist not in val_cache:
            val_cache[artist] = tag_valence(artist)
        tv = val_cache[artist]
        t = tempo.get(sid)
        if t and (t[1] >= ml.TEMPO_AGREE or not f.get("bpm")):
            f = audio.with_tempo(f, t[0])
        m = mlf.get(sid)
        if m:
            f = ml.fuse(f, m, tv)
        elif tv is not None:
            f = {**f, "valence": round(0.45 * f["valence"] + 0.55 * tv, 3), "vsrc": "tags"}
        k, inst, sc, th = keys.get(sid), instr.get(sid), scores.get(sid), themes.get(sid)
        if (k and k[1] >= ml.KEY_MIN) or inst or sc or th:
            f = dict(f)
            if k and k[1] >= ml.KEY_MIN:
                if k[0] not in codes:
                    codes[k[0]] = ml.camelot(k[0])
                f["camelot"] = codes[k[0]]
            if inst:
                f["instr"] = inst
            if th:
                f["themes"] = th
            if sc:
                f.update(sc)
        out[i] = f
    with _lock:   # one entry per song list (default list, account lists) – older measurements are dropped right away
        for k in [k for k in _memo if k[2:] != stamps or ml.gone(k[1])]:   # or of a song list that is gone
            del _memo[k]
        _memo[key] = out
        while len(_memo) > ml.MEMO_SIZE:
            _memo.popitem(last=False)
    return out


# ---------------------------------------------------------------------------- Classification

def _vectors(lib):
    """One feature vector per band from Last.fm tags, file genres and the styles of the AI sound analysis (TF-IDF, normalized)."""
    count, genres, _, _ = rules.artist_stats(lib.songs)
    styles = ml.artist_styles(lib)
    raw = {}
    for artist, n in count.items():
        v = Counter()
        for t, c in _tags(artist).items():
            v["t:" + t] += c / 100
        for g, c in (genres.get(artist) or {}).items():
            v["g:" + g.lower()] += 0.6 * c / n
        for k, x in styles.get(artist, {}).items():   # sound – helps above all with bands Last.fm does not know
            v["k:" + k] += 0.7 * x
        raw[artist] = v
    df = Counter(k for v in raw.values() for k in v)
    idf = {k: math.log((1 + len(raw)) / (1 + d)) + 0.5 for k, d in df.items()}

    def norm(v):
        w = {k: x * idf.get(k, 1) for k, x in v.items()}
        n = math.sqrt(sum(x * x for x in w.values())) or 1.0
        return {k: x / n for k, x in w.items()}

    return {a: norm(v) for a, v in raw.items()}, count


def _cos(a, b):
    if len(a) > len(b):
        a, b = b, a
    return sum(x * b.get(k, 0) for k, x in a.items())


def suggestions(cfg, lib, ctx=None, min_songs=3):
    """Bands without a music world -> [{artist, welt, score, why, songs}] (best world per band), sorted by certainty."""
    ctx = ctx or rules.BuildContext(lib)
    vecs, count = _vectors(lib)
    present = {a.lower(): a for a in count}
    members = {w["id"]: set(rules.welt_artists(w, ctx)) for w in cfg["welten"]}
    assigned = set().union(*members.values()) if members else set()
    excluded = {a for w in cfg["welten"] for a in w.get("excludedArtists", [])}
    # profile per world = mean of its members
    profiles = {}
    for wid, ms in members.items():
        acc = Counter()
        for a in ms:
            for k, x in vecs.get(a, {}).items():
                acc[k] += x
        n = math.sqrt(sum(x * x for x in acc.values())) or 1.0
        profiles[wid] = {k: x / n for k, x in acc.items()}
    scene_of, scene_auto = {}, {}
    for w in cfg["welten"]:
        if w.get("scene"):
            for a in scenes.members(w["scene"], ctx.artist_index):
                scene_of.setdefault(a, w["id"])
            scene_auto[w["id"]] = bool(w.get("autoScene"))
    sounds, cents = sound_profiles(lib, members)
    out = []
    for artist, n in count.items():
        if artist in assigned or artist in excluded or n < min_songs or artist in ("Various Artists", ""):
            continue
        sim = [(present.get(s.lower()), m) for s, m in (lastfm.artist(artist) or {}).get("similar", [])]
        sim = [(s, m) for s, m in sim if s]
        mine = cents.get(artist)
        mine = mine[0] if mine and mine[1] >= 3 else None   # the band's sound: from 3 analyzed songs
        best = None
        for w in cfg["welten"]:
            wid = w["id"]
            tag_score = _cos(vecs.get(artist, {}), profiles[wid]) if profiles[wid] else 0
            hits = [(s, m) for s, m in sim if s in members[wid]]
            sim_score = min(1.0, sum(m for _, m in hits) / 1.5) if hits else 0.0
            score = 0.5 * tag_score + 0.5 * sim_score if sim else tag_score * 0.85
            sound = sound_score(mine, sounds.get(wid))
            if sound is not None:   # only with enough sound vectors – otherwise exactly as before
                score = (1 - SOUND_WEIGHT) * score + SOUND_WEIGHT * sound
            why = []
            if hits:
                why.append(_("similar to {bands}", bands=", ".join(s for s, _m in sorted(hits, key=lambda x: -x[1])[:3])))
            # reason: the features band and world have in common (not just the band's strongest)
            top = sorted(((k, x * profiles[wid].get(k, 0)) for k, x in vecs.get(artist, {}).items()), key=lambda x: -x[1])
            top = [(k, x) for k, x in top[:3] if x > 0]
            if tag_score > 0.35 and top:
                why.append(_("matches {features}", features=", ".join(
                    _("“{tag}” (sound)", tag=k[2:]) if k.startswith("k:") else _("“{tag}”", tag=k[2:]) for k, _x in top)))
            if sound is not None and sound >= 0.6:
                why.append(_("sounds similar"))
            if scene_of.get(artist) == wid:
                # "add typical bands automatically" off: only suggest, do not classify automatically
                score, why = max(score, 0.9 if scene_auto.get(wid) else 0.65), [_("typical band of the scene")] + why
            if best is None or score > best["score"]:
                best = {"artist": artist, "welt": wid, "score": round(score, 2), "why": "; ".join(why) or _("similar genres"), "songs": n}
        if best and best["score"] >= 0.3:
            out.append(best)
    out.sort(key=lambda x: (-x["score"], -x["songs"]))
    return out


def sound_profiles(lib, members):
    """Sound of the music worlds for the classification: world id -> unit vector (mean of the sound of its bands,
    from 2 bands with a sound) – plus the band centroids (similar.Index.centroids()). Empty without sound vectors."""
    idx = similar.index(lib)
    if not idx:
        return {}, {}
    cents = idx.centroids()
    out = {}
    for wid, ms in members.items():
        vecs = [cents[a][0] for a in ms if a in cents]
        if len(vecs) >= 2:
            out[wid] = similar.mean_unit(vecs)
    return out, cents


def sound_score(band, world):
    """Cosine of band and world sound -> 0–1: from 0.2 (unrelated bands reach that at most in one case out of ten)
    to 0.7 (typical for a band and its own world) – None if one of them has no sound."""
    if band is None or world is None:
        return None
    return max(0.0, min(1.0, (similar.cosine(band, world) - 0.2) / 0.5))


AUTO_FILE = STATE_DIR / "auto_assigned.json"   # {band lowercase: {"name", "welt", "score", "at"}} – at most once per band
NEW_DAYS = 45                                   # "new band": first song at most this many days in the library (like "New:" in "to review")


def auto_log(write=False):
    """Automatically classified bands. write: read to be written again (remember) – briefly not readable (NAS): the
    OSError goes on, and a damaged file is set aside (auto_assigned.defekt-<time>.json) instead of being overwritten:
    otherwise bands taken out by hand would come back."""
    try:
        data = json.loads(read_text(AUTO_FILE))
    except FileNotFoundError:
        return {}
    except OSError:
        if write:
            raise
        return {}
    except ValueError:
        data = None
    if isinstance(data, dict):
        return data
    if write:
        import os
        from . import events
        from .i18n import _s
        broken = AUTO_FILE.with_name(f"auto_assigned.defekt-{dt.datetime.now():%Y%m%d-%H%M%S}.json")   # file name: data
        os.replace(AUTO_FILE, broken)
        events.say(_s("⚠ {file} was damaged – set aside as {name}.", file=AUTO_FILE.name, name=broken.name))
    return {}


def new_artists(lib, days=NEW_DAYS, today=None):
    """Bands whose first song has been in the library for at most `days` days (e.g. from Lidarr)."""
    today = today or dt.date.today()
    first = {}
    for s in lib.songs:
        c = (s.get("created") or "")[:10]
        a = lib._main_artist(s)
        if c and (a not in first or c < first[a]):
            first[a] = c
    since = (today - dt.timedelta(days=days)).isoformat()
    return {a for a, c in first.items() if c >= since}


def auto_assign(cfg, lib, threshold=0.7, log=print, dry_run=False, new_only=False):
    """Add confident matches straight to the music world (cfg – inside update_config). -> list of assignments; once
    the configuration is saved, remember() them. Each band at most once: whoever removes an automatically classified
    band again does not get it back. new_only: only bands that are new in the library (Lidarr) – older ones stay
    suggestions under "to review"."""
    done = auto_log(write=not dry_run)
    fresh = new_artists(lib) if new_only else None
    made = []
    for s in suggestions(cfg, lib):
        if s["score"] < threshold or s["artist"].lower() in done or (fresh is not None and s["artist"] not in fresh):
            continue
        w = next((x for x in cfg["welten"] if x["id"] == s["welt"]), None)
        if not w:
            continue
        if not dry_run:
            w.setdefault("artists", []).append(s["artist"])
        made.append(s)
        log(f"  ✓ {s['artist']} → {w['name']} ({int(s['score'] * 100)} %, {s['why']})")
    return made


def remember(made):
    """After the configuration with the assignments is saved: each band at most once (state/auto_assigned.json)."""
    if not made:
        return
    done = auto_log(write=True)
    at = dt.datetime.now().isoformat(timespec="seconds")
    for s in made:
        done[s["artist"].lower()] = {"name": s["artist"], "welt": s["welt"], "score": s["score"], "at": at}
    write_atomic(AUTO_FILE, json.dumps(done, ensure_ascii=False))


def stil_suggestions(cfg, lib, limit=40):
    """Bands without matching genre tags in the files -> vibes based on the Last.fm tags (otherwise the styles of the
    AI sound analysis)."""
    count, genres, untagged, _rest = rules.artist_stats(lib.songs)
    styles = ml.artist_styles(lib)
    out = []
    stile = [s for s in cfg["stile"] if s.get("kind") != "season" and s.get("group") in ("Genre", "Thema") and s.get("genres")]
    for artist, n in count.items():
        if n < 3 or genres.get(artist):
            continue
        tags, by_sound = _tags(artist), False
        if not tags:
            tags, by_sound = {k: round(x * 100) for k, x in styles.get(artist, {}).items()}, True
        if not tags:
            continue
        for s in stile:
            if artist in (s.get("artists") or []):
                continue
            keys = [g.lower() for g in s["genres"]]
            hit = [t for t in tags if any(k in t for k in keys)]
            if hit and sum(tags[t] for t in hit) >= 40:
                found = ", ".join(hit[:3])
                why = _("Sound: {tags}", tags=found) if by_sound else _("Tags: {tags}", tags=found)
                out.append({"artist": artist, "stil": s["id"], "why": why, "songs": n})
    return out[:limit]


# ---------------------------------------------------------------------------- Radio & discover

def radio_artists(seeds, lib, limit=25, min_match=0.12):
    """Seed bands + similar bands that are in the library (sorted by similarity): Last.fm's similar bands and – with
    the AI's sound vectors – bands that sound like the seed band (centroid ≥ RADIO_SOUND_MIN, 0.8 × similarity: a
    band that is similar by both counts most)."""
    present = {a.lower(): a for a in rules.artist_stats(lib.songs)[0]}
    score = Counter()
    for seed in seeds:
        real = present.get(seed.lower(), seed)
        score[real] += 10
        for name, m in (lastfm.artist(real) or {}).get("similar", []):
            hit = present.get(name.lower())
            if hit and m >= min_match:
                score[hit] += m
    by_lastfm = len(score)
    idx = similar.index(lib)
    if idx:
        for seed in seeds:
            for a, x in idx.similar_artists(present.get(seed.lower(), seed), k=limit):
                if x >= RADIO_SOUND_MIN:
                    score[a] += 0.8 * x
    if by_lastfm <= len(seeds):   # without Last.fm data: genre similarity in addition
        vecs, _ = _vectors(lib)
        for seed in seeds:
            sv = vecs.get(present.get(seed.lower(), seed), {})
            for a, v in vecs.items():
                if a not in score:
                    s = _cos(sv, v)
                    if s > 0.45:
                        score[a] += s * 0.5
    return [a for a, _ in score.most_common(limit)]


# Separators between the artists of a credit ("A & B", "A, B", "A feat. B", "A und B") and leading articles –
# matched on folded text (lower case, no diacritics); data, not texts
_CREDIT_SEP = re.compile(r"\s*(?:[,;&]|\bfeat\b\.?|\bft\b\.?|\bfeaturing\b|\band\b|\bund\b)\s*")
_ARTICLE = re.compile(r"^(?:the|die|der)\s+")   # i18n-ignore


def artist_parts(name):
    """Comparable parts of an artist credit: "Simone Sommerland, Karsten Glück & die Kita-Frösche" →
    ["simone sommerland", "karsten gluck", "kita frosche"] – lower case, without diacritics and punctuation,
    without a leading "the/die/der"."""
    s = unicodedata.normalize("NFKD", (name or "").casefold())
    s = "".join(c for c in s if not unicodedata.combining(c))
    parts = []
    for part in _CREDIT_SEP.split(s):
        part = _ARTICLE.sub("", " ".join(re.sub(r"[\W_]+", " ", part).split()))
        if part:
            parts.append(part)
    return parts


def library_artist_parts(lib):
    """Parts of all artist names in the library – album artists and the artists of every song (also on
    compilations and as a guest)."""
    names = set()
    for s in lib.songs:
        names.update(x for x in (s.get("artist"), s.get("displayArtist"), s.get("albumArtist"), s.get("displayAlbumArtist")) if x)
        names.update(a["name"] for a in (s.get("artists") or []) + (s.get("albumArtists") or []) if a.get("name"))
    names.discard("Various Artists")
    return {part for n in names for part in artist_parts(n)}


def in_library(name, known):
    """Is a band (e.g. a suggestion from Last.fm) already in the library? Yes if every part of its name is an artist
    of the library or a part of one: "Rolf Zuckowski" ↔ "Rolf Zuckowski und seine Freunde",
    "A, B, Die C" ↔ "A, B & die C". known: library_artist_parts()."""
    parts = artist_parts(name)
    return bool(parts) and all(p in known for p in parts)


def missing_artists(seeds, lib, limit=24):
    """Similar bands the library is still missing (by frequency over all seed bands)."""
    known = library_artist_parts(lib)
    score, because = Counter(), defaultdict(list)
    for seed in seeds:
        for name, m in (lastfm.artist(seed) or {}).get("similar", [])[:30]:
            if m >= 0.2 and not in_library(name, known):
                score[name] += m
                because[name].append(seed)
    return [{"artist": a, "score": round(s, 2), "because": because[a][:3]} for a, s in score.most_common(limit)]


def artist_profile(name, lib):
    """For the artist panel: tags, similar bands (present/missing), sound profile."""
    a = lastfm.artist(name) or {}
    present = {x.lower(): x for x in rules.artist_stats(lib.songs)[0]}
    sim_here, sim_missing = [], []
    for s, m in a.get("similar", [])[:40]:
        (sim_here if s.lower() in present else sim_missing).append([present.get(s.lower(), s), m])
    feats = song_features(lib)
    mine = [feats[i] for i, s in enumerate(lib.songs) if lib._main_artist(s) == name and i in feats]
    idx = similar.index(lib)
    sounds_like = [[a, sc] for a, sc in (idx.similar_artists(name, 8) if idx else []) if sc >= SOUNDS_LIKE_MIN]
    prof = None
    if mine:
        def med(k):
            vals = sorted(f[k] for f in mine if f.get(k) is not None)
            return vals[len(vals) // 2] if vals else None
        prof = {"songs": len(mine), "bpm": med("bpm"), "energy": med("energy"), "dance": med("dance"),
                "valence": med("valence"), "moods": [m for m, c in Counter(x for f in mine for x in audio.moods(f)).most_common(3)
                                                     if c >= max(2, len(mine) // 4)],
                "styles": [ml.style_label(k) for k, x in ml.artist_styles(lib).get(name, {}).items() if x >= 0.4][:4]}
    return {"tags": [t for t, c in a.get("tags", []) if t not in NOISE][:8], "similar": sim_here[:12],
            "missing": sim_missing[:10], "sound": prof, "lastfm": bool(a), "soundsLike": sounds_like}


def song_details(lib, i):
    """For the song window: key ("key", "camelot", "keyStrength"), instruments, themes and where the tempo comes from
    ("bpmSource": "ai" or "measured", missing without a tempo)."""
    out = ml.song_info(lib.songs[i]["id"])
    f = song_features(lib).get(i) or {}
    if f.get("bpm"):
        out["bpmSource"] = "ai" if f.get("bsrc") == "ml" else "measured"
    return out


def rank_like(lib, i, pool, rnd):
    """“More like this”: the songs of the pool ordered by how much they sound like song i. With sound vectors
    (similar.py) mainly by sound similarity, plus our own features (arousal, mood, tempo) – songs without a vector
    come after the ones that sound alike. Without vectors as before: only the features. A little chance (rnd) keeps
    the list from always being the same."""
    feats = song_features(lib)
    me = feats.get(i)
    idx = similar.index(lib)
    sound = idx is not None and idx.has(i)

    def features(j):
        f = feats.get(j)
        if not me or not f:
            return None
        d = (me.get("arousal", .5) - f.get("arousal", .5)) ** 2 + (me.get("valence", .5) - f.get("valence", .5)) ** 2
        if me.get("bpm") and f.get("bpm"):
            d += 0.5 * ((me["bpm"] - f["bpm"]) / 60) ** 2
        return d

    def distance(j):
        d = features(j)
        if not sound:
            return (1 if d is None else d) + (rnd.random() if d is None else 0.08 * rnd.random())
        c = idx.cos(i, j)
        # sound: 1 − cosine (same band ≈ 0.6, unrelated ≈ 1); without a vector like an unrelated song
        return (1.0 if c is None else 1 - c) + 0.5 * (0.3 if d is None else d) + 0.05 * rnd.random()
    return sorted(pool, key=distance)
