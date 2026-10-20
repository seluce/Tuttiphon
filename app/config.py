"""Paths, credentials (.env) and the configuration (config.json) including migration."""
import copy
import datetime as dt
import json
import math
import os
import re
import secrets
import string
import threading
from pathlib import Path

from .i18n import LANGS, N_, _, _s

ROOT = Path(__file__).resolve().parent.parent      # program: the project folder (/app in the container)
PREFIX = "TUTTIPHON_"   # own environment variables
# Password of the local administrator (sign-in without Navidrome, turns on sign-in)
ADMIN_PASSWORD = "TUTTIPHON_ADMIN_PASSWORD"
# placeholder in the template – with it the container refuses to start on the network
PASSWORD_PLACEHOLDERS = ("change-me",)


def weak_password(pw):
    """Too short (< 8 characters) or a template placeholder (in any spelling)."""
    return not isinstance(pw, str) or len(pw) < 8 or pw.strip().lower() in PASSWORD_PLACEHOLDERS


def env_var(name, default=None):
    """Environment variable TUTTIPHON_<name>, otherwise default."""
    return os.environ.get(PREFIX + name) or default


def admin_password(env=None):
    """Password of the local administrator ('' = none, then there is no sign-in)."""
    return (env if env is not None else load_env()).get(ADMIN_PASSWORD) or ""


# Data (configuration, credentials, state, logs, backups) – never in Git:
# on the PC data/ in the project folder (also when started without tuttiphon.sh – never the project folder itself,
# where backups with credentials could end up in Git), in the container TUTTIPHON_DATA=/config.
DATA_DIR = Path(env_var("DATA") or ROOT / "data")
# Navidrome folder: default home of Music/ and Archiv/, base for relative paths (on the PC from dev.local.env)
BASE = Path(env_var("BASE") or ROOT.parent)
CONFIG_FILE = DATA_DIR / "config.json"
DEFAULT_CONFIG_FILE = ROOT / "app" / "default_config.json"
ENV_FILE = DATA_DIR / ".env"
STATE_DIR = DATA_DIR / "state"
LOG_DIR = DATA_DIR / "logs"
BACKUP_DIR = DATA_DIR / "backup"
# Built interface (npm run build → web/). TUTTIPHON_WEB only for tests with their own build folder.
WEB_DIR = Path(env_var("WEB") or ROOT / "web")
# Storage locations: environment (docker-compose) > settings > default
PATH_ENV = {"music": "MUSIC_DIR", "playlists": "PLAYLIST_DIR", "archive": "ARCHIVE_DIR"}

MARKER = "Tuttiphon"   # start of the "comment" of every generated playlist
CONFIG_VERSION = 12

_lock = threading.RLock()


def _in_data_dir(path):
    try:
        return DATA_DIR.resolve() in Path(path).resolve().parents
    except (OSError, RuntimeError):
        return False


def write_atomic(path, data, mode=None):
    """Write safely: unique temporary file, set the permissions explicitly, then replace.
    (On the NAS share files otherwise sometimes got the permissions 000 and were unreadable.)
    Without mode: 0640 in the data folder (configuration, state – not for other users of the NAS), otherwise 0664
    (playlists and lyrics on the music share, which Navidrome reads)."""
    if mode is None:
        mode = 0o640 if _in_data_dir(path) else 0o664
    tmp = path.with_name(f".{path.name}.{os.getpid()}.{threading.get_ident()}.{secrets.token_hex(4)}.tmp")
    raw = data.encode("utf-8") if isinstance(data, str) else data
    # create it with the target permissions right away – so a file with credentials (0600) is not readable even
    # briefly. O_EXCL and O_NOFOLLOW: never write into an existing file or through a link (e.g. on the music share)
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0), mode)
    try:
        with os.fdopen(fd, "wb", closefd=False) as f:
            f.write(raw)
        os.fchmod(fd, mode)
        tmp.replace(path)
        try:
            # once more after the rename (NAS share) – through the open file, never through the path: in a shared
            # folder someone could have put a link there in the meantime
            os.fchmod(fd, mode)
        except OSError:
            pass
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise
    finally:
        os.close(fd)


def read_bytes(path, attempts=4):
    """Like read_text, for binary files (image cache)."""
    import time
    for i in range(attempts):
        try:
            return path.read_bytes()
        except (PermissionError, OSError) as e:
            if isinstance(e, FileNotFoundError) or i == attempts - 1:
                raise
            time.sleep(0.15 * (i + 1))


def read_text(path, attempts=4):
    """Read a file – on the NFS share this can fail briefly while it is being replaced."""
    import time
    for i in range(attempts):
        try:
            return path.read_text(encoding="utf-8")
        except (PermissionError, OSError) as e:
            if isinstance(e, FileNotFoundError) or i == attempts - 1:
                raise
            time.sleep(0.15 * (i + 1))


# --------------------------------------------------------------------------- credentials

def _read_env_file(path):
    values = {}
    if not path.exists():
        return values
    for line in read_text(path).splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]   # remove exactly one pair of quotes (save_env adds it when needed)
        values[key.strip()] = value
    return values


def _stamp(path):
    try:
        st = path.stat()
        return (st.st_mtime_ns, st.st_size)
    except OSError:
        return None


_env_cache = {"key": None, "env": None}


def load_env():
    """Merge the credentials: <data>/.env < environment.
    Kept in memory until the file changes (spares the NAS share)."""
    key = _stamp(ENV_FILE)
    if _env_cache["key"] == key and _env_cache["env"] is not None:
        return dict(_env_cache["env"])
    env = _load_env_files()
    _env_cache.update(key=key, env=env)
    return dict(env)


def environment():
    """Credentials and switches from the environment (docker-compose).
    Empty variables (e.g. NAV_ADMIN_PASS: "" in docker-compose) do not count: they do not override the .env."""
    return {k: v for k, v in os.environ.items() if v.strip() and (
        k.startswith(("NAV_", PREFIX)) or k in ("RATING_USERS", "LASTFM_API_KEY", "NTFY_TOKEN"))}


def _load_env_files():
    env = {k: v for k, v in _read_env_file(ENV_FILE).items() if v}
    env.update(environment())   # the environment (docker-compose) takes precedence over the .env
    env["NAV_URL"] = env.get("NAV_URL", "").rstrip("/")
    return env


def ensure_dirs():
    """Create the data folders. -> error message or None (e.g. when /config is not writable in the container)."""
    try:
        for d in (DATA_DIR, STATE_DIR, LOG_DIR, BACKUP_DIR):
            d.mkdir(parents=True, exist_ok=True)
        probe = DATA_DIR / ".schreibtest"
        probe.write_text("ok")
        probe.unlink()
    except OSError as e:
        return _s("The data folder {path} is not writable ({error}). In the container: create the folder for /config "
                  "beforehand and give the user from “user:” (e.g. 1000:1000) write access.", path=DATA_DIR, error=e.strerror)
    for secret in (ENV_FILE, STATE_DIR / "secret", STATE_DIR / "sessions.json"):   # credentials: for Tuttiphon only
        try:
            if secret.exists():
                os.chmod(secret, 0o600)
        except OSError:
            pass   # belongs to another user – Tuttiphon can still work
    return None


