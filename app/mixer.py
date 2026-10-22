"""Mixes (daily, weekly, monthly): the tool picks the songs itself (smart playlists cannot do that).

* at most N songs per band (default 3) and 2 per album
* weighted random selection: stars, favorites, listening habits – depending on the flavor
* never the same band twice in a row
* the randomness depends on the mix day: a mix stays the same for a day and is new the next day
* smooth transitions (settings.smoothTransitions): one song leads into the next – similar sound (AI sound vectors),
  close tempo, compatible key (Camelot wheel) and energy

Stable over the day: every song gets its own random value (hash of day, playlist and song ID) – so a new album
does not shift the whole selection. Plays after the start of the mix day only count tomorrow, and the written
selection is remembered in state/mixes.json.

The result is written as .m3u into the playlist folder; Navidrome reads it during the scan and keeps ID, name and
owner (as with the .nsp files).
"""
import datetime as dt
import hashlib
import json
import math
import re
import threading
import time
from collections import Counter

from .config import MARKER, STATE_DIR, read_text, write_atomic
from .i18n import N_, _, _s

FLAVORS = {   # translated where shown: _(FLAVORS[x])
    "ausgewogen": N_("balanced – familiar and new"),
    "hits": N_("mostly the hits"),
    "entdecken": N_("mostly lesser-known songs"),
}
DEFAULTS = {"size": 50, "perArtist": 3, "perAlbum": 2, "flavor": "ausgewogen", "avoidRecent": 7, "every": "day"}
# How often a mix is rebuilt – it stays the same in between (good for offline playlists in Symfonium).
# -> (name, how often); the name is the same in every language, "how often" is translated where used
EVERY = {"day": ("Daily Mix", N_("daily")), "week": ("Weekly Mix", N_("weekly")), "month": ("Monthly Mix", N_("monthly"))}
MIX_STATE = STATE_DIR / "mixes.json"
_state_lock = threading.Lock()
# smooth transitions: share of each part in the cost of a transition (a missing part counts as 0.5) – measured on
# 177 songs of 59 bands: energy jumps 0.32 -> 0.14, sound cosine of neighbours 0.0 -> 0.33, Camelot steps 2.4 -> 1.8
TRANSITION = {"sound": 0.5, "energy": 0.2, "tempo": 0.15, "key": 0.15}
_TEMPO_SPAN = math.log2(1.15)   # tempo 15 % apart = full cost
_KEY_COST = (0.0, 0.2, 0.6)     # Camelot steps 0, 1, 2 – further away = 1


def _daily_at():
    from .config import load_config
    st = load_config()["settings"]
    try:
        hh, mm = (int(x) for x in (st.get("dailyAt") or "05:30").split(":"))
        at = dt.time(hh, mm)
    except ValueError:
        at = dt.time(5, 30)
    return st.get("dailyMode", "playlists"), at


def mix_day(now=None):
    """Which "mix day" it is: a mix only changes at the time of the daily refresh, not at midnight – otherwise all
    mixes would be "changed" at night."""
    now = now or dt.datetime.now()
    mode, at = _daily_at()
    if mode == "aus":   # i18n-ignore: stored value
        return now.date()
    return now.date() if now.time() >= at else now.date() - dt.timedelta(days=1)


def period_start(every="day", day=None):
    """First mix day of the current period: today, Monday of this week or the 1st of the month."""
    d = day or mix_day()
    if every == "week":
        return d - dt.timedelta(days=d.weekday())
    if every == "month":
        return d.replace(day=1)
    return d


def label(playlist):
    return EVERY.get(options(playlist).get("every"), EVERY["day"])[0]


def _day_start_utc(day):
    """Start of the mix day as naive UTC time (Navidrome returns "played" in UTC)."""
    mode, at = _daily_at()
    local = dt.datetime.combine(day, dt.time(0, 0) if mode == "aus" else at)   # i18n-ignore: stored value
    return local.astimezone(dt.timezone.utc).replace(tzinfo=None)


def options(playlist):
    return {**DEFAULTS, **(playlist.get("mix") or {})}


def _played_utc(iso):
    if not iso:
        return None
    try:
        t = dt.datetime.fromisoformat(iso.replace("Z", "+00:00"))
    except ValueError:
        return None
    return t.astimezone(dt.timezone.utc).replace(tzinfo=None) if t.tzinfo else t


