"""Login, roles and permissions.

* Every person logs in with their Navidrome account (the same as in Symfonium) – Tuttiphon checks the password
  directly with Navidrome and does not have to manage any passwords itself.
* Roles: Navidrome administrators are administrators in Tuttiphon, everyone else is a user.
  Settings → Users & permissions changes this per account (also “no access”).
* Local administrator: Tuttiphon's own administrator – password set in the browser at the first start or as
  TUTTIPHON_ADMIN_PASSWORD (docker-compose), see app/localadmin.py. No Navidrome account, so it also works when
  Navidrome is not reachable. Internally the user "@notfall".
* Without such a password (Tuttiphon only locally on the PC) there is no login; you are administrator.
"""
import base64
import hashlib
import hmac
import json
import re
import secrets
import threading
import time

from . import localadmin
from .config import (STATE_DIR, load_config, load_env, pass_key, read_text, save_env, update_config, user_password,
                     write_atomic)
from .i18n import _
from .navidrome import Navidrome, NavidromeError

SESSION_DAYS = 90
NOTFALL = "@notfall"
ROLES = ("admin", "user", "none")
_local = threading.local()
_users = {"at": 0.0, "list": []}
_ulock = threading.Lock()


class LoginError(Exception):
    def __init__(self, message, counts=True):
        super().__init__(message)
        self.counts = counts   # counts toward the lockout after failed attempts (not: Navidrome gone, field empty)


def required(env=None):
    return localadmin.configured(env)


def _secret():
    path = STATE_DIR / "secret"
    if not path.exists():
        STATE_DIR.mkdir(exist_ok=True)
        write_atomic(path, secrets.token_hex(32), mode=0o600)
    return read_text(path).strip()


def _sign(payload):
    return hmac.new(_secret().encode(), payload.encode(), hashlib.sha256).hexdigest()


# Every login gets a session id that the server keeps in state/sessions.json. So “log out” really ends exactly
# this session (deleting only the cookie would leave a copied token valid).
SESSIONS_FILE = STATE_DIR / "sessions.json"
_sessions_cache = {"key": None, "data": {}}
_slock = threading.Lock()


def _load_sessions():
    try:
        st = SESSIONS_FILE.stat()
        key = (st.st_mtime_ns, st.st_size)
    except OSError:
        return {}
    if _sessions_cache["key"] != key:
        try:
            data = json.loads(read_text(SESSIONS_FILE))
        except (OSError, ValueError):
            return _sessions_cache["data"]   # briefly unreadable (NFS): last state
        _sessions_cache.update(key=key, data=data if isinstance(data, dict) else {})
    return _sessions_cache["data"]


def _save_sessions(data):
    now = time.time()
    data = {k: v for k, v in data.items() if isinstance(v, dict) and v.get("e", 0) > now}   # drop expired ones
    write_atomic(SESSIONS_FILE, json.dumps(data), mode=0o600)
    _sessions_cache.update(key=None, data=data)


def _notfall_mark():
    """Mark of the current administrator password: when it changes, all sessions of the local administrator end."""
    return _sign("notfall:" + localadmin.identity())[:16]


def make_token(user, days=SESSION_DAYS):
    sid = secrets.token_urlsafe(12)
    exp = int(time.time()) + days * 86400
    with _slock:
        data = dict(_load_sessions())
        data[sid] = {"u": user, "e": exp}
        if user == NOTFALL:
            data[sid]["p"] = _notfall_mark()
        _save_sessions(data)
    payload = base64.urlsafe_b64encode(json.dumps({"u": user, "e": exp, "s": sid}).encode()).decode().rstrip("=")
    return f"{payload}.{_sign(payload)}"


def _decode(token):
    try:
        payload, sig = (token or "").rsplit(".", 1)
        if not hmac.compare_digest(_sign(payload).encode(), sig.encode("utf-8", "replace")):
            return None
        data = json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))
    except (ValueError, TypeError):
        return None
    if not isinstance(data, dict) or data.get("e", 0) < time.time() or not isinstance(data.get("u"), str):
        return None
    return data