def paths(cfg=None):
    """Music, playlist and archive folder. Environment (docker-compose) > settings > default next to Tuttiphon.
    Relative paths: music relative to the Navidrome folder (BASE), playlists relative to the music folder, archive
    relative to its parent folder."""
    st = (cfg or load_config())["settings"]
    conf = st.get("paths") or {}
    m = os.environ.get("MUSIC_DIR") or conf.get("music")
    # relative path: to the Navidrome folder (not to the working directory of the process)
    music = (Path(m) if os.path.isabs(m) else BASE / m) if m else BASE / "Music"
    pl = os.environ.get("PLAYLIST_DIR") or conf.get("playlists")
    if pl:
        playlists = Path(pl) if os.path.isabs(pl) else music / pl
    else:   # default: in the music folder (older setting "Music/…" relative to the Navidrome folder)
        legacy = st.get("playlistDir") or "Music/00_SmartPlaylists"
        playlists = music / legacy[6:] if legacy.startswith("Music/") else BASE / legacy
    ar = os.environ.get("ARCHIVE_DIR") or conf.get("archive") or (st.get("opus") or {}).get("archiveDir") or "Archiv"
    archive = Path(ar) if os.path.isabs(ar) else music.parent / ar
    return {"music": music, "playlists": playlists, "archive": archive}


def is_inside(path, folder):
    """Is path the folder itself or inside it (symbolic links resolved)?"""
    p, f = Path(os.path.realpath(path)), Path(os.path.realpath(folder))
    return p == f or f in p.parents


def archive_in_music(cfg=None):
    """Is the archive the music folder or inside it? Then archived originals would be converted again (and the
    archive would end up inside itself)."""
    p = paths(cfg)
    return is_inside(p["archive"], p["music"])


def paths_info(cfg=None):
    """For the settings: path, origin, exists/writable."""
    cfg = cfg or load_config()
    conf = cfg["settings"].get("paths") or {}
    out = {}
    for key, path in paths(cfg).items():
        source = "docker" if os.environ.get(PATH_ENV[key]) else "einstellung" if conf.get(key) else "standard"   # i18n-ignore
        out[key] = {"path": str(path), "source": source, "exists": path.is_dir(), "writable": os.access(path, os.W_OK)}
    return out


def pass_key(user):
    return "NAV_PASS_" + re.sub(r"\W", "_", user.upper())


def user_password(env, user):
    if not user:
        return None
    if env.get(pass_key(user)):
        return env[pass_key(user)]
    if user.lower() == (env.get("NAV_ADMIN_USER") or "").lower():
        return env.get("NAV_ADMIN_PASS")
    return None


def rating_users(env, cfg=None):
    """Whom Deezer sets stars for: the setting (Deezer stars → accounts), otherwise RATING_USERS from .env, otherwise
    all Navidrome users of the people."""
    cfg = cfg or load_config()
    chosen = (cfg["settings"].get("deezer") or {}).get("users")
    if isinstance(chosen, list):
        return [u for u in chosen if isinstance(u, str) and u]
    if env.get("RATING_USERS"):
        return [u.strip() for u in env["RATING_USERS"].split(",") if u.strip()]
    users = []
    for person in cfg.get("personen", []):
        u = person.get("user")
        if u and u.lower() not in [x.lower() for x in users]:
            users.append(u)
    return users


# keys of the .env the interface may set (everything else only through docker-compose/the environment)
EDITABLE_ENV = re.compile(r"^(NAV_URL|NAV_PUBLIC_URL|NAV_ADMIN_USER|NAV_ADMIN_PASS|NAV_PASS_\w+|RATING_USERS|"
                          r"LASTFM_API_KEY|NTFY_TOKEN)$")


def save_env(updates):
    """Set single keys in <data>/.env (empty values are ignored, None deletes)."""
    allowed = EDITABLE_ENV
    with _lock:
        lines = read_text(ENV_FILE).splitlines() if ENV_FILE.exists() else []
        for key, value in updates.items():
            if not allowed.match(key):
                raise ValueError(_("Unknown key: {key}", key=key))
            if value == "":   # empty = unchanged
                continue
            if value is not None and (not isinstance(value, str) or not value.isprintable()):
                raise ValueError(_("Only plain text values without line breaks/control characters are allowed"))
            active = next((i for i, l in enumerate(lines) if re.match(rf"^\s*{re.escape(key)}=", l)), None)
            if value is None:   # delete: only a real line, never a commented-out template
                if active is not None:
                    del lines[active]
                continue
            # set: replace the existing line, otherwise a commented-out template, otherwise append
            idx = active if active is not None else next(
                (i for i, l in enumerate(lines) if re.match(rf"^\s*#\s*{re.escape(key)}=", l)), None)
            if value != value.strip() or value[:1] in "\"'" or value[-1:] in "\"'":
                value = f'"{value}"'   # this keeps spaces/quotes at the edges
            new = f"{key}={value}"
            if idx is None:
                lines.append(new)
            else:
                lines[idx] = new
        write_atomic(ENV_FILE, "\n".join(lines) + "\n", mode=0o600)


# --------------------------------------------------------------------------- configuration

_cfg_cache = {"key": None, "cfg": None, "defaults": None, "dkey": None}


def default_config():
    key = _stamp(DEFAULT_CONFIG_FILE)
    if _cfg_cache["dkey"] != key or _cfg_cache["defaults"] is None:
        _cfg_cache.update(defaults=json.loads(read_text(DEFAULT_CONFIG_FILE)), dkey=key)
    return _cfg_cache["defaults"]


def _fill(dst, defaults):
    """Fill missing settings (also nested ones, e.g. settings.lyrics.retryDays) with default values."""
    for k, value in defaults.items():
        if k not in dst:
            dst[k] = copy.deepcopy(value)
        elif isinstance(value, dict) and isinstance(dst[k], dict):
            _fill(dst[k], value)


class ConfigDamaged(ValueError):
    """config.json cannot be read as a configuration (broken JSON, wrong structure)."""


def _finite_or_none(text):
    value = float(text)
    return value if math.isfinite(value) else None


def _parse_config(text):
    """Text of config.json -> configuration (dict) or ConfigDamaged with the reason."""
    if text.startswith("﻿"):   # saved by an editor with a byte order mark
        text = text[1:]
    try:
        # NaN/Infinity (an older version let an endless number through): null – otherwise GET /api/config would not
        # be valid JSON for the interface any more; the setting then falls back to its default
        cfg = json.loads(text, parse_constant=lambda name: None, parse_float=_finite_or_none)
    except ValueError as e:
        raise ConfigDamaged(str(e)) from None
    if not isinstance(cfg, dict):
        raise ConfigDamaged(_s("not an object"))
    for k in ("settings", "welten", "stile", "playlists", "personen", "dismissed", "ignored"):
        if k in cfg and cfg[k] is None:   # “null” (edited by hand): like missing – filled in below
            del cfg[k]
    if not isinstance(cfg.get("settings", {}), dict):
        raise ConfigDamaged(_s("“{key}” has the wrong type", key="settings"))
    for k in ("welten", "stile", "playlists", "personen", "dismissed", "ignored"):
        if not isinstance(cfg.get(k, []), list):
            raise ConfigDamaged(_s("“{key}” has the wrong type", key=k))
    v = cfg.get("version", 1)
    if not isinstance(v, int) or isinstance(v, bool) or v < 1:
        raise ConfigDamaged(_s("“{key}” has the wrong type", key="version"))
    return cfg


def _migration_backup(version, text):
    """Back up config.json before a migration – a unique name (two migrations in the same second keep both)."""
    BACKUP_DIR.mkdir(exist_ok=True)
    stem = f"config_v{version}_{dt.datetime.now():%Y%m%d_%H%M%S}"
    path, n = BACKUP_DIR / f"{stem}.json", 2
    while path.exists():
        path, n = BACKUP_DIR / f"{stem}_{n}.json", n + 1
    write_atomic(path, text)   # with write_atomic (otherwise possibly permissions 000 on the NAS share)