def weight(song, flavor, avoid_recent, ref):
    """ref = start of the mix day (UTC). What was played after that only counts tomorrow."""
    r = song.get("userRating") or song.get("averageRating") or 0
    loved = bool(song.get("starred"))
    plays = song.get("playCount") or 0
    played = _played_utc(song.get("played"))
    if played and played >= ref:   # already played today -> act as if it had not happened yet
        plays, played = max(0, plays - 1), None
    if flavor == "hits":
        w = 0.15 + 0.5 * r * r + (3 if loved else 0)
    elif flavor == "entdecken":
        w = 1.0 + (2.0 if plays == 0 else 0) + (0.8 if r <= 2 else 0) - (0.5 if r >= 4 else 0) + (0.5 if loved else 0)
    elif flavor == "geschmack":   # "Your sound": taste decides (pick), familiar songs a little less often
        w = 1.0 + (0.6 if plays == 0 else 0) + (0.4 if loved else 0)
    else:
        w = 1.0 + 0.6 * r + (2 if loved else 0)
    if avoid_recent and played is not None and (ref - played).days < avoid_recent:
        w *= 0.08   # played recently: only rarely again
    return max(w, 0.01)


def _u(seed, song_id):
    """Uniformly distributed random value in (0, 1) – fixed for (day, playlist, song)."""
    h = hashlib.sha1(f"{seed}|{song_id}".encode()).digest()
    return (int.from_bytes(h[:8], "big") + 1) / (2 ** 64 + 2)


