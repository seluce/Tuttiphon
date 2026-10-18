"""Languages of the server's texts. English is the source language: every text in the code is English and goes through
one of the functions below; German comes from app/locales/de/*.json ({"English text": "German text"}, one file per
area). A missing entry shows the English text.

* _(text)  – for the person using the interface: error messages and texts in API answers. Language of the request
  (header X-Lang, sent by the interface), outside a request the server language.
* _s(text) – texts that are written down or sent without anyone looking at the page: run logs, notifications,
  playlist names and descriptions for Navidrome, file headers. Always the server language: settings.language
  (Settings → General), "en" or "de".
* _n / _sn – the same with a count: _n(n, "{n} song", "{n} songs").

Values go into {placeholders}: _("Unknown playlist: {name}", name=x) – any name works, also "text". Only literal texts – tools/i18n_check.py reads
them from the code. Never translate at import time (the language changes per request and with the setting): fixed
texts in module-level constants are marked with N_("…") and translated where they are used, e.g. _(STEP_TITLES[s]).
"""
import json
import threading
import time
from pathlib import Path

LANGS = ("en", "de")
LOCALES = Path(__file__).resolve().parent / "locales"
_local = threading.local()
_dicts = {}
_lock = threading.Lock()
_server = {"lang": None, "at": 0.0}


def _dict(lang):
    """Dictionary English → lang, merged from app/locales/<lang>/*.json (loaded once)."""
    if lang not in _dicts:
        with _lock:
            merged = {}
            for f in sorted((LOCALES / lang).glob("*.json")):
                merged.update(json.loads(f.read_text(encoding="utf-8")))
            _dicts[lang] = merged
    return _dicts[lang]


def server_lang():
    """settings.language – checked at most every few seconds (log lines ask for it all the time)."""
    if _server["lang"] is None or time.monotonic() - _server["at"] > 5:
        from .config import load_config   # here, not at the top: config itself uses _()
        try:
            lang = (load_config().get("settings") or {}).get("language")
        except Exception:   # noqa: BLE001 – a broken configuration must not break every message
            lang = None
        _server.update(lang=lang if lang in LANGS else "en", at=time.monotonic())
    return _server["lang"]


def forget_server_lang():
    """After saving the configuration: use a new server language right away."""
    _server["lang"] = None


def use(lang):
    """Language of the current request (thread); None or an unknown value = server language."""
    _local.lang = lang if lang in LANGS else None


def current():
    return getattr(_local, "lang", None) or server_lang()


def tr(text, lang, /, **values):
    s = text if lang == "en" else _dict(lang).get(text, text)
    return s.format(**values) if values else s


def N_(text, /):
    """Marks a fixed text for translation without translating it (constants; translated where used)."""
    return text


def _(text, /, **values):
    return tr(text, current(), **values)


def _s(text, /, **values):
    return tr(text, server_lang(), **values)


def _n(n, one, other, /, **values):
    return tr(one if n == 1 else other, current(), n=n, **values)


def _sn(n, one, other, /, **values):
    return tr(one if n == 1 else other, server_lang(), n=n, **values)