def _damaged(key, error):
    """config.json became unreadable while Tuttiphon is running: keep working with the last good state (it is
    written back with the next save) – keep a copy of the damaged file and say so once in the server log."""
    if _cfg_cache.get("damaged") == key:
        return
    _cfg_cache["damaged"] = key
    copy_name = ""
    try:
        target = CONFIG_FILE.with_name(f"config.defekt-{dt.datetime.now():%Y%m%d-%H%M%S}.json")   # file name: data
        write_atomic(target, read_bytes(CONFIG_FILE))
        copy_name = target.name
    except OSError:
        pass
    from . import events
    events.say(_s("⚠ The configuration {file} is damaged ({error}) – Tuttiphon keeps working with the last good state "
                  "and writes it back with the next save. Copy of the damaged file: {copy}",
                  file=CONFIG_FILE, error=error, copy=copy_name or "–"))


def load_config():
    """The configuration – kept in memory until config.json changes. Always returns a copy.
    A damaged config.json: ConfigDamaged before the first good state (serve() refuses to start with a clear
    message instead of silently starting over), afterwards the last good state stays (see _damaged)."""
    with _lock:
        if not CONFIG_FILE.exists():
            write_atomic(CONFIG_FILE, read_text(DEFAULT_CONFIG_FILE))
        key = _stamp(CONFIG_FILE)
        if _cfg_cache["cfg"] is not None and _cfg_cache.get("damaged") == key:
            return copy.deepcopy(_cfg_cache["cfg"])   # still the same damaged file: do not read it again every time
        if _cfg_cache["key"] != key or _cfg_cache["cfg"] is None:
            try:
                text = read_text(CONFIG_FILE)
                cfg = _parse_config(text)
                if cfg.get("version", 1) < CONFIG_VERSION:
                    _migration_backup(cfg.get("version", 1), text)   # the original stays, even if migrating fails
                    try:
                        cfg = migrate(cfg)
                    except (KeyError, TypeError, AttributeError, IndexError, ValueError) as e:
                        raise ConfigDamaged(_s("migration failed: {error}", error=f"{type(e).__name__}: {e}")) from None
                    _write(cfg)
                    key = _stamp(CONFIG_FILE)
            except ConfigDamaged as e:
                if _cfg_cache["cfg"] is None:
                    raise ConfigDamaged(_s(
                        "The configuration {file} is damaged and cannot be read ({error}). Tuttiphon does not start, so "
                        "that nothing gets overwritten – please correct the file or replace it with a backup "
                        "(backup/config_v*.json or config.json from a tuttiphon-sicherung-*.zip), then start again.",
                        file=CONFIG_FILE, error=e)) from None
                _damaged(key, e)
                return copy.deepcopy(_cfg_cache["cfg"])
            _fill(cfg.setdefault("settings", {}), default_config()["settings"])
            for k in ("welten", "stile", "playlists", "personen", "dismissed", "ignored"):
                cfg.setdefault(k, [])
            _cfg_cache.update(key=key, cfg=cfg, damaged=None)
        return copy.deepcopy(_cfg_cache["cfg"])


def save_config(cfg):
    validate_config(cfg)
    with _lock:
        _write(cfg)
    from . import i18n
    i18n.forget_server_lang()   # a changed language applies right away


SERVER_FIELDS = ("file", "takeover")
PLAYLIST_EXT = (".nsp", ".m3u")


def plain_playlist_file(name):
    """Only a plain file name in the playlist folder (no path, no hidden file, .nsp/.m3u). Tuttiphon ignores
    everything else in the field "file" – otherwise it could be used to write or delete files outside the folder."""
    return (isinstance(name, str) and 0 < len(name) <= 255 and "/" not in name and "\\" not in name and "\0" not in name
            and not name.startswith(".") and name.lower().endswith(PLAYLIST_EXT))


def merge_server_fields(incoming, current, keep_accounts=False):
    """Do not lose fields that only the server maintains (file name, takeover backup, cover signature) through an
    older copy from the interface."""
    if not keep_accounts:   # only the server maintains accounts/roles (the interface may know an old state)
        incoming["accounts"] = copy.deepcopy(current.get("accounts", {}))
    cur = {p["id"]: p for p in current.get("playlists", [])}
    used = {p["file"] for p in current.get("playlists", []) if p.get("file")}
    foreign = None   # files in the playlist folder that never belonged to Tuttiphon (handmade)

    def handmade(name):
        nonlocal foreign
        if foreign is None:
            from . import playlists   # only here: playlists imports config
            try:
                folder = playlists.playlist_dir(current)
                ours = set(playlists.load_managed().get("ever", []))
                foreign = {f.name for f in folder.iterdir() if f.is_file()} - ours
            except (OSError, KeyError):
                foreign = set()
        return name in foreign

    for p in incoming.get("playlists", []):
        c = cur.get(p.get("id"))
        # only the server sets the cover (/api/cover/*) – a new playlist from the interface has none yet
        p.pop("cover", None)
        if not c:
            # new (or brought back by undo): take the file name from the interface – but only a plain name that no
            # other playlist uses and that is not a handmade file in the folder
            # (otherwise a foreign file could be overwritten, applied in Navidrome and deleted)
            if "file" in p and (not plain_playlist_file(p["file"]) or p["file"] in used or handmade(p["file"])):
                p.pop("file")
            elif p.get("file"):
                used.add(p["file"])
            continue
        # the server maintains file name, takeover backup and cover; the interface may know an old state
        for key in SERVER_FIELDS + ("cover",):
            if key in c:
                p[key] = c[key]
            else:
                p.pop(key, None)
    # Music worlds the server has meanwhile created on its own (autowelten.py) are not yet known to an older copy of
    # the interface – they stay. Only someone who also hid them has deleted them („scene|…“).
    stamp_dismissed(incoming, current.get("dismissedAt"))
    have = {w.get("id") for w in incoming.get("welten", [])}
    gone = set(incoming.get("dismissed", []))
    for w in current.get("welten", []):
        if w.get("auto") and w.get("scene") and w["id"] not in have and f"scene|{w['scene']}" not in gone:
            incoming.setdefault("welten", []).append(copy.deepcopy(w))
    return incoming


def stamp_dismissed(target, old):
    """For every entry in target["dismissed"], remember since when it has been hidden (target["dismissedAt"]) –
    known ones keep their date, new ones get today. Hidden suggestions come back after half a year
    (langzeit.expire_dismissed()); deleted music worlds („scene|…“) stay away."""
    old = old if isinstance(old, dict) else {}
    today = dt.date.today().isoformat()
    target["dismissedAt"] = {k: old.get(k) or today for k in target.get("dismissed", []) if isinstance(k, str)}


def normalize_playlists(cfg):
    """Playlists with a sound filter (their own or that of their vibe) only exist as a mix – Navidrome cannot filter
    by sound. The interface already sets it up that way; here it applies to everything else too."""
    sound = {s["id"] for s in cfg.get("stile", []) if s.get("sound")}
    for p in cfg.get("playlists", []):
        if p.get("rules") is None and (p.get("sound") or p.get("stil") in sound) and p.get("type") != "mix":
            p["type"] = "mix"
            p.setdefault("mix", {"size": 40, "perArtist": 3, "every": "week"})
    return cfg


