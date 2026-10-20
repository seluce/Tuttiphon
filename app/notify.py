"""Notifications to the phone – through the app itself (web push, webpush.py) and/or ntfy (ntfy.sh or an own ntfy
server, the ntfy app on the phone).

* The administrator turns them on (settings.notify) and chooses server, topic and events: run failed, new music
  processed, new bands classified.
* Every person can enter their own topic in the profile (person.push) and gets their messages there: news from their
  favorite bands, "Your October is here" and on Mondays "New for you this week" (discovered for you, album of the
  week).
* For protected topics on an own server: access token in .env (NTFY_TOKEN).
* Every event goes out at most once (state/notified.json).
"""
import datetime as dt
import json
import threading
import urllib.error
import urllib.request

from .config import STATE_DIR, load_config, load_env, read_text, write_atomic
from .i18n import _, _s, _sn

SENT_FILE = STATE_DIR / "notified.json"
EVENTS = ("failed", "newMusic", "autoAssigned", "favorites", "review", "weekly")
_lock = threading.RLock()   # reentrant: once() may call once() again inside a delivery
# Names of the runs the folder watch starts for new music (watch.py) – German in older history entries
NEW_MUSIC_RUNS = ("Neue Musik", "Process new music")   # i18n-ignore


def settings(cfg=None):
    cfg = cfg or load_config()
    return cfg["settings"].get("notify") or {}


def wants(cfg, event):
    st = settings(cfg)
    return bool(st.get("enabled")) and (st.get("events") or {}).get(event, True)


