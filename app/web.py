"""HTTP server: serves the interface from web/, images from Navidrome and a JSON API."""
import datetime as dt
import copy
import json
import math
import mimetypes
import os
import posixpath
import re
import socket
import threading
import time
from collections import OrderedDict
import urllib.parse
from pathlib import Path
from collections import Counter
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from . import audio, auth, autowelten, i18n, backup, localadmin, classify, events, instances, lastfm, liedtext, lyrics, mixer, ml, notify, opus, pflege, taste, rueckblick, watch, webpush, covers, deezer, images, playlists, rules, scenes, stats, suggest
from .i18n import N_, _, _s, _sn
from .config import (CONFIG_FILE, DATA_DIR, EDITABLE_ENV, LOG_DIR, STATE_DIR,
                     WEB_DIR, ConfigDamaged, admin_password, env_var, environment, load_config, load_env, pass_key, paths, paths_info,
                     rating_users, read_bytes, read_text, save_env, save_from_ui, update_config, user_password,
                     weak_password, write_atomic)
from .library import CACHE
from .navidrome import Navidrome, NavidromeError
from .rules import ALL, BuildContext
from .tasks import PIPELINE, STEP_TITLES, TaskRunner, admin_client, history, pipeline

RUNNER = TaskRunner()
_memo = OrderedDict()
_memo_lock = threading.Lock()


def _date(value):
    return dt.date.fromisoformat(value) if value else None


_inflight = {}        # key -> Event: being computed right now (the same request a second time waits for it)
INFLIGHT_WAIT = 120   # seconds; after that a waiting request computes the result itself


def _memoized(name, fn, *extra):
    """Remember the result as long as configuration and library have not changed – per language, since the
    results contain texts. Parallel identical requests (e.g. several pages after a save) compute it only once."""
    stamp = (CONFIG_FILE.stat().st_mtime if CONFIG_FILE.exists() else 0, CACHE.loaded_at, dt.date.today())
    key = (name, *stamp, i18n.current(), extra)
    waited = False
    while True:
        with _memo_lock:
            if key in _memo:
                _memo.move_to_end(key)
                return _memo[key]
            busy = _inflight.get(key)
            if busy is None or waited:
                mine = threading.Event()
                _inflight.setdefault(key, mine)
                break
        busy.wait(INFLIGHT_WAIT)   # another request computes it – then take its result (after an error: compute)
        waited = True
    try:
        value = fn()
        with _memo_lock:
            for k in [k for k in _memo if k[1:4] != stamp]:   # free outdated states right away
                del _memo[k]
            _memo[key] = value
            while len(_memo) > 60:   # otherwise the least recently used
                _memo.popitem(last=False)
    finally:
        with _memo_lock:
            if _inflight.get(key) is mine:
                del _inflight[key]
        mine.set()
    return value


def users_ok(env, cfg):
    return {u: bool(user_password(env, u)) for u in rating_users(env, cfg)}


def _web_address(value):
    """Only http(s) addresses become links in the interface (never javascript: or the like)."""
    value = str(value or "").strip().rstrip("/")
    return value if re.match(r"^https?://[^\s/]+", value, re.I) and value.isprintable() else ""


def nav_web_url(env):
    return _web_address(env.get("NAV_PUBLIC_URL")) or _web_address(env.get("NAV_URL"))


# --------------------------------------------------------------------------- apply automatically

class AutoApply:
    """After changes to the configuration wait a few seconds, then run playlists + scan."""

    def __init__(self):
        self.timer = None
        self.due = None
        self.gen = 0   # every new schedule/cancellation counts up -> an _fire already running sees that it is outdated
        self.forced = False   # also without "apply automatically" (kid-safe mode: new rude songs were found)
        self.lock = threading.Lock()

    def schedule(self, delay=8, force=False):
        if force:
            self.forced = True
        if not self.forced and not load_config()["settings"].get("autoApply", True):
            return
        with self.lock:
            if self.timer:
                self.timer.cancel()
            self.gen += 1
            self.due = time.time() + delay
            self.timer = threading.Timer(delay, self._fire, args=(self.gen,))
            self.timer.daemon = True
            self.timer.start()

    def cancel(self):
        with self.lock:
            if self.timer:
                self.timer.cancel()
            self.gen += 1
            self.timer = self.due = None
            self.forced = False

    def _fire(self, gen):
        with self.lock:
            if gen != self.gen:
                return
            self.timer = None
            self.due = time.time()   # "soon" – until it is clear whether there is anything to do
        try:
            if RUNNER.running():
                # analysis, lyrics, Opus or Deezer pause briefly; a run that writes playlists itself is waited for
                try:
                    due = pending_count()
                except Exception:   # Navidrome briefly gone -> try again later
                    due = 0
                if due and RUNNER.pause_for(["playlists", "scan"], name=_s("Applied automatically")):
                    self.forced = False
                    return
                self.schedule(30)   # after the running task (state() reports “waiting” meanwhile)
                return
            try:
                if not pending_count():
                    self.forced = False
                    return
            except Exception:   # Navidrome briefly gone -> try again later
                self.schedule(60)
                return
            with self.lock:
                if gen != self.gen:
                    return   # cancelled meanwhile (e.g. "Apply now") or rescheduled
            try:
                RUNNER.start(["playlists", "scan"], name=_s("Applied automatically"))
                self.forced = False
            except RuntimeError:
                self.schedule(20)
        finally:
            with self.lock:
                if self.timer is None:
                    self.due = None

    def state(self):
        if not self.due:
            return {"due": None}
        if RUNNER.running() and not RUNNER.can_pause():   # waiting for a run that writes playlists itself
            return {"due": None, "waiting": True}
        return {"due": max(0, round(self.due - time.time()))}


AUTO = AutoApply()


def _kidsafe_after_index(new):
    """Indexing in the background (e.g. the very first one, or after a damaged index) found new rude songs: if
    someone has kid-safe mode on, write the playlists again soon – like the step in a run does."""
    if new and any(p.get("clean") for p in load_config()["personen"]):
        events.say(_sn(len(new), "Kid-safe mode: {n} new song with explicit lyrics found – adjusting the playlists.",
                       "Kid-safe mode: {n} new songs with explicit lyrics found – adjusting the playlists."))
        AUTO.schedule(force=True)


liedtext.on_indexed(_kidsafe_after_index)


def pending_count():
    st = api_playlists()
    return (sum(1 for p in st["playlists"] if p.get("state") in ("neu", "geändert", "scan", "entfernen"))   # i18n-ignore
            + len(st.get("orphans", [])))


_welten_sig = {"sig": None}


def _sync_welten():
    """Check for new music worlds – only when the library, the worlds or hidden items have changed since last time
    (warm_up runs after every save)."""
    lib = CACHE.get()
    cfg = load_config()
    sig = (id(lib), CACHE.loaded_at, json.dumps([[w.get("id"), w.get("scene"), w.get("autoScene"), sorted(w.get("artists", [])),
                                                 sorted(w.get("excludedArtists", []))] for w in cfg["welten"]]),
           json.dumps(sorted(x for x in cfg.get("dismissed", []) if x.startswith("scene|"))),
           json.dumps(cfg["settings"].get("welten") or {}, sort_keys=True))
    if sig == _welten_sig["sig"]:
        return
    autowelten.sync(lib, log=events.say)
    _welten_sig["sig"] = sig


def warm_up():
    """Prepare expensive calculations in the background so the pages are there right away."""
    def run():
        for fn in (lambda: CACHE.get(), _sync_welten, api_playlists, api_inbox, api_suggestions):
            try:
                fn()
            except Exception:
                pass
    threading.Thread(target=run, daemon=True).start()


_warm = {"timer": None}
_warm_lock = threading.Lock()


def schedule_warm(delay=2.5):
    with _warm_lock:   # several saves at once: only one timer
        if _warm["timer"]:
            _warm["timer"].cancel()
        _warm["timer"] = threading.Timer(delay, warm_up)
        _warm["timer"].daemon = True
        _warm["timer"].start()


# --------------------------------------------------------------------------- API

def api_status():
    from .version import VERSION
    out = {**_status_full(), "version": VERSION}
    m = auth.current()
    if m["role"] == "admin":
        return out
    # users only see what concerns them – no server details, admin names or paths
    own_users = {(p.get("user") or "").lower() for p in load_config()["personen"] if p["id"] in m["own"]}
    env = out.get("env", {})
    return {"navidrome": {k: v for k, v in (out.get("navidrome") or {}).items() if k in ("ok", "version", "scan")},
            "env": {"users": [u for u in env.get("users", []) if u["name"].lower() in own_users], "auth": env.get("auth"),
                    "webUrl": env.get("webUrl"), "lastfm": env.get("lastfm")},
            "steps": [], "allSteps": [], "daily": out.get("daily"), "instance": {"docker": out.get("instance", {}).get("docker"), "others": []},
            "version": out["version"]}


def api_changelog():
    """CHANGELOG.md as a list: [{"version", "date", "unreleased", "items": [text, …], "levels": [0|1, …]}], newest
    first. Headings "## <version>" (older ones "## <version> – <date>") and "## Unreleased" (changes of a build between
    releases). A nested bullet ("  - …") is an item of its own with level 1 (it belongs to the item above it)."""
    from .config import ROOT
    try:
        text = read_text(ROOT / "CHANGELOG.md")
    except OSError:
        return []
    out, cur = [], None
    for line in text.splitlines():
        head = re.match(r"^##\s+(\S+)(?:\s+[–-]\s+(.+?))?\s*$", line)
        if head:
            cur = {"version": head.group(1), "date": (head.group(2) or "").strip(),
                   "unreleased": head.group(1).lower() == "unreleased", "items": [], "levels": []}
            out.append(cur)
        elif cur and line.startswith("- "):
            cur["items"].append(line[2:].strip())
            cur["levels"].append(0)
        elif cur and re.match(r"^\s+- ", line) and cur["items"]:
            cur["items"].append(line.strip()[2:].strip())
            cur["levels"].append(1)
        elif cur and line.startswith("  ") and cur["items"]:
            cur["items"][-1] += " " + line.strip()   # continuation line
    return out


def _status_full():
    env = load_env()
    cfg = load_config()
    for u in rating_users(env, cfg):   # do the stored passwords still work? (background, at most every few hours)
        auth.check_password_soon(u, env)
    out = {
        "env": {
            "url": env.get("NAV_URL"), "webUrl": nav_web_url(env),
            "admin": env.get("NAV_ADMIN_USER"), "adminOk": bool(env.get("NAV_ADMIN_PASS")),
            # ok: a password is stored; rejected: Navidrome no longer accepts it (auth.password_rejected)
            "users": [{"name": u, "ok": ok, "key": pass_key(u), "rejected": ok and auth.password_rejected(u)}
                      for u, ok in users_ok(env, cfg).items()],
            "auth": localadmin.configured(env),
            "adminPassword": localadmin.source(env),   # env (docker-compose) · stored (set in the browser) · "" (none)
            "publicUrl": env.get("NAV_PUBLIC_URL") or "",
            "lastfm": bool(env.get("LASTFM_API_KEY")),
            "ntfyToken": bool(env.get("NTFY_TOKEN")),
            # values from docker-compose/the environment take precedence – the interface cannot change them
            # (only keys the interface could set otherwise)
            "locked": sorted(k for k in environment() if EDITABLE_ENV.match(k)),
        },
        "deezer": deezer.stats(),
        "steps": [{"id": s, "title": _(STEP_TITLES[s])} for s in pipeline(cfg)],   # i18n-ignore
        "allSteps": [{"id": s, "title": _(STEP_TITLES[s])} for s in PIPELINE],   # i18n-ignore
        "daily": _daily_state(),
        "watch": watch.state(),
        "paths": paths_info(cfg),
        "instance": {"docker": IN_DOCKER, "others": other_instances(foreign_only=True)},
    }
    try:
        nav = admin_client(env)
        ping = nav.ping()
        out["navidrome"] = {"ok": True, "version": ping.get("serverVersion"), "scan": nav.scan_status()}
    except NavidromeError as e:
        out["navidrome"] = {"ok": False, "error": str(e)}
    return out


def api_library(force=False):
    # reload only for administrators and at most once a minute – the interface asks after every run
    force = force and auth.current()["role"] == "admin" and time.time() - CACHE.loaded_at > 60
    lib = CACHE.get(force=force)

    def build():
        cfg = load_config()
        ctx = BuildContext(lib)
        index = rules.library_index(lib.songs)
        aid = lib.artist_ids()
        index["artists"] = [[a, n, aid.get(a)] for a, n in index["artists"]]
        index["similar"] = rules.similar_artists(cfg, lib.songs, ctx)
        for lst in index["similar"].values():
            for x in lst:
                x["id"] = aid.get(x["artist"])
        index["untagged"] = rules.untagged_artists(cfg, lib.songs)
        for x in index["untagged"]:
            x["id"] = aid.get(x["artist"])
        index["autoArtists"] = {w["id"]: rules.auto_artists(w, ctx) for w in cfg["welten"]}
        index["weltInfo"] = {w["id"]: welt_info(cfg, lib, ctx, w) for w in cfg["welten"]}
        idx = lib.artist_index()
        linked = {w.get("scene"): w["id"] for w in cfg["welten"] if w.get("scene")}
        index["scenes"] = []
        for s in scenes.catalog():
            present = scenes.members(s["id"], idx)
            index["scenes"].append({"id": s["id"], "name": s["name"], "icon": s["icon"],
                                    "description": s.get("description", ""), "present": present,
                                    "presentIds": [aid.get(a) for a in present], "linked": linked.get(s["id"])})
        index["ratingsExact"] = lib.ratings_exact
        index["ratingSource"] = CACHE.source
        index["deezer"] = deezer.stats(songs=lib.songs)
        return index
    return _memoized("library", build)


def welt_info(cfg, lib, ctx, w):
    members = rules.welt_artists(w, ctx)
    counts = artist_counts(lib)
    top = sorted(members, key=lambda a: -counts.get(a, 0))
    aid = lib.artist_ids()
    ids = lib.match(rules.build_nsp(cfg, {"welt": w["id"], "stil": ALL, "person": None}, ctx))
    return {"members": len(members), "songs": len(ids), "covers": lib.covers(ids),
            "artists": [[a, counts.get(a, 0), aid.get(a)] for a in top[:8]]}


