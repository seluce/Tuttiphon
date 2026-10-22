"""Music worlds that create themselves – from the collection and from what is played.

The basis is the catalog in app/scenes.json: per world a name, icon, typical bands and keywords (`keys` – genres of
the files, Last.fm tags, AI music styles, lowercase), plus where needed language (`lang`), period (`era`: as a
condition, e.g. rock classics up to 1999), decade world (`decade`: 80s hits, 90s hits – only the time counts there,
and bands belong to it in addition to their main world), "broad" (`broad`, e.g. pop & charts), "separate world"
(`separate`, e.g. kids and audio plays – left out of the all-playlists) and "niche" (`niche`: bands of these worlds
are not also added to the decade worlds – 80s children's songs do not belong to "The 80s").

* profiles(lib): per band (2 songs or more) the genres of the files, Last.fm tags, AI music styles, language (lyrics,
  otherwise titles) and era (early quarter of the release years – reissues and best-ofs shift the mean)
* assign(lib): per band its main world (best match from 0.45) and for decade worlds also the bands whose time it was
  (early quarter of the years within the decade and middle at most six years later, or Last.fm tag "80s" …)
* members(scene, lib): bands of a world – typical bands of the catalog plus the recognized ones (for rules.welt_artists())
* candidates(cfg, lib): catalog worlds with enough bands and songs that do not exist yet – with fewer bands already when
  someone listens to them a lot (taste, taste.py)
* sync(lib): creates such worlds (settings.welten.auto) and reports them under "to review". Deleted ones do not come
  back (cfg.dismissed "scene|<id>"), worlds created by hand are never touched.
"""
import datetime as dt
import re
import threading
import weakref
from collections import Counter, defaultdict

from . import scenes
from .i18n import _s

MIN_SONGS = 2            # a band needs this many songs to be recognized
PRIMARY = 0.45           # from this match on a band belongs to its best world
ERA = 0.6                # from this match on a band also belongs to a decade world
CREATE = (4, 60)         # new world from this many bands and songs …
CREATE_ERA = (5, 80)     # … for decade worlds
HEARD = (2, 20, 0.05)    # … or from 2 bands, 20 songs if someone listens to them at least 5 % of the time
_memo = weakref.WeakKeyDictionary()   # library -> (state of the sources, result); new with every freshly loaded one
_lock = threading.Lock()


def _norm(text):
    return re.sub(r"[^0-9a-zäöüß&'+]+", " ", (text or "").lower()).strip()   # i18n-ignore


def _stamps():
    from . import lastfm, liedtext, ml
    # lyrics: recompute only after a finished read, not at every intermediate state
    return (lastfm._mem.get("stamp"), ml.stamp(), liedtext.generation(), id(scenes.catalog()))


# ---------------------------------------------------------------------------- Describing bands