def read_token(token):
    """-> user name or None (invalid, expired or logged out)."""
    data = _decode(token)
    if not data:
        return None
    sess = _load_sessions().get(str(data.get("s") or ""))
    if not sess or sess.get("u") != data["u"]:
        return None
    if data["u"] == NOTFALL and sess.get("p") != _notfall_mark():
        return None   # administrator password changed in the meantime
    return data["u"]


def end_sessions_of(user):
    """End all sessions of an account (e.g. when it should no longer have access)."""
    low = (user or "").lower()
    with _slock:
        sessions = dict(_load_sessions())
        kept = {k: v for k, v in sessions.items() if str(v.get("u", "")).lower() != low}
        if len(kept) != len(sessions):
            _save_sessions(kept)


def end_session(token):
    """Log out: end the session of this token."""
    data = _decode(token)
    if not data or not data.get("s"):
        return
    with _slock:
        sessions = dict(_load_sessions())
        if sessions.pop(data["s"], None) is not None:
            _save_sessions(sessions)


# ---------------------------------------------------------------------------- Navidrome accounts

USERS_FILE = STATE_DIR / "navidrome_users.json"


def navidrome_users(force=False):
    """[{name, admin, fullName}] – cached for 10 minutes (via the admin access). If Navidrome is not reachable, the
    last state applies – also across a restart (state/navidrome_users.json), so admins do not suddenly count as
    users then."""
    with _ulock:
        if not force and _users["list"] and time.time() - _users["at"] < 600:
            return _users["list"]
        if not force and time.time() - _users.get("failed", 0) < 60:
            return _users["list"]   # just failed: do not ask again with every request
    try:
        from .playlists import native_api
        lst = [{"name": u["userName"], "admin": bool(u.get("isAdmin")), "fullName": u.get("name") or u["userName"]}
               for u in native_api(load_env()).users()]
    except Exception:   # noqa: BLE001 – Navidrome gone, timeout, restart, broken answer: last state
        with _ulock:
            _users["failed"] = time.time()
            if not _users["list"]:
                try:
                    _users["list"] = json.loads(read_text(USERS_FILE))
                except (OSError, ValueError):
                    pass
            return _users["list"]
    with _ulock:
        changed = lst != _users["list"]
        _users.update(at=time.time(), list=lst)
    if changed:
        try:
            write_atomic(USERS_FILE, json.dumps(lst, ensure_ascii=False))
        except OSError:
            pass
    return lst


def _account(cfg, user):
    return (cfg.get("accounts") or {}).get((user or "").lower(), {})


def role_of(user, cfg=None):
    if user == NOTFALL:
        return "admin"
    cfg = cfg or load_config()
    users = navidrome_users()
    nav = next((u for u in users if u["name"].lower() == user.lower()), None)
    if users and nav is None:
        return "none"   # the account does not exist in Navidrome (any more) – then no access to Tuttiphon either
    acc = _account(cfg, user)
    if acc.get("role") in ROLES:
        return acc["role"]
    return "admin" if nav and nav["admin"] else "user"


def persons_of(user, cfg):
    """Own people – the shared default person (e.g. “Familie”) last, so the personal profile comes first."""
    default = cfg.get("settings", {}).get("defaultPerson")
    own = [p["id"] for p in cfg.get("personen", []) if (p.get("user") or "").lower() == (user or "").lower()]
    return sorted(own, key=lambda pid: pid == default)


SEEN_FILE = STATE_DIR / "seen.json"          # {"tour": [account, …], "welcome": [account, …]}
TOUR_FILE = STATE_DIR / "tour_seen.json"     # older version (tour only) – read as well
SEEN_KINDS = ("tour", "welcome")
_seen_cache = {"key": None, "seen": {}}


def _stamp(path):
    try:
        st = path.stat()
        return st.st_mtime_ns, st.st_size
    except OSError:
        return None