def save_from_ui(incoming, keep_accounts=False):
    """Save the configuration from the interface – take the server fields from the current state, all under the lock.
    incoming may be a function: it gets the current state and builds the new one from it (under the lock) –
    so nothing the server changed in between gets lost (e.g. login, roles)."""
    with _lock:
        current = load_config()
        new = incoming(copy.deepcopy(current)) if callable(incoming) else incoming
        new = normalize_playlists(merge_server_fields(new, current, keep_accounts))
        lang = (new.get("settings") or {}).get("language")
        if lang and lang != current["settings"].get("language"):
            localize_defaults(new, lang)
        save_config(new)


def localize_defaults(cfg, lang):
    """New server language: the delivered vibes, the delivered person and the name of "all" follow it – but only
    while they still have a delivered name (in any language); names someone chose stay as they are."""
    from .i18n import LANGS, tr
    defaults = default_config()
    names = {s["id"]: s["name"] for s in defaults["stile"]}
    names.update({p["id"]: p["name"] for p in defaults["personen"]})
    for item in cfg.get("stile", []) + cfg.get("personen", []):
        en = names.get(item.get("id"))
        if en and item.get("name") in {tr(en, x) for x in LANGS}:
            item["name"] = tr(en, lang)
    st = cfg.setdefault("settings", {})
    if st.get("allName") in {tr(defaults["settings"]["allName"], x) for x in LANGS}:
        st["allName"] = tr(defaults["settings"]["allName"], lang)
    return cfg


def update_config(fn):
    """Load a fresh configuration, apply fn(cfg), save – all under one lock."""
    with _lock:
        cfg = load_config()
        fn(cfg)
        save_config(cfg)
        return cfg


def _write(cfg):
    write_atomic(CONFIG_FILE, json.dumps(cfg, ensure_ascii=False, indent=2) + "\n")


def validate_config(cfg):
    """ValueError (the interface shows it, HTTP 400) for anything that does not fit – also for wrong types that the
    single checks below do not foresee (instead of a TypeError, i.e. an error 500)."""
    try:
        _validate_config(cfg)
    except (TypeError, AttributeError, KeyError, IndexError) as e:
        raise ValueError(_("config: invalid value ({error})", error=f"{type(e).__name__}: {e}")) from None


def _validate_config(cfg):
    if not isinstance(cfg, dict):
        raise ValueError(_("config: {kind} invalid", kind="config"))
    for key in ("welten", "stile", "playlists", "settings", "personen"):
        if key not in cfg:
            raise ValueError(_("config: '{key}' is missing", key=key))
    for kind in ("welten", "stile", "personen", "playlists"):
        ids = [x.get("id") for x in cfg[kind]]
        if any(not i for i in ids) or len(ids) != len(set(ids)):
            raise ValueError(_("config: {kind} need unique ids", kind=kind))
        if "*" in ids:
            raise ValueError(_("config: '*' is reserved as an id"))
    _validate_types(cfg)
    welten = {w["id"] for w in cfg["welten"]}
    stile = {s["id"] for s in cfg["stile"]} | {"*"}
    personen = {p["id"] for p in cfg["personen"]}
    for p in cfg["playlists"]:
        if p.get("rules") is not None:          # playlist taken over unchanged
            continue
        w = p.get("welt")
        wl = w if isinstance(w, list) else ([] if w == "*" else [w])
        if any(x not in welten for x in wl) or p.get("stil") not in stile:
            raise ValueError(_("config: playlist '{id}' refers to an unknown world/vibe", id=p.get('id')))
        radio = p.get("radio")
        if radio is not None and not (isinstance(radio, dict) and isinstance(radio.get("seed"), list) and radio["seed"]
                                      and all(isinstance(x, str) and x for x in radio["seed"])):
            raise ValueError(_("config: playlist '{id}': radio needs at least one starting band", id=p.get('id')))
        taste_mix = p.get("type") == "mix" and isinstance(p.get("mix"), dict) and p["mix"].get("flavor") == "geschmack"
        special = p.get("fav") or p.get("review") or p.get("together") or p.get("daytime") or p.get("unheard") \
            or p.get("album")   # favorite bands, recap, family mix, the morning, never played, album of the week
        # an instrument narrows the whole library enough (“ruhige Klaviermusik”, combined search)
        special = special or (isinstance(p.get("sound"), dict) and (p["sound"].get("instruments") or p["sound"].get("themes")))
        if not wl and p.get("stil") == "*" and not radio and not taste_mix and not special:   # “Your sound” picks from everything
            raise ValueError(_("config: 'All × Everything' is not a useful playlist"))
        st_ = next((x for x in cfg["stile"] if x["id"] == p.get("stil")), None)
        if (p.get("sound") or (st_ or {}).get("sound")) and p.get("type") != "mix":
            raise ValueError(_("config: playlist '{id}': sound vibes only exist as a mix", id=p.get('id')))
        if p.get("person") and p["person"] not in personen:
            raise ValueError(_("config: playlist '{id}' refers to an unknown person", id=p.get('id')))
        fav = p.get("fav")
        if fav is not None and not (isinstance(fav, dict) and isinstance(fav.get("days", 60), int)
                                    and not isinstance(fav.get("days", 60), bool) and 7 <= fav.get("days", 60) <= 365):
            raise ValueError(_("config: playlist '{id}': the period for favorite bands must be between 7 and 365 days",
                               id=p.get('id')))
        together = p.get("together")
        if together is not None and not (isinstance(together, list) and len(together) >= 2
                                         and all(isinstance(x, str) and x in personen for x in together)):
            raise ValueError(_("config: playlist '{id}': a family mix needs at least two known people", id=p.get('id')))
        review = p.get("review")
        if review is not None and not (isinstance(review, dict) and review.get("period", "month") in ("month", "year")
                                       and p.get("type") == "mix"):
            raise ValueError(_("config: playlist '{id}': recap invalid", id=p.get('id')))
        if p.get("daytime") is not None and not (p["daytime"] == "morning" and p.get("type") == "mix"):
            raise ValueError(_("config: playlist '{id}': time of day invalid", id=p.get('id')))
        if p.get("unheard") is not None and not (p["unheard"] is True and p.get("type") == "mix"):
            raise ValueError(_("config: playlist '{id}': “never played” only exists as a mix", id=p.get('id')))
        if p.get("album") is not None and not (p["album"] is True and p.get("type") == "mix"):
            raise ValueError(_("config: playlist '{id}': “album of the week” only exists as a mix", id=p.get('id')))
    for p in cfg["playlists"]:
        # minDuration: seconds (null = from the music world or the settings); every number ends up in int() when
        # writing – a text or an endless number there would stop the playlists of the whole family
        for key, lo, hi in (("limit", 1, 100000), ("minRating", 0, 5), ("notPlayedDays", 1, 3650), ("minDuration", 0, 3600)):
            v = p.get(key)
            if v is not None and (not isinstance(v, (int, float)) or isinstance(v, bool) or not lo <= v <= hi):
                raise ValueError(_("config: playlist '{id}': {key} must be a number between {lo} and {hi}",
                                   id=p.get('id'), key=key, lo=lo, hi=hi))
        bands = p["radio"].get("bands") if isinstance(p.get("radio"), dict) else None
        if bands is not None and (not isinstance(bands, int) or isinstance(bands, bool) or not 1 <= bands <= 100):
            raise ValueError(_("config: playlist '{id}': {key} must be a number between {lo} and {hi}",
                               id=p.get('id'), key="radio.bands", lo=1, hi=100))
        _validate_sound(p.get("sound"), _("playlist '{id}'", id=p.get('id')))
        if p.get("type") not in (None, "mix"):
            raise ValueError(_("config: playlist '{id}' has an unknown type", id=p.get('id')))
        m = p.get("mix")
        if m is not None:
            if not isinstance(m, dict):
                raise ValueError(_("config: playlist '{id}': mix settings invalid", id=p.get('id')))
            if m.get("every", "day") not in ("day", "week", "month"):
                raise ValueError(_("config: playlist '{id}': unknown renewal interval", id=p.get('id')))
            if m.get("flavor") is not None and not (isinstance(m["flavor"], str) and len(m["flavor"]) <= 40):
                raise ValueError(_("config: playlist '{id}': mix settings invalid", id=p.get('id')))
            for key, lo, hi in (("size", 5, 500), ("perArtist", 0, 20), ("perAlbum", 0, 20), ("avoidRecent", 0, 365),
                                ("minutes", 10, 240)):
                v = m.get(key)
                if v is not None and (not isinstance(v, (int, float)) or isinstance(v, bool) or not lo <= v <= hi):
                    raise ValueError(_("config: playlist '{id}': {key} must be between {lo} and {hi}",
                                       id=p.get('id'), key=key, lo=lo, hi=hi))
    for w in cfg["welten"]:
        for key, lo, hi in (("minDuration", 0, 3600), ("minRating", 0, 5)):
            v = w.get(key)
            if v is not None and (not isinstance(v, (int, float)) or isinstance(v, bool) or not lo <= v <= hi):
                raise ValueError(_("config: music world '{id}': {key} must be a number between {lo} and {hi}",
                                   id=w.get('id'), key=key, lo=lo, hi=hi))
    for st in cfg["stile"]:
        _validate_sound(st.get("sound"), _("vibe '{id}'", id=st.get('id')))
        season = st.get("season")
        if season is not None and not (isinstance(season, list) and len(season) == 2
                                       and all(isinstance(x, str) and re.fullmatch(r"(0[1-9]|1[0-2])-(0[1-9]|[12]\d|3[01])", x) for x in season)):
            raise ValueError(_("config: vibe '{id}': please give the season as MM-DD", id=st.get('id')))
    accounts = cfg.get("accounts", {})
    if not isinstance(accounts, dict) or any(not isinstance(v, dict) or v.get("role") not in (None, "admin", "user", "none")
                                             for v in accounts.values()):
        raise ValueError(_("config: accounts invalid"))
    settings = cfg["settings"]
    if not isinstance(settings, dict):
        raise ValueError(_("config: {kind} invalid", kind="settings"))
    _validate_settings(settings)
    if settings.get("defaultPerson") not in (None, "") and settings["defaultPerson"] not in personen:
        raise ValueError(_("Settings: the default person does not exist"))
    if settings.get("dailyMode", "playlists") not in ("playlists", "alles", "aus"):   # i18n-ignore
        raise ValueError(_("config: dailyMode unknown"))
    if not re.fullmatch(r"([01]\d|2[0-3]):[0-5]\d", str(settings.get("dailyAt") or "05:30")):
        raise ValueError(_("config: please give dailyAt as HH:MM"))


