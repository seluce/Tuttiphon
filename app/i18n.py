"""Languages of the server's texts. English is the source language: every text in the code is English and goes through
one of the functions below; the other languages (LANGS) come from app/locales/<lang>/*.json ({"English text":
"translation"}, one file per area). A missing entry shows the English text. A text with a count (_n/_sn) picks its form
by the plural rules of the language (category()): the English "one" form for the category "one", otherwise the
"other" form – whose entry may be an object of forms such as {"few": …, "many": …} (Polish).

* _(text)  – for the person using the interface: error messages and texts in API answers. Language of the request
  (header X-Lang, sent by the interface), outside a request the server language.
* _s(text) – texts that are written down or sent without anyone looking at the page: run logs, notifications,
  playlist names and descriptions for Navidrome, file headers. Always the server language: settings.language
  (Settings → General), one of LANGS.
* _n / _sn – the same with a count: _n(n, "{n} song", "{n} songs").

The server log (stdout – docker logs) is always English: a translated text is a Text that also carries its English
form (.en, also for values that are translated texts themselves); events.say() and the run log print english(text).
Texts glued together with + keep both forms, f-strings and str.join() do not – use a template or join() for log lines.

Values go into {placeholders}: _("Unknown playlist: {name}", name=x) – any name works, also "text". Only literal texts – tools/i18n_check.py reads
them from the code. Never translate at import time (the language changes per request and with the setting): fixed
texts in module-level constants are marked with N_("…") and translated where they are used, e.g. _(STEP_TITLES[s]).
"""
import contextlib
import json
import threading
import time
from pathlib import Path

LANGS = ("en", "de", "fr", "nl", "es", "it", "pt", "pl")
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


@contextlib.contextmanager
def speaking(lang):
    """Texts for one reader: inside, _s()/_sn() speak lang instead of the server language (a notification to a device
    in the language it uses). None or an unknown language: the server language."""
    before = getattr(_local, "speak", None)
    _local.speak = lang if lang in LANGS else None
    try:
        yield
    finally:
        _local.speak = before


@contextlib.contextmanager
def reading_config():
    """While config.load_config() reads the file: a message from inside (a damaged or outdated file) must not read it
    again for the server language – that would start over until the stack runs out."""
    before = getattr(_local, "reading", False)
    _local.reading = True
    try:
        yield
    finally:
        _local.reading = before


def server_lang():
    """settings.language – checked at most every few seconds (log lines ask for it all the time); inside speaking() the
    reader's language."""
    if getattr(_local, "speak", None):
        return _local.speak
    if getattr(_local, "reading", False):
        return _server["lang"] or "en"
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


def requested():
    """The language the interface asked for in the current request – None if it sent none (or an unknown one)."""
    return getattr(_local, "lang", None)


def category(n, lang):
    """Plural category of the count n in lang (CLDR rules for whole numbers): "one", "few", "many" or "other"."""
    try:
        i = abs(int(n))
        if i != abs(float(n)):
            return "other"
    except (TypeError, ValueError):
        return "other"
    if lang == "pl":
        if i == 1:
            return "one"
        return "few" if 2 <= i % 10 <= 4 and not 12 <= i % 100 <= 14 else "many"
    if lang == "fr":
        return "one" if i in (0, 1) else "other"
    return "one" if i == 1 else "other"


def tr(text, lang, form="other", /, **values):
    """text in lang, {placeholders} filled; form: the plural category (an entry with several forms picks it)."""
    s = text if lang == "en" else _dict(lang).get(text, text)
    if isinstance(s, dict):
        s = s.get(form) or s.get("other") or s.get("many") or next(iter(s.values()), text)
    return s.format(**values) if values else s


class Text(str):
    """A translated text that also knows its English form (.en) – for the server log, which is always English."""

    def __new__(cls, local, en):
        obj = super().__new__(cls, local)
        obj.en = en
        return obj

    def __getnewargs__(self):   # copy.deepcopy() and pickle rebuild it with both forms
        return str(self), self.en

    def __add__(self, other):
        return Text(str.__add__(self, str(other)), self.en + english(other))

    def __radd__(self, other):
        return Text(str(other) + str(self), english(other) + self.en)


def english(text):
    """English form of a text (Text) or of an exception whose message is one – everything else as it is."""
    if isinstance(text, BaseException):
        args = text.args
        return english(args[0]) if len(args) == 1 and isinstance(args[0], Text) else str(text)
    return text.en if isinstance(text, Text) else str(text)


def said(error):
    """Message of an exception for a log line – with its English form if it is a translated text."""
    msg, en = str(error), english(error)
    return Text(msg, en) if en != msg else msg


def join(sep, parts):
    """sep.join(parts) that keeps the English form of translated parts."""
    parts = list(parts)
    local = sep.join(str(x) for x in parts)
    en = sep.join(english(x) for x in parts)
    return Text(local, en) if en != local else local


def _has_en(value):
    return isinstance(value, Text) or (isinstance(value, BaseException) and len(value.args) == 1
                                       and isinstance(value.args[0], Text))


def _both(text, lang, values, en_text=None, form="other"):
    """Text in lang – with its English form if that differs (values that are Texts go in as their English form).
    en_text: the English text if it is another one (a count: the forms of English and lang differ, e.g. 0 in French)."""
    local = tr(text, lang, form, **values)
    has_text = any(_has_en(v) for v in values.values())
    if lang == "en" and not has_text and en_text in (None, text):
        return local
    en = tr(en_text or text, "en", **({k: english(v) if _has_en(v) else v for k, v in values.items()} if has_text else values))
    return Text(local, en) if en != local else local


def _count(n, one, other, lang, values):
    form = category(n, lang)
    return _both(one if form == "one" else other, lang, {"n": n, **values}, one if n == 1 else other, form)


def N_(text, /):
    """Marks a fixed text for translation without translating it (constants; translated where used)."""
    return text


def _(text, /, **values):
    return _both(text, current(), values)


def _s(text, /, **values):
    return _both(text, server_lang(), values)


def _n(n, one, other, /, **values):
    return _count(n, one, other, current(), values)


def _sn(n, one, other, /, **values):
    return _count(n, one, other, server_lang(), values)