def _seen():
    """What which accounts have already seen (tour, welcome assistant) – in memory until the file changes;
    me() runs with every request."""
    key = (_stamp(SEEN_FILE), _stamp(TOUR_FILE))
    if _seen_cache["key"] != key:
        out = {k: set() for k in SEEN_KINDS}
        try:
            data = json.loads(read_text(SEEN_FILE)) if key[0] else {}
            for k in SEEN_KINDS:
                out[k] |= set(data.get(k, [])) if isinstance(data, dict) else set()
        except (OSError, ValueError):
            return _seen_cache["seen"] or out
        try:
            old = json.loads(read_text(TOUR_FILE)) if key[1] else []
            out["tour"] |= set(old) if isinstance(old, list) else set()
        except (OSError, ValueError):
            pass
        _seen_cache.update(key=key, seen=out)
    return _seen_cache["seen"]


def mark_seen(user, kind):
    """Remember for this account that the tour or the welcome assistant is done – on the server, so they do not come
    back on any device or under any address (IP or domain via the reverse proxy)."""
    if kind not in SEEN_KINDS:
        raise ValueError(_("Unknown"))
    seen = _seen()
    who = (user or "").lower()
    if who in seen[kind]:
        return
    data = {k: sorted(v | ({who} if k == kind else set())) for k, v in seen.items()}
    write_atomic(SEEN_FILE, json.dumps(data, ensure_ascii=False))


def mark_tour_seen(user):
    mark_seen(user, "tour")


def me(user, cfg=None):
    """Who is logged in? user=None: no login needed (local) -> administrator."""
    cfg = cfg or load_config()
    if user is None:
        return {"user": None, "name": "", "role": "admin", "local": True, "persons": [p["id"] for p in cfg["personen"]],
                "own": [p["id"] for p in cfg["personen"]], "tourSeen": "" in _seen()["tour"], "welcomeSeen": True}
    role = role_of(user, cfg)
    own = persons_of(user, cfg)
    # the local administrator is meant precisely for “Navidrome gone” – do not look it up for that
    nav = None if user == NOTFALL else next((u for u in navidrome_users() if u["name"].lower() == user.lower()), None)
    name = "Administrator" if user == NOTFALL else (nav or {}).get("fullName") or user
    stored = bool(user_password(load_env(), user)) if user != NOTFALL else True
    if stored and user != NOTFALL:
        check_password_soon(user)
    return {"user": user, "name": name.split(" ")[0] if name else user, "fullName": name, "role": role, "local": False,
            "persons": [p["id"] for p in cfg["personen"]] if role == "admin" else own, "own": own,
            "notfall": user == NOTFALL, "passwordStored": stored,
            "passwordRejected": stored and user != NOTFALL and password_rejected(user),
            "tourSeen": user.lower() in _seen()["tour"], "welcomeSeen": user.lower() in _seen()["welcome"]}


# ---------------------------------------------------------------------------- does the stored password still work?
# The password an account stored for statistics & stars can change in Navidrome. Tuttiphon remembers whether
# Navidrome last accepted it (state/passwords.json: {account: {"ok": true/false, "at": time}} – no passwords) and
# checks it in the background at most every CHECK_EVERY seconds. Unknown (Navidrome not reachable) never counts as
# rejected.

PASSWORDS_FILE = STATE_DIR / "passwords.json"
CHECK_EVERY = 6 * 3600
_pw = {"key": None, "data": {}, "checking": {}}
_pw_lock = threading.Lock()


def wrong_password(e):
    """Is this Navidrome error “wrong user name or password” (Subsonic error 40/41 – by its code; the message is
    translated)?"""
    return getattr(e, "code", None) in (40, 41) or bool(re.search(r"(Fehler|error) 4[01]\b", str(e), re.IGNORECASE))   # i18n-ignore


def _pw_state():
    key = _stamp(PASSWORDS_FILE)
    if _pw["key"] != key:
        try:
            data = json.loads(read_text(PASSWORDS_FILE)) if key else {}
        except (OSError, ValueError):
            data = {}
        _pw.update(key=key, data=data if isinstance(data, dict) else {})
    return _pw["data"]


