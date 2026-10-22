"""Taste per Navidrome account – from what the person really listens to in Navidrome or Symfonium.

Signals per song (only for accounts with a stored password – otherwise Tuttiphon does not know the account's stars and
plays):
* plays of the last RECENT_DAYS days (recap, state/plays/) – count the most
* plays overall (playCount) – damped
* favorites and stars the account gave by hand – stars set by the Deezer rating only say something about popularity
  and do not count; a 1 star given by hand is a clear dislike
* skipped songs from mixes (feedback.factors) dampen

This yields favorite bands, favorite music worlds, the sound (energy, mood, danceability … from measurement and AI)
and the AI music styles. Used for suggestions (suggest.py), "From your listening" in the profile and the weighting of
mixes (mixer.pick): songs that sound like the person's taste come more often. With the AI's sound vectors there is
also the sound taste (soundtaste.py, profile["soundTaste"]): a few typical sounds of what the account plays.

A person can keep music worlds out of their taste (person.tasteExclude, e.g. the children's music a parent plays for
the kids on their own phone): their songs count neither as liked nor as disliked – profile(…, exclude=…). The family's
playlists still take them into account (suggest.played_worlds()).
"""
import datetime as dt
import json
import math
import threading
from collections import Counter, defaultdict

from . import audio, feedback, ml, rueckblick, rules, soundtaste
from .i18n import _

RECENT_DAYS = 60
MIN_SIGNAL = 15          # a profile needs this many songs with a signal – otherwise it is chance
SOUND_KEYS = ("energy", "arousal", "valence", "dance", "inst", "acoustic")
FLAVOR_SOUND = 1.4       # "Your sound": the sound taste counts this much more (up to 70 % instead of 50 %)
_lock = threading.Lock()
_memo = {}


def excluded(person):
    """Music worlds the person keeps out of their taste (person.tasteExclude) – as a sorted tuple, part of cache keys.
    None on a child profile: there children's music is the own taste (an exclusion from before stays without effect)."""
    if (person or {}).get("child"):
        return ()
    return tuple(sorted({w for w in (person or {}).get("tasteExclude") or [] if isinstance(w, str)}))


_excl_memo = {}


def excluded_ids(cfg, plib, exclude, today=None):
    """Song indices of plib in the music worlds `exclude` (frozenset) – cached per song list, worlds and their rules."""
    if not exclude:
        return frozenset()
    worlds = json.dumps([w for w in cfg["welten"] if w["id"] in exclude], sort_keys=True, default=str)
    key = (ml.lib_key(plib), tuple(exclude), worlds)   # the excluded worlds with all their rules
    with _lock:
        hit = _excl_memo.get(key)
    if hit is not None:
        return hit
    ctx = rules.BuildContext(plib, today)
    ids = set()
    for w in cfg["welten"]:
        if w["id"] in exclude:
            block = rules.welt_block(w, ctx)
            if block:
                ids |= plib.ids({"any": block})
    out = frozenset(ids)
    with _lock:
        if len(_excl_memo) > 16:
            _excl_memo.clear()
        _excl_memo[key] = out
    return out


def song_scores(plib, user, today=None, cfg=None, exclude=()):
    """Song index -> weight (>0 liked, <0 rejected) for this account – without the songs of the music worlds
    `exclude` (they say nothing about this person's taste)."""
    today = today or dt.date.today()
    recent, _ = rueckblick.plays_between(user, today - dt.timedelta(days=RECENT_DAYS), today)
    skip = feedback.factors(user, today)
    never = feedback.manual_dislikes(plib, user)
    by_deezer = feedback.deezer_stars(user)
    out = {}
    for i, s in enumerate(plib.songs):
        sid = s["id"]
        if sid in never:
            out[i] = -3.0
            continue
        score = 0.0
        r = recent.get(sid, 0)
        if r:
            score += 1.0 + 1.5 * math.log1p(r)
        plays = s.get("playCount") or 0
        if plays:
            score += 0.6 * math.log1p(plays)
        rating = s.get("userRating") or 0
        if rating and sid in by_deezer and by_deezer[sid] != rating:   # rated by hand
            if rating >= 4:
                score += 0.8 * (rating - 3)
            elif rating <= 2:
                score -= 1.0
        if s.get("starred"):
            score += 1.5
        if score > 0 and sid in skip:
            score *= skip[sid]
        if score:
            out[i] = score
    if exclude and cfg is not None:
        skip = excluded_ids(cfg, plib, exclude, today)
        out = {i: v for i, v in out.items() if i not in skip}
    return out