def artist_counts(lib):
    if getattr(lib, "_artist_counts", None) is None:
        c = Counter()
        for s in lib.songs:
            names = {a["name"] for a in (s.get("artists") or []) + (s.get("albumArtists") or [])}
            c.update(names)
        lib._artist_counts = c
    return lib._artist_counts


def _my_favorites(cfg, lib):
    """Favorite bands of the signed-in person – administrators: those of the shared person and of their own account."""
    m = auth.current()
    user = (m.get("user") or "").lower()
    if m["role"] == "admin":
        mine = [p for p in cfg["personen"] if p["id"] == cfg["settings"].get("defaultPerson")
                or (user and (p.get("user") or "").lower() == user)]
    else:
        mine = [p for p in cfg["personen"] if p["id"] in m["own"]]
    ctx = BuildContext(lib)
    out = set()
    for p in mine:
        try:
            out |= set(rules.favorite_artists(cfg, p, ctx))
        except Exception:   # noqa: BLE001 – the start page must never fail because of this
            pass
    return out


def api_home():
    lib = CACHE.get()
    cfg = load_config()
    active = [p for p in cfg["playlists"] if p.get("status", "aktiv") == "aktiv"]
    favs = _my_favorites(cfg, lib)
    recent = (dt.date.today() - dt.timedelta(days=45)).isoformat()
    albums = [{**a, "fav": a.get("artist") in favs} for a in lib.new_albums(18)]
    # new releases of the favorite bands from the last weeks first
    albums.sort(key=lambda a: not (a["fav"] and a["created"][:10] >= recent))
    return {"newAlbums": albums, "favNew": sum(1 for a in albums if a["fav"] and a["created"][:10] >= recent),
            "songs": len(lib.songs), "albums": len(lib.albums()),
            "artists": len(lib.artist_ids(all=True)), "playlists": len(active), "personen": len(cfg["personen"])}