def _validate_types(cfg):
    """Field types of people and playlists – a wrong type (say, a number as prefix) would otherwise make writing
    all playlists or whole pages fail, for the whole family."""
    def strs(v):
        return isinstance(v, list) and all(isinstance(x, str) for x in v)

    def long(v, n):   # a text or the texts of a list longer than allowed (lengths: TEXT_MAX)
        return (len(v) > n) if isinstance(v, str) else isinstance(v, list) and (len(v) > LIST_MAX or any(len(x) > n for x in v))

    for kind in ("personen", "playlists", "welten", "stile"):
        if not isinstance(cfg[kind], list) or any(not isinstance(x, dict) or not isinstance(x.get("id"), str)
                                                  or len(x["id"]) > 100 for x in cfg[kind]):
            raise ValueError(_("config: {kind} invalid", kind=kind))
    for p in cfg["personen"]:
        for k in ("name", "icon", "color", "prefix", "user"):
            if p.get(k) is not None and not isinstance(p[k], str):
                raise ValueError(_("config: person '{id}': {key} must be text", id=p['id'], key=k))
            if long(p.get(k), TEXT_MAX.get(k, 200)):
                raise ValueError(_("config: person '{id}': {key} is too long", id=p['id'], key=k))
        if p.get("color") and not COLOR.fullmatch(p["color"]):
            raise ValueError(_("config: person '{id}': {key} invalid", id=p['id'], key="color"))
        for k in ("public", "clean"):
            if p.get(k) is not None and not isinstance(p[k], bool):
                raise ValueError(_("config: person '{id}': {key} invalid", id=p['id'], key=k))
        if p.get("push") not in (None, "") and not (isinstance(p["push"], str) and re.fullmatch(r"[A-Za-z0-9_-]{1,64}", p["push"])):
            raise ValueError(_("config: person '{id}': the topic for notifications may only contain letters, digits, - and _",
                               id=p['id']))
        te = p.get("tasteExclude")   # music worlds that do not count for the person's taste (ids; unknown ones are ignored)
        if te is not None and (not strs(te) or len(te) > 50 or any(long(x, 100) for x in te)):
            raise ValueError(_("config: person '{id}': {key} invalid", id=p['id'], key="tasteExclude"))
        for k in ("likes", "dislikes"):
            v = p.get(k)
            if v is not None and (not isinstance(v, dict) or any(not strs(x) for x in v.values())):
                raise ValueError(_("config: person '{id}': {key} invalid", id=p['id'], key=k))
            if v is not None and (len(v) > 20 or any(long(x, 300) for x in v.values())):
                raise ValueError(_("config: person '{id}': {key} is too long", id=p['id'], key=k))
    for p in cfg["playlists"]:
        for k in ("name", "file", "person", "stil", "sort", "icon", "color", "status", "source", "created", "sortRaw",
                  "originalName"):
            if p.get(k) is not None and not isinstance(p[k], str):
                raise ValueError(_("config: playlist '{id}': {key} must be text", id=p['id'], key=k))
            if long(p.get(k), TEXT_MAX.get(k, 300)):
                raise ValueError(_("config: playlist '{id}': {key} is too long", id=p['id'], key=k))
        if p.get("color") and not COLOR.fullmatch(p["color"]):
            raise ValueError(_("config: playlist '{id}': {key} invalid", id=p['id'], key="color"))
        for k in ("excludeArtists", "addArtists", "excludeTitles"):
            if p.get(k) is not None and not strs(p[k]):
                raise ValueError(_("config: playlist '{id}': {key} must be a list of names", id=p['id'], key=k))
            if long(p.get(k), 300):
                raise ValueError(_("config: playlist '{id}': {key} is too long", id=p['id'], key=k))
        for k in ("public", "hits", "yearRound"):
            if p.get(k) is not None and not isinstance(p[k], bool):
                raise ValueError(_("config: playlist '{id}': {key} invalid", id=p['id'], key=k))
        w = p.get("welt")
        if w is not None and not (isinstance(w, str) or strs(w)):
            raise ValueError(_("config: playlist '{id}': {key} invalid", id=p['id'], key="welt"))
        for k, typ in (("rules", list), ("rulesExtra", dict), ("takeover", dict)):   # mix/radio: own check below
            if p.get(k) is not None and not isinstance(p[k], typ):
                raise ValueError(_("config: playlist '{id}': {key} invalid", id=p['id'], key=k))


