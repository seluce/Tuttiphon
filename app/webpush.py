"""Notifications through the app itself (web push) – without ntfy, without an extra app.

* Every device signs up once (profile or Settings → Notifications → "Turn on on this device"). For that the browser
  gives an address of its push service (Google, Mozilla, Apple, Microsoft) and two keys.
* Stored per account in state/push.json (at most 10 devices per account). Messages for administrators go to devices
  that were signed up as administrator; messages for a person go to the devices of their Navidrome account.
* The message is end-to-end encrypted (RFC 8291, aes128gcm) – the push service only delivers it, it cannot read it.
  Tuttiphon identifies itself with its own key pair (VAPID, RFC 8292, state/push_keys.json).
* Messages only go to the known push services (PUSH_HOSTS) – no subscription can make Tuttiphon request addresses in
  the local network. Expired subscriptions (404/410) are forgotten.
* Needs the package cryptography (in the Docker image) and an https address of Tuttiphon (browser rule).
"""
import base64
import json
import os
import struct
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

from .config import STATE_DIR, read_text, write_atomic
from .i18n import _

KEYS_FILE = STATE_DIR / "push_keys.json"
SUBS_FILE = STATE_DIR / "push.json"
MAX_DEVICES = 10
PUSH_HOSTS = ("fcm.googleapis.com", "android.googleapis.com", "push.services.mozilla.com", "push.apple.com",
              "notify.windows.com")
_lock = threading.Lock()


def available():
    try:
        from cryptography.hazmat.primitives.asymmetric import ec  # noqa: F401
        return True, ""
    except ImportError:
        return False, _("not installed")


def _b64(data):
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _unb64(text):
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


# ---------------------------------------------------------------------------- Keys and subscriptions

def _keys():
    """-> (private key, public one as base64url). Created and remembered the first time."""
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import ec
    with _lock:
        try:
            priv = serialization.load_pem_private_key(json.loads(read_text(KEYS_FILE))["private"].encode(), None)
        except FileNotFoundError:
            priv = None   # the very first time
        except (ValueError, KeyError, TypeError, AttributeError):
            # damaged: the key is lost anyway – set the file aside and start with a new one (devices sign up again)
            broken = KEYS_FILE.with_name(f"push_keys.defekt-{time.strftime('%Y%m%d-%H%M%S')}.json")   # file name: data
            os.replace(KEYS_FILE, broken)
            priv = None
        # any other OSError (NAS briefly not readable) goes up: a new key would make every signed-up device useless
        if priv is None:
            priv = ec.generate_private_key(ec.SECP256R1())
            pem = priv.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                     serialization.NoEncryption()).decode()
            write_atomic(KEYS_FILE, json.dumps({"private": pem}), 0o600)
    pub = priv.public_key().public_bytes(serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint)
    return priv, _b64(pub)


def public_key():
    return _keys()[1]


def _load():
    try:
        data = json.loads(read_text(SUBS_FILE))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def _save(data):
    write_atomic(SUBS_FILE, json.dumps(data), 0o600)


def push_host_ok(endpoint):
    u = urllib.parse.urlsplit(endpoint or "")
    host = (u.hostname or "").lower()
    return u.scheme == "https" and any(host == h or host.endswith("." + h) for h in PUSH_HOSTS)


def check(sub):
    """Check a subscription from the browser -> {"endpoint", "p256dh", "auth"} or ValueError."""
    if not isinstance(sub, dict):
        raise ValueError(_("Subscription missing"))
    endpoint = str(sub.get("endpoint") or "")
    keys = sub.get("keys") or {}
    if len(endpoint) > 1000 or not push_host_ok(endpoint):
        raise ValueError(_("Unknown push service"))
    try:
        p256dh, auth = _unb64(str(keys.get("p256dh") or "")), _unb64(str(keys.get("auth") or ""))
    except (ValueError, TypeError):
        raise ValueError(_("Invalid subscription keys"))
    if len(p256dh) != 65 or p256dh[0] != 4 or len(auth) != 16:
        raise ValueError(_("Invalid subscription keys"))
    return {"endpoint": endpoint, "p256dh": keys["p256dh"], "auth": keys["auth"]}


def add(account, sub, admin=False, origin="", lang=None):
    """Remember a device for an account (the same device replaces its old entry) – with the language of its interface,
    for the notifications it gets."""
    from .i18n import LANGS
    entry = {**check(sub), "admin": bool(admin), "origin": origin if origin.startswith("https://") else "",
             "added": int(time.time()), **({"lang": lang} if lang in LANGS else {})}
    with _lock:
        data = _load()
        for acc in list(data):   # same device under another account? remove it there
            data[acc] = [x for x in data[acc] if x.get("endpoint") != entry["endpoint"]]
        mine = data.setdefault(account.lower(), [])
        mine.append(entry)
        data[account.lower()] = mine[-MAX_DEVICES:]
        _save({k: v for k, v in data.items() if v})
    return len(data[account.lower()])


