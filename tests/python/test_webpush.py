"""Notifications through the app (web push): checking and storing subscriptions, encryption (RFC 8291) and signature
(VAPID), delivery to the right devices, forgetting expired subscriptions, no duplicate messages per account.
No network – the push service is mocked. Needs cryptography (skipped otherwise)."""
from tests.python import env  # noqa: F401  (before app.*)

import json
import secrets
import unittest
import urllib.error
from unittest import mock

from app import notify, webpush
from tests.python.factory import base_config

HAVE = webpush.available()[0]


def browser():
    """Mock browser: key pair + subscription as from pushManager.subscribe()."""
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import ec
    key = ec.generate_private_key(ec.SECP256R1())
    pub = key.public_key().public_bytes(serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint)
    auth = b"0123456789abcdef"
    sub = {"endpoint": f"https://fcm.googleapis.com/fcm/send/{secrets.token_hex(8)}", "keys": {"p256dh": webpush._b64(pub), "auth": webpush._b64(auth)}}
    return key, pub, auth, sub


def decrypt(blob, key, pub, auth):
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    from cryptography.hazmat.primitives.kdf.hkdf import HKDF
    salt, idlen = blob[:16], blob[20]
    as_pub, ct = blob[21:21 + idlen], blob[21 + idlen:]
    shared = key.exchange(ec.ECDH(), ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256R1(), as_pub))
    ikm = HKDF(hashes.SHA256(), 32, auth, b"WebPush: info\x00" + pub + as_pub).derive(shared)
    cek = HKDF(hashes.SHA256(), 16, salt, b"Content-Encoding: aes128gcm\x00").derive(ikm)
    nonce = HKDF(hashes.SHA256(), 12, salt, b"Content-Encoding: nonce\x00").derive(ikm)
    return AESGCM(cek).decrypt(nonce, ct, None).rstrip(b"\x02")


class Resp:
    def __init__(self, status=201):
        self.status = status

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


@unittest.skipUnless(HAVE, "cryptography missing")
@env.german   # checks the German output of existing installations
class WebPushTest(unittest.TestCase):
    def setUp(self):
        for f in (webpush.SUBS_FILE, notify.SENT_FILE):
            f.unlink(missing_ok=True)
            self.addCleanup(f.unlink, missing_ok=True)

    def test_only_known_push_services(self):
        _, _, _, sub = browser()
        webpush.check(sub)
        for bad in ("https://192.168.1.10:4533/x", "http://fcm.googleapis.com/x", "https://evil.example/fcm.googleapis.com"):
            with self.assertRaises(ValueError):
                webpush.check({**sub, "endpoint": bad})
        with self.assertRaises(ValueError):
            webpush.check({**sub, "keys": {"p256dh": "kurz", "auth": "x"}})

    def test_encrypted_message_reaches_the_device(self):
        key, pub, auth, sub = browser()
        webpush.add("Jonas", sub, origin="https://tuttiphon.example")
        sent = []

        def fake(req, timeout=10):
            sent.append(req)
            return Resp(201)
        with mock.patch("urllib.request.urlopen", fake):
            self.assertTrue(webpush.send_to("Neu von Aqua", "„Aquarium“ ist da", "#/", accounts=["jonas"]))
        req = sent[0]
        self.assertEqual(req.get_header("Content-encoding"), "aes128gcm")
        msg = json.loads(decrypt(req.data, key, pub, auth))
        self.assertEqual((msg["title"], msg["url"]), ("Neu von Aqua", "https://tuttiphon.example/#/"))
        # VAPID: the token can be verified with the public key
        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.primitives.asymmetric import ec
        from cryptography.hazmat.primitives.asymmetric.utils import encode_dss_signature
        token, k = req.get_header("Authorization")[len("vapid t="):].split(", k=")
        head, claims, sig = token.split(".")
        raw = webpush._unb64(sig)
        der = encode_dss_signature(int.from_bytes(raw[:32], "big"), int.from_bytes(raw[32:], "big"))
        pubkey = ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256R1(), webpush._unb64(k))
        pubkey.verify(der, f"{head}.{claims}".encode(), ec.ECDSA(hashes.SHA256()))
        self.assertEqual(json.loads(webpush._unb64(claims))["aud"], "https://fcm.googleapis.com")

    def test_expired_subscription_is_forgotten(self):
        _, _, _, sub = browser()
        webpush.add("Jonas", sub)

        def gone(req, timeout=10):
            raise urllib.error.HTTPError(req.full_url, 410, "Gone", {}, None)
        with mock.patch("urllib.request.urlopen", gone):
            self.assertFalse(webpush.send_to("x", "y", accounts=["jonas"]))
        self.assertEqual(webpush.devices("jonas"), [])

    def test_routing_admins_and_accounts(self):
        _, _, _, admin_sub = browser()
        _, _, _, other_sub = browser()
        webpush.add("niklas", admin_sub, admin=True)
        webpush.add("Jonas", other_sub)
        hits = []
        with mock.patch.object(webpush, "send", side_effect=lambda sub, *a, **k: hits.append(sub["endpoint"]) or True):
            cfg = base_config()
            cfg["settings"]["notify"] = {"enabled": True}
            notify.after_run({"name": "Nacht", "results": {"scan": "fehler"}}, cfg)
        self.assertEqual(hits, [admin_sub["endpoint"]])               # errors only to administrator devices

    def test_one_message_per_device_and_album(self):
        _, _, _, sub = browser()
        webpush.add("niklas", sub)
        cfg = base_config()
        cfg["settings"]["notify"] = {"enabled": True}
        cfg["personen"][2]["likes"]["artists"] = ["Band A"]
        from app.rules import Library
        from tests.python.factory import iso_days_ago, song
        lib = Library([song("n", artist="Band A", album="Neu", created=iso_days_ago(1))])
        sent = []
        with mock.patch.object(webpush, "send", side_effect=lambda sub, title, *a, **k: sent.append(title) or True), \
                mock.patch("app.taste.profile", return_value=None):
            notify.for_persons(cfg, lib)
            notify.for_persons(cfg, lib)
        self.assertEqual(sent, ["Neu von Band A"])