def settings_key(cfg, playlist):
    """Fingerprint of everything that determines the selection (but not of name, cover, status …)."""
    from . import rules
    p = {k: playlist.get(k) for k in ("welt", "stil", "person", "hits", "minRating", "addArtists", "excludeArtists",
                                       "mix", "type", "rules", "rulesOp")}
    # World and vibe only with what determines the selection – renaming or a new icon does not reshuffle mixes
    cosmetic = ("name", "icon", "color", "description", "group")
    welten = [{k: v for k, v in w.items() if k not in cosmetic} for w in cfg["welten"] if w["id"] in rules.welt_ids(playlist)]
    stil = next(({k: v for k, v in s.items() if k not in cosmetic} for s in cfg["stile"] if s["id"] == playlist.get("stil")), None)
    person = rules.person_of(cfg, playlist) or {}
    st = cfg["settings"]
    parts = [p, welten, stil, person.get("user"), person.get("dislikes"),
             [st.get(k) for k in ("minDuration", "allMinRating", "excludeTitles", "hitsShare")]]
    # Radio bands, own sound filter and minimum length count too – only appended when set, so the fingerprint of
    # existing mixes without these fields does not change (otherwise all would be picked anew mid-period)
    extra = {k: playlist[k] for k in ("radio", "sound", "minDuration", "notPlayedDays", "together", "review", "daytime",
                                      "unheard", "album", "episodes")
             if playlist.get(k) is not None}
    if extra:
        parts.append(extra)
    if person.get("child"):   # a child profile: children's music belongs to "all" – pick anew right away
        parts.append({"child": True})
    from .taste import excluded
    if excluded(person):   # music worlds kept out of the taste: pick anew right away, not only next week
        parts.append({"tasteExclude": list(excluded(person))})
    raw = json.dumps(parts, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha1(raw.encode()).hexdigest()[:16]


def _load_state():
    try:
        data = json.loads(read_text(MIX_STATE))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def remember(cfg, playlist, lib, order, day, albums=None):
    """Remember the written selection of the day (song IDs) – so it stays the same over the day. Also records the
    selection in the mix history the mixes learn from (app/feedback.py). albums: for whole albums ("Album of the week",
    "Next episode") how many there were to choose from – the preview shows it again later."""
    from . import feedback, rules
    user = (rules.person_of(cfg, playlist) or {}).get("user")
    feedback.record(playlist["id"], user, options(playlist).get("every", "day"), day, [lib.songs[i]["id"] for i in order])
    with _state_lock:
        data = _load_state()
        ids = {p["id"] for p in cfg["playlists"]}
        data = {k: v for k, v in data.items() if k in ids}
        data[playlist["id"]] = {"day": day.isoformat(), "key": settings_key(cfg, playlist),
                                "ids": [lib.songs[i]["id"] for i in order]}
        if albums is not None:
            data[playlist["id"]]["albums"] = albums
        try:
            write_atomic(MIX_STATE, json.dumps(data))
        except OSError:
            pass


def select(lib, ids, playlist, today=None, cfg=None, adjust=None, arrange=None, keep=None):
    """List of song indices in playing order. adjust: song ID -> weight factor (learned skipping).
    arrange(lib, chosen) -> playing order or None: for a new selection instead of spread() (smooth transitions) – a
    selection already written in this period keeps its order. keep(song) -> may a song of that selection stay? It stays
    the same for the whole period – what was played since (discovered), a star Deezer set anew or a sound measured
    since do not change it; without keep only what is still in `ids`."""
    adjust = adjust or {}
    opt = options(playlist)
    day = period_start(opt.get("every", "day"), today)
    if cfg is not None:   # already written in this period? Then exactly that selection
        saved = _load_state().get(playlist.get("id"))
        if saved and saved.get("day") == day.isoformat() and saved.get("key") == settings_key(cfg, playlist):
            index, pool = lib.index_of(), set(ids)
            order = [index[s] for s in saved.get("ids", []) if s in index
                     and (keep(lib.songs[index[s]]) if keep else index[s] in pool)]
            if order:
                return order
    seed = f"{day.isoformat()}|{playlist.get('id')}|{opt.get('salt', '')}"
    ref = _day_start_utc(day)
    songs = lib.songs
    # Efraimidis-Spirakis: weighted random order without replacement
    keyed = sorted(((math.log(_u(seed, songs[i]["id"]))
                     / (weight(songs[i], opt["flavor"], opt["avoidRecent"], ref) * adjust.get(songs[i]["id"], 1.0)), i)
                    for i in ids), reverse=True)
    per_artist, per_album, chosen = Counter(), Counter(), []
    size = max(5, int(opt["size"]))
    # fixed length ("Good night", 30 minutes): as many songs as fill the time
    seconds = int(opt.get("minutes") or 0) * 60
    if seconds:
        size, total = 500, 0
    cap_artist = int(opt["perArtist"]) or 10 ** 9   # 0 = no limit
    cap_album = int(opt["perAlbum"]) or 10 ** 9
    for _, i in keyed:
        s = songs[i]
        artist = lib._main_artist(s)
        album = s.get("albumId") or f"?{i}"   # without an album ID no album limit
        if per_artist[artist] >= cap_artist or per_album[album] >= cap_album:
            continue
        per_artist[artist] += 1
        per_album[album] += 1
        chosen.append(i)
        if seconds:
            total += int(s.get("duration") or 0)
            if total >= seconds:
                break
        if len(chosen) >= size:
            break
    return (arrange and arrange(lib, chosen)) or spread(lib, chosen)


def spread(lib, chosen):
    """Order so that the same band comes twice in a row as rarely as possible.
    Greedy: next the band with the most remaining songs (except the one just played);
    within a band the weighted order is kept."""
    artist = lambda i: lib._main_artist(lib.songs[i])  # noqa: E731
    queues = {}
    for i in chosen:
        queues.setdefault(artist(i), []).append(i)
    first = {a: k for k, a in enumerate(queues)}   # tie: whoever came earlier in the selection
    out, last = [], None
    while queues:
        cands = [a for a in queues if a != last] or list(queues)
        a = max(cands, key=lambda x: (len(queues[x]), -first[x]))
        out.append(queues[a].pop(0))
        if not queues[a]:
            del queues[a]
        last = a
    return out


def _tempo_gap(a, b):
    """0 (same tempo) … 1 (15 % or more apart); half or double tempo counts as fairly close (from 0.4)."""
    x = abs(math.log2(a / b))
    return min(1.0, x / _TEMPO_SPAN, 0.4 + abs(x - 1) / _TEMPO_SPAN)


def transition_cost(a, b, idx=None):
    """How well song b follows song a: 0 (seamless) … 1. a, b = (song index, features) – sound from the sound vectors
    (idx: similar.Index; cosine 0.7 and more = 0, −0.1 and less = 1), tempo, key on the Camelot wheel, energy. A part
    without data on one of the two songs counts as 0.5."""
    from .ml import key_distance
    (i, fa), (j, fb) = a, b
    c = idx.cos(i, j) if idx is not None else None
    parts = {"sound": None if c is None else min(1.0, max(0.0, (0.7 - c) / 0.8))}
    if fa.get("bpm") and fb.get("bpm"):
        parts["tempo"] = _tempo_gap(fa["bpm"], fb["bpm"])
    if fa.get("camelot") and fb.get("camelot"):
        d = key_distance(fa["camelot"], fb["camelot"])
        parts["key"] = _KEY_COST[d] if d < len(_KEY_COST) else 1.0
    if fa.get("energy") is not None and fb.get("energy") is not None:
        parts["energy"] = min(1.0, abs(fa["energy"] - fb["energy"]) / 0.4)
    return sum(w * (0.5 if parts.get(k) is None else parts[k]) for k, w in TRANSITION.items())


def smooth(lib, chosen):
    """Playing order with smooth transitions: starting with the first song of the selection, always the remaining song
    that follows the last one best (transition_cost) – greedy and deterministic, so the mix stays the same for the
    same selection. Never the same band twice in a row: a band only comes next if this is still possible for the rest
    (otherwise the band that would be left over goes first). -> None if fewer than half of the songs have a sound
    vector or a key (then spread() as before)."""
    from . import similar
    from .classify import song_features
    if len(chosen) < 3:
        return None
    feats = song_features(lib)
    idx = similar.index(lib)
    info = {i: feats.get(i) or {} for i in chosen}
    known = sum(1 for i in chosen if (idx is not None and idx.has(i)) or info[i].get("camelot"))
    if known * 2 < len(chosen):
        return None
    band = {i: lib._main_artist(lib.songs[i]) for i in chosen}
    left = list(chosen)
    count = Counter(band.values())
    out = [left.pop(0)]
    count[band[out[0]]] -= 1
    while left:
        last = band[out[-1]]
        rest = len(left) - 1                  # songs after the next one
        top = count.most_common(2)

        def possible(b):
            """After a song of band b: can the rest still be arranged without a band twice in a row?"""
            other = next((n for a, n in top if a != b), 0)
            return count[b] - 1 <= rest // 2 and other <= (rest + 1) // 2
        ok = {b: b != last and possible(b) for b in count if count[b] > 0}
        cands = [j for j in left if ok[band[j]]] or [j for j in left if band[j] != last] or left
        _cost, k, nxt = min((transition_cost((out[-1], info[out[-1]]), (j, info[j]), idx), k, j)
                            for k, j in enumerate(cands))
        left.remove(nxt)
        count[band[nxt]] -= 1
        out.append(nxt)
    return out


def radio_sound(lib, pool, seeds, adjust):
    """Radio: weight factor by how much a song sounds like the seed bands (closest seed band; 0.6 for unrelated …
    1.4 from a cosine of 0.6 to the band's centroid) – multiplied into adjust (song ID -> factor). Songs without a
    sound vector and seed bands without a sound stay unchanged."""
    from . import similar
    idx = similar.index(lib)
    if idx is None:
        return
    cents = [c for c in (idx.centroid(s) for s in seeds) if c is not None]
    if not cents:
        return
    for i in pool:
        near = [x for x in (idx.closeness(i, c) for c in cents) if x is not None]
        if near:
            sid = lib.songs[i]["id"]
            adjust[sid] = adjust.get(sid, 1.0) * (0.6 + 0.8 * min(1.0, max(0.0, (max(near) + 0.1) / 0.7)))


MORNING_POWER = 3   # like "Your sound": the sound of the mornings decides strongly


def morning_sound(cfg, base, plib, pool, playlist, today, adjust):
    """"Good morning" from the listening clock: weight factor by how much a song sounds like what the person's account
    plays in the morning (listenclock.morning_taste(): sound prototypes of the morning plays) – multiplied into adjust.
    Without the habit, sound vectors or enough morning songs with one: nothing changes."""
    from . import listenclock, rules, taste
    person = rules.person_of(cfg, playlist) or {}
    user = person.get("user")
    st = listenclock.morning_taste(cfg, base, plib, user, today, taste.excluded(person)) if user else None
    if st is None:
        return
    by = st.for_lib(plib)
    for i in pool:
        v = by[i]
        if v is not None:
            sid = plib.songs[i]["id"]
            adjust[sid] = adjust.get(sid, 1.0) * taste.factor(v) ** MORNING_POWER


def calm_down(lib, order, feats, quiet_end=0, rise=False):
    """By arousal, descending (rise: ascending, "Good morning") – still never the same band twice in a row.
    quiet_end: this many songs without vocals (AI sound analysis) at the end, so it fades out without a voice."""
    rest = sorted(order, key=lambda i: (feats.get(i) or {}).get("arousal", 0.5) * (1 if rise else -1))
    tail = []
    if quiet_end:   # the calmest songs without vocals go to the end only after spreading
        tail = [i for i in rest if (feats.get(i) or {}).get("inst", 0) >= 0.8][-quiet_end:]
        rest = [i for i in rest if i not in set(tail)]
    out, last = [], None
    while rest:
        # as close to the order as possible – but look further back if needed so no band comes twice in a row
        k = next((k for k, i in enumerate(rest) if lib._main_artist(lib.songs[i]) != last), 0)
        i = rest.pop(k)
        out.append(i)
        last = lib._main_artist(lib.songs[i])
    return out + tail


ALBUM_MIN_TRACKS = 6   # album of the week: no singles or EPs
ALBUM_MAX_ARTISTS = 3  # … and no compilations


def album_candidates(cfg, base, plib, playlist, nsp, today=None):
    """Albums for "Album of the week": [(weight, album id)] – at least ALBUM_MIN_TRACKS songs, at most ALBUM_MAX_ARTISTS
    bands, at least half of them in the playlist's selection (music world, filters, dislikes), not a single song of it
    played on the account. Weight: how much the album sounds like the account's taste (taste.matcher with the sound
    weighted as for "Your sound", power 3), × 2 for a favorite band, × the Deezer stars of its songs."""
    from . import rules, taste
    pool = rules.apply_sound(cfg, plib, playlist, plib.match(nsp))
    albums = {}
    for i, s in enumerate(plib.songs):
        if s.get("albumId"):
            albums.setdefault(s["albumId"], []).append(i)
    in_pool = Counter(plib.songs[i].get("albumId") for i in pool)
    person = rules.person_of(cfg, playlist) or {}
    user = person.get("user")
    sim = taste.matcher(taste.for_person(cfg, base, person, today), plib, sound=taste.FLAVOR_SOUND) if user else None
    favorites = set(rules.favorite_artists(cfg, person, rules.BuildContext(plib, today))) if person else set()
    out = []
    for aid, idx in albums.items():
        if len(idx) < ALBUM_MIN_TRACKS or in_pool[aid] * 2 < len(idx):
            continue
        songs = [plib.songs[i] for i in idx]
        if any(s.get("playCount") for s in songs):
            continue   # already (partly) heard
        bands = {plib._main_artist(s) for s in songs}
        if len(bands) > ALBUM_MAX_ARTISTS:
            continue
        fit = sum(sim(i) for i in idx) / len(idx) if sim else 0.5
        stars = sum((s.get("userRating") or s.get("averageRating") or 0) for s in songs) / len(songs)
        out.append((taste.factor(fit) ** 3 * (2.0 if bands & favorites else 1.0) * (0.5 + 0.25 * stars), aid))
    return out


def album_order(cfg, base, plib, playlist, nsp, today=None):
    """"Album of the week" -> (song indices in plib in album order, number of candidate albums). One album per period,
    picked by weight with a random value fixed for (period, playlist) – it stays for the whole period, even after its
    songs were played (remembered like a mix)."""
    opt = options(playlist)
    day = period_start(opt.get("every", "week"), today)
    saved = _load_state().get(playlist.get("id"))
    if saved and saved.get("day") == day.isoformat() and saved.get("key") == settings_key(cfg, playlist):
        index = plib.index_of()
        order = [index[s] for s in saved.get("ids", []) if s in index]
        if order:   # remembered before the count was: the albums to choose from now (the one taken may be begun)
            return order, saved.get("albums") or max(1, len(album_candidates(cfg, base, plib, playlist, nsp, today)))
    cands = album_candidates(cfg, base, plib, playlist, nsp, today)
    if not cands:
        return [], 0
    seed = f"{day.isoformat()}|{playlist.get('id')}|{opt.get('salt', '')}"
    aid = max(cands, key=lambda c: math.log(_u(seed, c[1])) / c[0])[1]   # weighted random choice (Efraimidis-Spirakis)
    songs = plib.songs
    order = sorted((i for i, s in enumerate(songs) if s.get("albumId") == aid),
                   key=lambda i: (songs[i].get("discNumber") or 1, songs[i].get("track") or 0, songs[i].get("title") or ""))
    return order, len(cands)


EPISODE_DAYS = 90      # "Next episode": the series an account listened to this recently …
EPISODE_SERIES = 12    # … at most this many, the most recently heard first
_EPISODE = (re.compile(r"\b(?:folge|episode|fall|teil|band|vol(?:ume)?|part|nr|no)\.?\s*(\d{1,4})\b", re.I),
            re.compile(r"#\s*(\d{1,4})\b"),
            re.compile(r"^\s*(\d{1,4})(?!\d)"),
            re.compile(r"(?:^|\s)[-–]\s*(\d{1,4})\s*(?:[-–:/.]|$)"))


def episode_number(album):
    """The number of an episode in its album name – “Folge 12: …”, “012/Der Super-Papagei”, “Episode 3”, “Vol. 4”,
    “Die drei ??? - 125 - …” – or None."""
    for rx in _EPISODE:
        m = rx.search(album or "")
        if m:
            return int(m.group(1))
    return None


def _listened(user, plib, today):
    """When this account last began each song in the last EPISODE_DAYS days (Unix seconds) and which songs it ever
    played to the end – from the live plays, the recap's counts and, where the song list is the account's own (a stored
    password), Navidrome's counters. -> ({song id: time}, {song ids played})"""
    from . import listen, rueckblick
    last, done = {}, set(rueckblick.played_ever(user))
    since = time.time() - EPISODE_DAYS * 86400
    first = today - dt.timedelta(days=EPISODE_DAYS)
    rows = listen.events(user, first, today)
    if listen.is_family(user):   # the family's mixes heard on the people's accounts – a child on a parent's phone
        rows = rows + listen.family_events(first, today)
    for r in rows:
        if r["k"] in ("start", "play"):
            last[r["id"]] = max(last.get(r["id"], 0), r["t"])
            if r["k"] == "play":
                done.add(r["id"])
    if (getattr(plib, "user", None) or "").lower() == user.lower():
        for s in plib.songs:
            if s.get("playCount"):
                done.add(s["id"])
                t = _played_utc(s.get("played"))
                sec = t.replace(tzinfo=dt.timezone.utc).timestamp() if t else 0
                if sec >= since:
                    last[s["id"]] = max(last.get(s["id"], 0), sec)
    return last, done


def episode_order(cfg, base, plib, playlist, nsp, today=None):
    """"Next episode" -> (song indices in plib, number of series): for every series (album artist) of the playlist's
    worlds the account listened to in the last EPISODE_DAYS days – the most recently heard first, at most
    EPISODE_SERIES – its next episode: the rest of the episode heard last while it is not finished, otherwise the first
    one after it (by episode number, without one by year and name) that was never begun – after the last one the first
    never begun. The tracks in album order. It stays the same for the day (remembered like a mix)."""
    from . import rules
    today = today or mix_day()
    saved = _load_state().get(playlist.get("id"))
    if saved and saved.get("day") == period_start(options(playlist).get("every", "day"), today).isoformat() \
            and saved.get("key") == settings_key(cfg, playlist):
        index = plib.index_of()
        order = [index[s] for s in saved.get("ids", []) if s in index]
        if order:   # remembered before the count was: one episode per series
            return order, saved.get("albums") or len({plib.songs[i].get("albumId") for i in order})
    user = (rules.person_of(cfg, playlist) or {}).get("user")
    if not user:
        return [], 0
    songs = plib.songs
    albums = {}
    for i in plib.match(nsp):
        if songs[i].get("albumId"):
            albums.setdefault(songs[i]["albumId"], []).append(i)
    last, done = _listened(user, plib, today)
    series = {}
    for idx in albums.values():
        idx.sort(key=lambda i: (songs[i].get("discNumber") or 1, songs[i].get("track") or 0, songs[i].get("title") or ""))
        first = songs[idx[0]]
        name = first.get("displayAlbumArtist") or plib._main_artist(first) or ""
        heard = max(last.get(songs[i]["id"], 0) for i in idx)
        number = episode_number(first.get("album"))
        series.setdefault(name, []).append(((number is None, number or 0, first.get("year") or 0,
                                             (first.get("album") or "").lower()), idx, heard))
    picks = []
    for eps in series.values():
        latest = max(e[2] for e in eps)
        if not latest:
            continue   # not listened to lately
        eps.sort(key=lambda e: e[0])
        cur = next(k for k, e in enumerate(eps) if e[2] == latest)
        rest = [i for i in eps[cur][1] if songs[i]["id"] not in done]
        if rest:   # begun and not finished: on with it
            picks.append((latest, rest))
            continue
        untouched = [e for e in eps[cur + 1:] + eps[:cur] if not e[2] and not any(songs[i]["id"] in done for i in e[1])]
        if untouched:
            picks.append((latest, untouched[0][1]))
    picks.sort(key=lambda x: -x[0])
    return [i for _t, idx in picks[:EPISODE_SERIES] for i in idx], len(picks)


def unheard(lib, ids):
    """The songs among ids that the account of this song list has never played (playCount 0)."""
    songs = lib.songs
    return [i for i in ids if not songs[i].get("playCount")]


def person_lib(cfg, playlist, base):
    """Song list as seen by the person the mix is for (their stars, favorites, plays).
    Without a password for their account: the default library."""
    from . import rules
    user = ((rules.person_of(cfg, playlist) or {}).get("user") or "").lower()
    if not user or (base.user or "").lower() == user:
        return base
    try:
        from .stats import songs_for
        return songs_for(user, base)
    except Exception:   # no password / Navidrome briefly gone
        return base


def review_order(cfg, base, playlist, today=None):
    """Recap playlist ("Your October 2026"): the most played songs of the period, most played first."""
    from . import rueckblick, rules
    user = (rules.person_of(cfg, playlist) or {}).get("user")
    if not user:
        return []
    start, end, _ = rules.review_period((playlist.get("review") or {}).get("period", "month"), today or mix_day())
    per_song, _ = rueckblick.plays_between(user, start, end)
    index = base.index_of()
    person = rules.person_of(cfg, playlist) or {}
    dis = person.get("dislikes") or {}
    nogo = set(dis.get("artists", [])) | set(playlist.get("excludeArtists", []))
    genres = [g.lower() for g in dis.get("genres", [])]
    skip = _never(base, person_lib(cfg, playlist, base), [user])   # rated 1 star by the person
    if person.get("clean"):
        from . import liedtext
        allow = set((cfg["settings"].get("kinderschutz") or {}).get("allow", []))
        skip |= set(liedtext.derb(allow)) | {s["id"] for s in base.songs if s.get("explicitStatus") in ("explicit", "e") and s["id"] not in allow}

    def ok(s):
        if s["id"] in skip or base._main_artist(s) in nogo or s.get("artist") in nogo:
            return False
        g = " ".join(x.get("name", "") for x in s.get("genres") or []).lower() + " " + (s.get("genre") or "").lower()
        return not any(x in g for x in genres)
    ranked = sorted(((n, sid) for sid, n in per_song.items() if sid in index and ok(base.songs[index[sid]])),
                    key=lambda x: (-x[0], x[1]))
    return [index[sid] for _, sid in ranked[:max(5, int(options(playlist)["size"]))]]


def _never(base, plib, users):
    """Songs rated 1 star by hand on any of the accounts (family mix: what one dislikes, nobody gets)."""
    from . import feedback
    out = set()
    for u in users:
        lib = plib
        if (getattr(plib, "user", None) or "").lower() != u.lower():
            try:
                from .stats import songs_for
                lib = songs_for(u, base)
            except Exception:   # noqa: BLE001 – no password for this account
                continue
        out |= set(feedback.manual_dislikes(lib, u) or ())
    return out


def pick(cfg, base, playlist, nsp, today=None, keep=False):
    """-> (song indices in base in playing order, size of the pool). keep=True remembers the selection."""
    if playlist.get("review"):   # recap: no random selection but the listening statistics
        order = review_order(cfg, base, playlist, today)
        return order, len(order)
    plib = person_lib(cfg, playlist, base)
    from . import feedback, rules
    if playlist.get("album") or playlist.get("episodes"):   # whole albums instead of a selection
        if playlist.get("album"):   # album of the week
            order, n = album_order(cfg, base, plib, playlist, nsp, today)
        else:   # the next episode of every series being listened to
            order, n = episode_order(cfg, base, plib, playlist, nsp, today)
        if keep and order:
            remember(cfg, playlist, plib, order, period_start(options(playlist).get("every", "week"), today), albums=n)
        if plib is not base:
            index = base.index_of()
            order = [index[plib.songs[i]["id"]] for i in order if plib.songs[i]["id"] in index]
        return order, n
    pool = rules.apply_sound(cfg, plib, playlist, plib.match(nsp))   # sound vibes: only matching songs
    if playlist.get("unheard"):   # "Discovered for you": only what this account has never played
        pool = frozenset(unheard(plib, pool))
    adjust, never = {}, set()
    if cfg["settings"].get("mixLearn", True):   # learn from listening: skipped -> less often, 1 star by hand -> never
        person = rules.person_of(cfg, playlist) or {}   # none: a neutral view
        user = person.get("user")
        members = [x for x in cfg["personen"] if x["id"] in (playlist.get("together") or [])]
        never = _never(base, plib, [x["user"] for x in [person] + members if x.get("user")])   # protection: everyone
        together = rules.together_of(cfg, playlist)   # taste: only with consent
        # one per account – the playlist's own person first (with its own exclusion); the members are never the family
        tasters = [x for x in [person] + together if x.get("user")]
        if never:
            pool = frozenset(i for i in pool if plib.songs[i]["id"] not in never)
        adjust = dict(feedback.factors(user, today))
        # Taste: what sounds like what the person likes comes more often ("Your sound": much more often).
        # Family mix ("What everyone likes"): everyone's taste counts the same – what everyone likes comes much more often
        from . import taste
        if together:
            sims = [m for m in (taste.matcher(taste.for_person(cfg, base, x, today), plib) for x in tasters) if m]
            power = 3 / len(sims) if sims else 0
        else:   # "Your sound": the sound taste (soundtaste.py) counts more too
            own_sound = options(playlist).get("flavor") == "geschmack" or bool(playlist.get("unheard"))
            sim = taste.matcher(taste.for_person(cfg, base, person, today), plib,
                                sound=taste.FLAVOR_SOUND if own_sound else 1.0)
            sims, power = ([sim] if sim else []), (3 if own_sound else 1)
        if sims:
            for i in pool:
                sid = plib.songs[i]["id"]
                f = 1.0
                for sim in sims:
                    f *= taste.factor(sim(i))
                adjust[sid] = adjust.get(sid, 1.0) * f ** power
    if playlist.get("radio"):   # radio: songs that sound like the seed bands come more often
        radio_sound(plib, pool, playlist["radio"].get("seed", []), adjust)
    if playlist.get("daytime") == "morning":   # Good morning: what sounds like the person's mornings comes much more often
        morning_sound(cfg, base, plib, pool, playlist, today, adjust)
    snd = rules.sound_of(cfg, playlist) or {}
    stil = next((s for s in cfg["stile"] if s["id"] == playlist.get("stil")), None) or {}
    rise = stil.get("arc") == "rise" or playlist.get("daytime") == "morning"
    calm = set(snd.get("moods", [])) & {"schlaf", "ruhig"}
    # smooth transitions – not where an arc sets the order (falling asleep, good morning)
    smoothly = cfg["settings"].get("smoothTransitions", True) and not rise and not calm
    # the selection written in this period stays – only a song gone missing (converted, deleted), rated 1 star by hand
    # since or one kid-safe mode takes out leaves it
    bad = rules.rude(cfg) if rules.kid_safe(cfg, playlist) else None
    keep = lambda s: not s.get("missing") and s["id"] not in never and not (bad and bad(s))   # noqa: E731
    order = select(plib, pool, playlist, today, cfg, adjust, arrange=smooth if smoothly else None, keep=keep)
    if rise:   # Good morning: start calm, then livelier
        from .classify import song_features
        order = calm_down(plib, order, song_features(plib), rise=True)
    elif calm:   # for falling asleep: from a bit livelier to very calm
        from .classify import song_features   # with a fixed length ("Good night"): without vocals at the end
        order = calm_down(plib, order, song_features(plib), quiet_end=3 if options(playlist).get("minutes") else 0)
    if keep:
        remember(cfg, playlist, plib, order, period_start(options(playlist).get("every", "day"), today))
    if plib is not base:
        index = base.index_of()
        order = [index[plib.songs[i]["id"]] for i in order if plib.songs[i]["id"] in index]
    return order, len(pool)


def m3u(lib, order, name, to_root="..", kind="Daily Mix"):
    """Extended M3U with paths relative to the playlist folder (to_root = way to the music root).
    The header line starts with "# Tuttiphon" (MARKER) – that is how playlists._has_marker() recognizes own files."""
    name = " ".join(str(name).splitlines())   # a line break in the name would start an entry of its own
    lines = ["#EXTM3U", f"#PLAYLIST:{name}",
             f"# {MARKER} " + _s("{kind} – created automatically, please make changes in Tuttiphon", kind=kind)]
    entries = 0
    for i in order:
        s = lib.songs[i]
        path = lib.real_path(i)
        if not path:   # song not found right now (e.g. renamed) -> leave it out instead of a dead entry
            continue
        line = f"{to_root}/{path}" if to_root not in ("", ".") else path
        if line.startswith("#"):   # lines starting with # would be comments
            line = "./" + line
        title = f"{s.get('artist', '')} - {s.get('title', '')}".replace("\n", " ").replace("\r", " ")
        lines.append(f"#EXTINF:{int(s.get('duration') or 0)},{title}")
        lines.append(line)
        entries += 1
    if order and not entries:
        raise RuntimeError(_("No file paths were found for the mix (Navidrome not reachable?) – nothing written."))
    return "\n".join(lines) + "\n"