def api_playlists():
    lib = CACHE.get()

    def build():
        cfg = load_config()
        env = load_env()
        try:
            native = playlists.native_api(env)
        except NavidromeError:
            native = None
        out = playlists.status(cfg, BuildContext(lib), native)
        out["handmade"] = [{"file": h["file"], "name": h["name"]} for h in playlists.handmade(cfg)]
        out["webUrl"] = nav_web_url(env)
        return out
    out = _memoized("playlists", build, int(time.time() // 20))   # Navidrome state at most 20 s old
    m = auth.current()
    if m["role"] == "admin":
        return out
    cfg = load_config()
    by_id = {p["id"]: p for p in cfg["playlists"]}
    return {**out, "playlists": [x for x in out["playlists"] if x["id"] in by_id and auth.visible_playlist(by_id[x["id"]], cfg, m)],
            "handmade": [], "orphans": []}


# Summary lines (rules.summary) that reveal a person's likes and dislikes – hidden on someone else's playlist
PRIVATE_SUMMARY = (N_("Never included: {artists}"), N_("New from the favorite bands in the last {days} days: {bands}"),
                   N_("Prefers what {names} like to hear – everyone’s dislikes count"))


def _private_line(line):
    """Does this summary line come from PRIVATE_SUMMARY? Compares the text before the first value, in every language
    (the variant without favorite bands starts the same way)."""
    return any(line.startswith(i18n.tr(key, lang).split("{")[0]) for key in PRIVATE_SUMMARY for lang in i18n.LANGS)


def api_playlist(query):
    lib = CACHE.get()
    cfg = load_config()
    p = next((x for x in cfg["playlists"] if x["id"] == query.get("id")), None)
    if not p or not auth.visible_playlist(p, cfg):
        raise ValueError(_("Playlist not found"))
    res = rules.preview(cfg, lib, p, sample=25)
    res["own"] = auth.own_playlist(p)
    if not res["own"] and auth.current()["role"] != "admin":   # someone else's playlist: the person's dislikes stay private
        res.pop("nsp", None)
        res["summary"] = [x for x in res["summary"] if not _private_line(x)]
    st = next((x for x in api_playlists()["playlists"] if x["id"] == p["id"]), {})
    res.update({"state": st.get("state"), "navidrome": st.get("navidrome"), "webUrl": nav_web_url(load_env())})
    if p.get("type") == "mix" and (res["own"] or auth.current()["role"] == "admin"):   # someone else's listening stays private
        from . import feedback
        res["usage"] = feedback.usage({p["id"]}).get(p["id"])
    return res


def _preview_config(sent):
    """Configuration for preview/song counts. Administrators: as sent from the interface (changes not saved yet).
    Users: the server state – their own people from the interface, other people without likes and dislikes."""
    m = auth.current()
    if m["role"] == "admin":
        return sent or load_config()
    cfg = dict(load_config())
    sent_persons = sent.get("personen") if isinstance(sent, dict) and isinstance(sent.get("personen"), list) else []
    mine = {}
    for p in sent_persons:   # own people: only the fields they may save – id and account from the server
        if isinstance(p, dict) and p.get("id") in m["own"]:
            server = next((x for x in cfg["personen"] if x["id"] == p["id"]), None)
            if server:
                mine[p["id"]] = {**server, **{k: p[k] for k in auth.PERSON_FIELDS if k in p}}
    cfg["personen"] = [mine.get(p["id"], p) if p["id"] in m["own"]
                       else {k: v for k, v in p.items() if k not in ("likes", "dislikes", "push")} for p in cfg["personen"]]
    return cfg


def _guard_preview(body, cfg):
    """Preview for users: only for their own people, without fields only the server sets, family mix only with their
    own people and those visible to everyone, sizes limited – otherwise other people's listening could be queried."""
    m = auth.current()
    body["sampleSize"] = max(1, min(100, int(body.get("sampleSize", 15) or 15)))
    if isinstance(body.get("mix"), dict) and isinstance(body["mix"].get("size"), (int, float)):
        body["mix"]["size"] = max(5, min(500, int(body["mix"]["size"])))
    if m["role"] == "admin":
        return
    _own_person(auth.person_id(body, cfg))
    for k in auth.SERVER_PLAYLIST_FIELDS:
        body.pop(k, None)
    if isinstance(body.get("together"), list):
        allowed = set(m["own"]) | {p["id"] for p in cfg["personen"] if p.get("public")}
        body["together"] = [x for x in body["together"] if x in allowed]
        if len(body["together"]) < 2:
            body.pop("together")


def api_preview(body):
    lib = CACHE.get()
    cfg = _preview_config(body.pop("config", None))
    date = _date(body.pop("date", None))
    _guard_preview(body, cfg)
    return rules.preview(cfg, lib, body, sample=body.pop("sampleSize"), today=date)


def api_counts(body):
    """Song counts per vibe for a selection of worlds (for the wizard)."""
    lib = CACHE.get()
    cfg = _preview_config(body.get("config"))
    ctx = BuildContext(lib)
    base = {k: body[k] for k in ("welt", "person", "hits", "minRating") if k in body}
    if auth.current()["role"] != "admin":
        _own_person(auth.person_id(base, cfg))
    out = {}
    for s in [{"id": ALL}] + cfg["stile"]:
        p = {**base, "stil": s["id"]}
        if rules.welt_ids(p) == [] and s["id"] == ALL:
            out[ALL] = len(lib.songs)
            continue
        out[s["id"]] = rules.count(cfg, lib, p, ctx)
    return out


def api_welt(query):
    lib = CACHE.get()
    cfg = load_config()
    w = next((x for x in cfg["welten"] if x["id"] == query.get("id")), None)
    if not w:
        raise ValueError(_("Music world not found"))
    ctx = BuildContext(lib)
    counts = artist_counts(lib)
    aid = lib.artist_ids()
    auto = set(rules.auto_artists(w, ctx))
    members = [{"name": a, "id": aid.get(a), "songs": counts.get(a, 0), "auto": a in auto}
               for a in rules.welt_artists(w, ctx)]
    members.sort(key=lambda m: -m["songs"])
    similar = rules.similar_artists(cfg, lib.songs, ctx, limit=16).get(w["id"], [])
    for x in similar:
        x["id"] = aid.get(x["artist"])
    used = []
    for p in cfg["playlists"]:
        if w["id"] in rules.welt_ids(p) and p.get("status") != "papierkorb" and auth.visible_playlist(p, cfg):
            try:
                used.append({"id": p["id"], "name": rules.playlist_name(cfg, p), "status": p.get("status", "aktiv")})
            except playlists.BROKEN:   # a broken playlist must not break the page of the music world
                continue
    sc = scenes.scene(w.get("scene")) if w.get("scene") else None
    # personal: what the signed-in person listens to most from this world (from the taste profile)
    for_me = None
    me_user = auth.current()["user"]
    if me_user and me_user != auth.NOTFALL:
        try:
            prof = taste.profile(cfg, lib, me_user)
        except Exception:   # noqa: BLE001 – the page must never fail because of this
            prof = None
        if prof and prof.get("enough"):
            in_world = {m["name"] for m in members}
            for_me = {"bands": [{"name": a, "id": aid.get(a)} for a, _score in prof["artists"] if a in in_world][:8],
                      "share": dict(prof["welten"]).get(w["id"], 0)}
    return {**welt_info(cfg, lib, ctx, w), "memberList": members, "similar": similar, "playlists": used, "forMe": for_me,
            "excluded": [{"name": a, "id": aid.get(a)} for a in w.get("excludedArtists", [])],
            "scene": {"id": sc["id"], "name": sc["name"], "icon": sc["icon"], "description": sc.get("description")} if sc else None}


def api_artist(query):
    lib = CACHE.get()
    cfg = load_config()
    name = query.get("name", "")
    aid_any = lib.artist_ids(all=True).get(name)
    aid = lib.artist_ids().get(name)
    idx = [i for i, s in enumerate(lib.songs)
           if any(a["name"] == name for a in (s.get("artists") or []) + (s.get("albumArtists") or []))]
    if not idx:
        raise ValueError(_("“{name}” is not in the library", name=name))
    albums_all = lib.albums()
    alb = Counter(lib.songs[i].get("albumId") for i in idx)
    albums = sorted((dict(albums_all[a], mine=n) for a, n in alb.items() if a in albums_all),
                    key=lambda a: (a.get("year") or 0), reverse=True)
    genres = Counter(g["name"] for i in idx for g in lib.songs[i].get("genres") or [])
    ctx = BuildContext(lib)
    welten = []
    for w in cfg["welten"]:
        state = None
        if name in w.get("artists", []):
            state = "manuell"
        elif name in w.get("excludedArtists", []):
            state = "herausgenommen"
        elif name in rules.auto_artists(w, ctx):
            state = "automatisch"
        welten.append({"id": w["id"], "state": state})
    in_pl = []
    ids_set = set(idx)
    for p in cfg["playlists"]:
        if p.get("status", "aktiv") != "aktiv" or not auth.visible_playlist(p, cfg):
            continue
        try:   # a broken playlist (someone else's, too) must not break the band window
            n = len(ids_set & lib.match(rules.build_nsp(cfg, p, ctx)))
            if n:
                in_pl.append({"id": p["id"], "name": rules.playlist_name(cfg, p), "songs": n})
        except playlists.BROKEN:
            continue
    info = images.artist_info(aid_any) if aid_any else {}
    known, pics = lib.artist_ids(all=True), lib.artist_ids()
    intel = classify.artist_profile(name, lib)
    # similar bands: Last.fm (more precise), otherwise Navidrome's own list
    sim_names = [s for s, _score in intel["similar"]] or [s for s in info.get("similar", []) if s in known]
    similar = [{"name": s, "id": pics.get(s)} for s in sim_names][:12]
    plays = sum(lib.songs[i].get("playCount") or 0 for i in idx)
    top = sorted(idx, key=lambda i: (-(lib.songs[i].get("playCount") or 0), -(lib.songs[i].get("userRating") or 0),
                                     lib.songs[i].get("title") or ""))
    blocked = _child_filter(cfg)
    top = [i for i in top[:40] if not blocked(lib.songs[i])]   # kid-safe mode: without rude songs
    return {"name": name, "id": aid, "songs": len(idx), "albums": albums, "genres": genres.most_common(6),
            "top": rules._with_sound(lib, top[:5]),
            "welten": welten, "stile": [s["id"] for s in cfg["stile"] if name in s.get("artists", [])],
            "dislikedBy": [p["id"] for p in cfg["personen"] if name in p.get("dislikes", {}).get("artists", []) and p["id"] in auth.current()["persons"]],
            "likedBy": [p["id"] for p in cfg["personen"] if name in p.get("likes", {}).get("artists", []) and p["id"] in auth.current()["persons"]],
            "playlists": in_pl, "bio": info.get("bio", ""), "similar": similar, "plays": plays,
            "tags": intel["tags"], "missing": intel["missing"], "sound": intel["sound"], "lastfm": intel["lastfm"],
            "soundsLike": [{"name": a, "id": pics.get(a), "score": round(sc, 2)} for a, sc in intel["soundsLike"]],
            "scenes": [scenes.scene(s)["name"] for s in scenes.scenes_for_artist(name)],
            "rating": round(sum((lib.field_values("rating")[i] or 0) for i in idx) / len(idx), 1)}


# ---------------------------------------------------------------------------- rebuild a music world

WELT_RESET = {"artists": [], "excludedArtists": [], "albums": [], "genres": []}   # what the scene replaces


def api_welt_reset(query):
    """Preview for “Rebuild”: the bands come only from the scene, name and icon from the catalog – filters (excluded
    titles/albums, stars, minimum length, own world) stay. Changes nothing; the interface applies it with “Undo”.
    -> {name, icon, before, after, dropped, added, renamed[[old, new]]}"""
    lib = CACHE.get()
    cfg = load_config()
    w = next((x for x in cfg["welten"] if x["id"] == query.get("id")), None)
    sc = scenes.scene(w.get("scene")) if w and w.get("scene") else None
    if not sc:
        raise ValueError(_("This music world is not linked to a scene – it cannot be rebuilt."))
    ctx = BuildContext(lib)
    fresh = {**w, **copy.deepcopy(WELT_RESET), "name": sc["name"], "icon": sc["icon"], "autoScene": True}
    before, after = set(rules.welt_artists(w, ctx)), set(rules.welt_artists(fresh, ctx))
    cfg2 = {**cfg, "welten": [fresh if x["id"] == w["id"] else x for x in cfg["welten"]]}
    renamed = []
    for p in cfg["playlists"]:
        if p.get("status", "aktiv") != "papierkorb" and not p.get("name") and w["id"] in rules.welt_ids(p):
            old, new = rules.playlist_name(cfg, p), rules.playlist_name(cfg2, p)
            if old != new:
                renamed.append([old, new])
    return {"name": sc["name"], "icon": sc["icon"], "before": len(before), "after": len(after),
            "dropped": sorted(before - after, key=str.lower), "added": sorted(after - before, key=str.lower),
            "renamed": renamed}


# ---------------------------------------------------------------------------- songs: listening in, song window

SONG_ID = re.compile(r"[A-Za-z0-9_-]{1,64}")


def _song(lib, sid):
    i = lib.index_of().get(sid) if SONG_ID.fullmatch(sid or "") else None
    if i is None:
        raise ValueError(_("This song no longer exists."))
    return i


def _child_filter(cfg):
    """Kid-safe mode: if one of the account's own people has it on, rude songs are neither playable nor shown in the
    song window. -> function song -> blocked? – worked out once per request (lists check thousands of songs)."""
    m = auth.current()
    if m["role"] == "admin" or not any(p.get("clean") for p in cfg["personen"] if p["id"] in m["own"]):
        return lambda song: False
    allow = set((cfg["settings"].get("kinderschutz") or {}).get("allow", []))
    rude = liedtext.derb(allow)
    return lambda song: song["id"] in rude or (song.get("explicitStatus") in ("explicit", "e") and song["id"] not in allow)


def _child_blocked(cfg, song):
    return _child_filter(cfg)(song)


def api_song(query):
    """Song window: info, sound, lyrics and in which (visible, active) playlists the song appears."""
    lib = CACHE.get()
    cfg = load_config()
    i = _song(lib, query.get("id", ""))
    s = lib.songs[i]
    if _child_blocked(cfg, s):
        raise PermissionError(_("This song is hidden by kid-safe mode."))
    row = rules._with_sound(lib, [i])[0]
    ctx = BuildContext(lib)
    saved = mixer._load_state()
    in_pl = []
    for p in cfg["playlists"]:
        if p.get("status", "aktiv") != "aktiv" or not auth.visible_playlist(p, cfg):
            continue
        try:
            if rules.resting(cfg, p):
                continue
            if rules.is_mix(p):   # mix: the selection just written
                hit = s["id"] in ((saved.get(p["id"]) or {}).get("ids") or ())
            else:
                hit = i in lib.match(rules.build_nsp(cfg, p, ctx))
            if hit:
                in_pl.append({"id": p["id"], "name": rules.playlist_name(cfg, p), "mix": rules.is_mix(p)})
        except playlists.BROKEN:
            continue
    text = liedtext.text_of(s["id"])
    synced, plain = _structured_lyrics(s["id"])
    return {**row, **classify.song_details(lib, i), "track": s.get("track"), "suffix": s.get("suffix"), "albumId": s.get("albumId"),
            "lyrics": text or plain, "synced": synced, "playlists": in_pl}


def _structured_lyrics(song_id):
    """Lyrics from Navidrome (getLyricsBySongId: .lrc next to the file or embedded) -> (synced lines [[ms, text], …]
    or None, text without times or None). Older Navidrome versions do not know this: (None, None)."""
    try:
        data = admin_client(load_env()).call("getLyricsBySongId", timeout=15, id=song_id)
    except (NavidromeError, KeyError, ValueError):
        return None, None
    lists = (data.get("lyricsList") or {}).get("structuredLyrics") or []
    synced = next((x for x in lists if x.get("synced") and x.get("line")), None)
    lines = [[int(x.get("start") or 0), (x.get("value") or "").strip()] for x in (synced or {}).get("line") or []]
    any_text = next((x for x in lists if x.get("line")), None)
    plain = "\n".join((x.get("value") or "").strip() for x in (any_text or {}).get("line") or []) or None
    return (lines if len(lines) >= 3 else None), plain


def api_song_more(query):
    """“More like this”: up to 20 songs that sound like this one – by the band and similar bands from the collection,
    with the dislikes and kid-safe mode of one's own person. Only for listening in, no playlist is created."""
    import random
    lib = CACHE.get()
    cfg = load_config()
    i = _song(lib, query.get("id", ""))
    if _child_blocked(cfg, lib.songs[i]):
        raise PermissionError(_("This song is hidden by kid-safe mode."))
    artist = lib._main_artist(lib.songs[i])
    temp = {"id": "_mehr", "person": _default_person(cfg), "welt": "*", "stil": "*", "type": "mix",
            "radio": {"seed": [artist]}, "minRating": 0, "mix": {"size": 20, "perArtist": 2, "every": "day"}}
    pool = set(lib.match(rules.build_nsp(cfg, temp, BuildContext(lib)))) - {i}
    rnd = random.Random()
    per, out = Counter(), []
    for j in classify.rank_like(lib, i, pool, rnd):   # by sound (AI sound vectors), arousal, mood, tempo
        a = lib._main_artist(lib.songs[j])
        if per[a] >= (3 if a == artist else 2):
            continue
        per[a] += 1
        out.append(j)
        if len(out) >= 20:
            break
    rnd.shuffle(out)
    return {"artist": artist, "songs": rules._with_sound(lib, out)}


def api_suggestions(query=None):
    lib = CACHE.get()
    m = auth.current()
    if query and query.get("person"):
        _own_person(query["person"])
        cfg = load_config()
        if m["role"] != "admin":   # their own hidden suggestions instead of the admin's
            cfg = {**cfg, "dismissed": ((cfg.get("accounts") or {}).get((m["user"] or "").lower()) or {}).get("dismissed", [])}
        return _memoized("suggestions-person", lambda: suggest.suggestions(
            cfg, lib, handmade_list=playlists.handmade(cfg), only_person=query["person"], per_person=12),
            query["person"], tuple(cfg.get("dismissed", [])))

    def build():
        cfg = load_config()
        return suggest.suggestions(cfg, lib, handmade_list=playlists.handmade(cfg))
    items = _memoized("suggestions", build)
    if m["role"] == "admin":
        return items
    own = set(m["own"])   # users: only suggestions for their own people (no creating new music worlds)
    hidden = set(((load_config().get("accounts") or {}).get((m["user"] or "").lower()) or {}).get("dismissed", []))
    return [x for x in items if x.get("kind") != "scene" and x.get("person") in own and x["key"] not in hidden]


def api_taste(query):
    """“From your listening”: what Tuttiphon has learned from plays, favorites and one's own stars – for a person
    (?person=) or one's own account (?me=1, e.g. in the welcome wizard before there is a profile)."""
    cfg = load_config()
    if query.get("me"):
        user = auth.current()["user"]
        if not user or user == auth.NOTFALL:
            return {"available": False, "hasAccount": False}
    else:
        pid = query.get("person") or ""
        _own_person(pid)
        person = next((p for p in cfg["personen"] if p["id"] == pid), None)
        if not person:
            raise ValueError(_("Person not found"))
        user = person.get("user")
    lib = CACHE.get()
    prof = taste.profile(cfg, lib, user) if user else None
    return {**taste.summary(cfg, prof, lib), "hasAccount": bool(user)}


def api_search(query):
    """Search beyond what the interface knows itself: songs by title, music styles of the AI (with bands) and moods
    (with the matching sound vibe). The interface searches bands, playlists and music worlds itself."""
    q = (query.get("q") or "").strip().lower()
    if len(q) < 2:
        return {"songs": [], "styles": [], "moods": [], "instruments": [], "themes": [], "combos": [], "lyrics": []}
    lib = CACHE.get()
    cfg = load_config()
    # kid-safe mode: like in the song window – rude lyrics and songs tagged as explicit stay out (_child_blocked)
    blocked = _child_filter(cfg)
    songs = [s for s in lib.songs if q in (s.get("title") or "").lower() and not blocked(s)]
    songs.sort(key=lambda s: (not (s.get("title") or "").lower().startswith(q), -(s.get("playCount") or 0)))
    aid = lib.artist_ids()
    out_songs = [{"id": s["id"], "title": s.get("title"), "artist": lib._main_artist(s), "album": s.get("album"),
                  "albumId": s.get("albumId"), "artistId": aid.get(lib._main_artist(s))} for s in songs[:8]]
    # music styles of the AI: bands in which the style is strong
    by_style = {}
    for artist, styles in ml.artist_styles(lib).items():
        for k, x in styles.items():
            if x >= 0.4 and q in k:
                by_style.setdefault(ml.style_label(k), []).append((x, artist))
    out_styles = [{"style": k, "bands": [{"name": a, "id": aid.get(a)} for _weight, a in sorted(v, reverse=True)[:8]]}
                  for k, v in sorted(by_style.items(), key=lambda kv: -len(kv[1]))[:4]]
    # moods: label or id matches -> number of songs and the matching sound vibe
    feats = classify.song_features(lib)
    out_moods = []
    for mid, english in audio.MOODS.items():   # matches the label in the page's language, in English and the id
        label = _(english)   # i18n-ignore – fixed mood labels from audio.MOODS
        if q in label.lower() or q in english.lower() or q in mid:
            n = sum(1 for f in feats.values() if mid in audio.moods(f))
            stil = next((x for x in cfg["stile"] if (x.get("sound") or {}).get("moods") == [mid]), None)
            out_moods.append({"id": mid, "label": label, "count": n, "stil": stil and stil["id"],
                              "stilName": stil and stil["name"]})
    # listening vibes (AI: approachable, engaging): „Hintergrundmusik“, „easy listening“, „zum Zuhören“ or their name ->
    # the delivered sound vibe with the number of matching songs – as long as it exists (deleted = not wanted)
    for st in _listen_vibes(q, cfg):
        n = sum(1 for f in feats.values() if audio.matches(f, st["sound"]))
        out_moods.append({"id": st["id"], "label": st["name"], "count": n, "stil": st["id"], "stilName": st["name"]})
    # lyrics: “the song with …” – the first time, the index is built in the background
    out_lyrics = []
    if liedtext.ready():
        index, seen = lib.index_of(), set()
        for hit in liedtext.search(q, 8):
            i = index.get(hit["song"])
            if i is None:
                continue
            s = lib.songs[i]
            a = lib._main_artist(s)
            if (a, (s.get("title") or "").lower()) in seen or len(out_lyrics) >= 5 or blocked(s):   # duplicate / kid-safe mode
                continue
            seen.add((a, (s.get("title") or "").lower()))
            out_lyrics.append({"id": s["id"], "title": s.get("title"), "artist": a, "album": s.get("album"),
                               "albumId": s.get("albumId"), "artistId": aid.get(a), "line": hit["line"]})
    elif not liedtext.status()["running"]:
        liedtext.update_soon(lib)
    return {"songs": out_songs, "styles": out_styles, "moods": out_moods, "instruments": ml.search_instruments(q, lib),
            "themes": _search_themes(q, cfg, lib), "combos": _search_combos(q, cfg, lib), "lyrics": out_lyrics}


# Words for moods in the search (the start of a word is enough): „ruhige“, „tanzbare“, „fröhlicher“ … – German search
# words matched against the input, i.e. data.
# i18n-ignore-start
MOOD_WORDS = {"ruhig": "ruhig", "sanft": "ruhig", "chill": "ruhig", "entspann": "ruhig", "relax": "ruhig",
              "schlaf": "schlaf", "einschlaf": "schlaf", "fröhlich": "froh", "froh": "froh", "lustig": "froh",
              "happy": "froh", "gutelaune": "froh", "tanz": "tanzbar", "party": "tanzbar", "energ": "energie",
              "power": "energie", "wild": "energie", "toben": "energie", "laut": "energie", "traurig": "melancholisch",
              "nachdenk": "melancholisch", "melanchol": "melancholisch", "akustisch": "akustisch", "unplugged": "akustisch",
              "instrumental": "instrumental",
              # English search words
              "calm": "ruhig", "quiet": "ruhig", "gentle": "ruhig", "soft": "ruhig", "sleep": "schlaf", "asleep": "schlaf",
              "bedtime": "schlaf", "lullab": "schlaf", "cheer": "froh", "joy": "froh", "goodmood": "froh", "danc": "tanzbar",
              "sad": "melancholisch", "thought": "melancholisch", "acoustic": "akustisch"}
# Words for the listening vibes (the start of a word is enough) -> id of the delivered sound vibe whose filter on the AI
# values approachable/engaging fits: „Hintergrundmusik“, „nebenbei“, „easy listening“, „zum Zuhören“, „hinhören“
LISTEN_WORDS = {"hintergrund": "klang-hintergrund", "nebenbei": "klang-hintergrund", "berieselung": "klang-hintergrund",
                "background": "klang-hintergrund", "easylistening": "klang-hintergrund",
                "zuhör": "klang-zuhoeren", "zuhoer": "klang-zuhoeren", "hinhör": "klang-zuhoeren", "hinhoer": "klang-zuhoeren",
                "closelistening": "klang-zuhoeren", "attentivelistening": "klang-zuhoeren"}
# two-word terms that become one word before the input is split (also takes the „zum“ along)
LISTEN_PHRASES = {"zum zuhören": "zuhören", "zum zuhoeren": "zuhören", "im hintergrund": "hintergrund",
                  "background music": "background", "easy listening": "easylistening", "close listening": "closelistening",
                  "listening closely": "closelistening", "listen closely": "closelistening",
                  "attentive listening": "attentivelistening"}
# i18n-ignore-end


def _listen_word(w):
    """Search word -> id of a listening vibe or None („Hintergrundmusik“ -> klang-hintergrund); a started word counts
    from 6 letters („hinter“)."""
    return next((v for k, v in LISTEN_WORDS.items() if w.startswith(k) or (len(w) >= 6 and k.startswith(w))), None)


def _listen_vibes(q, cfg):
    """Listening vibes a search names – by a search word or by their name (from 4 letters); only vibes that still
    exist and have a sound filter."""
    text = q
    for phrase, word in LISTEN_PHRASES.items():
        text = text.replace(phrase, word)
    ids = {_listen_word(w) for w in re.split(r"[^a-zäöüß0-9]+", text) if w}   # i18n-ignore: German letters in the search input
    return [x for x in cfg["stile"] if x.get("sound") and x["id"] in LISTEN_WORDS.values()
            and (x["id"] in ids or (len(q) >= 4 and q in x["name"].lower()))]


def _words(text):
    return [x for x in re.split(r"[^a-zäöüß0-9]+", text) if x]   # i18n-ignore: German letters in the search input


def _name_hits(name, pool):
    """Words of pool that fit a word (from 3 letters) of name: equal – or, both from 5 letters, the same first 5
    letters („kinder“ ~ „Kinderlieder“)."""
    parts = [x for x in _words(name.lower()) if len(x) >= 3]
    return [w for w in pool for part in parts if (w[:5] == part[:5] if len(w) >= 5 and len(part) >= 5 else w == part)]


def _theme_vibe(cfg, theme, words):
    """The vibe that stands for a theme of the AI in the search – or None: the delivered vibe linked to it
    (ml.THEME_VIBES, „Weihnachten“ -> Christmas) or a vibe whose name fits a search word of the theme („Sommer“). Its
    keywords find the songs much more precisely than the AI; sound vibes and “Right for the season” do not count."""
    own = [w for w in words if theme in (ml.theme_word(w) or ())]
    return next((x for x in cfg["stile"] if not x.get("sound") and x.get("kind") != "season"
                 and (x["id"] == ml.THEME_VIBES.get(theme) or _name_hits(x["name"], own))), None)


def _search_themes(q, cfg, lib):
    """Themes of the AI for the search ({id, label, ids, count}, ml.search_themes()). A music world whose name contains
    the input wins – the interface lists it, the theme is left out („Kinder“, „Film“); a vibe that stands for the theme
    (_theme_vibe()) comes along as stil/stilName with the number of its songs: the interface then offers the vibe."""
    if any(q in w["name"].lower() for w in cfg["welten"]):
        return []
    text = q
    for phrase, word in ml.THEME_PHRASES.items():
        text = text.replace(phrase, word)
    words = _words(text)
    out = []
    for x in ml.search_themes(q, lib):
        st = _theme_vibe(cfg, x["id"], words + [text.replace(" ", "")])
        if st:
            m = auth.current()
            person = m["own"][0] if m["role"] != "admin" and m["own"] else cfg["settings"].get("defaultPerson")
            p = {"person": person, "welt": ALL, "stil": st["id"], "type": "mix", "mix": {"size": 40, "perArtist": 3, "every": "week"}}
            try:
                x = {**x, "stil": st["id"], "stilName": st["name"], "count": rules.count(cfg, lib, p, BuildContext(lib))}
            except (ValueError, KeyError):
                pass
        out.append(x)
    return out


def _search_combos(q, cfg, lib):
    """Combined search: „ruhige Kinderlieder“, „fröhlicher Mittelalter-Mix“, „tanzbare 90er“, „ruhige Klaviermusik“ –
    recognizes music world, mood, vibe, instrument and theme (AI) in the input and suggests a matching mix (with song
    count). Only when at least two of them are recognized; the search finds single worlds and moods anyway. A listening
    word („Hintergrundmusik“, „zum Zuhören“) stands for its delivered sound vibe – unless a vibe is named as well. A
    world or vibe of the same name takes a word before the AI („Kinder“, „Weihnachten“), and so does the vibe linked
    to a theme (ml.THEME_VIBES)."""
    phrases = {"gute laune": "gutelaune", "good mood": "goodmood", "ohne gesang": "instrumental",   # i18n-ignore
               "without vocals": "instrumental", "no vocals": "instrumental", **ml.INSTRUMENT_PHRASES,
               **ml.THEME_PHRASES, **LISTEN_PHRASES}
    text = q
    for phrase, word in phrases.items():   # two-word moods become one word before splitting
        text = text.replace(phrase, word)
    words = _words(text)

    # every word counts only once: first mood, then music world, then vibe („ruhige“ is a mood, not „Ruhig & Chill“)
    moods, listen, rest = [], [], []
    for w in words:
        m = next((v for k, v in MOOD_WORDS.items() if w.startswith(k) or (len(w) >= 5 and k.startswith(w))), None)
        heard = None if m else _listen_word(w)
        if m:
            if m not in moods:
                moods.append(m)
        elif heard:
            if heard not in listen:
                listen.append(heard)
        else:
            rest.append(w)

    hits = _name_hits
    welten, used = [], set()
    for w in cfg["welten"]:
        h = hits(w["name"], rest) or hits(w["id"], rest)
        if h:
            welten.append(w)
            used |= set(h)
    stile = [x for x in cfg["stile"] if not x.get("sound") and x.get("kind") != "season"
             and hits(x["name"], [w for w in rest if w not in used])]
    used |= {h for x in stile for h in hits(x["name"], rest)}
    if not stile:   # listening vibe (AI: approachable, engaging) – only while it exists (deleted = not wanted)
        stile = [x for x in cfg["stile"] if x["id"] in listen and x.get("sound")][:1]
    # instruments (AI): from the words no world or vibe has taken – „Klaviermusik“, „ruhige Gitarre“
    word = next((w for w in rest if w not in used and ml.instrument_word(w)), None)
    instruments = ml.instrument_word(word) if word else None
    # themes (AI): likewise – „epische Filmmusik“, „düstere Mittelalter“; the first one counts
    themes = next((ids for ids in (ml.theme_word(w) for w in rest if w not in used and w != word) if ids), None)
    for t in themes or ():   # a vibe linked to the theme (Christmas) takes its place
        st = next((x for x in cfg["stile"] if x["id"] == ml.THEME_VIBES.get(t) and not x.get("sound")), None)
        if st:
            stile = stile if st in stile else [*stile, st]
            themes = [y for y in themes if y != t] or None
    if sum(1 for x in (welten, moods, stile, instruments, themes) if x) < 2:
        return []
    m = auth.current()
    person = (m["own"][0] if m["role"] != "admin" and m["own"] else cfg["settings"].get("defaultPerson"))
    ctx = BuildContext(lib)
    out = []
    for w in welten[:2] or [None]:
        for st in (stile[:2] or [None]) + ([None] if stile and w and (moods or instruments or themes) else []):   # if need be without a vibe
            p = {"person": person, "welt": w["id"] if w else ALL, "stil": st["id"] if st else ALL, "type": "mix",
                 "mix": {"size": 40, "perArtist": 3, "every": "week"}}
            if moods or instruments or themes:   # the playlist's own filter replaces the vibe's: a sound vibe's ranges come along
                p["sound"] = dict((st or {}).get("sound") or {})
            if moods:
                p["sound"]["moods"] = moods[:1]
            if instruments:
                p["sound"]["instruments"] = instruments
            if themes:
                p["sound"]["themes"] = themes
            try:
                n = rules.count(cfg, lib, p, ctx)
            except (ValueError, KeyError):
                continue
            if n < 15:
                continue
            title = " · ".join([x for x in (w and w["name"], st and st["name"], moods and _(audio.MOODS[moods[0]]),   # i18n-ignore
                                            instruments and _(ml.INSTRUMENTS[instruments[0]]),   # i18n-ignore
                                            themes and _(ml.THEMES[themes[0]])) if x])   # i18n-ignore
            if all(o["title"] != title for o in out):
                out.append({"title": title, "playlist": p, "count": n})
        if out and stile:
            break
    return out[:3]


def api_inbox():
    lib = CACHE.get()
    if auth.current()["role"] != "admin":
        return user_inbox(auth.current())

    def build():
        env = load_env()
        cfg = load_config()
        return suggest.inbox(cfg, lib, env, deezer.stats(songs=lib.songs), playlists.handmade(cfg), users_ok(env, cfg))
    items = list(_memoized("inbox", build))
    others = other_instances(foreign_only=True)
    if others:
        where = ", ".join(_("“{host}” (Docker on the NAS)", host=o["host"]) if o["docker"] else _("“{host}”", host=o["host"])
                          for o in others)
        if any(o["docker"] for o in others):
            text = _("Tuttiphon is also running on {where} right now. Please use only one instance for editing – "
                     "otherwise changes can overwrite each other. The container takes care of the daily refresh.", where=where)
        else:
            text = _("Tuttiphon is also running on {where} right now. Please use only one instance for editing – "
                     "otherwise changes can overwrite each other.", where=where)
        items.insert(0, {"key": "instance", "level": "warn", "title": _("Tuttiphon is running twice"), "text": text,
                         "actions": []})
    return items


def api_matrix(query):
    lib = CACHE.get()
    date = _date(query.get("date"))
    return _memoized("matrix", lambda: rules.matrix(load_config(), lib, date), query.get("date"))


def api_takeover_preview(body):
    return playlists.takeover_preview(load_config(), body["file"], CACHE.get())


def api_takeover(body):
    out = {}
    update_config(lambda cfg: out.update(p=playlists.takeover(cfg, body["file"], body.get("mode", "unveraendert"))))
    AUTO.schedule()
    return {"ok": True, "playlist": out["p"]}


def api_mapping(body):
    cfg = load_config()
    lib = CACHE.get()
    mapping = playlists.guess_mapping(cfg, {"all": body.get("rules", []), "name": body.get("name", "")})
    if not mapping:
        return {"mapping": None}
    p = {"person": body.get("person"), **mapping}
    return {"mapping": {**mapping, "count": rules.count(cfg, lib, p, BuildContext(lib)), "describe": rules.describe(cfg, p)}}


def api_snapshot(body):
    _own_playlist_id(body.get("id"))
    return playlists.snapshot(load_config(), load_env(), BuildContext(CACHE.get()), body["id"])


def _default_person(cfg):
    m = auth.current()
    if m["role"] != "admin" and m["own"]:
        return m["own"][0]
    return cfg["settings"].get("defaultPerson")


def _own_person(pid):
    m = auth.current()
    if m["role"] != "admin" and pid not in m["own"]:
        raise PermissionError(_("This belongs to another account."))


def _own_playlist_id(pid):
    p = _find_playlist(pid)
    if not auth.own_playlist(p):
        raise PermissionError(_("This playlist belongs to another account."))
    return p


def user_inbox(m):
    """"To review" for users: only what they can take care of themselves."""
    cfg = load_config()
    items = []
    own = [p for p in cfg["personen"] if p["id"] in m["own"]]
    if not own:
        items.append({"key": "profil", "level": "warn", "title": _("Set up your profile"),
                      "text": _("A few questions about your taste in music – then there are matching playlists just for you."),
                      "actions": [{"label": _("Let’s go"), "do": "goto", "href": "#/willkommen"}]})
    def heard(p):   # does Tuttiphon already know the taste from listening? Then no likes by hand are needed
        try:
            prof = taste.profile(cfg, CACHE.get(), p.get("user")) if p.get("user") else None
        except Exception:   # noqa: BLE001 – without a password, or Navidrome briefly gone
            prof = None
        return bool(prof and prof.get("enough"))
    for p in own:
        likes = p.get("likes") or {}
        if not likes.get("welten") and not likes.get("artists") and not heard(p):
            fresh = not any(pl.get("person") == p["id"] for pl in cfg["playlists"])
            items.append({"key": f"likes|{p['id']}", "level": "info",
                          "title": _("What do you like to listen to?") if len(own) == 1
                          else _("What does “{name}” like to listen to?", name=p["name"]),
                          "text": _("Choose favorite worlds and bands – that makes the suggestions much better."),
                          "actions": [{"label": _("Choose your taste"), "do": "goto", "href": "#/willkommen" if fresh and len(own) == 1 else f"#/person/{p['id']}"}]})
    if own and not any(pl.get("person") in m["own"] and pl.get("status", "aktiv") == "aktiv" for pl in cfg["playlists"]):
        items.append({"key": "erste-playlist", "level": "info", "title": _("Your first playlist"),
                      "text": _("Under “Discover” there are ready-made suggestions for you – one click creates them."),
                      "actions": [{"label": _("View suggestions"), "do": "goto", "href": "#/entdecken"}]})
    if not m.get("passwordStored") and not m.get("notfall"):
        items.append({"key": "passwort", "level": "info", "title": _("Turn on statistics & stars"),
                      "text": _("For your personal statistics and your own stars, Tuttiphon needs your Navidrome password. "
                                "It stays on your NAS."),
                      "actions": [{"label": _("Turn on"), "do": "goto", "href": "#/einstellungen/konto"}]})
    try:   # tidying up: own playlists nobody listens to or that exist twice
        for key, level, title, text, actions in suggest.playlist_tidy_items(cfg, CACHE.get(), set(m["own"]), user=True):
            items.append({"key": key, "level": level, "title": title, "text": text, "actions": actions})
    except Exception:   # noqa: BLE001 – “To review” must never fail because of this
        pass
    ignored = set(m.get("ignored") or (cfg.get("accounts") or {}).get((m["user"] or "").lower(), {}).get("ignored", []))
    return [x for x in items if x["key"] not in ignored]


def api_me_password(body):
    """Remember (or forget) one's own Navidrome password for statistics & stars."""
    m = auth.current()
    if not m["user"] or m.get("notfall"):
        raise ValueError(_("Only possible with a Navidrome account."))
    pw = body.get("password")
    env = load_env()
    if pw is None:
        if env.get(pass_key(m["user"])):   # only when something changes – otherwise the library stays in memory
            save_env({pass_key(m["user"]): None})
            auth.note_password(m["user"], None)
            CACHE.invalidate()
        return {"ok": True}
    if not isinstance(pw, str) or not pw:
        raise ValueError(_("Please enter the password."))
    try:
        Navidrome(env["NAV_URL"], m["user"], pw).ping()
    except NavidromeError:
        raise ValueError(_("The password is wrong."))
    if env.get(pass_key(m["user"])) != pw:
        save_env({pass_key(m["user"]): pw})
        CACHE.invalidate()
    auth.note_password(m["user"], True)
    return {"ok": True}


def api_accounts():
    """Navidrome accounts with role, people and last sign-in (for users & permissions)."""
    cfg = load_config()
    out = []
    for u in auth.navidrome_users(force=True):
        acc = (cfg.get("accounts") or {}).get(u["name"].lower(), {})
        out.append({"name": u["name"], "fullName": u["fullName"], "navidromeAdmin": u["admin"], "role": auth.role_of(u["name"], cfg),
                    "override": acc.get("role"), "lastLogin": acc.get("lastLogin"),
                    "persons": auth.persons_of(u["name"], cfg),
                    "passwordStored": bool(user_password(load_env(), u["name"])),
                    "passwordRejected": bool(user_password(load_env(), u["name"])) and auth.password_rejected(u["name"])})
    return out


def api_accounts_save(body):
    user, role = body.get("user"), body.get("role")
    if role not in (None, "admin", "user", "none"):
        raise ValueError(_("Unknown role"))
    m = auth.current()
    if m["user"] and (user or "").lower() == m["user"].lower():
        nav_admin = any(u["name"].lower() == user.lower() and u["admin"] for u in auth.navidrome_users())
        if role in ("user", "none") or (role is None and not nav_admin):   # also: override removed, without Navidrome admin
            raise ValueError(_("You cannot give up your own administrator role – sign in with another admin account for that."))

    def apply(cfg):
        acc = cfg.setdefault("accounts", {}).setdefault((user or "").lower(), {})
        if role is None:
            acc.pop("role", None)
        else:
            acc["role"] = role
    update_config(apply)
    if role == "none":   # no access any more: also end existing sessions (e.g. on a lost phone)
        auth.end_sessions_of(user)
    return {"ok": True}


def api_login_info(setup=False):
    """For the sign-in page, without signing in. setup: no administrator password yet – the page asks for the setup
    code and a new password. navidrome: can people sign in with their Navidrome account yet? Only once the address and
    the admin access are there – before that only the local administrator gets in (and the setup assistant connects
    Navidrome)."""
    env = load_env()
    return {"setup": bool(setup),
            "navidrome": bool(env.get("NAV_URL") and env.get("NAV_ADMIN_USER") and env.get("NAV_ADMIN_PASS"))}


def api_users():
    try:
        native = playlists.native_api(load_env())
        return [{"name": u["userName"], "admin": u.get("isAdmin", False), "fullName": u.get("name")} for u in native.users()]
    except NavidromeError as e:
        raise RuntimeError(str(e))


def api_env_save(body):
    for key in ("NAV_URL", "NAV_PUBLIC_URL"):   # becomes a link in the interface: only http(s), never javascript: …
        if key in body and body[key] not in (None, "") and not re.match(r"^https?://[^\s/]+", str(body[key]), re.I):
            raise ValueError(_("Please enter the address with http:// or https://, e.g. http://192.168.1.10:4533"))
    save_env(dict(body))
    for u in rating_users(load_env()):   # a password entered anew counts as not tried yet
        if body.get(pass_key(u)):
            auth.note_password(u, None)
    CACHE.invalidate()
    schedule_warm()
    return {"ok": True}


def api_env_test(body):
    """Test access – optionally with a new server address before it is saved."""
    env = load_env()
    saved_url = (env.get("NAV_URL") or "").strip().rstrip("/")
    url = (body.get("url") or saved_url).strip().rstrip("/")
    if not re.match(r"^https?://[^\s/]+", url):
        return {"ok": False, "error": _("Please enter the address with http:// or https://, e.g. http://192.168.1.10:4533")}
    user = body.get("user") or env.get("NAV_ADMIN_USER")
    if not body.get("password") and url != saved_url:   # send stored passwords only to the saved address
        return {"ok": False, "error": _("For a new address, please enter the password as well.")}
    pw = body.get("password") or user_password(env, user)
    if not pw:
        return {"ok": False, "error": _("No password stored")}
    try:
        ping = Navidrome(url, user, pw).ping()
        return {"ok": True, "version": ping.get("serverVersion")}
    except NavidromeError as e:
        return {"ok": False, "error": str(e)}


def api_paths_check(body):
    """Check proposed storage locations (before saving): present, writable, playlists inside the music folder?"""
    import copy as _copy
    cfg = _copy.deepcopy(load_config())
    cfg["settings"]["paths"] = {k: (str(body.get(k) or "").strip()) for k in ("music", "playlists", "archive")}
    info = paths_info(cfg)
    music = Path(info["music"]["path"]).resolve()
    pl = Path(info["playlists"]["path"]).resolve()
    info["playlists"]["insideMusic"] = pl == music or music in pl.parents
    arch = Path(info["archive"]["path"]).resolve()
    info["archive"]["insideMusic"] = arch == music or music in arch.parents
    if info["archive"]["insideMusic"]:   # archived originals would be converted again
        raise ValueError(_("The archive folder must not be the music folder or inside it – the originals there would "
                           "be converted again."))
    return info


def api_intel():
    """For Settings → Intelligence: state of Last.fm, sound analysis and classification."""
    lib = CACHE.get()
    cfg = load_config()

    def build():
        names = {w["id"]: w["name"] for w in cfg["welten"]}
        sugg = classify.suggestions(cfg, lib)
        feats = classify.song_features(lib)   # own measurement + AI + Last.fm – so the AI moods count too
        return {"lastfm": lastfm.stats(), "audio": {**audio.stats(feats.values()), "total": len(lib.songs)},
                "ml": ml.stats(), "classify": [{**x, "weltName": names.get(x["welt"])} for x in sugg[:30]],
                "stile": classify.stil_suggestions(cfg, lib)[:20],
                "moods": {k: _(v) for k, v in audio.MOODS.items()}}   # i18n-ignore – fixed mood labels
    audio.features()   # refresh the timestamp of the sound analysis
    from . import fingerprint   # audio fingerprints (same recording twice): small file, read fresh every time
    return {**_memoized("intel", build, audio._cache["stamp"], ml.stamp(), lastfm._mem["stamp"]),
            "fingerprints": fingerprint.stats(cfg, lib)}


def api_missing(query):
    """Bands that resemble your favorites but are not in the library yet (Last.fm)."""
    lib = CACHE.get()
    cfg = load_config()
    person = next((p for p in cfg["personen"] if p["id"] == (query.get("person") or _default_person(cfg))), None)
    if person:
        _own_person(person["id"])
    seeds = list((person or {}).get("likes", {}).get("artists", []))
    try:
        st = stats.compute(cfg, stats.songs_for(person["user"], lib)) if person else None
        seeds += [a["name"] for a in (st or {}).get("topArtists", [])[:12]]
    except (ValueError, KeyError):
        pass
    if not seeds:
        count = rules.artist_stats(lib.songs)[0]
        seeds = [a for a, _count in count.most_common(12)]
    return {"seeds": list(dict.fromkeys(seeds))[:15], "missing": classify.missing_artists(list(dict.fromkeys(seeds)), lib),
            "lastfm": bool(lastfm.api_key())}


def api_lastfm_test(body):
    key = (body.get("key") or "").strip() or lastfm.api_key()
    if not key:
        return {"ok": False, "error": _("Please enter a key")}
    return lastfm.test(key)


def api_deezer_ranks():
    """Rank distribution for the star setting."""
    return {**deezer.rank_histogram(), "defaults": deezer.DEFAULT_THRESHOLDS}


def api_opus_info(refresh=False):
    op = load_config()["settings"].get("opus") or {}
    t = opus.tools()
    out = {"ffmpeg": bool(t["ffmpeg"] and t["ffprobe"]), "aac": opus.mp4_available(), "musicDir": str(opus.music_dir()),
           "archiveDir": str(opus.archive_dir(op))}
    try:
        files = opus.find_sources(op, use_cache=not refresh)
        out.update(pending=len(files), sample=[str(f.relative_to(opus.music_dir())) for f in files[:8]])
    except OSError as e:
        out["error"] = str(e)
    from . import lautstaerke   # loudness normalization: possible? how far along?
    ok, why = lautstaerke.available()
    songs = lautstaerke.load().get("songs") or {}
    out["loudness"] = {"available": ok, "why": why, "songs": len(CACHE.get().songs),
                       "measured": sum(1 for e in songs.values() if e.get("l") is not None),
                       "written": sum(1 for e in songs.values() if e.get("w")),
                       "external": sum(1 for e in songs.values() if e.get("x"))}
    return out


def api_rueckblick(query):
    cfg = load_config()
    person = next((p for p in cfg["personen"] if p["id"] == (query.get("person") or _default_person(cfg))), None)
    if not person:
        raise ValueError(_("Unknown person"))
    _own_person(person["id"])
    kind = query.get("kind", "woche")
    if kind not in ("woche", "monat", "jahr"):
        raise ValueError(_("Unknown period"))
    lib = stats.songs_for(person["user"], CACHE.get())
    last = rueckblick.last_snapshot(person["user"])
    if not last or (dt.datetime.now() - dt.datetime.fromisoformat(last["at"])).total_seconds() > 1800:
        rueckblick.snapshot(person["user"], lib.songs)   # keep it fresh (at most every 30 min)
    return {**rueckblick.summary(cfg, lib, person["user"], kind, query.get("year")), "person": person["id"]}


def api_rueckblick_keep(body):
    """Keep a recap as a fixed playlist – it never changes again, in the person's account."""
    cfg = load_config()
    person = next((p for p in cfg["personen"] if p["id"] == (body.get("person") or _default_person(cfg))), None)
    if not person:
        raise ValueError(_("Unknown person"))
    _own_person(person["id"])
    kind = body.get("kind", "monat")
    if kind not in ("woche", "monat", "jahr"):
        raise ValueError(_("Unknown period"))
    start, end = rueckblick.period(kind, year=body.get("year"))[:2]
    per_song = rueckblick.plays_between(person["user"], start, end)[0]
    lib = CACHE.get()
    index = lib.index_of()
    ids = [sid for sid, _plays in sorted(per_song.items(), key=lambda x: (-x[1], x[0])) if sid in index][:50]
    if not ids:
        raise ValueError(_("Nothing has been played in this period yet."))
    # name and comment go to Navidrome (server language); each language formats the dates in its own text
    name = person.get("prefix", "") + (_s("Recap {year}", year=start.year) if kind == "jahr"
                                       else _s("Recap {start:%m/%d}–{end:%m/%d/%Y}", start=start, end=end))
    try:   # do not create the same playlist twice
        existing = playlists.native_api(load_env())._request("GET", "/api/playlist?_start=0&_end=10000")
    except (NavidromeError, ValueError):
        existing = []
    if any(x.get("name") == name for x in existing or []):
        raise ValueError(_("“{name}” already exists in Navidrome.", name=name))
    playlists.save_fixed(load_env(), person, name, ids,
                         _s("The most played songs from {start:%m/%d/%Y} to {end:%m/%d/%Y} (Tuttiphon)", start=start, end=end),
                         person.get("public", False))
    return {"name": name, "count": len(ids)}


def api_kinderschutz(query):
    """For the settings: songs recognized as rude (allowed ones too) and who has kid-safe mode on."""
    cfg = load_config()
    lib = CACHE.get()
    allow = set((cfg["settings"].get("kinderschutz") or {}).get("allow", []))
    index = lib.index_of()
    aid = lib.artist_ids()
    songs = []
    for sid, words in liedtext.derb_details().items():
        i = index.get(sid)
        if i is None:
            continue
        s = lib.songs[i]
        a = lib._main_artist(s)
        songs.append({"id": sid, "title": s.get("title"), "artist": a, "album": s.get("album"), "artistId": aid.get(a),
                      "allowed": sid in allow, "words": words})
    songs.sort(key=lambda x: (x["artist"] or "", x["title"] or ""))
    return {"index": liedtext.status(), "songs": songs,
            "persons": [p["name"] for p in cfg["personen"] if p.get("clean")]}


def api_liedtexte_update(body):
    liedtext.update_soon(CACHE.get(), force=True)
    return {"ok": True}


_notify_tests = {}


def api_notify_test(body):
    """Test message: administrators to their topic (or one from the form), otherwise to the one of their own person.
    At most one per 30 seconds and account."""
    cfg = load_config()
    who = (auth.current().get("user") or "").lower()
    if time.time() - _notify_tests.get(who, 0) < 30:
        raise ValueError(_("Please wait a moment – a test message has just gone out."))
    if body.get("topic") and not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", str(body["topic"])):
        raise ValueError(_("Please use only letters, digits, - and _ for the topic."))
    m = auth.current()
    if body.get("person"):
        _own_person(body["person"])
        person = next((p for p in cfg["personen"] if p["id"] == body["person"]), None)
        topic = body.get("topic") or (person or {}).get("push")
        if m["role"] != "admin":
            # users: only to the topic of their own person (also the one just being entered) – never the
            # administrator's or another person's, and without a topic not to the administrator's either
            if not topic:
                raise ValueError(_("No topic entered."))
            foreign = {(notify.settings(cfg).get("topic") or "").lower()} | {
                (x.get("push") or "").lower() for x in cfg["personen"] if x["id"] not in m["own"]}
            if str(topic).lower() in foreign - {""}:
                raise PermissionError(_("This topic belongs to someone else – please choose your own."))
    else:
        if m["role"] != "admin":
            raise PermissionError(_("Administrators only."))
        topic = body.get("topic")
    if not notify.settings(cfg).get("enabled"):
        raise ValueError(_("Notifications are turned off."))
    _notify_tests[who] = time.time()
    return notify.test(topic, cfg, fallback=m["role"] == "admin")


# ---------------------------------------------------------------------------- notifications through the app

def _push_account():
    m = auth.current()
    return (m.get("user") or "lokal").lower(), m.get("role") == "admin"


def api_push_key(query=None):
    ok, why = webpush.available()
    return {"available": ok, "why": why, "key": webpush.public_key() if ok else None,
            "enabled": bool(notify.settings().get("enabled"))}


def api_push_subscribe(body):
    ok, why = webpush.available()
    if not ok:
        raise ValueError(_("Notifications through the app: {why}.", why=why))
    account, admin = _push_account()
    origin = str(body.get("origin") or "")
    n = webpush.add(account, body.get("subscription"), admin=admin, origin=origin if re.fullmatch(r"https://[^/\s]{1,200}", origin) else "")
    return {"ok": True, "devices": n}


def api_push_unsubscribe(body):
    account = _push_account()[0]
    webpush.remove(str(body.get("endpoint") or ""), account)
    return {"ok": True}


def api_push_status(body):
    account = _push_account()[0]
    mine = webpush.devices(account)
    return {"known": str(body.get("endpoint") or "") in mine, "devices": len(mine)}


def api_push_test(body):
    """Test message to one's own devices – at most one per 30 seconds and account. In the language of the page:
    the person who asked for it reads it right away."""
    account = _push_account()[0]
    if time.time() - _notify_tests.get("push|" + account, 0) < 30:
        raise ValueError(_("Please wait a moment – a test message has just gone out."))
    if not notify.settings().get("enabled"):
        raise ValueError(_("Notifications are turned off."))
    _notify_tests["push|" + account] = time.time()
    ok = webpush.send_to("Tuttiphon", _("This is what notifications from Tuttiphon look like."), "#/", accounts=[account], tag="test")
    return {"ok": ok} if ok else {"ok": False, "error": _("No device accepted the message.")}


def api_log(query):
    name = query.get("file", "")
    path = (LOG_DIR / name).resolve()
    if LOG_DIR.resolve() not in path.parents or not path.is_file():
        raise ValueError(_("Log not found"))
    return {"file": name, "text": read_bytes(path).decode("utf-8", errors="replace")[-400_000:]}


def api_save_config(body):
    m = auth.current()
    if m["role"] == "admin":
        save_from_ui(body)
    else:   # only take over their own things
        save_from_ui(lambda current: auth.merge_user_changes(current, body, m), keep_accounts=True)
    AUTO.schedule()
    schedule_warm()
    return {"ok": True}


def api_stats(query):
    cfg = load_config()
    pid = query.get("person") or _default_person(cfg)
    person = next((p for p in cfg["personen"] if p["id"] == pid), None)
    if not person:
        raise ValueError(_("Unknown person"))
    _own_person(pid)
    lib = stats.songs_for(person["user"], CACHE.get())
    out = _memoized("stats", lambda: stats.compute(cfg, lib), person["user"].lower(), ml.lib_key(lib))
    return {**out, "person": pid, "personsSameUser": [p["id"] for p in cfg["personen"] if p["user"].lower() == person["user"].lower()]}


def _navidrome_playlist(p):
    native = playlists.native_api(load_env())
    np = playlists.navidrome_index(native).get(p.get("file") or "")
    if not np:
        raise ValueError(_("The playlist is not in Navidrome yet – apply first, then set the cover."))
    return native, np


def _find_playlist(pid):
    p = next((x for x in load_config()["playlists"] if x["id"] == pid), None)
    if not p:
        raise ValueError(_("Playlist not found"))
    return p


def api_cover_apply(body):
    p = _own_playlist_id(body["id"])
    style = body.get("style", "mosaik")
    if style not in covers.available_styles():
        raise ValueError(_("This style is not available here"))
    lib = CACHE.get()
    cfg = load_config()
    data = covers.render(cfg, lib, p, style)
    native, np = _navidrome_playlist(p)
    covers.upload(native, np["id"], data)
    sig = covers.signature(cfg, lib, p)

    def apply(fresh):
        for x in fresh["playlists"]:
            if x["id"] == p["id"]:
                x["cover"] = {"style": style, "sig": sig, "nid": np["id"], "at": dt.date.today().isoformat(), "rev": int(time.time())}
    update_config(apply)
    return {"ok": True}


def api_cover_upload(pid, data, ctype):
    if not covers.sniff(data):
        raise ValueError(_("Please choose an image in JPG, PNG or WebP format"))
    p = _own_playlist_id(pid)
    native, np = _navidrome_playlist(p)
    covers.upload(native, np["id"], data, ctype)
    try:   # keep it – if Navidrome creates the playlist anew (seasonal pause), the next run uploads it again
        covers.keep_own(p["id"], data)
    except OSError:
        pass

    def apply(fresh):
        for x in fresh["playlists"]:
            if x["id"] == p["id"]:
                x["cover"] = {"style": "eigenes", "at": dt.date.today().isoformat(), "rev": int(time.time()), "nid": np["id"]}
    update_config(apply)
    return {"ok": True}


def api_cover_remove(body):
    p = _own_playlist_id(body["id"])
    native, np = _navidrome_playlist(p)
    try:
        native.delete_playlist_image(np["id"])
    except NavidromeError:
        pass   # had no image of its own at all

    def apply(fresh):
        for x in fresh["playlists"]:
            if x["id"] == p["id"]:
                x.pop("cover", None)
    update_config(apply)
    covers.forget_own(p["id"])
    return {"ok": True}


def api_task_status(query):
    st = {**RUNNER.status(int(query.get("since") or 0)), "auto": AUTO.state()}
    if auth.current()["role"] != "admin":   # users: only whether something is running – no log
        st["lines"] = []
    return st


def api_apply_now():
    """“Apply” (also for users): write playlists and let Navidrome scan. The planned auto-apply is dropped only when
    the run really starts; only administrators get log lines."""
    if RUNNER.running() and RUNNER.pause_for(["playlists", "scan"], name=_s("Apply playlists in Navidrome")):
        st = RUNNER.status()   # runs right after the short pause of the running task
    else:
        st = RUNNER.start(["playlists", "scan"], name=_s("Apply playlists in Navidrome"))
    AUTO.cancel()
    if auth.current()["role"] != "admin":
        st = {**st, "lines": []}
    return st


def api_task_start(body):
    auth.require_admin()
    AUTO.cancel()
    opts = {k: body[k] for k in ("deezer_mode", "dry_run", "full_scan", "overwrite_manual", "lyrics_all", "lyrics_full", "analyse_full") if k in body}
    if opts.get("deezer_mode") not in (None, "new", "missing", "full", "recalc", "refresh"):
        raise ValueError(_("Unknown Deezer mode"))
    return RUNNER.start(body.get("steps") or pipeline(), **opts)


# --------------------------------------------------------------------------- sign-in (for Docker/LAN)

# --------------------------------------------------------------------------- HTTP

mimetypes.add_type("application/manifest+json", ".webmanifest")
mimetypes.add_type("text/javascript", ".js")


class BodyTooLarge(Exception):
    pass


_login_fails = {}   # key (account or address) -> times of the failed attempts
_login_pending = Counter()   # key -> attempts being checked with Navidrome right now (count like failed ones)
_login_blocked_said = {}   # key -> time a block was reported in the server log (once per block)
_login_lock = threading.Lock()
_setup_lock = threading.Lock()
LOOPBACK = ("127.0.0.1", "localhost", "::1")


def client_of(addr, headers, trusted):
    """(address of the person, via https?) of a request. Only when the connection comes from a reverse proxy listed in
    TUTTIPHON_TRUSTED_PROXIES (addresses or networks, comma-separated) do X-Forwarded-For/-Proto count – otherwise
    anyone could claim any address."""
    import ipaddress

    def listed(ip):
        try:
            a = ipaddress.ip_address(ip)
        except ValueError:
            return False
        a = getattr(a, "ipv4_mapped", None) or a   # bound to "::", IPv4 clients arrive as ::ffff:a.b.c.d
        for net in trusted:
            try:
                if a in ipaddress.ip_network(net, strict=False):
                    return True
            except ValueError:
                continue
        return False
    if not trusted or not listed(addr):
        return addr, False
    hops = [h.strip() for h in (headers.get("X-Forwarded-For") or "").split(",") if h.strip()]
    while hops and listed(hops[-1]):   # the last address no trusted proxy added is the person's
        hops.pop()
    return (hops[-1] if hops else addr), (headers.get("X-Forwarded-Proto") or "").strip().lower() == "https"
MAX_BODY = 2_000_000


# for every answer: no embedding in foreign pages (clickjacking), no guessing of content types, no addresses of
# Tuttiphon in the Referer to other servers
SECURITY_HEADERS = {"X-Content-Type-Options": "nosniff", "X-Frame-Options": "DENY",
                    "Content-Security-Policy": "frame-ancestors 'none'", "Referrer-Policy": "same-origin"}


def _finite_float(text):
    """JSON numbers of a request: 1e999 would become an endless number that breaks every calculation with it."""
    value = float(text)
    if not math.isfinite(value):
        raise ValueError(text)
    return value


def _no_constant(name):
    raise ValueError(name)   # NaN, Infinity, -Infinity are not JSON


class Handler(BaseHTTPRequestHandler):
    server_version = "Tuttiphon"
    sys_version = ""   # the Server header without the Python version
    timeout = 30   # do not keep slow/hanging connections open forever

    def log_message(self, fmt, *args):
        pass

    def version_string(self):
        return self.server_version

    def end_headers(self):
        for k, v in SECURITY_HEADERS.items():
            self.send_header(k, v)
        super().end_headers()

    def _send(self, data, ctype, code=200, headers=None):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        for k, v in (headers or {}).items():
            self.send_header(k, v)
        self.end_headers()
        if getattr(self, "command", "GET") != "HEAD":   # HEAD: the same headers, without the content
            self.wfile.write(data)

    def _json(self, obj, code=200, headers=None):
        self._send(json.dumps(obj, ensure_ascii=False).encode("utf-8"), "application/json; charset=utf-8", code,
                   {"Cache-Control": "no-store", **(headers or {})})

    def _length(self, limit=MAX_BODY):
        try:
            length = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            raise ValueError(_("invalid length"))
        if not 0 <= length <= limit:
            raise BodyTooLarge()
        return length

    def _body(self):
        length = self._length()
        if not length:
            return {}
        try:
            body = json.loads(self.rfile.read(length).decode("utf-8"), parse_float=_finite_float,
                              parse_constant=_no_constant)
        except (UnicodeDecodeError, ValueError, RecursionError):   # JSONDecodeError is a ValueError
            raise ValueError(_("invalid request")) from None
        if not isinstance(body, dict):
            raise ValueError(_("invalid request"))
        return body

    def _host_ok(self, pw):
        """Without a password only reachable via localhost – protects against DNS rebinding (a foreign web page that
        poses as 127.0.0.1 could otherwise change credentials)."""
        if pw:
            return True
        host = (self.headers.get("Host") or "").strip().lower()
        host = host[1:].split("]")[0] if host.startswith("[") else host.rsplit(":", 1)[0] if host.count(":") == 1 else host
        extra = {x.strip().lower() for x in (load_env().get("TUTTIPHON_HOSTS") or "").split(",") if x.strip()}
        return host in LOOPBACK or host in extra

    def _client(self):
        trusted = [x.strip() for x in (load_env().get("TUTTIPHON_TRUSTED_PROXIES") or "").split(",") if x.strip()]
        return client_of(self.client_address[0], self.headers, trusted)

    def _admin(self):
        """(source, plain): where the password of the local administrator comes from (localadmin.source()) and the
        plain one from docker-compose/.env, if any – checked at most every 10 s. On the network without any: the setup
        code is made sure of (and announced in the server log)."""
        at, state = Handler._pw_cache
        if time.time() - at > 10 or state is None:
            env = load_env()
            state = (localadmin.source(env), admin_password(env))
            Handler._pw_cache = (time.time(), state)
            if self.network and not state[0]:
                localadmin.setup_code()
        return state

    _pw_cache = (0.0, None)
    network = False   # serve(): reachable on the network – then never without a proper password (see _handle)

    def _cookies(self):
        return dict(c.strip().split("=", 1) for c in (self.headers.get("Cookie") or "").split(";") if "=" in c)

    def _session_user(self):
        return auth.read_token(self._cookies().get("tuttiphon", ""))

    def _limited(self, keys, label, attempt, status=401):
        """Lockout around a password or code check: per account and address (10 failed attempts in 10 min), per address
        (30) and per account from everywhere together (50) – so a single stranger can neither guess nor lock an account
        for everyone. attempt() returns the result or raises auth.LoginError. -> (True, result), or (False, None) once
        the refusal has been answered."""
        now = time.time()
        with _login_lock:
            for k in list(_login_fails):
                _login_fails[k] = [t for t in _login_fails[k] if now - t < 600]
                if not _login_fails[k]:
                    del _login_fails[k]
            for k in [k for k, at in _login_blocked_said.items() if now - at >= 600]:
                del _login_blocked_said[k]
            # attempts still being checked count too – otherwise many at the same time would all get through
            full = [k for k, limit in keys if len(_login_fails.get(k, ())) + _login_pending[k] >= limit]
            if full:
                if full[0] not in _login_blocked_said:   # the server log says it once per block, not per attempt
                    _login_blocked_said[full[0]] = now
                    events.say(_s("Sign-in blocked (too many failed attempts): {who}", who=label))
                self._json({"error": _("Too many failed attempts – please try again in a few minutes.")}, 429)
                return False, None
            for k, _limit in keys:   # reserve the attempt before checking
                _login_pending[k] += 1

        def release(failed):
            with _login_lock:
                for k, _limit in keys:
                    _login_pending[k] -= 1
                    if _login_pending[k] <= 0:
                        del _login_pending[k]
                    if failed:
                        _login_fails.setdefault(k, []).append(now)
        try:
            result = attempt()
        except auth.LoginError as e:
            release(e.counts)   # “Navidrome not reachable” or an empty field do not count
            if e.counts:
                events.say(_s("Sign-in failed: {who}", who=label))
                time.sleep(1)
            self._json({"error": str(e)}, status)
            return False, None
        except BaseException:
            release(False)
            raise
        release(False)
        return True, result

    def _session_cookie(self, user, https):
        cookie = f"tuttiphon={auth.make_token(user)}; Path=/; Max-Age={auth.SESSION_DAYS * 86400}; HttpOnly; SameSite=Lax"
        if https:   # reached via https through a trusted reverse proxy: never send the cookie unencrypted
            cookie += "; Secure"
        return cookie

    def _login(self):
        body = self._body()
        ip, https = self._client()
        name = str(body.get("username") or "").strip().lower()[:200]
        if name in ("", "notfall", auth.NOTFALL):   # all spellings of the local administrator count together
            name = auth.NOTFALL
        keys = ((f"u:{name}|{ip}", 10), (f"ip:{ip}", 30), (f"u:{name}", 50))
        ok, user = self._limited(keys, _who(name), lambda: auth.login(
            body.get("username", ""), body.get("password", ""), body.get("remember", True) is not False))
        if not ok:
            return None
        events.say(_s("Signed in: {who}", who=_who(user)))
        return self._json({"ok": True, "user": user}, headers={"Set-Cookie": self._session_cookie(user, https)})

    def _setup(self, pending):
        """First start without an administrator password: setup code + new password -> signed in as local administrator."""
        if not pending:
            return self._json({"error": _("Tuttiphon is already set up – sign in as local administrator.")}, 409)
        body = self._body()
        ip, https = self._client()

        def attempt():
            with _setup_lock:   # two at the same time: only the first sets the password
                if localadmin.configured():
                    raise auth.LoginError(_("Tuttiphon is already set up – sign in as local administrator."), counts=False)
                if not localadmin.check_code(body.get("code")):
                    raise auth.LoginError(_("The setup code is wrong – look for the line “Setup code:” in the container "
                                            "log, or open setup-code.txt in the data folder."))
                password = body.get("password")
                if not isinstance(password, str) or weak_password(password):
                    raise auth.LoginError(_("The administrator password needs at least 8 characters."), counts=False)
                localadmin.set_password(password)
                Handler._pw_cache = (0.0, None)
                return auth.NOTFALL
        ok, user = self._limited(((f"setup|{ip}", 10), ("setup", 50)), _s("setup code"), attempt)
        if not ok:
            return None
        events.say(_s("Setup: the password of the local administrator is set."))
        return self._json({"ok": True, "user": user}, headers={"Set-Cookie": self._session_cookie(user, https)})

    def _admin_password(self):
        """Settings → Users & permissions: set or change the password of the local administrator (kept as a hash)."""
        body = self._body()
        ip, https = self._client()
        src = localadmin.source()
        if src == "env":
            raise ValueError(_("The password of the local administrator is set in docker-compose.yaml – change it there."))
        password = body.get("password")
        if not isinstance(password, str) or weak_password(password):
            raise ValueError(_("The administrator password needs at least 8 characters."))
        if src == "stored":   # changing it needs the current one – a forgotten one: see docs (delete the file)
            def attempt():
                if not localadmin.check(body.get("current")):
                    raise auth.LoginError(_("The current password is wrong."))
                return True
            name = auth.NOTFALL
            ok, _done = self._limited(((f"u:{name}|{ip}", 10), (f"ip:{ip}", 30), (f"u:{name}", 50)),
                                      _who(name), attempt, status=400)
            if not ok:
                return None
        localadmin.set_password(password)
        Handler._pw_cache = (0.0, None)
        events.say(_s("The password of the local administrator was changed."))
        me = auth.current()
        # the local administrator's sessions end with the old password – this browser stays signed in (also on the
        # PC, where sign-in starts right now)
        headers = {"Set-Cookie": self._session_cookie(auth.NOTFALL, https)} if me.get("user") in (None, auth.NOTFALL) else None
        return self._json({"ok": True}, headers=headers)

    def _static(self, path):
        name = "index.html" if path in ("", "/") else path.lstrip("/")
        file = (WEB_DIR / name).resolve()
        if WEB_DIR.resolve() not in file.parents or not file.is_file():
            if name == "index.html":   # interface not built yet (npm run build)
                return self._send(_("Tuttiphon: the interface has not been built yet – please run “npm run build” "
                                    "or start ./tuttiphon.sh.").encode("utf-8"), "text/plain; charset=utf-8", 503)
            return self._json({"error": "not found"}, 404)   # i18n-ignore – technical code
        ctype = mimetypes.guess_type(file.name)[0] or "application/octet-stream"
        if file.suffix == ".js":
            ctype = "text/javascript"
        if ctype.startswith("text/"):
            ctype += "; charset=utf-8"
        # Built files under /assets/ carry a content hash in their name – so they never change. index.html and
        # login.html on the other hand are always fetched fresh, otherwise they point to old files after an update.
        cache = "public, max-age=31536000, immutable" if name.startswith("assets/") else "no-cache"
        self._send(read_bytes(file), ctype, headers={"Cache-Control": cache})

    def _stream(self, query):
        """Listening in: pass a song's audio through from Navidrome (the credentials stay here). Seeking via Range."""
        lib = CACHE.get()
        song = lib.songs[_song(lib, query.get("id", ""))]
        if _child_blocked(load_config(), song):
            raise PermissionError(_("This song is hidden by kid-safe mode."))
        fmt = "mp3" if query.get("f") == "mp3" else "raw"
        resp = admin_client(load_env()).stream(song["id"], fmt, byte_range=self.headers.get("Range") if fmt == "raw" else None)
        try:
            self.send_response(resp.status)
            for h in ("Content-Type", "Content-Length", "Content-Range", "Accept-Ranges"):
                if resp.headers.get(h):
                    self.send_header(h, resp.headers[h])
            self.send_header("Cache-Control", "private, max-age=3600")
            self.end_headers()
            while self.command != "HEAD" and (chunk := resp.read(64 * 1024)):
                self.wfile.write(chunk)
        finally:
            resp.close()

    def _image(self, path, query):
        res = images.get_image(urllib.parse.unquote(path[len("/img/"):]), query.get("s", 300))
        if not res:
            return self._send(b"", "text/plain", 404, {"Cache-Control": "max-age=3600"})
        data, ctype = res
        self._send(data, ctype, headers={"Cache-Control": "max-age=604800"})

    GET_ROUTES = {
        "/api/push/key": api_push_key,
        "/api/status": lambda q: api_status(),
        "/api/changelog": lambda q: api_changelog(),
        "/api/taste": api_taste,
        "/api/search": api_search,
        "/api/config": lambda q: auth.view_config(load_config()),
        "/api/me": lambda q: auth.current(),
        "/api/accounts": lambda q: api_accounts(),
        "/api/library": lambda q: api_library(force=q.get("refresh") == "1"),
        "/api/home": lambda q: api_home(),
        "/api/playlists": lambda q: api_playlists(),
        "/api/playlist": api_playlist,
        "/api/welt": api_welt,
        "/api/artist": api_artist,
        "/api/song": api_song,
        "/api/welt/neu": api_welt_reset,   # i18n-ignore – route
        "/api/song/more": api_song_more,
        "/api/sound/catalog": lambda q: ml.sound_catalog(CACHE.get()),
        "/api/instruments": lambda q: ml.sound_catalog(CACHE.get()),   # older name of the same catalog
        "/api/matrix": api_matrix,
        "/api/suggestions": api_suggestions,
        "/api/inbox": lambda q: api_inbox(),
        "/api/history": lambda q: history(60),
        "/api/log": api_log,
        "/api/users": lambda q: api_users(),
        "/api/task": api_task_status,
        "/api/stats": api_stats,
        "/api/cover/styles": lambda q: covers.available_styles(),
        "/api/deezer/ranks": lambda q: api_deezer_ranks(),
        "/api/lyrics/stats": lambda q: lyrics.stats(),
        "/api/opus/info": lambda q: api_opus_info(q.get("refresh") == "1"),
        "/api/rueckblick": api_rueckblick,
        "/api/intel": lambda q: api_intel(),
        "/api/missing": api_missing,
        "/api/backups": lambda q: backup.status(),
        "/api/kinderschutz": api_kinderschutz,
        "/api/pflege": lambda q: pflege.report(load_config(), CACHE.get()),
    }
    POST_ROUTES = {
        "/api/preview": api_preview,
        "/api/counts": api_counts,
        "/api/takeover/preview": api_takeover_preview,
        "/api/takeover": api_takeover,
        "/api/snapshot": api_snapshot,
        "/api/mapping": api_mapping,
        "/api/cover/apply": api_cover_apply,
        "/api/cover/remove": api_cover_remove,
        "/api/env/test": api_env_test,
        "/api/paths/check": api_paths_check,
        "/api/lastfm/test": api_lastfm_test,
        "/api/task": api_task_start,
        "/api/task/cancel": lambda b: (RUNNER.cancel(), AUTO.cancel(), {"ok": True})[2],
        "/api/me/password": api_me_password,
        "/api/apply/now": lambda b: api_apply_now(),
        "/api/backups/now": lambda b: backup.create(log=lambda *_: None),
        "/api/tour/seen": lambda b: (auth.mark_seen(auth.current()["user"], "tour"), {"ok": True})[1],   # only one's own account
        "/api/seen": lambda b: (auth.mark_seen(auth.current()["user"], str(b.get("what") or "")), {"ok": True})[1],
        "/api/rueckblick/keep": api_rueckblick_keep,
        "/api/liedtexte/update": api_liedtexte_update,
        "/api/notify/test": api_notify_test,
        "/api/push/subscribe": api_push_subscribe,
        "/api/push/unsubscribe": api_push_unsubscribe,
        "/api/push/status": api_push_status,
        "/api/push/test": api_push_test,
    }
    PUT_ROUTES = {
        "/api/config": api_save_config,
        "/api/env": api_env_save,
        "/api/accounts": api_accounts_save,
    }
    ADMIN_ONLY = {"/api/history", "/api/log", "/api/users", "/api/deezer/ranks", "/api/lyrics/stats", "/api/opus/info", "/api/intel",
                  "/api/accounts", "/api/takeover/preview", "/api/takeover", "/api/mapping", "/api/env/test", "/api/paths/check",
                  "/api/lastfm/test", "/api/task/cancel", "/api/env", "/api/backups", "/api/backups/now", "/api/backups/file",
                  "/api/kinderschutz", "/api/pflege", "/api/liedtexte/update", "/api/welt/neu", "/api/admin-password"}   # i18n-ignore – routes; /api/task: status for everyone, api_task_start checks starting

    def _handle(self, method):
        url = urllib.parse.urlparse(self.path)
        query = dict(urllib.parse.parse_qsl(url.query))
        path = url.path
        i18n.use(self.headers.get("X-Lang"))   # messages in the language of the interface (otherwise the server's)
        try:
            src, plain = self._admin()
            if self.network and plain and weak_password(plain):
                # reachable on the network, but the password from docker-compose/.env is weak (e.g. edited while
                # running): stay locked instead of letting anyone in with it
                return self._json({"error": _("Tuttiphon is locked: TUTTIPHON_ADMIN_PASSWORD is too short or still the "
                                              "placeholder – please set at least 8 characters.")}, 503)
            setup = self.network and not src   # on the network without a password: only the setup with the code
            needs_login = bool(src) or setup
            if not self._host_ok(needs_login):
                return self._json({"error": _("Access only via 127.0.0.1 – or set an administrator password "
                                              "(Settings → Users & permissions).")}, 421)
            auth.set_current({"user": None, "role": "none", "own": [], "persons": [], "local": False})
            if path == "/api/login" and method == "POST":
                if self.headers.get("X-Tuttiphon") != "1":
                    return self._json({"error": "forbidden"}, 403)   # i18n-ignore – sign-in only from the interface
                return self._login()
            if path == "/api/login" and method == "GET":   # public: which sign-in the page offers
                if setup:
                    localadmin.remind()   # the setup page is open: the code into the log once more
                return self._json(api_login_info(setup))
            if path == "/api/setup" and method == "POST":
                if self.headers.get("X-Tuttiphon") != "1":
                    return self._json({"error": "forbidden"}, 403)   # i18n-ignore – only from the interface
                return self._setup(setup)
            clean = posixpath.normpath(urllib.parse.unquote(path))   # “/assets/../help/…” is not public
            public = clean in ("/login.html", "/favicon.svg", "/manifest.webmanifest", "/sw.js") or clean.startswith(("/icons/", "/assets/"))
            if path == "/api/logout" and method == "POST":
                auth.end_session(self._cookies().get("tuttiphon", ""))   # really end the session, not just delete the cookie
                return self._json({"ok": True}, headers={"Set-Cookie": "tuttiphon=; Path=/; Max-Age=0; HttpOnly; SameSite=Lax"})
            user = self._session_user() if needs_login else None
            m = auth.me(user) if (user or not needs_login) else None
            if m and m["role"] == "none":   # access blocked in the meantime
                m = None
            if m is None and needs_login:
                if path.startswith(("/api/", "/img/", "/live/", "/cover")):
                    return self._json({"error": "login"}, 401)   # i18n-ignore – technical code
                if not public:
                    return self._send(b"", "text/plain", 302, {"Location": "/login.html"})
            if m:
                auth.set_current(m)
                if path in self.ADMIN_ONLY and m["role"] != "admin":
                    return self._json({"error": _("Only administrators may do this.")}, 403)
            if method == "GET":
                if path.startswith("/img/"):
                    return self._image(path, query)
                if path == "/api/stream":
                    return self._stream(query)
                if path.startswith("/live/"):   # current playlist image from Navidrome
                    res = images.live_image(urllib.parse.unquote(path[len("/live/"):]), query.get("s", 300), query.get("v", ""))
                    if not res:
                        return self._send(b"", "text/plain", 404)
                    return self._send(res[0], res[1], headers={"Cache-Control": "max-age=86400"})
                if path == "/cover":   # preview of a designed cover
                    p = _own_playlist_id(query.get("id", ""))
                    style = query.get("style", "mosaik")
                    if style not in covers.available_styles():
                        raise ValueError(_("Unknown cover style"))
                    data = covers.render(load_config(), CACHE.get(), p, style)
                    return self._send(data, "image/jpeg", headers={"Cache-Control": "no-store"})
                if path == "/api/backups/file":   # download a backup (admin only, see ADMIN_ONLY)
                    file = backup.path_of(query.get("name", ""))
                    return self._send(read_bytes(file), "application/zip", headers={
                        "Content-Disposition": f'attachment; filename="{file.name}"', "Cache-Control": "no-store"})
                if not path.startswith("/api/"):
                    return self._static(path)
                route = self.GET_ROUTES.get(path)
                return self._json(route(query)) if route else self._json({"error": "not found"}, 404)   # i18n-ignore – technical code
            # protection against foreign pages posting to localhost
            if self.headers.get("X-Tuttiphon") != "1":
                return self._json({"error": "forbidden"}, 403)   # i18n-ignore – technical code
            if method == "POST" and path == "/api/admin-password":   # answers with a new session cookie
                return self._admin_password()
            if method == "POST" and path == "/api/cover/upload":   # raw data instead of JSON
                data = self.rfile.read(self._length(10 * 1024 * 1024))
                return self._json(api_cover_upload(query.get("id", ""), data, self.headers.get("Content-Type", "")))
            route = (self.POST_ROUTES if method == "POST" else self.PUT_ROUTES).get(path)
            if not route:
                return self._json({"error": "not found"}, 404)   # i18n-ignore – technical code
            return self._json(route(self._body()))
        except PermissionError as e:
            if e.errno is not None:   # from the file system (e.g. NFS briefly EACCES) – not a permission problem of the person
                return self._json({"error": _("A file was not accessible just now – please try again in a moment.")}, 503)
            return self._json({"error": str(e) or _("No permission")}, 403)
        except (ValueError, KeyError, RuntimeError, NavidromeError, StopIteration) as e:
            msg = str(e) or type(e).__name__
            if auth.current()["role"] != "admin" and (isinstance(e, NavidromeError) or msg.startswith("Navidrome")):
                # users: no addresses, error numbers or admin settings they cannot open
                msg = _("Navidrome cannot be reached right now – please try again later.")
            return self._json({"error": msg}, 400)
        except BodyTooLarge:
            self.close_connection = True
            return self._json({"error": _("Request too large")}, 413)
        except (BrokenPipeError, ConnectionResetError, TimeoutError):
            return None
        except Exception as e:   # noqa: BLE001 – show errors instead of dropping the connection
            events.say(_s("⚠ Error at {method} {path}: {kind}: {error}", method=method, path=path, kind=type(e).__name__, error=e))
            # the details (type, message – possibly paths or values) only in the server log
            return self._json({"error": _("Something went wrong – the details are in the server log.")}, 500)
        finally:
            i18n.use(None)   # the thread may serve another request afterwards

    def do_GET(self):
        self._handle("GET")

    def do_HEAD(self):   # like GET, without the content (_send) – e.g. for uptime checks
        self._handle("GET")

    def do_POST(self):
        self._handle("POST")

    def do_PUT(self):
        self._handle("PUT")


DAILY_FILE = STATE_DIR / "daily.json"


# ---------------------------------------------------------------------------- several instances
# Tuttiphon can run on the PC and in the Docker container on the NAS. Both write into the same playlist folder –
# so every instance reports there every minute (app/instances.py), and the other one sees it.
heartbeat = instances.heartbeat
other_instances = instances.others
IN_DOCKER = instances.IN_DOCKER


def _safe(fn):
    try:
        fn()
    except Exception:
        pass


_plays_day = {"date": None}
_tidy_day = {"date": None}
_backup_fail = {"date": None, "at": 0.0}


def _backup_daily():
    """Back up once a day from the time of the daily refresh on (when turned on and there is none yet today)."""
    cfg = load_config()
    if not backup.settings(cfg).get("enabled", True):
        return
    now = dt.datetime.now()
    try:
        hh, mm = (int(x) for x in (cfg["settings"].get("dailyAt") or "05:30").split(":"))
    except ValueError:
        hh, mm = 5, 30
    if (now.hour, now.minute) >= (hh, mm) and not backup.done_today(cfg):
        if time.time() - _backup_fail["at"] < 3600:   # after a failure try again only once an hour
            return
        try:
            res = backup.create(cfg, log=lambda *_: None)
        except Exception as e:
            _backup_fail["at"] = time.time()
            if _backup_fail["date"] != now.date():   # say it once a day in the server log
                _backup_fail["date"] = now.date()
                events.say(_s("Backup failed: {error}", error=e))
            return
        events.say(_s("Backup created: {name} ({size} KB) in {folder}", name=res["name"], size=res["size"] // 1024,
                      folder=backup.folder(cfg)))


def _tidy_daily():
    """Once a day tidy up logs, history and image cache (tasks.tidy)."""
    today = dt.date.today()
    if _tidy_day["date"] != today:
        _tidy_day["date"] = today
        from .tasks import tidy
        tidy()


def _plays_snapshot_daily():
    """Once a day (at the time of the refresh, otherwise from 05:30 on) remember the play counts for the recap."""
    now = dt.datetime.now()
    at = load_config()["settings"].get("dailyAt") or "05:30"
    try:
        hh, mm = (int(x) for x in at.split(":"))
    except ValueError:
        hh, mm = 5, 30
    if (now.hour, now.minute) < (hh, mm) or _plays_day["date"] == now.date():
        return
    _plays_day["date"] = now.date()
    try:
        rueckblick.snapshot_all()
    except Exception:   # the recap must not disturb anything else
        pass


_night = {"end": None}


def _hm(value, default):
    try:
        hh, mm = (int(x) for x in str(value).split(":"))
        return hh, mm
    except (TypeError, ValueError):
        return default


def _night_analysis():
    """Night analysis: within the set time window (default 01:00–05:00) analyze open songs – own measurement, then
    AI. Without a time limit, but ending at the latest at the end of the window and 10 minutes before the daily
    refresh. Once per night (even if someone cancels the run)."""
    st = load_config()["settings"]
    an = st.get("analysis") or {}
    night = an.get("night") or {}
    if not night.get("enabled", True) or RUNNER.running():
        return
    now = dt.datetime.now()
    start, end = _hm(night.get("from"), (1, 0)), _hm(night.get("to"), (5, 0))
    t = (now.hour, now.minute)
    if not (start <= t < end if start < end else (t >= start or t < end)):
        return
    window = now.replace(hour=end[0], minute=end[1], second=0, microsecond=0)
    if window <= now:
        window += dt.timedelta(days=1)
    if _night["end"] == window:
        return   # already ran this night
    until = window
    if st.get("dailyMode", "playlists") != "aus":
        hh, mm = _hm(st.get("dailyAt"), (5, 30))
        daily = now.replace(hour=hh, minute=mm, second=0, microsecond=0)
        if daily <= now:
            daily += dt.timedelta(days=1)
        until = min(until, daily - dt.timedelta(minutes=10))
    if until - now < dt.timedelta(minutes=10):
        return
    cfg = load_config()
    lib = CACHE.get()
    from . import albumcover
    covers = (cfg["settings"].get("covers") or {}).get("enabled", True) and albumcover.due()   # once a week
    from . import fingerprint, lautstaerke
    analyse = ((an.get("enabled", True) and (audio.pending(cfg, lib) or ml.pending(cfg, lib))) or lautstaerke.pending(cfg, lib)
               or fingerprint.pending(cfg, lib))
    # refresh Deezer ranks: a portion every night (deezer.REFRESH_PER_RUN) when there are accounts to rate with
    dz = deezer.settings(cfg)
    refresh = dz.get("refresh", True) and any(user_password(load_env(), u) for u in rating_users(load_env(), cfg))
    if not covers and not analyse and not refresh:
        _night["end"] = window
        return
    try:
        steps = (["cover"] if covers else []) + (["deezer"] if refresh else []) + (["analyse"] if analyse else [])
        name = (_s("Sound analysis (at night)") if analyse else _s("Refresh Deezer (at night)") if refresh
                else _s("Missing covers (at night)"))
        RUNNER.start(steps, name=name, night_until=until.timestamp(), deezer_mode="refresh")
    except RuntimeError:
        return   # something else is running right now -> try again in a minute
    _night["end"] = window


def _daily_state():
    try:
        return json.loads(read_text(DAILY_FILE))
    except (OSError, ValueError):
        return {}


def daily_loop():
    """As long as the server runs (e.g. in the Docker container): once a day at the set time refresh mixes and
    seasons – or update everything."""
    while True:
        time.sleep(60)
        try:
            heartbeat()
            _safe(_tidy_daily)   # own logs and caches – even when the container is otherwise in charge
            _safe(stats.purge)   # do not keep song lists of other accounts in memory permanently
            if not IN_DOCKER and any(o["docker"] for o in other_instances()):
                continue   # the container on the NAS is in charge
            _plays_snapshot_daily()
            _safe(_backup_daily)   # only the instance in charge (not on the PC while a container is running)
            _safe(lambda: watch.check(RUNNER))   # folder watch (only when turned on)
            _safe(_night_analysis)
            st = load_config()["settings"]
            mode, at = st.get("dailyMode", "playlists"), st.get("dailyAt") or "05:30"
            if mode == "aus":
                continue
            now = dt.datetime.now()
            hh, mm = (int(x) for x in at.split(":"))
            if (now.hour, now.minute) < (hh, mm) or RUNNER.running():
                continue
            state = _daily_state()
            attempt = 1
            if state.get("date") == now.date().isoformat():
                if state.get("result") is None and _is_daily(RUNNER.name) and RUNNER.finished_at:
                    state["result"] = "fehler" if "fehler" in RUNNER.results.values() else "ok"
                    write_atomic(DAILY_FILE, json.dumps(state))
                # failed (e.g. Navidrome not reachable right now): up to 4 attempts 15 minutes apart
                if not (state.get("result") == "fehler" and state.get("attempt", 1) < 4
                        and time.time() - state.get("at", 0) > 900):
                    continue
                attempt = state.get("attempt", 1) + 1
            steps = pipeline() if mode == "alles" else ["playlists", "scan"]   # i18n-ignore
            try:
                RUNNER.start(steps, name=_daily_name(mode, attempt))
            except RuntimeError:
                continue   # something else is running right now -> try again in a minute
            write_atomic(DAILY_FILE, json.dumps({"date": now.date().isoformat(), "mode": mode, "attempt": attempt,
                                                 "at": time.time()}))
        except Exception:   # the schedule must never disturb the server
            continue


def _daily_name(mode, attempt):
    """Name of the daily refresh run (shown in the history)."""
    if mode == "alles":   # i18n-ignore
        return (_s("Daily refresh (everything) – attempt {n}", n=attempt) if attempt > 1
                else _s("Daily refresh (everything)"))
    return _s("Daily refresh – attempt {n}", n=attempt) if attempt > 1 else _s("Daily refresh")


def _is_daily(name):
    """Is this run the daily refresh? Its name starts with "Daily refresh" in any language (the server language
    can change while it runs)."""
    return str(name or "").startswith(tuple(i18n.tr("Daily refresh", lang) for lang in i18n.LANGS))


def _who(user):
    """Account for the server log – the sign-in name comes from outside: without control characters (a line break
    would fake a log line of its own), at most 64 characters."""
    if user == auth.NOTFALL:
        return _s("Local administrator")
    text = events.clean(user or "?", keep_lines=False)
    return text[:64] + "…" if len(text) > 64 else text or "?"


def startup_report():
    """Lines for the log at startup: version, storage locations, Navidrome, AI, schedules."""
    from .version import VERSION
    cfg = load_config()
    st = cfg["settings"]
    out = [_s("Tuttiphon {version} is starting in the Docker container", version=VERSION) if IN_DOCKER
           else _s("Tuttiphon {version} is starting", version=VERSION)]
    p = paths(cfg)
    for label, path in ((_s("Data"), DATA_DIR), (_s("Music"), p["music"]), ("Playlists", playlists.playlist_dir(cfg)),
                        (_s("Archive"), p["archive"]), (_s("Backups"), backup.folder(cfg))):
        if path.is_dir():
            state = _s("writable") if os.access(path, os.W_OK) else _s("NOT writable")
        elif path.parent.is_dir() and os.access(path.parent, os.W_OK):
            state = _s("created when needed")
        else:
            state = _s("MISSING")
        out.append("  " + label + f": {path} – " + state)   # + keeps the English form for the server log
    env = load_env()
    url = env.get("NAV_URL") or _s("address missing (Settings → Navidrome)")
    out.append("  Navidrome: " + url if env.get("NAV_ADMIN_USER")
               else _s("  Navidrome: {url} – admin access not entered yet", url=url))
    ok, why = ml.available()
    out.append(_s("  AI sound analysis: {state}", state=_s("ready") if ok else why))
    an = st.get("analysis") or {}
    night = an.get("night") or {}
    modes = {"playlists": _s("refresh playlists"), "alles": _s("update everything"), "aus": _s("off")}   # i18n-ignore
    parts = [_s("  Daily at {time}: {what}", time=st.get("dailyAt") or "05:30", what=modes.get(st.get("dailyMode", "playlists"), "?"))]
    if night.get("enabled", True) and an.get("enabled", True):
        parts.append(_s("night analysis {start}–{end}", start=night.get("from") or "01:00", end=night.get("to") or "05:00"))
    if (st.get("watch") or {}).get("enabled"):
        parts.append(_s("folder watch on"))
    out.append(i18n.join(" · ", parts))
    return out


class _ServerV6(ThreadingHTTPServer):
    address_family = socket.AF_INET6


def serve(host="127.0.0.1", port=8765, strict=True):
    """strict: bound to a network address, sign-in is required at all times (tuttiphon.py --unsafe-no-password: off)."""
    Handler.network = strict and host not in LOOPBACK
    try:   # a damaged config.json: do not start (nothing may overwrite it) – with a clear message instead of errors everywhere
        load_config()
    except ConfigDamaged as e:
        raise SystemExit(f"✕ {e}") from None
    server = (_ServerV6 if ":" in host else ThreadingHTTPServer)((host, port), Handler)   # "::1" / "::" = IPv6
    server.daemon_threads = True
    warm_up()
    if env_var("NO_SCHEDULER") == "1":   # only for testing: no schedules, no watching
        return server
    heartbeat()
    threading.Thread(target=lambda: _safe(rueckblick.snapshot_all), daemon=True).start()   # recap: count from now on
    threading.Thread(target=daily_loop, daemon=True).start()
    return server