STEPS = ("flac", "lyrics", "cover", "analyse", "playlists", "scan", "deezer")
START_SECTIONS = ("heute", "todo", "woche", "neu", "playlists", "karten", "verlauf")   # i18n-ignore
SOUND_KEYS = ("energy", "bpm", "arousal", "valence", "dance", "approachable", "engaging")   # ranges, audio.RANGE_KEYS
SCORE_KEYS = ("approachable", "engaging")   # ranges within 0–1 (values of the AI, ml_worker.SCORES)
MOOD_IDS = ("ruhig", "energie", "tanzbar", "froh", "melancholisch", "schlaf", "instrumental", "akustisch")
# Longest texts of people and playlists (everything else: 300 characters) and entries per list – an account must not
# be able to store huge amounts in the configuration everyone loads
TEXT_MAX = {"name": 120, "prefix": 40, "icon": 64, "color": 40, "user": 100, "person": 100, "stil": 100, "file": 255,
            "status": 20, "created": 40}
LIST_MAX = 2000
# a person's color goes into the page's styles: only #rgb, #rrggbb or hsl(…), never url(…) or the like
COLOR = re.compile(r"#[0-9A-Fa-f]{3}(?:[0-9A-Fa-f]{3})?|hsl\(\s*\d{1,3}(?:\.\d+)?(?:deg)?\s*,?\s*\d{1,3}(?:\.\d+)?%\s*,?\s*"
                   r"\d{1,3}(?:\.\d+)?%\s*\)")


def _num(d, key, lo, hi, name):
    """name: N_() text, translated only for the error message."""
    v = d.get(key)
    if v is not None and (not isinstance(v, (int, float)) or isinstance(v, bool) or not lo <= v <= hi):
        raise ValueError(_("Settings: {name} must be between {lo} and {hi}", name=_(name), lo=lo, hi=hi))   # i18n-ignore


def _validate_sound(snd, where):
    """where: already translated label of the playlist or vibe, e.g. _("playlist '{id}'")."""
    if snd is None:
        return
    if not isinstance(snd, dict):
        raise ValueError(_("config: {where}: sound filter invalid", where=where))
    for k, v in snd.items():
        if k == "moods":
            if not isinstance(v, list) or any(m not in MOOD_IDS for m in v):
                raise ValueError(_("config: {where}: unknown mood", where=where))
        elif k == "instruments":   # instruments of the AI sound analysis (ml.INSTRUMENTS)
            from .ml import INSTRUMENTS
            if not isinstance(v, list) or any(not isinstance(x, str) or x not in INSTRUMENTS for x in v):
                raise ValueError(_("config: {where}: unknown instrument", where=where))
        elif k == "themes":   # themes of the AI sound analysis (ml.THEMES)
            from .ml import THEMES
            if not isinstance(v, list) or any(not isinstance(x, str) or x not in THEMES for x in v):
                raise ValueError(_("config: {where}: unknown theme", where=where))
        elif k in SOUND_KEYS:
            if not (isinstance(v, list) and len(v) == 2 and all(isinstance(x, (int, float)) and not isinstance(x, bool)
                                                                and math.isfinite(x) for x in v) and v[0] <= v[1]):
                raise ValueError(_("config: {where}: range for {key} invalid", where=where, key=k))
            if k in SCORE_KEYS and not all(0 <= x <= 1 for x in v):   # values of the AI: 0–1
                raise ValueError(_("config: {where}: range for {key} invalid", where=where, key=k))
        # other keys: a feature of a newer version (after going back to an older one) – the filter ignores it
        # (audio.matches only looks at the known ones), so saving keeps working