def remove(endpoint, account=None):
    with _lock:
        data = _load()
        for acc in list(data):
            if account is None or acc == account.lower():
                data[acc] = [x for x in data[acc] if x.get("endpoint") != endpoint]
        _save({k: v for k, v in data.items() if v})


def devices(account):
    return [x["endpoint"] for x in _load().get((account or "").lower(), [])]


def set_lang(endpoint, account, lang):
    """The interface of this device speaks another language now – its notifications follow."""
    from .i18n import LANGS
    if lang not in LANGS:
        return
    with _lock:
        data = _load()
        for x in data.get((account or "").lower(), []):
            if x.get("endpoint") == endpoint and x.get("lang") != lang:
                x["lang"] = lang
                _save(data)
                return


def lang_of(account):
    """The language of the account's device added last – None without devices (then the server language)."""
    subs = _load().get((account or "").lower(), [])
    return next((x["lang"] for x in reversed(subs) if x.get("lang")), None)


# ---------------------------------------------------------------------------- Encrypting and sending

def encrypt(payload, p256dh, auth, _salt=None, _key=None):
    """Encrypt a message for a device (RFC 8291, aes128gcm, one record)."""
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    from cryptography.hazmat.primitives.kdf.hkdf import HKDF
    ua_public = _unb64(p256dh)
    auth_secret = _unb64(auth)
    as_private = _key or ec.generate_private_key(ec.SECP256R1())
    as_public = as_private.public_key().public_bytes(serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint)
    shared = as_private.exchange(ec.ECDH(), ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256R1(), ua_public))
    ikm = HKDF(hashes.SHA256(), 32, auth_secret, b"WebPush: info\x00" + ua_public + as_public).derive(shared)
    salt = _salt or os.urandom(16)
    cek = HKDF(hashes.SHA256(), 16, salt, b"Content-Encoding: aes128gcm\x00").derive(ikm)
    nonce = HKDF(hashes.SHA256(), 12, salt, b"Content-Encoding: nonce\x00").derive(ikm)
    body = AESGCM(cek).encrypt(nonce, payload + b"\x02", None)
    return salt + struct.pack(">I", 4096) + bytes([len(as_public)]) + as_public + body


def vapid_header(endpoint, contact):
    """Authorization header: signed token (ES256) for this device's push service."""
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.hazmat.primitives.asymmetric.utils import decode_dss_signature
    priv, pub = _keys()
    u = urllib.parse.urlsplit(endpoint)
    head = _b64(json.dumps({"typ": "JWT", "alg": "ES256"}, separators=(",", ":")).encode())
    claims = _b64(json.dumps({"aud": f"{u.scheme}://{u.netloc}", "exp": int(time.time()) + 12 * 3600, "sub": contact},
                             separators=(",", ":")).encode())
    r, s = decode_dss_signature(priv.sign(f"{head}.{claims}".encode(), ec.ECDSA(hashes.SHA256())))
    return f"vapid t={head}.{claims}.{_b64(r.to_bytes(32, 'big') + s.to_bytes(32, 'big'))}, k={pub}"


def send(sub, title, body, path="", tag=None):
    """-> True (delivered), "gone" (subscription expired) or False."""
    if not push_host_ok(sub.get("endpoint")):
        return False
    origin = sub.get("origin") or ""
    url = (origin + "/" + path.lstrip("/")) if origin else "/" + path.lstrip("/")
    payload = json.dumps({"title": title[:120], "body": body[:600], "url": url, "tag": tag}).encode()
    data = encrypt(payload, sub["p256dh"], sub["auth"])
    contact = origin or "mailto:tuttiphon@localhost"
    req = urllib.request.Request(sub["endpoint"], data=data, method="POST", headers={
        "Content-Encoding": "aes128gcm", "Content-Type": "application/octet-stream", "TTL": "86400", "Urgency": "normal",
        "Authorization": vapid_header(sub["endpoint"], contact)})
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return 200 <= r.status < 300
    except urllib.error.HTTPError as e:
        return "gone" if e.code in (404, 410) else False
    except (urllib.error.URLError, OSError, ValueError):
        return False


def send_to(title, body, path="", accounts=(), admins=False, tag=None, make=None):
    """To all devices of these accounts (and, with admins, all administrator devices). make: a function -> (title,
    body), called in the language of each device (i18n.speaking) instead of title and body. -> True if one received
    it."""
    if not available()[0]:
        return False
    from .i18n import speaking
    accounts = {(a or "").lower() for a in accounts if a}
    targets = {}
    for acc, subs in _load().items():
        for sub in subs:
            if acc in accounts or (admins and sub.get("admin")):
                targets[sub["endpoint"]] = sub
    ok, texts = False, {}
    for sub in targets.values():
        if make:
            lang = sub.get("lang")
            if lang not in texts:
                with speaking(lang):
                    texts[lang] = make()
            title, body = texts[lang]
        res = send(sub, title, body, path, tag)
        if res == "gone":
            remove(sub["endpoint"])
        ok = ok or res is True
    return ok