def _person_lib(cfg, base, user):
    from .stats import songs_for
    try:
        plib = songs_for(user, base)
    except Exception:   # noqa: BLE001 – no password, Navidrome briefly away
        return None
    return plib if getattr(plib, "ratings_exact", False) else None


def profile(cfg, base, user, today=None, exclude=()):
    """Taste of an account, or None (no password stored). {"enough": False, …} if too little was played.
    exclude: music worlds that do not count (excluded(person))."""
    if not user:
        return None
    today = today or dt.date.today()
    plib = _person_lib(cfg, base, user)
    if plib is None:
        return None
    exclude = tuple(sorted(set(exclude or ())))
    key = (user.lower(), ml.lib_key(plib), today, audio._cache["stamp"], ml.stamp(), cfg_key(cfg), exclude)
    with _lock:
        out = _memo.get(key)
    if out is None:
        out = _compute(cfg, plib, user, today, exclude)
        with _lock:
            if len(_memo) > 8:
                _memo.clear()
            _memo[key] = out
    if out.get("enough"):   # sound taste: cached on its own, per account and day
        st = soundtaste.of(plib, user, today, lambda: song_scores(plib, user, today, cfg, exclude), variant=exclude)
        if st is not None:
            out = {**out, "soundTaste": st}
    return out


def for_person(cfg, base, person, today=None):
    """profile() of a person: their account without the music worlds they keep out of their taste."""
    return profile(cfg, base, (person or {}).get("user"), today, excluded(person))


def cfg_key(cfg):
    return tuple((w["id"], len(w.get("artists", [])), w.get("scene"), tuple(w.get("genres", []))) for w in cfg["welten"])


def _compute(cfg, plib, user, today, exclude=()):
    from .classify import song_features
    scores = song_scores(plib, user, today, cfg, exclude)
    pos = {i: s for i, s in scores.items() if s > 0}
    recent, _ = rueckblick.plays_between(user, today - dt.timedelta(days=RECENT_DAYS), today)
    by_deezer = feedback.deezer_stars(user)
    basis = {"songs": len(pos), "recent": sum(1 for v in recent.values() if v),
             "favorites": sum(1 for s in plib.songs if s.get("starred")),
             "rated": sum(1 for s in plib.songs if s.get("userRating") and s["id"] in by_deezer
                          and by_deezer[s["id"]] != s["userRating"])}
    if len(pos) < MIN_SIGNAL:
        return {"user": user, "enough": False, "basis": basis}
    total = sum(pos.values())

    # Bands
    per_artist = Counter()
    for i, sc in pos.items():
        per_artist[plib._main_artist(plib.songs[i])] += sc
    disliked = Counter()
    for i, sc in scores.items():
        if sc < 0:
            disliked[plib._main_artist(plib.songs[i])] += -sc
    artists = [(a, round(v / total, 4)) for a, v in per_artist.most_common(25) if a]

    # music worlds: share of what was played that falls into the world
    ctx = rules.BuildContext(plib, today)
    welten = []
    kids, candidates = set(), rules.child_candidates(cfg)
    for w in cfg["welten"]:
        block = rules.welt_block(w, ctx)
        if not block:
            continue
        ids = plib.ids({"any": block})
        if w["id"] in candidates:
            kids |= ids
        share = sum(sc for i, sc in pos.items() if i in ids) / total
        if share > 0:
            welten.append((w["id"], round(share, 4)))
    welten.sort(key=lambda x: -x[1])
    # children's music together (each song once – a song can be in several worlds): is it a child's account?
    child_share = round(sum(sc for i, sc in pos.items() if i in kids) / total, 4)

    # sound and mood (measurement + AI + Last.fm, as in the sound filters)
    feats = song_features(plib)
    acc, wsum = defaultdict(float), defaultdict(float)
    moods = Counter()
    for i, sc in pos.items():
        f = feats.get(i)
        if not f:
            continue
        for k in SOUND_KEYS:
            if f.get(k) is not None:
                acc[k] += sc * f[k]
                wsum[k] += sc
        for m in audio.moods(f):
            moods[m] += sc
    sound = {k: round(acc[k] / wsum[k], 3) for k in SOUND_KEYS if wsum[k] > 0}
    msum = sum(moods.values()) or 1
    mood_share = [(m, round(v / msum, 3)) for m, v in moods.most_common(4)]

    # AI music styles (averaged per band), weighted with what was played
    band_styles = ml.artist_styles(plib)
    styles = Counter()
    for a, v in per_artist.items():
        for k, x in band_styles.get(a, {}).items():
            styles[k] += v * x
    ssum = sum(styles.values()) or 1
    style_share = {k: round(v / ssum, 4) for k, v in styles.most_common(12)}

    return {"user": user, "enough": True, "basis": basis, "artists": artists, "welten": welten[:8], "childShare": child_share,
            "disliked": [a for a, _ in disliked.most_common(10)], "sound": sound, "moods": mood_share,
            "styles": style_share, "measured": sum(wsum.values()) > 0}