def _validate_settings(st):
    # sections that are used as objects: another type would make every page or run that reads them fail
    for key in ("start", "deezer", "lyrics", "analysis", "watch", "backup", "opus", "loudness", "kinderschutz", "notify",
                "covers", "welten", "navidrome", "paths"):
        if st.get(key) is not None and not isinstance(st[key], dict):
            raise ValueError(_("Settings: {key} invalid", key=key))
    _num(st, "limit", 1, 100000, N_("Max. songs per playlist"))
    _num(st, "minDuration", 0, 3600, N_("Minimum length"))
    _num(st, "hitsShare", 0, 1, N_("“Only the hits”"))
    _num(st, "allMinRating", 0, 5, N_("Minimum rating for “All”"))
    for key in ("autoApply", "public", "seasonRest", "smoothTransitions", "mixLearn"):
        if st.get(key) is not None and not isinstance(st[key], bool):
            raise ValueError(_("Settings: {key} must be yes/no", key=key))
    for key, n in (("namePattern", 200), ("allName", 120), ("filePrefix", 60)):
        if st.get(key) is not None and not (isinstance(st[key], str) and len(st[key]) <= n):
            raise ValueError(_("Settings: {key} invalid", key=key))
    try:   # the name of a playlist “world · vibe” – only {welt} and {stil}, without format details ({welt:>999999})
        fields = list(string.Formatter().parse(str(st.get("namePattern") or "{welt} · {stil}")))
    except ValueError:
        fields = [("", "?", "", None)]
    if any(f is not None and (f not in ("welt", "stil") or spec or conv) for _lit, f, spec, conv in fields):
        raise ValueError(_("Settings: the name pattern may only contain {welt} and {stil}"))
    ex = st.get("excludeTitles")
    if ex is not None and not (isinstance(ex, list) and len(ex) <= LIST_MAX
                               and all(isinstance(x, str) and len(x) <= 300 for x in ex)):
        raise ValueError(_("Settings: {key} invalid", key="excludeTitles"))
    pipe = st.get("pipeline")
    if pipe is not None and (not isinstance(pipe, list) or any(x not in STEPS for x in pipe) or len(set(pipe)) != len(pipe)):
        raise ValueError(_("Settings: unknown step in “Update everything”"))
    start = st.get("start") or {}
    if not all(isinstance(x, dict) and x.get("id") in START_SECTIONS for x in start.get("sections", [])):
        raise ValueError(_("Settings: unknown section of the home page"))
    dz = st.get("deezer") or {}
    th = dz.get("thresholds")
    if th is not None and (not isinstance(th, list) or len(th) != 5
                           or any(not isinstance(x, int) or isinstance(x, bool) or x < 0 for x in th) or th != sorted(th)):
        raise ValueError(_("Settings: the Deezer levels must be five ascending numbers"))
    if dz.get("pipelineMode", "new") not in ("new", "missing"):
        raise ValueError(_("Settings: Deezer mode unknown"))
    if dz.get("users") is not None and not (isinstance(dz["users"], list) and all(isinstance(u, str) for u in dz["users"])):
        raise ValueError(_("Settings: Deezer users invalid"))
    _num(dz, "rate", 1, 15, N_("Deezer requests per second"))
    for key in ("topBoost", "refresh"):
        if key in dz and not isinstance(dz[key], bool):
            raise ValueError(_("Settings: Deezer {key} must be yes/no", key=key))
    ld = st.get("loudness") or {}
    if not isinstance(ld, dict) or any(k in ld and not isinstance(ld[k], bool) for k in ("enabled", "album")):
        raise ValueError(_("Settings: even out loudness – yes/no expected"))
    ly = st.get("lyrics") or {}
    if ly.get("instrumental", "mark") not in ("mark", "skip"):
        raise ValueError(_("Settings: lyrics/instrumental unknown"))
    _num(ly, "retryDays", 1, 365, N_("Lyrics: search again after (days)"))
    _num(ly, "workers", 1, 8, N_("Lyrics: parallel requests"))
    _num(ly, "budgetMinutes", 0, 600, N_("Lyrics: time limit"))
    provs = ly.get("providers")
    if provs is not None and (not isinstance(provs, list) or any(not isinstance(x, dict) or x.get("id") not in ("lrclib", "netease") for x in provs)):
        raise ValueError(_("Settings: unknown lyrics provider"))
    if any(not isinstance(x.get("on", True), bool) for x in provs or []):
        raise ValueError(_("Settings: {key} must be yes/no", key="lyrics.providers.on"))
    an = st.get("analysis") or {}
    _num(an, "budgetMinutes", 0, 1440, N_("Sound analysis: time limit"))
    _num(an, "lastfmBudget", 0, 600, N_("Last.fm: time limit"))
    _num(an, "workers", 0, 32, N_("Sound analysis: parallel analyses"))
    _num(an, "autoThreshold", 0.3, 1, N_("Classification: minimum confidence"))
    _num(an, "mlBudget", 0, 1440, N_("AI sound analysis: time limit"))
    _num(an, "mlThreads", 1, 8, N_("AI sound analysis: processor cores"))
    if not isinstance(an.get("fingerprints", True), bool):
        raise ValueError(_("Settings: same recording twice – yes/no expected"))
    night = an.get("night") or {}
    if not isinstance(night, dict) or any(not re.fullmatch(r"([01]\d|2[0-3]):[0-5]\d", str(night.get(k) or d))
                                          for k, d in (("from", "01:00"), ("to", "05:00"))):
        raise ValueError(_("Settings: night analysis – please give the times as HH:MM"))
    if (night.get("from") or "01:00") == (night.get("to") or "05:00"):
        raise ValueError(_("Settings: night analysis – start and end must not be the same"))
    if an.get("classify", "suggest") not in ("off", "suggest", "auto"):
        raise ValueError(_("Settings: classification unknown"))
    if an.get("depth", "standard") not in ("schnell", "standard", "gruendlich", "tief"):
        raise ValueError(_("Settings: analysis depth unknown"))
    wt = st.get("watch") or {}
    _num(wt, "interval", 5, 1440, N_("Folder watch: interval (minutes)"))
    bk = st.get("backup") or {}
    _num(bk, "keep", 1, 365, N_("Backup: number to keep"))
    bdir = str(bk.get("dir") or "")
    if ".." in bdir.replace("\\", "/").split("/") or "\0" in bdir:
        raise ValueError(_("Settings: backup folder invalid"))
    # every backup would contain the earlier ones. A value saved before stays accepted (otherwise every save, also the
    # server's own, would fail) – backup.py keeps the backups from nesting anyway
    stored = (_cfg_cache.get("cfg") or {}).get("settings") or {}
    if (bdir.strip() and bdir != str((stored.get("backup") or {}).get("dir") or "")
            and any(is_inside(Path(bdir.strip()) if os.path.isabs(bdir.strip()) else BASE / bdir.strip(), d)
                    for d in (STATE_DIR, BACKUP_DIR))):
        raise ValueError(_("Settings: the backup folder must not be inside state/ or backup/ of the data folder – "
                           "every backup would contain the earlier ones"))
    if st.get("language", "en") not in LANGS:
        raise ValueError(_("Settings: unknown language"))
    op = st.get("opus") or {}
    _num(op, "bitrate", 48, 320, N_("Opus bitrate"))
    _num(op, "aacBitrate", 64, 320, N_("AAC bitrate"))
    if op.get("codec", "opus") not in ("opus", "aac"):
        raise ValueError(_("Settings: target format of the conversion unknown"))
    _num(op, "minAgeMinutes", 0, 1440, N_("Opus: waiting time"))
    _num(op, "jobs", 1, 8, N_("Opus: parallel conversions"))
    if op.get("original", "archive") not in ("archive", "keep", "delete"):
        raise ValueError(_("Settings: Opus/original unknown"))
    if not all(f in ("flac", "wav", "aiff", "ape", "wv", "alac") for f in op.get("formats", ["flac"])):
        raise ValueError(_("Settings: Opus/source format unknown"))
    arch = str(op.get("archiveDir") or "Archiv")
    if arch.startswith("/") or ".." in arch.replace("\\", "/").split("/"):
        raise ValueError(_("Settings: the archive folder must be a folder inside the Navidrome folder (e.g. “Archiv”)"))
    if op.get("owner") and not re.fullmatch(r"\d+:\d+", str(op["owner"])):
        raise ValueError(_("Settings: please give the owner as UID:GID, e.g. 1000:1000"))
    for key, value in (st.get("paths") or {}).items():
        if key not in PATH_ENV or (value is not None and not isinstance(value, str)):
            raise ValueError(_("Settings: unknown storage location"))
        if value and not os.path.isabs(value) and ".." in value.replace("\\", "/").split("/"):
            raise ValueError(_("Settings: please give storage locations without “..”"))
    # set in docker-compose.yaml, or saved like this before: not refused here (every save would fail, also the server's
    # own) – the conversion refuses to run with such an archive (opus.archive_problem)
    if (not (os.environ.get("MUSIC_DIR") and os.environ.get("ARCHIVE_DIR")) and archive_in_music({"settings": st})
            and not (stored and paths({"settings": stored}) == paths({"settings": st}))):
        raise ValueError(_("Settings: the archive folder must not be the music folder or inside it – the originals "
                           "there would be converted again"))
    if (st.get("navidrome") or {}).get("scan", "quick") not in ("quick", "full"):
        raise ValueError(_("Settings: scan type unknown"))
    cv = st.get("covers") or {}
    if not isinstance(cv, dict) or not isinstance(cv.get("enabled", True), bool):
        raise ValueError(_("Settings: covers invalid"))
    su = st.get("setup", {})
    if not isinstance(su, dict) or not isinstance(su.get("done", False), bool) or (
            su.get("at") is not None and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(su["at"]))):
        raise ValueError(_("Settings: setup assistant invalid"))
    wl = st.get("welten") or {}
    if not isinstance(wl, dict) or not isinstance(wl.get("auto", True), bool):
        raise ValueError(_("Settings: music worlds invalid"))
    ks = st.get("kinderschutz") or {}
    if not isinstance(ks, dict) or not isinstance(ks.get("allow", []), list) or not all(
            isinstance(x, str) for x in ks.get("allow", [])):
        raise ValueError(_("Settings: kid-safe mode invalid"))
    nt = st.get("notify") or {}
    if not isinstance(nt, dict):
        raise ValueError(_("Settings: notifications invalid"))
    for key in ("server", "url"):
        if nt.get(key) and not re.fullmatch(r"https?://[^\s/$.?#][^\s]*", str(nt[key])):
            raise ValueError(_("Settings: notifications – please start the address with http:// or https://"))
    if nt.get("topic") and not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", str(nt["topic"])):
        raise ValueError(_("Settings: notifications – the topic may only contain letters, digits, - and _"))
    if not isinstance(nt.get("events", {}), dict) or any(not isinstance(v, bool) for v in nt.get("events", {}).values()):
        raise ValueError(_("Settings: notifications – events invalid"))


# For migrating very old configurations (v1 had no people yet): a neutral person „Familie“ (stored data)
DEFAULT_PERSONEN = [
    {"id": "familie", "name": "Familie", "icon": "i:home", "user": "", "public": True, "prefix": "",
     "likes": {"welten": [], "stile": [], "artists": []}, "dislikes": {"artists": [], "genres": []}},
]
WELT_SCENES = {"kinder": "kinder", "mittelalter": "mittelalter", "northern": "nordic", "deutsch": "deutsch-indie",
               "indie": "indie-folk", "crossover": "crossover"}


def slug(text):
    s = re.sub(r"[^\w]+", "-", text.lower()).strip("-")
    return s or "x"


