"""Password of the local administrator (Tuttiphon's own administrator, internally "@notfall").

Two sources – the environment wins:
* TUTTIPHON_ADMIN_PASSWORD in the environment (docker-compose.yaml) or in <data>/.env – plain text, optional.
* Set in the browser: at the first start or later under Settings → Users & permissions. Only a hash is kept
  (state/admin_password.json, scrypt), never the password itself.

On the network Tuttiphon never runs without it. As long as neither exists, it waits for its setup: a one-time setup
code in the server log and in <data>/setup-code.txt proves that whoever sets the password has access to the server –
otherwise the first stranger to open the page would become administrator.
"""
import base64
import hashlib
import hmac
import json
import secrets
import threading
import time

from . import events
from .config import DATA_DIR, STATE_DIR, admin_password, load_env, read_text, weak_password, write_atomic
from .i18n import _, _s

HASH_FILE = STATE_DIR / "admin_password.json"
CODE_FILE = DATA_DIR / "setup-code.txt"
CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"   # without 0/O and 1/I – easy to type off the log
_lock = threading.Lock()
_cache = {"key": None, "hash": ""}


def _b64(data):
    return base64.urlsafe_b64encode(data).decode().rstrip("=")


def _unb64(text):
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def make_hash(password, salt=None):
    """scrypt (16 MB, ~50 ms) – or PBKDF2 where Python has no scrypt."""
    salt = salt or secrets.token_bytes(16)
    if hasattr(hashlib, "scrypt"):
        digest = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=2 ** 14, r=8, p=1, dklen=32)
        return f"scrypt:16384:8:1:{_b64(salt)}:{_b64(digest)}"
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 600_000)
    return f"pbkdf2:600000:{_b64(salt)}:{_b64(digest)}"


def verify_hash(password, stored):
    try:
        kind, *parts = str(stored).split(":")
        if kind == "scrypt":
            n, r, p, salt, digest = int(parts[0]), int(parts[1]), int(parts[2]), _unb64(parts[3]), _unb64(parts[4])
            if not (2 <= n <= 2 ** 20 and 1 <= r <= 32 and 1 <= p <= 16):
                return False
            got = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=n, r=r, p=p, dklen=len(digest),
                                 maxmem=256 * 1024 * 1024)
        elif kind == "pbkdf2":
            rounds, salt, digest = int(parts[0]), _unb64(parts[1]), _unb64(parts[2])
            if not 1 <= rounds <= 10_000_000:
                return False
            got = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, rounds)
        else:
            return False
    except (ValueError, IndexError, TypeError, MemoryError):
        return False
    return hmac.compare_digest(got, digest)


def stored_hash():
    """Hash set in the browser ('' = none). Read again only when the file changes."""
    try:
        st = HASH_FILE.stat()
        key = (st.st_mtime_ns, st.st_size)
    except OSError:
        _cache.update(key=None, hash="")
        return ""
    if _cache["key"] != key:
        try:
            data = json.loads(read_text(HASH_FILE))
            value = data.get("hash") if isinstance(data, dict) else ""
        except (OSError, ValueError):
            return _cache["hash"]   # briefly unreadable (NFS): last state
        _cache.update(key=key, hash=value if isinstance(value, str) else "")
    return _cache["hash"]


def source(env=None):
    """Where the password comes from: "env" (docker-compose/.env), "stored" (set in the browser) or "" (none)."""
    if admin_password(env if env is not None else load_env()):
        return "env"
    return "stored" if stored_hash() else ""


def configured(env=None):
    return bool(source(env))


def check(password, env=None):
    """Is this the password of the local administrator? (constant time; False without a password)"""
    if not isinstance(password, str) or not password:
        return False
    plain = admin_password(env if env is not None else load_env())
    if plain:
        return hmac.compare_digest(password.encode("utf-8"), plain.encode("utf-8"))
    stored = stored_hash()
    return bool(stored) and verify_hash(password, stored)


def identity(env=None):
    """Changes whenever the password changes – the sessions of the local administrator are tied to it."""
    plain = admin_password(env if env is not None else load_env())
    return ("env:" + plain) if plain else ("hash:" + stored_hash()) if stored_hash() else ""


def set_password(password):
    """Keep the hash of a new password (set in the browser). Ends the setup: the setup code is deleted."""
    if weak_password(password):
        raise ValueError(_("The administrator password needs at least 8 characters."))
    if source() == "env":
        raise ValueError(_("The password of the local administrator is set in docker-compose.yaml – change it there."))
    with _lock:
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        write_atomic(HASH_FILE, json.dumps({"hash": make_hash(password), "at": int(time.time())}), mode=0o600)
        _cache.update(key=None, hash="")
        try:
            CODE_FILE.unlink()
        except FileNotFoundError:
            pass


def changed_at():
    try:
        data = json.loads(read_text(HASH_FILE))
        return int(data.get("at") or 0) or None
    except (OSError, ValueError, TypeError, AttributeError):
        return None


# ---------------------------------------------------------------------------- setup code

def _normal(code):
    return "".join(ch for ch in str(code or "").upper() if ch.isalnum())


def setup_code():
    """-> (code, created): the one-time code of the setup, created when missing. It stays the same until the password
    is set – also across restarts; a new one is announced in the server log right away."""
    with _lock:
        try:
            code = _normal(read_text(CODE_FILE))
        except OSError:
            code = ""
        created = not (len(code) == 8 and all(ch in CODE_ALPHABET for ch in code))
        if created:
            code = "".join(secrets.choice(CODE_ALPHABET) for _i in range(8))
            DATA_DIR.mkdir(parents=True, exist_ok=True)
            write_atomic(CODE_FILE, f"{code[:4]}-{code[4:]}\n", mode=0o600)
    shown = f"{code[:4]}-{code[4:]}"
    if created:
        announce(shown)
    return shown, created


def announce(code):
    events.say(_s("No administrator password yet – open Tuttiphon in the browser and enter the setup code {code} "
                  "(also in setup-code.txt in the data folder).", code=code))


def check_code(code):
    try:
        expected = _normal(read_text(CODE_FILE))
    except OSError:
        return False
    given = _normal(code)
    return len(expected) == 8 and hmac.compare_digest(given.encode(), expected.encode())