def profiles(lib):
    """Band -> {n, genres {name: share}, tags {name: 0–1}, styles {name: 0–1}, lang, era, decades}."""
    from . import lastfm, liedtext, ml
    lastfm.load()
    langs = liedtext.languages()
    styles = ml.artist_styles(lib)
    by = defaultdict(list)
    for s in lib.songs:
        by[lib._main_artist(s)].append(s)
    out = {}
    for artist, ss in by.items():
        if not artist or len(ss) < MIN_SONGS:
            continue
        g = Counter()
        for s in ss:
            names = {_norm(x.get("name")) for x in (s.get("genres") or []) if x.get("name")} or \
                ({_norm(s["genre"])} if s.get("genre") else set())
            for name in names:
                g[name] += 1
        years = sorted(y for y in (s.get("year") for s in ss) if isinstance(y, int) and y > 1900)
        info = lastfm.artist(artist) or {}
        tags = {_norm(t): w / 100 for t, w in (info.get("tags") or []) if w >= 5}
        decades = {int(m.group(1)) + 1900 for t in tags for m in [re.fullmatch(r"(?:19)?([5-9]0)s", t)] if m}
        # language: recognized lyrics, otherwise the titles
        known = Counter(langs[s["id"]] for s in ss if s["id"] in langs)
        if sum(known.values()) >= 3:
            de, en = known["de"], known["en"]
        else:
            de, en = _title_lang(ss)
        lang = "de" if de > 1.5 * en and de >= 2 else "en" if en > 1.5 * de and en >= 2 else None
        out[artist] = {"n": len(ss), "genres": {k: v / len(ss) for k, v in g.items()}, "tags": tags,
                       "styles": {_norm(k): v for k, v in (styles.get(artist) or {}).items()}, "lang": lang,
                       "era": years[len(years) // 4] if years else None, "mid": years[len(years) // 2] if years else None,
                       "decades": decades}
    return out


def _title_lang(songs):
    from .liedtext import DE_WORDS, EN_WORDS
    de = en = 0
    for s in songs:
        words = re.findall(r"[a-zäöüß']+", f"{s.get('title') or ''} {s.get('album') or ''}".lower())   # i18n-ignore
        de += sum(w in DE_WORDS for w in words)
        en += sum(w in EN_WORDS for w in words)
    return de, en


def _specificity(profs):
    """Genre -> weight: genres almost every band has (rock, pop, electronic) say little about the world."""
    df = Counter(k for p in profs.values() for k, v in p["genres"].items() if v >= 0.2)
    n = max(1, len(profs))
    return {k: (1.0 if c < 10 or c / n < 0.12 else 0.5 if c / n < 0.25 else 0.15) for k, c in df.items()}


# ---------------------------------------------------------------------------- Assigning bands to worlds

def score(prof, entry, spec, typical=False):
    """How well does a band fit a catalog world? 0–1."""
    era = entry.get("era")
    if entry.get("decade"):   # decade world: only the time counts – the band's, not that of the reissues
        tagged = any(era[0] <= d + 5 <= era[1] for d in prof["decades"])
        heyday = prof["era"] is not None and era[0] - 2 <= prof["era"] <= era[1] and (prof["mid"] or 0) <= era[1] + 6
        return 0.8 if tagged else 0.65 if heyday else 0.0
    if typical:
        return 1.0
    keys = {_norm(k) for k in (entry.get("keys") or [])}
    g = sum(v * spec.get(k, 1.0) for k, v in prof["genres"].items() if k in keys)
    t = max([w * spec.get(k, 1.0) for k, w in prof["tags"].items() if k in keys] or [0])
    st = max([w for k, w in prof["styles"].items() if k in keys] or [0])
    parts = sorted([min(1.0, g / 0.5), 0.9 * t, 0.9 * st], reverse=True)
    s = min(0.99, parts[0] + 0.25 * (parts[1] + parts[2]))   # typical bands of the catalog win a tie
    if era and not (prof["era"] is not None and era[0] <= prof["era"] <= era[1]
                    or any(era[0] <= d + 5 <= era[1] for d in prof["decades"])):
        return 0.0   # period as a condition, e.g. rock classics
    lang = entry.get("lang")
    if lang and prof["lang"] != lang:
        s *= 0.5 if prof["lang"] is None else 0.15
    if entry.get("broad"):
        s *= 0.8
    return round(s, 3)


def assign(lib):
    """{"primary": {band: (world, match)}, "members": {world: [bands]}, "profiles": …} – cached."""
    key = _stamps()
    with _lock:
        hit = _memo.get(lib)
        if hit and hit[0] == key:
            return hit[1]
    profs = profiles(lib)
    spec = _specificity(profs)
    cat = scenes.catalog()
    typical = {sc["id"]: {scenes.norm(b) for b in sc["bands"]} for sc in cat}
    primary, members = {}, defaultdict(list)
    for artist, prof in profs.items():
        na = scenes.norm(artist)
        scored = [(score(prof, sc, spec, na in typical[sc["id"]]), sc) for sc in cat]
        plain = [x for x in scored if not x[1].get("decade")]
        best = max(plain, key=lambda x: x[0]) if plain else (0, None)
        if best[0] >= PRIMARY:
            primary[artist] = (best[1]["id"], best[0])
            members[best[1]["id"]].append(artist)
        niche = best[1] is not None and best[0] >= PRIMARY and best[1].get("niche")
        for s, sc in scored:   # decade worlds: in addition to the main world – not for niches like kids or medieval
            if sc.get("decade") and s >= ERA and not niche:
                members[sc["id"]].append(artist)
    out = {"primary": primary, "members": dict(members), "profiles": profs}
    with _lock:
        _memo[lib] = (key, out)
    return out


def members(scene_id, lib):
    """Bands of a world linked to the catalog: typical bands that exist, and the recognized ones."""
    found = scenes.members(scene_id, lib.artist_index())
    for a in assign(lib)["members"].get(scene_id, []):
        if a not in found:
            found.append(a)
    return found


# ---------------------------------------------------------------------------- New worlds

def _songs(lib, artists):
    count = Counter(lib._main_artist(s) for s in lib.songs)
    return sum(count.get(a, 0) for a in artists)


def candidates(cfg, lib, today=None):
    """Catalog worlds that do not exist yet and offer enough – sorted by size.
    -> [{"scene", "bands", "songs", "heard": [people who listen to them a lot]}]"""
    from . import rules
    ctx = rules.BuildContext(lib)
    dismissed = set(cfg.get("dismissed", []))
    linked = {w.get("scene") for w in cfg["welten"] if w.get("scene")}
    taken = set()
    decades = {sc["id"] for sc in scenes.catalog() if sc.get("decade")}
    for w in cfg["welten"]:   # decade worlds overlap with everything – they do not prevent a style world
        if w.get("scene") not in decades:
            taken |= set(rules.welt_artists(w, ctx))
    shares = _heard_shares(cfg, lib, today)
    out = []
    for sc in scenes.catalog():
        if sc["id"] in linked or f"scene|{sc['id']}" in dismissed:
            continue
        bands = members(sc["id"], lib)
        if not bands:
            continue
        if not sc.get("decade") and len([a for a in bands if a in taken]) >= 0.5 * len(bands):
            continue   # basically exists already (a world created by hand with these bands)
        songs = _songs(lib, bands)
        heard = [name for name, share in shares.items() if sum(share.get(a, 0) for a in bands) >= HEARD[2]]
        need = CREATE_ERA if sc.get("decade") else CREATE
        if (len(bands) >= need[0] and songs >= need[1]) or (heard and len(bands) >= HEARD[0] and songs >= HEARD[1]):
            out.append({"scene": sc, "bands": bands, "songs": songs, "heard": heard})
    out.sort(key=lambda c: (-len(c["heard"]), -c["songs"]))
    return out


def _heard_shares(cfg, lib, today):
    """Person -> {band: share of what was played} for all people with a taste profile (taste.py)."""
    from . import taste
    out = {}
    for p in cfg["personen"]:
        try:
            prof = taste.profile(cfg, lib, p["user"], today)
        except Exception:   # noqa: BLE001 – no password, or Navidrome briefly away
            prof = None
        if prof and prof.get("enough"):
            out[p["name"]] = dict(prof["artists"])
    return out


def new_welt(sc, taken_ids):
    wid, n = sc["id"], 2
    while wid in taken_ids:
        wid, n = f"{sc['id']}-{n}", n + 1
    return {"id": wid, "name": sc["name"], "icon": sc["icon"], "artists": [], "albums": [], "genres": [],
            "excludeTitles": [], "excludeAlbums": [], "minRating": 3, "minDuration": None,
            "separate": bool(sc.get("separate")), "scene": sc["id"], "autoScene": True, "excludedArtists": [],
            "auto": dt.date.today().isoformat()}


def sync(lib, log=lambda *_: None):
    """Create missing music worlds (if turned on). -> list of the new worlds (id, name, bands)."""
    from .config import load_config, update_config
    cfg = load_config()
    if not (cfg["settings"].get("welten") or {}).get("auto", True):
        return []
    found = candidates(cfg, lib)
    if not found:
        return []
    made = []

    def apply(fresh):
        linked = {w.get("scene") for w in fresh["welten"]}
        ids = {w["id"] for w in fresh["welten"]}
        dismissed = set(fresh.get("dismissed", []))
        for c in found:
            sc = c["scene"]
            if sc["id"] in linked or f"scene|{sc['id']}" in dismissed:
                continue
            w = new_welt(sc, ids)
            fresh["welten"].append(w)
            ids.add(w["id"])
            linked.add(sc["id"])
            made.append({"id": w["id"], "name": w["name"], "bands": len(c["bands"]), "heard": c["heard"]})
    update_config(apply)
    for m in made:
        if m["heard"]:
            log(_s("  ✓ New music world “{name}” with {bands} bands – listened to by {people}",
                   name=m["name"], bands=m["bands"], people=", ".join(m["heard"])))
        else:
            log(_s("  ✓ New music world “{name}” with {bands} bands", name=m["name"], bands=m["bands"]))
    return made


def recent(cfg, days=14):
    """Worlds created automatically in the last days (for "to review")."""
    since = (dt.date.today() - dt.timedelta(days=days)).isoformat()
    return [w for w in cfg["welten"] if isinstance(w.get("auto"), str) and w["auto"] >= since]