EMOJI_ICON = {"🧸": "teddy", "⚔️": "swords", "⚔": "swords", "🌲": "tree", "☘️": "clover", "☘": "clover", "🤘": "skull", "🦇": "ghost", "💃": "party", "🎤": "mic", "🎙️": "mic", "🎪": "tent", "🇩🇪": "flag", "🎧": "headphones", "🎸": "guitar", "🎹": "piano", "🎻": "notes", "🎼": "notes", "🌙": "moon", "🪩": "disco", "⚡": "zap", "🎮": "gamepad", "🪕": "campfire", "🎷": "waves", "🌴": "palm", "🎺": "party", "🕺": "footprints", "😴": "bed", "☀️": "sun", "☀": "sun", "🐣": "flower", "🏮": "leaf", "🍂": "leaf", "🎃": "ghost", "❄️": "snowflake", "❄": "snowflake", "🎄": "xmas", "🗓️": "calendar", "📻": "radio", "📼": "cassette", "💿": "disc", "📀": "player", "📱": "smartphone", "⭐": "star", "❤️": "heart", "❤": "heart", "🆕": "new", "🔁": "repeat", "🏠": "home", "🎵": "music", "🎶": "music", "🙂": "smile", "👶": "baby", "🐱": "cat", "👑": "crown", "🚀": "rocket", "🌍": "globe", "🔀": "sparkles", "✨": "sparkles", "🔥": "flame"}


def migrate(cfg):
    """v1 -> v2: people, scene link, stable playlist files, status instead of deleting. Later versions below.
    Names and values written here are stored data (German, as in the old configurations)."""
    version = cfg.get("version", 1)
    if version < 2:
        cfg.setdefault("personen", copy.deepcopy(DEFAULT_PERSONEN))
        cfg.setdefault("dismissed", [])
        cfg.setdefault("ignored", [])
        cfg["settings"].setdefault("defaultPerson", "familie")
        for w in cfg["welten"]:
            w.setdefault("scene", WELT_SCENES.get(w["id"]))
            w.setdefault("autoScene", bool(w.get("scene")))
            w.setdefault("excludedArtists", [])
            if w["id"] == "kinder":   # Mo-Do is 90s eurodance, not children's music
                w["artists"] = [a for a in w["artists"] if a != "Mo‐Do"]
        try:
            managed = json.loads((STATE_DIR / "managed_playlists.json").read_text(encoding="utf-8"))
        except (FileNotFoundError, ValueError):
            managed = {}
        by_name = {name: f for f, name in managed.items()} if all(isinstance(v, str) for v in managed.values()) else {}
        today = dt.date.today().isoformat()
        used = set()
        for p in cfg["playlists"]:
            base = slug(f"{p['welt']}-{p['stil']}".replace("*", "alle"))   # i18n-ignore
            pid, n = base, 2
            while pid in used:
                pid, n = f"{base}-{n}", n + 1
            used.add(pid)
            p.setdefault("id", pid)
            p.setdefault("person", "familie")
            p.setdefault("status", "aktiv")
            p.setdefault("created", today)
            name = _v1_name(cfg, p)
            if name in by_name:
                p.setdefault("file", by_name[name])
        cfg["version"] = 2
    if version < 3:   # v3: emojis -> uniform SVG icons ("i:name")
        for kind in ("welten", "stile", "personen"):
            for x in cfg.get(kind, []):
                if isinstance(x.get("icon"), str) and x["icon"] in EMOJI_ICON:
                    x["icon"] = "i:" + EMOJI_ICON[x["icon"]]
        cfg["version"] = 3
    if version < 4:   # v4: sound vibes and the step "understand the music"
        have = {s["id"] for s in cfg.get("stile", [])}
        cfg["stile"] += [copy.deepcopy(s) for s in default_config()["stile"] if s.get("group") == "Klang" and s["id"] not in have]
        pipe = cfg.get("settings", {}).get("pipeline")
        if isinstance(pipe, list) and "analyse" not in pipe:
            pipe.insert(pipe.index("lyrics") + 1 if "lyrics" in pipe else 0, "analyse")
        cfg["version"] = 4
    if version < 5:   # v5: step “fetch missing covers”, vibe “Guten Morgen”
        pipe = cfg.get("settings", {}).get("pipeline")
        if isinstance(pipe, list) and "cover" not in pipe:
            pipe.insert(pipe.index("lyrics") + 1 if "lyrics" in pipe else 0, "cover")
        have = {s["id"] for s in cfg.get("stile", [])}
        cfg["stile"] += [copy.deepcopy(s) for s in default_config()["stile"] if s["id"] in ("klang-morgen",) and s["id"] not in have]
        cfg["version"] = 5
    if version < 6:   # v6: language of the server – existing installations speak German (new ones: English)
        cfg.setdefault("settings", {}).setdefault("language", "de")
        cfg["version"] = 6
    if version < 7:   # v7: the vibes added by v4/v5 came with their English name – also in German installations
        cfg["version"] = 7
    if version < 8:   # v8: “Niklas’ Mix” is no mix but a smart playlist – it becomes “Niklas’ Querbeet” (“Mix” only for mixes)
        from .suggest import rename_all_sorts   # here, not at the top: suggest imports rules, which imports config
        rename_all_sorts(cfg, cfg.get("settings", {}).get("language") or "en")
        cfg["version"] = 8
    if version < 9:   # v9: sound vibes “In the background” and “For listening closely” (AI: approachable, engaging)
        # only these two (whoever deleted another delivered vibe keeps it deleted); before v4 the v4 step added them
        have = {s["id"] for s in cfg.get("stile", [])}
        cfg["stile"] += [copy.deepcopy(s) for s in default_config()["stile"]
                         if s["id"] in ("klang-hintergrund", "klang-zuhoeren") and s["id"] not in have]
        cfg["version"] = 9
    if version < 10:   # v10: setup assistant on the first start – an existing installation counts as set up
        st = cfg.setdefault("settings", {})
        st["setup"] = {**(st["setup"] if isinstance(st.get("setup"), dict) else {}), "done": True}
        # defaults that new installations no longer have keep their earlier value here (until someone changes them):
        # conversion was on – with originals moved to the archive
        if not isinstance(st.get("opus"), dict):
            st["opus"] = {}
        st["opus"].setdefault("enabled", True)
        cfg["version"] = 10
    if version < 11:   # v11: new files no longer get the owner 1000:10 by default (empty = the user Tuttiphon runs as)
        st = cfg.setdefault("settings", {})
        if not isinstance(st.get("opus"), dict):
            st["opus"] = {}
        st["opus"].setdefault("owner", "1000:10")   # an existing installation keeps what it had
        cfg["version"] = 11
    if version < 12:   # v12: the weekly "new for you" notification – on like the other events (shown as a switch)
        st = cfg.setdefault("settings", {})
        if not isinstance(st.get("notify"), dict):
            st["notify"] = {}
        if not isinstance(st["notify"].get("events"), dict):
            st["notify"]["events"] = {}
        st["notify"]["events"].setdefault("weekly", True)
        cfg["version"] = 12
    if version < CONFIG_VERSION:   # whatever a stage added gets its name in the server language (chosen names stay)
        localize_defaults(cfg, cfg.get("settings", {}).get("language") or "en")
    return cfg


def _v1_name(cfg, p):
    """Name of a playlist in a v1 configuration – to find its file again (data, not translated)."""
    if p.get("name"):
        return p["name"]
    welt = next((w for w in cfg["welten"] if w["id"] == p["welt"]), None)
    stil = next((s for s in cfg["stile"] if s["id"] == p["stil"]), None)
    if welt is None:
        return stil["name"] if stil else "?"
    if stil is None:
        return f"{welt['name']} · Mix"
    return cfg["settings"]["namePattern"].format(welt=welt["name"], stil=stil["name"])