def password_rejected(user):
    """Did Navidrome reject the stored password of this account the last time it was used or checked?"""
    entry = _pw_state().get((user or "").lower())
    return isinstance(entry, dict) and entry.get("ok") is False


def note_password(user, ok):
    """Remember that the stored password of this account works (True) or that Navidrome rejected it (False);
    ok=None forgets it (a new password was entered and has not been tried yet)."""
    if not user or user == NOTFALL:
        return
    low = user.lower()
    with _pw_lock:
        data = dict(_pw_state())
        old = data.get(low) if isinstance(data.get(low), dict) else {}
        if ok is None:
            if low not in data:
                return
            data.pop(low)
            _pw["checking"].pop(low, None)
        elif old.get("ok") is ok and time.time() - old.get("at", 0) < CHECK_EVERY / 2:
            return   # nothing new – spare the file
        else:
            data[low] = {"ok": bool(ok), "at": int(time.time())}
        try:
            write_atomic(PASSWORDS_FILE, json.dumps(data, ensure_ascii=False))
        except OSError:
            pass


def check_password_soon(user, env=None):
    """In the background: does Navidrome still accept the stored password of this account? At most every
    CHECK_EVERY seconds per account (me() and the status ask often)."""
    env = env if env is not None else load_env()
    pw = user_password(env, user)
    if not pw or not user or user == NOTFALL or not env.get("NAV_URL"):
        return
    low = user.lower()
    now = time.time()
    with _pw_lock:
        entry = _pw_state().get(low) if isinstance(_pw_state().get(low), dict) else {}
        if now - max(entry.get("at", 0), _pw["checking"].get(low, 0)) < CHECK_EVERY:
            return
        _pw["checking"][low] = now

    def run():
        try:
            Navidrome(env["NAV_URL"], user, pw).ping()
        except NavidromeError as e:
            if wrong_password(e):
                note_password(user, False)
            return   # otherwise not reachable right now: unknown, again next time
        except Exception:   # noqa: BLE001 – a background check must never disturb anything
            return
        note_password(user, True)
    threading.Thread(target=run, daemon=True, name="password-check").start()


# ---------------------------------------------------------------------------- login

def login(username, password, remember=True):
    """-> user name (spelled as in Navidrome) or LoginError."""
    env = load_env()
    username = (username or "").strip()
    if not isinstance(password, str) or not password:
        raise LoginError(_("Please enter the password."), counts=False)
    if not username or username.lower() in ("notfall", NOTFALL):
        if localadmin.check(password, env):
            return NOTFALL
        raise LoginError(_("The administrator password is wrong."))
    try:
        Navidrome(env.get("NAV_URL", ""), username, password).ping()
    except NavidromeError as e:
        if wrong_password(e):
            raise LoginError(_("User name or password is wrong – it is the same as in Navidrome or Symfonium."))
        raise LoginError(_("Navidrome is not reachable right now. If needed, sign in as local administrator."), counts=False)
    users = navidrome_users(force=True)
    canonical = next((u["name"] for u in users if u["name"].lower() == username.lower()), username)
    cfg = load_config()
    if role_of(canonical, cfg) == "none":
        raise LoginError(_("Tuttiphon is not enabled for this account – please ask the administrator."))
    if remember and canonical.lower() != (env.get("NAV_ADMIN_USER") or "").lower():
        if env.get(pass_key(canonical)) != password:   # for personal stars, statistics and an exact preview
            save_env({pass_key(canonical): password})
    if user_password(load_env(), canonical) == password:   # the stored password has just worked
        note_password(canonical, True)

    def mark(c):
        c.setdefault("accounts", {}).setdefault(canonical.lower(), {})["lastLogin"] = time.strftime("%Y-%m-%d %H:%M")
    try:
        update_config(mark)
    except (OSError, ValueError):
        pass
    return canonical


# ---------------------------------------------------------------------------- permissions

def current():
    return getattr(_local, "me", None) or me(None)


