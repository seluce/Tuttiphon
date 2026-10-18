"""Scene catalog: which bands are typical for a kind of music (like Spotify's genre knowledge).

A music world can be linked to a scene. Then all bands of the catalog that appear in the library
belong to it automatically – also bands that are added later.

Name and description in app/scenes.json are English; catalog() and scene() return them translated
(app/locales/de/scenes.json) – in the language of the request, otherwise the server language.
"""
import json
import re
import unicodedata
from functools import lru_cache

from . import i18n
from .config import ROOT

CATALOG_FILE = ROOT / "app" / "scenes.json"


def norm(name):
    """Make names comparable: upper/lower case, apostrophe/hyphen variants, punctuation, "The"."""
    s = unicodedata.normalize("NFKC", name or "").casefold()
    s = re.sub(r"[’‘`´]", "'", s)
    s = re.sub(r"[‐‑‒–—]", "-", s)
    s = re.sub(r"^the\s+", "", s)
    s = re.sub(r"[\W_]+", " ", s)
    return " ".join(s.split())


@lru_cache(maxsize=1)
def _raw():
    return json.loads(CATALOG_FILE.read_text(encoding="utf-8"))


_by_lang = {}


def catalog():
    """The catalog in the current language – one list per language, the same object every time (callers use its
    id() as part of a cache key)."""
    lang = i18n.current()
    if lang not in _by_lang:
        _by_lang[lang] = [{**s, "name": i18n.tr(s["name"], lang), "description": i18n.tr(s.get("description", ""), lang)}
                          for s in _raw()]
    return _by_lang[lang]


def scene(scene_id):
    return next((s for s in catalog() if s["id"] == scene_id), None)


def members(scene_id, artist_index):
    """Bands of the scene that exist in the library (with the exact name from Navidrome)."""
    sc = scene(scene_id)
    if not sc or not artist_index:
        return []
    found = []
    for band in sc["bands"]:
        for name in sorted(artist_index.get(norm(band), ())):
            if name not in found:
                found.append(name)
    return found


def scenes_for_artist(name):
    key = norm(name)
    return [s["id"] for s in catalog() if any(norm(b) == key for b in s["bands"])]