class LanguageTest(unittest.TestCase):
    """Every device gets its notifications in the language of its interface; a person's ntfy topic in that of their
    account's devices."""

    def test_each_device_in_its_language(self):
        from app import i18n
        subs = {"anna": [{"endpoint": "https://push.example/1", "lang": "fr"},
                         {"endpoint": "https://push.example/2", "lang": "pl"},
                         {"endpoint": "https://push.example/3"}]}
        got, built = [], []

        def make():
            built.append(1)
            return (i18n._s("New for you this week"),
                    i18n._sn(5, "Tuttiphon: {n} new band classified", "Tuttiphon: {n} new bands classified"))
        with mock.patch.object(webpush, "available", lambda: (True, "")), mock.patch.object(webpush, "_load", lambda: subs), \
                mock.patch.object(webpush, "send", lambda sub, title, body, path="", tag=None: got.append((sub["endpoint"], title, body)) or True), \
                mock.patch.object(i18n, "server_lang", wraps=i18n.server_lang):
            self.assertTrue(webpush.send_to(None, None, "#/", accounts=["Anna"], make=make))
        mine = {e: (t, b) for e, t, b in got}
        self.assertEqual(mine["https://push.example/1"][0], i18n.tr("New for you this week", "fr"))
        self.assertEqual(mine["https://push.example/2"][1],
                         i18n.tr("Tuttiphon: {n} new bands classified", "pl", "many", n=5))   # Polish: 5 takes "many"
        self.assertNotEqual(mine["https://push.example/1"], mine["https://push.example/2"])
        self.assertEqual(len(built), 3)   # once per language

    def test_the_language_follows_the_interface(self):
        sub = {"endpoint": "https://fcm.googleapis.com/fcm/send/x", "keys": {"p256dh": "a", "auth": "b"}}
        import copy
        store = {"v": {}}   # like the file: every load a copy
        with mock.patch.object(webpush, "_load", lambda: copy.deepcopy(store["v"])), \
                mock.patch.object(webpush, "_save", lambda d: store.update(v=copy.deepcopy(d))), \
                mock.patch.object(webpush, "check", lambda s: {"endpoint": s["endpoint"], "keys": s["keys"]}):
            webpush.add("Anna", sub, lang="de")
            self.assertEqual(webpush.lang_of("anna"), "de")
            webpush.set_lang(sub["endpoint"], "anna", "nl")
            self.assertEqual(webpush.lang_of("Anna"), "nl")
            webpush.set_lang(sub["endpoint"], "anna", "xx")   # unknown: stays
            self.assertEqual(webpush.lang_of("anna"), "nl")
        self.assertIsNone(webpush.lang_of("nobody"))


if __name__ == "__main__":
    unittest.main()