def set_current(m):
    _local.me = m


def is_admin(m=None):
    return (m or current())["role"] == "admin"


def require_admin():
    if not is_admin():
        raise PermissionError(_("Only administrators may do this."))


def visible_playlist(p, cfg, m=None):
    """Can one see this playlist? Own ones always, others only when their person is visible to everyone."""
    m = m or current()
    pid = person_id(p, cfg)
    if m["role"] == "admin" or pid in m["own"]:
        return True
    person = next((x for x in cfg["personen"] if x["id"] == pid), None)
    if person is None:   # the person does not exist: the setting "public", like build_nsp()
        return bool(cfg["settings"].get("public", True))
    return bool(person.get("public"))


def person_id(p, cfg):
    """Person of a playlist – without one the default person (like rules.person_of)."""
    return p.get("person") or cfg["settings"].get("defaultPerson")


def own_playlist(p, m=None, cfg=None):
    m = m or current()
    return m["role"] == "admin" or person_id(p, cfg or load_config()) in m["own"]


def view_config(cfg, m=None):
    """Configuration as seen by the logged-in person (other people's private playlists hidden,
    own hide lists)."""
    m = m or current()
    if m["role"] == "admin" and m.get("local"):
        return cfg
    out = dict(cfg)
    if m["role"] != "admin":
        out["playlists"] = [p for p in cfg["playlists"] if visible_playlist(p, cfg, m)]
        out.pop("accounts", None)
        # settings only as far as the pages for users need them (no paths, accounts, owners …)
        out["settings"] = {k: v for k, v in cfg["settings"].items() if k in USER_SETTINGS}
        nt = cfg["settings"].get("notify") or {}   # for the own topic in the profile: on or off, and which server
        out["settings"]["notify"] = {"enabled": bool(nt.get("enabled")), "server": nt.get("server") or "https://ntfy.sh"}
        # people: own ones in full; others only when visible to everyone – without likes, dislikes and account names
        own = set(m["own"])
        out["personen"] = [p if p["id"] in own else {k: v for k, v in p.items() if k in PUBLIC_PERSON_FIELDS}
                           for p in cfg["personen"] if p["id"] in own or p.get("public")]
    acc = _account(cfg, m["user"])
    out["dismissed"] = acc.get("dismissed", []) if m["role"] != "admin" else cfg.get("dismissed", [])
    out["ignored"] = acc.get("ignored", []) if m["role"] != "admin" else cfg.get("ignored", [])
    if m["role"] != "admin":
        out.pop("dismissedAt", None)   # the administrator's hidden suggestions with their dates
    return out


PERSON_FIELDS = ("name", "icon", "color", "prefix", "likes", "dislikes", "public", "clean", "push", "tasteExclude")
# playlist fields that only the server or an administrator sets (handmade playlists taken over)
SERVER_PLAYLIST_FIELDS = ("rules", "rulesExtra", "sortRaw", "takeover", "originalName")
PUBLIC_PERSON_FIELDS = ("id", "name", "icon", "color", "prefix", "public")
USER_SETTINGS = ("autoApply", "defaultPerson", "namePattern", "allName", "limit", "minDuration", "allMinRating", "public",
                 "seasonRest")
# what one account may create at most – every playlist is computed for everyone's pages and every run
MAX_USER_PLAYLISTS = 200
MAX_USER_PERSONS = 20