def send(topic, title, message, tags=(), path="", cfg=None):
    """Send a message to a topic. path: target in Tuttiphon when tapped, e.g. "#/playlists". -> True/False"""
    st = settings(cfg)
    if not topic:
        return False
    server = (st.get("server") or "https://ntfy.sh").rstrip("/")
    body = {"topic": topic, "title": title[:200], "message": message[:3000]}
    if tags:
        body["tags"] = list(tags)
    if st.get("url"):
        body["click"] = st["url"].rstrip("/") + "/" + path.lstrip("/") if path else st["url"]
    headers = {"Content-Type": "application/json", "User-Agent": "Tuttiphon"}
    token = load_env().get("NTFY_TOKEN")
    if token and server.startswith("https://"):   # never send the token unencrypted
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(server, data=json.dumps(body).encode(), headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return 200 <= r.status < 300
    except (urllib.error.URLError, OSError, ValueError):
        return False


def deliver(title, message, tags=(), path="", cfg=None, topic=None, accounts=(), admins=False, tag=None):
    """Deliver through every channel: ntfy topic (if given) and the devices of these accounts or of the administrators.
    -> True if it arrived anywhere."""
    from . import webpush
    ok = bool(topic) and send(topic, title, message, tags, path, cfg)
    return webpush.send_to(title, message, path, accounts=accounts, admins=admins, tag=tag) or ok


def test(topic=None, cfg=None, fallback=True):
    """Test message – to the given topic or (fallback, only for administrators) the administrator's.
    -> {"ok", "error"?}"""
    st = settings(cfg)
    topic = topic or (st.get("topic") if fallback else None)
    if not topic:
        return {"ok": False, "error": _("No topic entered.")}
    ok = send(topic, "Tuttiphon", _("This is what notifications from Tuttiphon look like."), ("musical_note",), cfg=cfg)
    return {"ok": ok} if ok else {"ok": False, "error": _("The ntfy server did not accept the message.")}


# ---------------------------------------------------------------------------- once per event

def _load():
    try:
        data = json.loads(read_text(SENT_FILE))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def once(key, deliver=None):
    """Event not reported yet? Without deliver: True and remember it. With deliver (function -> True/False): call it and
    only remember the event if the message arrived – otherwise try again next time. -> reported?"""
    with _lock:
        if key in _load():
            return False
        ok = deliver() if deliver else True
        if not ok:
            return False
        data = _load()
        cutoff = (dt.date.today() - dt.timedelta(days=400)).isoformat()
        data = {k: v for k, v in data.items() if v >= cutoff}
        data[key] = dt.date.today().isoformat()
        try:
            write_atomic(SENT_FILE, json.dumps(data))
        except OSError:
            pass
        return True


# ---------------------------------------------------------------------------- Events

def after_run(entry, cfg=None):
    """After every run: errors, new music and newly classified bands to the administrator."""
    cfg = cfg or load_config()
    st = settings(cfg)
    if not st.get("enabled") or entry.get("dryRun"):
        return
    from .tasks import STEP_TITLES
    topic = st.get("topic")

    def to_admin(title, message, tags, path):   # the administrator's ntfy topic and all administrator devices
        return deliver(title, message, tags, path, cfg, topic=topic, admins=True)
    results = entry.get("results") or {}
    # step titles in the server language – they are also part of the "failed|…" key (German as before)
    failed = [_s(STEP_TITLES[s]) if s in STEP_TITLES else s for s, r in results.items() if r == "fehler"]   # i18n-ignore
    name = entry.get("name") or _s("Run")
    if failed and wants(cfg, "failed"):   # the same error at most once a day (the night runs repeat themselves)
        once(f"failed|{dt.date.today()}|{'+'.join(sorted(failed))}",
             lambda: to_admin(_s("Tuttiphon: {name} failed", name=name), _s("Errors in: {steps}", steps=", ".join(failed)),
                              ("warning",), "#/verlauf"))
    done = bool(results) and all(r in ("ok", "warnung") for r in results.values())   # cancelled is not done
    if name.startswith(NEW_MUSIC_RUNS) and done and wants(cfg, "newMusic"):
        to_admin(_s("Tuttiphon: New music has arrived"), _s("{name} – done, playlists are up to date.", name=name),
                 ("headphones",), "#/")
    welten = (entry.get("summary") or {}).get("welten") or []
    if welten and wants(cfg, "autoAssigned"):
        to_admin(_sn(len(welten), "Tuttiphon: {n} new music world", "Tuttiphon: {n} new music worlds"), ", ".join(welten),
                 ("sparkles",), "#/welten")
    bands = ((entry.get("summary") or {}).get("analyse") or {}).get("assignedBands") or []
    if bands and wants(cfg, "autoAssigned"):
        names = {w["id"]: w["name"] for w in cfg["welten"]}
        lines = [f"{a} → {names.get(w, w)}" for a, w in bands[:10]]
        to_admin(_sn(len(bands), "Tuttiphon: {n} new band classified", "Tuttiphon: {n} new bands classified"),
                 "\n".join(lines), ("sparkles",), "#/")


def for_persons(cfg, lib, today=None):
    """After the scan: news from the favorite bands and the new monthly recap – per person to their own topic."""
    if not settings(cfg).get("enabled"):
        return 0
    from . import rules
    today = today or dt.date.today()
    sent = 0
    ctx = rules.BuildContext(lib)
    from . import webpush
    for person in cfg["personen"]:
        topic = person.get("push")
        if not topic and not webpush.devices(person.get("user")):
            continue
        if wants(cfg, "favorites"):
            sent += _favorites(cfg, lib, ctx, person, topic, today)
        if wants(cfg, "review"):
            sent += _review(cfg, lib, person, topic, today)
        if wants(cfg, "weekly"):
            sent += _weekly(cfg, lib, person, topic, today)
    return sent


def _favorites(cfg, lib, ctx, person, topic, today):
    from . import rules
    favs = set(rules.favorite_artists(cfg, person, ctx))
    if not favs:
        return 0
    since = (today - dt.timedelta(days=3)).isoformat()
    sent = 0
    for album in lib.albums().values():
        if (album.get("created") or "")[:10] < since or album.get("artist") not in favs:
            continue
        title = _s("New from {artist}", artist=album['artist'])
        text = _s("“{album}” is now in your library.", album=album.get('name') or _s("New album"))

        def go(title=title, text=text, album=album):
            ok = bool(topic) and send(topic, title, text, ("cd",), "#/", cfg)
            account = (person.get("user") or "").lower()
            if account:   # devices of the account: once per album, even if several people share the account
                from . import webpush
                ok = once(f"favpush|{account}|{album['id']}",
                          lambda: webpush.send_to(title, text, "#/", accounts=[account], tag=f"fav-{album['id']}")) or ok
            return ok
        sent += once(f"fav|{person['id']}|{album['id']}", go)
    return sent


def _review(cfg, lib, person, topic, today):
    from . import rules
    from .mixer import mix_day
    mine = [p for p in cfg["playlists"] if p.get("review") and _of(cfg, p) == person["id"]
            and p.get("status", "aktiv") == "aktiv" and (p["review"].get("period") or "month") == "month"]
    if not mine:
        return 0
    day = mix_day()
    if day.day > 3:   # only in the first days of the month – otherwise the message would come mid-month when first set up
        return 0
    p = mine[0]
    name = rules.review_name(cfg, p, day)
    title, text = _s("{name} is here", name=name), _s("Your most played songs of last month – now in Symfonium.")
    return _to_person(f"review|{person['id']}|{day:%Y-%m}", f"reviewpush|{{account}}|{day:%Y-%m}", title, text,
                      ("calendar",), f"#/playlist/{p['id']}", cfg, person, topic, tag=f"review-{p['id']}")


def _of(cfg, playlist):
    """Id of the person a playlist is for (without "person": the default person)."""
    return playlist.get("person") or cfg["settings"].get("defaultPerson")


def _to_person(key, device_key, title, text, tags, path, cfg, person, topic, tag):
    """A message to one person: their ntfy topic once per `key`, the devices of their account once per `device_key`
    ("{account}" filled in) – so the devices get it once, even if several people share the account. -> 1/0"""
    from . import webpush

    def go():
        ok = bool(topic) and send(topic, title, text, tags, path, cfg)
        account = (person.get("user") or "").lower()
        if account:
            ok = once(device_key.format(account=account),
                      lambda: webpush.send_to(title, text, path, accounts=[account], tag=tag)) or ok
        return ok
    return int(once(key, go))


def _weekly_parts(cfg, lib, person, start, state, index):
    """What is new for a person this week: [(playlist, text)] – "Discovered for you" first, then the album of the week,
    each only if it renews weekly and was written for this week."""
    from . import mixer, rules
    mine = [p for p in cfg["playlists"] if _of(cfg, p) == person["id"] and p.get("status", "aktiv") == "aktiv"
            and (p.get("unheard") or p.get("album")) and mixer.options(p).get("every") == "week"]
    out = []
    for p in sorted(mine, key=lambda p: not p.get("unheard")):
        saved = state.get(p["id"]) or {}
        ids = [sid for sid in saved.get("ids") or [] if sid in index]
        if saved.get("day") != start.isoformat() or not ids:
            continue   # not written for this week (yet)
        name = rules.playlist_name(cfg, p)
        if p.get("album"):
            s = lib.songs[index[ids[0]]]
            out.append((p, _s("{name}: {artist} – {album}", name=name, artist=s.get("displayAlbumArtist") or lib._main_artist(s) or "?",
                              album=s.get("album") or "?")))
        else:
            out.append((p, _sn(len(ids), "{name}: {n} song you have never heard", "{name}: {n} songs you have never heard",
                               name=name)))
    return out


def _weekly(cfg, lib, person, topic, today):
    """Monday: what is new for the person this week – "Discovered for you" and the album of the week, as written for
    this week (state/mixes.json). Once per person and week; the devices of an account once per week with what is new
    for all its people. Not later in the week (e.g. when first set up)."""
    from . import mixer, webpush
    day = mixer.mix_day()
    if day.weekday() > 1:   # Monday, Tuesday as a fallback if the Monday run did not happen
        return 0
    start = mixer.period_start("week", day)
    state = mixer._load_state()
    index = lib.index_of()
    parts = _weekly_parts(cfg, lib, person, start, state, index)
    if not parts:
        return 0
    year, week, _wd = start.isocalendar()
    title = _s("New for you this week")
    account = (person.get("user") or "").lower()

    def go():
        ok = bool(topic) and send(topic, title, " · ".join(t for _p, t in parts), ("sparkles",),
                                  f"#/playlist/{parts[0][0]['id']}", cfg)
        if account:   # the devices of the account: once, with what is new for each of its people
            default = cfg["settings"].get("defaultPerson")
            same = sorted((x for x in cfg["personen"] if (x.get("user") or "").lower() == account),
                          key=lambda x: x["id"] == default)
            every = [pt for x in same for pt in (parts if x["id"] == person["id"]
                                                  else _weekly_parts(cfg, lib, x, start, state, index))]
            ok = once(f"weeklypush|{account}|{year}-{week}", lambda: webpush.send_to(
                title, " · ".join(t for _p, t in every), f"#/playlist/{every[0][0]['id']}", accounts=[account],
                tag=f"weekly-{account}")) or ok
        return ok
    return int(once(f"weekly|{person['id']}|{year}-{week}", go))
