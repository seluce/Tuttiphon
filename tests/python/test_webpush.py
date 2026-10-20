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

    def test_one_message_per_device_even_with_two_persons(self):
        _, _, _, sub = browser()
        webpush.add("niklas", sub)
        cfg = base_config()
        cfg["settings"]["notify"] = {"enabled": True}
        cfg["personen"][0]["user"] = "niklas"                          # family and Niklas on the same account
        cfg["personen"][0]["likes"]["artists"] = ["Band A"]
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


if __name__ == "__main__":
    unittest.main()