def merge_user_changes(current_cfg, incoming, m):
    """What a user saves may only change their own things: their people (profile, likes), their playlists and
    their hide lists. Everything else stays as it is on the server."""
    import copy
    out = copy.deepcopy(current_cfg)
    user = (m["user"] or "").lower()
    own = set(m["own"])
    cur_persons = {p["id"]: p for p in out["personen"]}
    # kid-safe mode counts for the whole account: a further profile of the same account gets it too (otherwise a
    # second own profile would be a way around it)
    clean = any(p.get("clean") for p in out["personen"] if p["id"] in own or (p.get("user") or "").lower() == user)
    persons_before = sum(1 for p in out["personen"] if p["id"] in own)
    for p in incoming.get("personen", []) if isinstance(incoming.get("personen"), list) else []:
        if not isinstance(p, dict):
            continue
        if p.get("id") in own and p["id"] in cur_persons:
            was_clean = bool(cur_persons[p["id"]].get("clean"))
            for k in PERSON_FIELDS:
                if k in p:
                    cur_persons[p["id"]][k] = p[k]
            if was_clean:   # anyone may turn kid-safe mode on, only the administrator may turn it off
                cur_persons[p["id"]]["clean"] = True
        elif (isinstance(p.get("id"), str) and re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,40}", p["id"]) and p["id"] != "neu"   # i18n-ignore
              and p["id"] not in cur_persons and (p.get("user") or "").lower() == user and str(p.get("name") or "").strip()):
            if sum(1 for x in out["personen"] if x["id"] in own) >= max(MAX_USER_PERSONS, persons_before):
                raise ValueError(_("You can have at most {n} profiles.", n=MAX_USER_PERSONS))
            fresh = {k: p[k] for k in PERSON_FIELDS if k in p}   # create the own profile (welcome assistant)
            fresh.update(id=p["id"], user=m["user"])
            if clean:
                fresh["clean"] = True
            out["personen"].append(fresh)
            own.add(p["id"])
    cur_pl = {p["id"]: p for p in out["playlists"]}
    inc_list = incoming.get("playlists") if isinstance(incoming.get("playlists"), list) else []
    inc_pl = {p["id"]: p for p in inc_list if isinstance(p, dict) and p.get("id")}
    result = []
    for p in out["playlists"]:   # existing ones in their order
        new = inc_pl.get(p["id"])
        if person_id(p, out) not in own:
            result.append(p)   # someone else's: unchanged
        elif new is None:
            continue           # own one deleted
        elif person_id(new, out) in own:
            for k in SERVER_PLAYLIST_FIELDS:   # stay as they are on the server
                if k in p:
                    new[k] = p[k]
                else:
                    new.pop(k, None)
            result.append(new)
        else:
            result.append(p)   # giving it away to someone else's person is not possible
    for pid, new in inc_pl.items():   # new own ones
        if pid not in cur_pl and person_id(new, out) in own:
            for k in SERVER_PLAYLIST_FIELDS:   # only the server creates takeovers of handmade playlists (administrator)
                new.pop(k, None)
            result.append(new)
    # family mix: only own people and people visible to everyone – other private profiles stay private
    allowed = own | {p["id"] for p in out["personen"] if p.get("public")}
    for p in result:
        if person_id(p, out) in own and isinstance(p.get("together"), list):
            p["together"] = [x for x in p["together"] if x in allowed]
            if len(p["together"]) < 2:
                p.pop("together")
                # without members “All × Everything” would be invalid – then it becomes a mix by the own taste
                if p.get("welt", "*") == "*" and p.get("stil", "*") == "*" and not (p.get("radio") or p.get("fav") or p.get("review")):
                    p["type"] = "mix"
                    p["mix"] = {**(p.get("mix") if isinstance(p.get("mix"), dict) else {}), "flavor": "geschmack"}
    mine_before = sum(1 for p in current_cfg["playlists"] if person_id(p, current_cfg) in own)
    mine = sum(1 for p in result if person_id(p, out) in own)
    if mine > max(MAX_USER_PLAYLISTS, mine_before):   # more than before is only possible up to the limit
        raise ValueError(_("You can have at most {n} playlists – please delete some you no longer listen to (also from "
                           "the trash).", n=MAX_USER_PLAYLISTS))
    out["playlists"] = result
    acc = out.setdefault("accounts", {}).setdefault(user, {})
    for k in ("dismissed", "ignored"):
        if isinstance(incoming.get(k), list):
            acc[k] = [x for x in incoming[k] if isinstance(x, str)][-500:]
    from .config import stamp_dismissed
    stamp_dismissed(acc, acc.get("dismissedAt"))
    return out