# ---------------------------------------------------------------------------- Similarity

def matcher(prof, plib, sound=1.0):
    """-> function(song index) -> 0–1: how much a song sounds like the taste of this profile.
    Sound (distance to the averaged sound) and the band's music style; without sound data only the style counts.
    With a sound taste (soundtaste.py) its score counts half for songs with a sound vector (less while few liked songs
    have one); sound: factor on that share ("Your sound": FLAVOR_SOUND)."""
    if not prof or not prof.get("enough"):
        return None
    from .classify import song_features
    feats = song_features(plib)
    averaged = prof.get("sound") or {}
    styles = prof.get("styles") or {}
    band_styles = ml.artist_styles(plib) if styles else {}
    snorm = math.sqrt(sum(v * v for v in styles.values())) or 1.0
    style_memo = {}

    def style_sim(artist):
        if artist not in style_memo:
            b = band_styles.get(artist) or {}
            bn = math.sqrt(sum(v * v for v in b.values())) or 1.0
            style_memo[artist] = sum(x * styles.get(k, 0) for k, x in b.items()) / (bn * snorm) if b else None
        return style_memo[artist]

    def features_sim(i):
        parts = []
        f = feats.get(i)
        if f and averaged:
            diffs = [abs(f[k] - averaged[k]) for k in averaged if f.get(k) is not None]
            if diffs:
                parts.append((1 - min(1.0, 2 * sum(diffs) / len(diffs)), 0.6))
        st = style_sim(plib._main_artist(plib.songs[i])) if styles else None
        if st is not None:
            parts.append((st, 0.4))
        if not parts:
            return 0.5
        return sum(v * w for v, w in parts) / sum(w for _, w in parts)

    taste_of_sound = prof.get("soundTaste")
    share = min(0.8, taste_of_sound.share * sound) if taste_of_sound else 0.0
    if share <= 0:
        return features_sim
    by_index = taste_of_sound.for_lib(plib)

    def sim(i):
        x = by_index[i]
        base = features_sim(i)
        return base if x is None else (1 - share) * base + share * x
    return sim


def factor(sim_value):
    """Weight factor for mixes: 0.6 (does not sound like you at all) … 1.4 (exactly your thing)."""
    return 0.6 + 0.8 * max(0.0, min(1.0, sim_value))


# ---------------------------------------------------------------------------- For the interface

def summary(cfg, prof, base):
    """For "From your listening": bands, worlds, moods and styles in plain words."""
    if prof is None:
        return {"available": False}
    if not prof.get("enough"):
        return {"available": True, "enough": False, "basis": prof["basis"]}
    names = {w["id"]: w["name"] for w in cfg["welten"]}
    aid = base.artist_ids()
    return {"available": True, "enough": True, "basis": prof["basis"],
            "artists": [{"name": a, "share": s, "id": aid.get(a)} for a, s in prof["artists"][:12]],
            "welten": [{"id": w, "name": names.get(w, w), "share": s} for w, s in prof["welten"] if s >= 0.05],
            "moods": [{"id": m, "label": _(audio.MOODS[m]) if m in audio.MOODS else m, "share": s}   # i18n-ignore
                      for m, s in prof["moods"]],
            "styles": [ml.style_label(k) for k in list(prof["styles"])[:6]],
            "disliked": prof.get("disliked", []), "sound": bool(prof.get("soundTaste"))}
