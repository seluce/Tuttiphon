"""AI sound analysis – pretrained models from Essentia (Music Technology Group, Universitat Pompeu Fabra), local and
without a cloud. Adds to our own sound analysis (audio.py) what loudness and spectrum cannot tell:

* mood: happy, sad, relaxed, aggressive, party · danceability · vocals or instrumental ·
  acoustic or electronic
* music style: 400 styles (Discogs), e.g. "Rock---Power Metal" – averaged per band, this helps classify new bands,
  even when Last.fm does not know them
* themes (MTG-Jamendo, 56 classes): nine of them – Christmas, film music, epic, dark … (THEMES) – for sound filters and
  the search; the others repeat the moods or are too vague
* instruments (MTG-Jamendo, 40 classes: piano, electric guitar, violin …) – for sound filters and the search
* key (with the Camelot wheel for smooth transitions) and tempo – the AI tempo replaces our own estimate (more reliable)
* how easy a song is to listen to (approachable) and how much it asks for close listening (engaging) – sound filters
  such as "In the background" and "For listening closely"
* a sound vector per song (state/sound_vectors.json, app/similar.py): which songs and bands sound alike

Merged in classify.song_features(): the AI values refine the basic mood, arousal and danceability of our own
measurement (together with the Last.fm tags) and add the moods "instrumental" and "acoustic". The AI only runs over
songs the sound analysis already knows.

Available when Essentia (package essentia-tensorflow) is installed and the models are in MODELS_DIR – the Docker
image contains both. The models run in a separate process (ml_worker.py) that ends after the run – the server itself
never loads TensorFlow.

state/ml.json: {"v", "songs": {song id: {"v", "path", "depth", "m": {...}, "g": {...}, "t": {...}, "i": {...},
                                                 "k", "ks", "b", "bc"}
                                       | {"v", "path", "depth", "error": true, "at": timestamp}}, "lastRun", "open"}
Entries of an older VERSION stay usable until the song is analyzed again (they only lack the newer fields); entries of
a newer VERSION (after going back to an older Tuttiphon) count as current. If analyzing a song fails again (after
ATTEMPTS tries) while it has a good earlier result, that result and its sound vector stay and only "retry": timestamp
is noted – the song is tried again after RETRY_DAYS.
"""
import importlib.util
import itertools
import json
import os
import signal
import subprocess
import sys
import threading
import time
from collections import OrderedDict, defaultdict
from pathlib import Path

from . import audio, progress, similar
from .config import ROOT, STATE_DIR, env_var, paths, read_text, write_atomic
from .i18n import N_, _, _s
from .ml_worker import HEADS, SCORES, VERSION, missing_models

MODELS_DIR = Path(env_var("MODELS") or ROOT / "models")
STATE_FILE = STATE_DIR / "ml.json"
WORKER = Path(__file__).with_name("ml_worker.py")
KEYS = tuple(HEADS)            # order of the values in memory (tuple instead of dict: ~22,000 songs)
RETRY_DAYS = 30
SONG_TIMEOUT = 600     # seconds per song, after that the analysis process counts as hung
START_TIMEOUT = 300    # seconds for loading TensorFlow and the models, after that the process counts as hung
ATTEMPTS = 3           # a song that cannot be read is tried this often (files on the NAS share are sometimes briefly
RETRY_PAUSE = 0.3      # unreadable) – with a pause of RETRY_PAUSE × attempt seconds in between
TEMPO_AGREE = 0.6      # the AI tempo replaces our own when at least this share of its windows agree
KEY_MIN = 0.5          # weaker key estimates (atonal, mostly drums, speech) do not count
# The 40 instrument classes of the model (ids stored in state/ml.json and in sound filters) -> label;
# translated where shown: _(INSTRUMENTS[x])
INSTRUMENTS = {
    "accordion": N_("accordion"), "acousticbassguitar": N_("acoustic bass guitar"),
    "acousticguitar": N_("acoustic guitar"), "bass": N_("bass"), "beat": N_("beat"), "bell": N_("bells"),
    "bongo": N_("bongos"), "brass": N_("brass"), "cello": N_("cello"), "clarinet": N_("clarinet"),
    "classicalguitar": N_("classical guitar"), "computer": N_("computer sounds"), "doublebass": N_("double bass"),
    "drummachine": N_("drum machine"), "drums": N_("drums"), "electricguitar": N_("electric guitar"),
    "electricpiano": N_("electric piano"), "flute": N_("flute"), "guitar": N_("guitar"), "harmonica": N_("harmonica"),
    "harp": N_("harp"), "horn": N_("French horn"), "keyboard": N_("keyboard"), "oboe": N_("oboe"),
    "orchestra": N_("orchestra"), "organ": N_("organ"), "pad": N_("synth pad"), "percussion": N_("percussion"),
    "piano": N_("piano"), "pipeorgan": N_("pipe organ"), "rhodes": N_("Rhodes piano"), "sampler": N_("sampler"),
    "saxophone": N_("saxophone"), "strings": N_("strings"), "synthesizer": N_("synthesizer"),
    "trombone": N_("trombone"), "trumpet": N_("trumpet"), "viola": N_("viola"), "violin": N_("violin"),
    "voice": N_("voice"),
}
# Search words for instruments (the start of a word is enough, the longest match wins) -> instrument ids, the first one
# names the group – search words of all interface languages matched against the input, i.e. data
# i18n-ignore-start
_GUITARS = ["guitar", "acousticguitar", "electricguitar", "classicalguitar"]
_STRINGS = ["strings", "violin", "viola", "cello"]
_BRASS = ["brass", "trumpet", "trombone", "horn"]
INSTRUMENT_WORDS = {
    "klavier": ["piano"], "piano": ["piano"], "pianist": ["piano"], "epiano": ["electricpiano", "rhodes"],
    "rhodes": ["rhodes", "electricpiano"], "gitarr": _GUITARS, "guitar": _GUITARS,
    "akustikgitarr": ["acousticguitar", "classicalguitar"], "acousticguitar": ["acousticguitar", "classicalguitar"],
    "konzertgitarr": ["classicalguitar"], "classicalguitar": ["classicalguitar"], "egitarr": ["electricguitar"],
    "electricguitar": ["electricguitar"], "streicher": _STRINGS, "strings": _STRINGS, "geige": ["violin"],
    "violin": ["violin"], "bratsche": ["viola"], "viola": ["viola"], "cello": ["cello"], "kontrabass": ["doublebass"],
    "doublebass": ["doublebass"], "bass": ["bass", "doublebass"], "orchest": ["orchestra"], "flöte": ["flute"],
    "floete": ["flute"], "flute": ["flute"], "klarinett": ["clarinet"], "clarinet": ["clarinet"], "oboe": ["oboe"],
    "sax": ["saxophone"], "trompet": ["trumpet"], "trumpet": ["trumpet"], "posaun": ["trombone"],
    "trombon": ["trombone"], "waldhorn": ["horn"], "frenchhorn": ["horn"], "bläser": _BRASS, "blaeser": _BRASS,
    "blechbläser": _BRASS, "brass": _BRASS, "akkordeon": ["accordion"], "accordion": ["accordion"],
    "ziehharmonika": ["accordion"], "schifferklavier": ["accordion"], "mundharmonika": ["harmonica"],
    "harmonica": ["harmonica"], "harfe": ["harp"], "harp": ["harp"], "orgel": ["organ", "pipeorgan"],
    "organ": ["organ", "pipeorgan"], "kirchenorgel": ["pipeorgan"], "pipeorgan": ["pipeorgan"],
    "synth": ["synthesizer", "pad"], "synthesizer": ["synthesizer", "pad"], "synthie": ["synthesizer", "pad"],
    "saxophon": ["saxophone"], "saxofon": ["saxophone"], "schlagzeug": ["drums"], "drum": ["drums"], "drumcomputer": ["drummachine"],
    "drummachine": ["drummachine"], "trommel": ["drums", "percussion"], "perkussion": ["percussion"],
    "percussion": ["percussion"], "bongo": ["bongo"], "glocke": ["bell"], "glockensp": ["bell"], "bells": ["bell"],
    "keyboard": ["keyboard"],
}
# the same in French, Dutch, Spanish, Italian, Portuguese and Polish – a typed word must cover most of such a key
# before it counts as its start (_word: „świat“ is no „świąteczny“)
_INSTRUMENT_MORE = {
    "chitarr": _GUITARS, "gitaar": _GUITARS, "gitara": _GUITARS, "violon": ["violin"], "violín": ["violin"],
    "viool": ["violin"], "skrzyp": ["violin"], "violoncel": ["cello"], "violonch": ["cello"], "wiolonczel": ["cello"],
    "contrebass": ["doublebass"], "contrabajo": ["doublebass"], "contrabbass": ["doublebass"],
    "contrabaix": ["doublebass"], "cordes": _STRINGS, "cuerdas": _STRINGS, "cordas": _STRINGS,
    "strijk": _STRINGS, "smyczk": _STRINGS, "flûte": ["flute"], "flauta": ["flute"], "flauto": ["flute"],
    "fluit": ["flute"], "flet": ["flute"], "klarinet": ["clarinet"], "klarnet": ["clarinet"], "tromba": ["trumpet"],
    "trąbka": ["trumpet"], "trabka": ["trumpet"], "trąbki": ["trumpet"], "trabki": ["trumpet"], "cuivres": _BRASS, "ottoni": _BRASS, "accordéon": ["accordion"],
    "accordeon": ["accordion"], "acordeón": ["accordion"], "acordeon": ["accordion"], "acordeão": ["accordion"],
    "fisarmonic": ["accordion"], "akordeon": ["accordion"], "armónic": ["harmonica"], "armonic": ["harmonica"],
    "harmonijk": ["harmonica"], "harpe": ["harp"], "arpa": ["harp"], "harpa": ["harp"], "harfa": ["harp"],
    "orgue": ["organ", "pipeorgan"], "órgano": ["organ", "pipeorgan"], "organo": ["organ", "pipeorgan"],
    "órgão": ["organ", "pipeorgan"], "orgao": ["organ", "pipeorgan"], "organy": ["organ", "pipeorgan"],
    "batterie": ["drums"], "batería": ["drums"], "bateria": ["drums"], "batteria": ["drums"],
    "perkusj": ["drums", "percussion"], "percusi": ["percussion"], "percuss": ["percussion"], "saksofon": ["saxophone"],
    "sintet": ["synthesizer", "pad"], "orkest": ["orchestra"], "orquest": ["orchestra"], "orkiestr": ["orchestra"],
    "cloche": ["bell"], "campan": ["bell"], "dzwonk": ["bell"], "dzwony": ["bell"],
}
INSTRUMENT_WORDS.update(_INSTRUMENT_MORE)
# short search words only count with these endings ("harp" fits "harps", not the band "Harpyie"; "organ" not "organic")
_ENDINGS = ("", "musik", "music", "klang", "klänge", "solo", "sound", "sounds", "ist", "isten", "er")
# two-word search terms that become one word before the input is split
INSTRUMENT_PHRASES = {"e-gitarre": "egitarre", "e-piano": "epiano", "acoustic guitar": "acousticguitar",
                      "classical guitar": "classicalguitar", "electric guitar": "electricguitar",
                      "double bass": "doublebass", "french horn": "frenchhorn", "pipe organ": "pipeorgan",
                      "drum machine": "drummachine"}
# i18n-ignore-end
# Themes of the mood/theme model (MTG-Jamendo, 56 classes, stored per song as "t": the strongest six from 0.02) that
# sound filters and the search offer: id (stored in sound filters) -> label; translated where shown: _(THEMES[x]).
# Left out: classes that repeat a mood or a listening vibe (calm, relaxing, soft, slow, meditative, energetic,
# powerful, fast, heavy, upbeat, happy, positive, fun, funny, uplifting, hopeful, inspiring, motivational, sad,
# melancholic, emotional, party, groovy, background), vague ones (cool, deep, melodic, dream, sexy, retro, commercial,
# corporate, advertising, drama, dramatic, soundscape) and those the model hardly ever recognizes – measured on 367
# songs of our library they never or almost never reach the stored six, and the few hits look random (children,
# holiday, movie, travel, game, nature, documentary, trailer, sport, adventure, action).
THEMES = {
    "christmas": N_("Christmas"), "film": N_("film music"), "epic": N_("epic"), "dark": N_("dark"),
    "love": N_("love songs"), "romantic": N_("romantic"), "ballad": N_("ballads"), "summer": N_("summer"),
    "space": N_("space"),
}
# A theme counts as "in the song" from this strength (the model's values differ a lot per class: "love" has a median
# of 0.10, "space" hardly ever exceeds 0.1) – chosen so that each theme picks a few percent of the library: measured
# on one song per band (243 bands), see docs/06-intelligence.md
THEME_PRESENT = {"christmas": 0.2, "film": 0.12, "epic": 0.15, "dark": 0.1, "love": 0.2, "romantic": 0.08,
                 "ballad": 0.12, "summer": 0.08, "space": 0.06}
# Delivered vibes that hide the same content from every other playlist (excludeElsewhere): a playlist that asks for
# the theme may contain it all the same (rules.shown_vibes)
THEME_VIBES = {"christmas": "weihnachten"}
# Search words for themes (the start of a word is enough, as for instruments) -> theme ids – search words of all
# interface languages matched against the input, i.e. data
# i18n-ignore-start
THEME_WORDS = {
    "weihnacht": ["christmas"], "christmas": ["christmas"], "xmas": ["christmas"], "filmmusik": ["film"],
    "film": ["film"], "filmisch": ["film"], "soundtrack": ["film"], "kino": ["film"], "movie": ["film"],
    "cinematic": ["film"], "episch": ["epic"], "epic": ["epic"], "düster": ["dark"], "duester": ["dark"],
    "finster": ["dark"], "dark": ["dark"], "liebeslied": ["love"], "lovesong": ["love"], "liebe": ["love"],
    "love": ["love"], "romanti": ["romantic"], "ballade": ["ballad"], "ballad": ["ballad"], "sommer": ["summer"],
    "summer": ["summer"], "weltraum": ["space"], "weltall": ["space"], "space": ["space"], "kosmisch": ["space"],
    "cosmic": ["space"],
}
_THEME_MORE = {   # the same in French, Dutch, Spanish, Italian, Portuguese and Polish
    "noël": ["christmas"], "navidad": ["christmas"], "navideñ": ["christmas"],
    "natale": ["christmas"], "natal": ["christmas"], "natalin": ["christmas"], "kerstmis": ["christmas"],
    "kerstlied": ["christmas"], "kerstmuziek": ["christmas"], "świątecz": ["christmas"], "swiatecz": ["christmas"],
    "kolędy": ["christmas"], "koledy": ["christmas"], "cinéma": ["film"], "cine": ["film"], "películ": ["film"],
    "pelicul": ["film"], "épique": ["epic"], "epique": ["epic"], "épico": ["epic"], "épica": ["epic"],
    "epico": ["epic"], "epicki": ["epic"], "sombre": ["dark"], "oscuro": ["dark"],
    "oscura": ["dark"], "escuro": ["dark"], "escura": ["dark"], "duister": ["dark"], "mroczn": ["dark"],
    "amour": ["love"], "amor": ["love"], "amore": ["love"], "liefde": ["love"], "miłość": ["love"],
    "milosc": ["love"], "miłosn": ["love"], "románti": ["romantic"], "romantycz": ["romantic"],
    "balada": ["ballad"], "ballata": ["ballad"], "verano": ["summer"], "verão": ["summer"], "verao": ["summer"],
    "estivo": ["summer"], "estiva": ["summer"], "zomer": ["summer"], "letni": ["summer"], "espace": ["space"],
    "espacio": ["space"], "spazio": ["space"], "espaço": ["space"], "ruimte": ["space"], "kosmos": ["space"],
    "cosmiq": ["space"], "cósmic": ["space"], "cosmico": ["space"], "cosmica": ["space"],
}
THEME_WORDS.update(_THEME_MORE)
_STRICT = set(_INSTRUMENT_MORE) | set(_THEME_MORE)
THEME_PHRASES = {"x-mas": "xmas", "love song": "lovesong", "film music": "filmmusic", "outer space": "space",
                 "musique de film": "film", "bande originale": "film", "banda sonora": "film",
                 "colonna sonora": "film", "trilha sonora": "film"}
# i18n-ignore-end
# Camelot wheel: key -> number 1–12 (A = minor, B = major); neighbours on the wheel blend well
_PITCH = {"C": 0, "C#": 1, "Db": 1, "D": 2, "D#": 3, "Eb": 3, "E": 4, "F": 5, "F#": 6, "Gb": 6, "G": 7, "G#": 8,
          "Ab": 8, "A": 9, "A#": 10, "Bb": 10, "B": 11}
_lock = threading.Lock()          # reading and writing ml.json during a run
_refresh_lock = threading.Lock()  # reading ml.json into memory (_refresh): once, even with parallel requests
_memo_lock = threading.Lock()
_cache = {"stamp": None, "songs": {}, "styles": {}, "labels": {}, "tempo": {}, "keys": {}, "instr": {}, "scores": {},
          "themes": {}}


# ---------------------------------------------------------------------------- Availability

def available():
    """-> (ready?, reason). Only checks files and the package – does not load TensorFlow."""
    if importlib.util.find_spec("essentia") is None:
        return False, _("Essentia is not installed (included in the Docker image).")
    left = missing_models(MODELS_DIR)
    if left:
        return False, _("AI models missing ({n} files) – rebuild the image.", n=len(left))
    return True, ""


# ---------------------------------------------------------------------------- State

def load():
    try:
        data = json.loads(read_text(STATE_FILE))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def _load_for_run(log):
    """Like load(), but a broken file is set aside instead of silently overwritten (work of many nights)."""
    try:
        data = json.loads(read_text(STATE_FILE))
    except FileNotFoundError:
        return {}
    except ValueError:
        broken = STATE_FILE.with_name(f"ml.defekt-{time.strftime('%Y%m%d-%H%M%S')}.json")   # file name: data
        os.replace(STATE_FILE, broken)
        log(_s("⚠ AI sound analysis: the results file was damaged – set aside as {name}, starting over.", name=broken.name))
        return {}
    return data if isinstance(data, dict) else {}


def save(data):
    try:
        write_atomic(STATE_FILE, json.dumps(data, separators=(",", ":"), ensure_ascii=False))
    except OSError:
        pass


def _vectors_for_run(log):
    """The sound vectors (state/sound_vectors.json) to extend – a damaged file is set aside like ml.json; the songs
    concerned are then simply due again (_todo)."""
    try:
        raw = read_text(similar.STATE_FILE)
    except FileNotFoundError:
        return {}
    try:
        data = json.loads(raw)
    except ValueError:
        broken = similar.STATE_FILE.with_name(f"sound_vectors.defekt-{time.strftime('%Y%m%d-%H%M%S')}.json")   # file name: data
        os.replace(similar.STATE_FILE, broken)
        log(_s("⚠ AI sound analysis: the results file was damaged – set aside as {name}, starting over.", name=broken.name))
        return {}
    if not isinstance(data, dict) or data.get("v") != similar.VERSION:   # other projection: start over
        return {}
    songs = data.get("songs")
    return dict(songs) if isinstance(songs, dict) else {}


def _save_vectors(vectors):
    try:
        similar.save(vectors)
    except OSError:
        pass


def _stamp():
    try:
        st = STATE_FILE.stat()
        return (st.st_mtime_ns, st.st_size)
    except OSError:
        return None


_EMPTY = ("songs", "styles", "labels", "tempo", "keys", "instr", "scores", "themes")


def _refresh():
    """Read ml.json into memory when it has changed – only once even with parallel requests (the file has ~17 MB at
    25,000 songs; every parse costs seconds and a few hundred MB for a moment)."""
    stamp = _stamp()
    if stamp is None:   # no file (yet): everything empty
        _cache.update(stamp=None, **{k: {} for k in _EMPTY})
        return
    if _cache.get("stamp") == stamp:
        return
    with _refresh_lock:
        if _cache.get("stamp") != _stamp():   # not read by another request in the meantime
            _read_into_cache(_stamp())


def _copy(value):
    """A float as a new object: nothing in the cache points into the parsed file any more, so its memory can go back
    to the system (otherwise a few cached numbers per memory block keep ~45 MB of it at 25,000 songs)."""
    return value * 1.0 if value.__class__ is float else value


def _read_into_cache(stamp):
    songs, styles, labels, tempo, keys, instr, scores, themes = {}, {}, {}, {}, {}, {}, {}, {}
    names = {}

    def name(text):   # the same ~400 names only once in memory – as new objects (see _copy)
        out = names.get(text)
        if out is None:
            out = names[text] = sys.intern(text.encode("utf-8", "surrogatepass").decode("utf-8", "surrogatepass"))
        return out
    raw = load().get("songs") or {}
    for sid in list(raw):
        e = raw.pop(sid)   # each parsed entry is freed right after – the parsed file and the copies never peak together
        m = e.get("m")
        if e.get("error") or not m:
            continue
        sid = sid.encode("utf-8", "surrogatepass").decode("utf-8", "surrogatepass")
        songs[sid] = tuple(_copy(float(m.get(k, 0.5))) for k in KEYS)
        styles[sid] = {name(k): _copy(v) for k, v in (e.get("g") or {}).items()}
        for style in styles[sid]:
            label = style.split("---")[-1]
            labels.setdefault(label.lower(), label)
        if isinstance(e.get("b"), (int, float)) and e["b"] > 0:
            tempo[sid] = (_copy(float(e["b"])), _copy(float(e.get("bc") or 0)))
        if isinstance(e.get("k"), str) and camelot(e["k"]):
            keys[sid] = (name(e["k"]), _copy(float(e.get("ks") or 0)))
        if isinstance(e.get("i"), dict) and e["i"]:
            instr[sid] = {name(k): _copy(v) for k, v in e["i"].items() if k in INSTRUMENTS}
        th = e.get("t")
        if isinstance(th, dict):   # only the offered themes, from their strength (THEME_PRESENT)
            th = {name(k): _copy(v) for k, v in th.items() if k in THEMES and isinstance(v, (int, float))
                  and v >= THEME_PRESENT[k]}
            if th:
                themes[sid] = th
        sc = {k: _copy(float(m[k])) for k in SCORES if isinstance(m.get(k), (int, float)) and not isinstance(m[k], bool)}
        if sc:   # only from VERSION 3 – an older entry has none (and does not count as a middle value)
            scores[sid] = sc
    _cache.update(stamp=stamp, songs=songs, styles=styles, labels=labels, artists=OrderedDict(), tempo=tempo,
                  keys=keys, instr=instr, scores=scores, themes=themes)


def features():
    """Song id -> tuple of the AI values in the order of KEYS (in memory until the file changes)."""
    _refresh()
    return _cache["songs"]


def stamp():
    _refresh()
    return _cache["stamp"]


def tempo():
    """Song id -> (AI tempo in BPM, share of the windows that agree) – classify.song_features() decides which tempo
    counts (TEMPO_AGREE)."""
    _refresh()
    return _cache["tempo"]


def keys():
    """Song id -> (key as "A minor", strength 0–1)."""
    _refresh()
    return _cache["keys"]


def instruments():
    """Song id -> {instrument: strength} – the strongest ones of the song (at most 5, from 0.1)."""
    _refresh()
    return _cache["instr"]


def themes():
    """Song id -> {theme: strength} – only the offered themes (THEMES) the AI hears in the song (from THEME_PRESENT);
    songs without any are left out."""
    _refresh()
    return _cache["themes"]


def scores():
    """Song id -> {"approachable": 0–1, "engaging": 0–1} – only songs analyzed with VERSION 3 or later.
    approachable: high = mainstream, easy to get into; low = demanding, experimental. engaging: high = asks for close
    listening (in our library loud, lively songs score high as well), low = background music."""
    _refresh()
    return _cache["scores"]


def approachable(sid):
    """How easy the song is to listen to (0–1), None without the analysis."""
    return scores().get(sid, {}).get("approachable")


def engaging(sid):
    """How much the song asks for close listening (0–1), None without the analysis."""
    return scores().get(sid, {}).get("engaging")


def camelot(key):
    """"A minor" -> "8A", "C major" -> "8B" (Camelot wheel) – None if unknown."""
    note, _sp, scale = (key or "").partition(" ")
    pitch = _PITCH.get(note)
    if pitch is None or scale not in ("major", "minor"):
        return None
    # C major = 8B, every fifth up one number; a minor key has the number of its relative major (3 semitones up)
    major = (pitch + 3) % 12 if scale == "minor" else pitch
    return f"{(major * 7 % 12 + 7) % 12 + 1}{'A' if scale == 'minor' else 'B'}"


def key_distance(a, b):
    """Steps between two Camelot codes: 0 same key, 1 neighbour (±1 or major/minor of the same number) … 7."""
    na, la, nb, lb = int(a[:-1]), a[-1], int(b[:-1]), b[-1]
    d = abs(na - nb) % 12
    d = min(d, 12 - d)
    return d + (la != lb)


def song_info(sid):
    """For the song window: key, Camelot code, the strongest instruments and the themes – {} without AI analysis."""
    _refresh()
    out = {}
    k = _cache["keys"].get(sid)
    if k:
        out.update(key=k[0], camelot=camelot(k[0]), keyStrength=round(k[1], 2))
    inst = _cache["instr"].get(sid)
    if inst:
        out["instruments"] = [{"id": x, "label": _(INSTRUMENTS[x]), "strength": round(v, 2)}   # i18n-ignore – N_ labels
                              for x, v in sorted(inst.items(), key=lambda kv: -kv[1])]
    th = _cache["themes"].get(sid)
    if th:
        out["themes"] = [{"id": x, "label": _(THEMES[x]), "strength": round(v, 2)}   # i18n-ignore – N_ labels
                         for x, v in sorted(th.items(), key=lambda kv: -kv[1])]
    return out


def instrument_word(word):
    """Search word -> instrument ids (longest matching word start), or None: "Klaviermusik" -> ["piano"]."""
    return _word(word, INSTRUMENT_WORDS)


def theme_word(word):
    """Search word -> theme ids (longest matching word start), or None: "Weihnachtsmusik" -> ["christmas"]."""
    return _word(word, THEME_WORDS)


def _word(word, table):
    """Search word -> ids of the longest matching key of table (a word start; short keys only with fitting endings) –
    otherwise of the shortest key that a typed word of 5 letters or more begins – a key of the other languages only if
    the word covers three quarters of it ("violon" is the violin, not the "violoncelle"; "swiat" is no "świąteczny")."""
    best, begun = None, None
    for k, ids in table.items():
        if word.startswith(k):
            rest = word[len(k):]
            if len(k) <= 5 and rest.removeprefix("en").removeprefix("e").removeprefix("n").removeprefix("s") not in _ENDINGS \
                    and rest not in _ENDINGS:
                continue
            if best is None or len(k) > len(best[0]):
                best = (k, ids)
        elif len(word) >= 5 and k.startswith(word) and (k not in _STRICT or len(word) * 4 >= len(k) * 3) \
                and (begun is None or len(k) < len(begun[0])):   # „weihn“ – but not „swiat“ of „świątecz…“
            begun = (k, ids)
    hit = best or begun
    return hit[1] if hit else None


def search_instruments(q, lib):
    """Search: instruments whose search word, label (in the page's language or English) or id fits the input (from 3
    letters) -> [{id, label, ids, count}] – ids: the instruments searched for together (e.g. all guitars), count:
    songs of the library that clearly contain one of them."""
    q = (q or "").strip().lower()
    if len(q) < 3:
        return []
    _refresh()
    groups = []
    word = instrument_word(q.replace(" ", ""))
    if word:
        groups.append(word)
    for x, english in INSTRUMENTS.items():
        label = _(english)   # i18n-ignore – N_ labels
        if (q in label.lower() or q in english.lower() or q == x) and not any(x in g for g in groups):
            groups.append([x])
    if not groups:
        return []
    ids = {s["id"] for s in lib.songs}
    out = []
    for g in groups[:4]:
        n = sum(1 for sid, inst in _cache["instr"].items()
                if sid in ids and any(inst.get(y, 0) >= audio.INSTRUMENT_PRESENT for y in g))
        if n:
            out.append({"id": g[0], "label": _(INSTRUMENTS[g[0]]), "ids": g, "count": n})   # i18n-ignore – N_ labels
    return out


def instrument_catalog(lib=None):
    """All instruments with label and how many songs of the library clearly contain them (strength from
    audio.INSTRUMENT_PRESENT) – for the sound editor and the search. Sorted by label."""
    _refresh()
    counts = {}
    ids = {s["id"] for s in lib.songs} if lib is not None else None
    for sid, inst in _cache["instr"].items():
        if ids is not None and sid not in ids:
            continue
        for x, v in inst.items():
            if v >= audio.INSTRUMENT_PRESENT:
                counts[x] = counts.get(x, 0) + 1
    items = [{"id": x, "label": _(label), "songs": counts.get(x, 0)} for x, label in INSTRUMENTS.items()]   # i18n-ignore – N_ labels
    return {"available": bool(_cache["instr"]), "instruments": sorted(items, key=lambda x: x["label"].lower())}


def search_themes(q, lib):
    """Search: themes whose search word, label (in the page's language or English) or id fits the input (from 3
    letters) -> [{id, label, ids, count}] – count: songs of the library in which the AI hears the theme (THEME_PRESENT);
    themes without songs are left out."""
    q = (q or "").strip().lower()
    if len(q) < 3:
        return []
    _refresh()
    text = q
    for phrase, word in THEME_PHRASES.items():
        text = text.replace(phrase, word)
    groups = []
    for w in [text.replace(" ", "")] + text.split():
        ids = theme_word(w)
        if ids and ids not in groups:
            groups.append(ids)
    for x, english in THEMES.items():
        label = _(english)   # i18n-ignore – N_ labels
        if (q in label.lower() or q in english.lower() or q == x) and not any(x in g for g in groups):
            groups.append([x])
    ids = {s["id"] for s in lib.songs}
    out = []
    for g in groups[:4]:
        n = sum(1 for sid, th in _cache["themes"].items() if sid in ids and any(y in th for y in g))
        if n:
            out.append({"id": g[0], "label": _(THEMES[g[0]]), "ids": g, "count": n})   # i18n-ignore – N_ labels
    return out


def theme_catalog(lib=None):
    """All themes with label and how many songs of the library have them (THEME_PRESENT) – for the sound editor.
    Sorted by label."""
    _refresh()
    counts = {}
    ids = {s["id"] for s in lib.songs} if lib is not None else None
    for sid, th in _cache["themes"].items():
        if ids is not None and sid not in ids:
            continue
        for x in th:
            counts[x] = counts.get(x, 0) + 1
    items = [{"id": x, "label": _(label), "songs": counts.get(x, 0)} for x, label in THEMES.items()]   # i18n-ignore – N_ labels
    return {"available": bool(_cache["themes"]), "themes": sorted(items, key=lambda x: x["label"].lower())}


def sound_catalog(lib=None):
    """GET /api/sound/catalog: instruments and themes of the AI with labels in the
    request's language and song counts. available / themesAvailable: the AI has recognized instruments / themes."""
    th = theme_catalog(lib)
    return {**instrument_catalog(lib), "themes": th["themes"], "themesAvailable": th["available"]}


def artist_styles(lib):
    """Band -> {style: strength 0–1} – mean over the analyzed songs, the strongest style = 1. For the classification."""
    _refresh()
    key = songs_key(lib)
    memo = _cache.get("artists")   # emptied when ml.json changes (_refresh)
    if not isinstance(memo, OrderedDict):
        memo = _cache["artists"] = OrderedDict()
    with _memo_lock:
        if key in memo:
            memo.move_to_end(key)
            return memo[key]
    acc, n = defaultdict(lambda: defaultdict(float)), defaultdict(int)
    for s in lib.songs:
        g = _cache["styles"].get(s["id"])
        if g is None:
            continue
        artist = lib._main_artist(s)
        n[artist] += 1
        for name, x in g.items():
            acc[artist][name.split("---")[-1].lower()] += x
    out = {}
    for artist, styles in acc.items():
        top = sorted(styles.items(), key=lambda kv: -kv[1])[:8]
        hi = top[0][1] if top else 0
        if hi <= 0:
            continue
        out[artist] = {k: round(v / hi, 3) for k, v in top if v / hi >= 0.15}
    with _memo_lock:   # a few song lists at once (default list, account lists): one entry each instead of thrashing
        for k in [k for k in memo if gone(k)]:
            del memo[k]
        memo[key] = out
        while len(memo) > MEMO_SIZE:
            memo.popitem(last=False)
    return out


_lib_ids = itertools.count(1)
MEMO_SIZE = 8   # song lists per cache (classify, ml, similar): the default list, accounts, the list before a reload


def lib_key(lib):
    """Unique key of a song list for caches (id() can come back after garbage collection)."""
    if not hasattr(lib, "_nt_key"):
        lib._nt_key = next(_lib_ids)
    return lib._nt_key


def gone(key):
    """Is this songs_key() of a song list that no longer exists (rules.RELEASED)? Then its cache entries can go."""
    from .rules import RELEASED
    return isinstance(key, tuple) and len(key) == 2 and key[0] == "songs" and key[1] in RELEASED


def songs_key(lib):
    """Key of a song list for caches that only depend on its songs and their account-independent fields (bands, order):
    an account list that shares its rule caches with the default list (rules.Library.share_with) gets the same key –
    sound features, band styles and the sound index are then computed once."""
    own = getattr(lib, "songs_key", None)
    return ("songs", own()) if callable(own) else lib_key(lib)


def style_label(key):
    """"power metal" -> "Power Metal" (spelling of the models, for display)."""
    return _cache["labels"].get(key, key)


# ---------------------------------------------------------------------------- Merging

def _clip(x):
    return 0.0 if x < 0 else 1.0 if x > 1 else x


def fuse(f, m, tag_valence=None):
    """Our own measurement f (audio.derive) + AI values m (+ Last.fm mood) -> features for moods and sound filters.
    The AI recognizes mood much better than loudness and spectrum; tempo and energy stay from the measurement."""
    v = dict(zip(KEYS, m))
    ml_val = _clip(0.5 + 0.4 * (v["happy"] - v["sad"]) + 0.15 * (v["party"] - 0.5))
    # wound up = aggressive OR party (children's pop is not aggressive, but just as wound up)
    ml_aro = _clip(0.5 + 0.45 * (max(v["aggressive"], v["party"]) - v["relaxed"]))
    parts = [(ml_val, 0.6), (f["valence"], 0.15)] + ([(tag_valence, 0.25)] if tag_valence is not None else [])
    valence = sum(x * w for x, w in parts) / sum(w for _, w in parts)
    return {**f, "valence": round(valence, 3), "arousal": round(0.6 * f["arousal"] + 0.4 * ml_aro, 3),
            "dance": round(0.5 * f["dance"] + 0.5 * v["dance"], 3), "inst": round(1 - v["voice"], 3),
            "acoustic": round(v["acoustic"], 3), "electronic": round(v["electronic"], 3), "vsrc": "ml"}


# ---------------------------------------------------------------------------- Run

def _depth(cfg):
    """How much of a song the AI hears: like the sound analysis, at most "thorough" (3 × 40 s: beginning, middle,
    end) – the whole song would hardly add anything but cost many times as much on the NAS."""
    depth = audio._depth(cfg)
    return "gruendlich" if depth == "tief" else depth


def _todo(lib, songs, depth, everything, vectors=None):
    """Songs that are due (again) – only those the sound analysis already knows. Songs the AI has never heard come
    first (newest first), then the ones to analyze again (newer VERSION, other path, deeper depth, retry – newest
    first as well). vectors: song ids with a sound vector – an analyzed song without one is due again (e.g. after a
    damaged state/sound_vectors.json); None = do not check."""
    measured = audio.features()
    out = []
    for i, s in enumerate(lib.songs):
        if s["id"] not in measured:
            continue
        rel = lib.real_path(i)
        if not rel:
            continue
        cur = songs.get(s["id"])
        if cur and not everything and not cur.get("error") and cur.get("retry") \
                and time.time() - cur["retry"] < RETRY_DAYS * 86400:
            continue   # the last attempt failed: the earlier result stays until the next try
        if cur and not everything and _current(cur) and cur.get("path") == rel:
            if cur.get("error"):
                if time.time() - (cur.get("at") or 0) < RETRY_DAYS * 86400:
                    continue
            elif audio.DEPTH_ORDER.index(cur.get("depth", "standard")) >= audio.DEPTH_ORDER.index(depth) and (
                    vectors is None or s["id"] in vectors or cur.get("nosv")):
                continue
        out.append((cur is None, s.get("created") or "", i, rel))
    out.sort(reverse=True)
    return [(created, i, rel) for _new, created, i, rel in out]


def _current(entry):
    """Analyzed with this VERSION or a newer one (after going back to an older Tuttiphon the newer results stay)."""
    v = entry.get("v")
    return isinstance(v, int) and not isinstance(v, bool) and v >= VERSION


def _failed(songs, vectors, sid, rel, depth):
    """A song could not be analyzed: a good earlier result stays – with its sound vector –, only the time of the
    attempt is noted (the song is tried again after RETRY_DAYS). Without one the song is marked as not readable."""
    cur = songs.get(sid)
    if cur and not cur.get("error") and cur.get("m"):
        cur["retry"] = int(time.time())
        return
    songs[sid] = {"v": VERSION, "path": rel, "depth": depth, "error": True, "at": int(time.time())}
    vectors.pop(sid, None)


def pending(cfg, lib):
    """How many songs the AI would still analyze (0 if it is not available or turned off)."""
    an = cfg["settings"].get("analysis") or {}
    if not an.get("ml", True) or not available()[0]:
        return 0
    return len(_todo(lib, load().get("songs") or {}, _depth(cfg), False, similar.stored()))


class _Canceled(Exception):
    """The run was canceled while the analysis process was starting."""


class _Worker:
    """The analysis process (ml_worker.py) – restarted when needed if it crashes."""

    def __init__(self, threads, track, stop=None):
        self.threads, self.track, self.stop, self.proc = threads, track, stop, None

    def start(self, timeout=START_TIMEOUT):
        """Start the process and wait until it has loaded the models – at most timeout seconds (a hang while loading
        TensorFlow must not block the run, and with it the night window, for good)."""
        env = {**os.environ, "TUTTIPHON_ML_THREADS": str(self.threads)}
        self.proc = subprocess.Popen([sys.executable, str(WORKER), str(MODELS_DIR)], stdin=subprocess.PIPE,
                                     stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, env=env,
                                     start_new_session=True)
        if self.track:
            self.track(self.proc, True)
        first, hung = self._answer(timeout)
        if not first or "ready" not in first:
            self.close()
            if self.stop is not None and self.stop.is_set():
                raise _Canceled()
            if hung:
                raise RuntimeError(_s("The analysis process was not ready after {seconds} s (loading the models) – "
                                      "continuing in the next run.", seconds=round(timeout)))
            raise RuntimeError((first or {}).get("fatal") or _s("The analysis process does not start"))

    def _answer(self, timeout):
        """Next answer -> (answer or None, did it take longer than timeout?). A process that hangs (TensorFlow,
        ffmpeg on a broken file) is ended."""
        proc, hung = self.proc, []

        def end():
            hung.append(True)
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except OSError:
                pass
        watchdog = threading.Timer(timeout, end)
        watchdog.daemon = True
        watchdog.start()
        try:
            return self._read(), bool(hung)
        finally:
            watchdog.cancel()

    def _read(self):
        line = self.proc.stdout.readline()
        if not line:
            return None
        try:
            return json.loads(line)
        except ValueError:
            return None

    def ask(self, job, timeout=SONG_TIMEOUT):
        """-> answer or None (process ended: cancelled, crashed, out of memory, hung longer than timeout)."""
        try:
            self.proc.stdin.write(json.dumps(job) + "\n")
            self.proc.stdin.flush()
        except (OSError, ValueError):
            return None
        return self._answer(timeout)[0]   # hung: the process is ended – the song counts as not readable

    def close(self):
        if not self.proc:
            return
        try:
            self.proc.stdin.close()
            self.proc.wait(timeout=20)
        except (OSError, ValueError, subprocess.TimeoutExpired):
            self.proc.kill()
            self.proc.wait()
        self.proc.stdout.close()
        if self.track:
            self.track(self.proc, False)
        self.proc = None


def run(cfg, lib, log=print, stop=None, budget=None, until=None, everything=False, track=None, only=None):
    """AI analysis of the pending songs (new ones first). budget in minutes (0 = no limit), until = time (time.time()).
    only: song ids – just these (folder watch: the new songs; the rest follows in the regular runs)."""
    an = cfg["settings"].get("analysis") or {}
    ok, why = available()
    if not ok:
        return {"skipped": why}
    root = paths(cfg)["music"]
    depth = _depth(cfg)
    try:
        with _lock:
            data = _load_for_run(log)
            vectors = _vectors_for_run(log)
    except OSError as e:   # not readable: better not run than overwrite everything
        log(_s("⚠ AI sound analysis: results file not readable ({error}) – skipped.", error=e))
        return {"analysed": 0, "errors": 0, "later": 0}
    songs = data.setdefault("songs", {})
    data["v"] = VERSION
    todo = _todo(lib, songs, depth, everything, vectors)
    if only is not None:
        todo = [t for t in todo if lib.songs[t[1]]["id"] in only]
    open_before = data.get("open")
    if not todo:
        if data.get("open") and only is None:   # the rest of a cancelled run has disappeared from the library meanwhile
            data["open"] = 0
            with _lock:
                save(data)
        log(_s("AI sound analysis: everything analyzed."))
        return {"analysed": 0, "errors": 0, "later": 0}
    minutes = an.get("mlBudget", 15) if budget is None else budget
    deadline = time.time() + minutes * 60 if minutes else None
    if until:
        deadline = min(deadline or until, until)
    finished = len([e for e in songs.values() if not e.get("error")])
    if only is not None:
        log(_s("AI sound analysis: {open} of the new songs pending.", open=len(todo)))
    elif deadline:
        log(_s("AI sound analysis: {done} songs done, {open} pending (until {time}).",
               done=finished, open=len(todo), time=time.strftime("%H:%M", time.localtime(deadline))))
    else:
        log(_s("AI sound analysis: {done} songs done, {open} pending.", done=finished, open=len(todo)))
    if deadline and time.time() > deadline - 30:
        log(_s("AI sound analysis: no time left in this run – continuing in the next one."))
        return {"analysed": 0, "errors": 0, "later": len(todo)}
    worker = _Worker(max(1, int(an.get("mlThreads") or 2)), track, stop)
    progress.part("ml", len(todo), until=deadline)

    def start_timeout():   # waiting for the models never runs past the end of the run
        return min(START_TIMEOUT, max(30, deadline - time.time())) if deadline else START_TIMEOUT
    done = errors = crashes = 0
    later = len(todo)
    started = saved = time.time()
    try:
        worker.start(start_timeout())
        for n, (_, i, rel) in enumerate(todo, 1):
            progress.at(n - 1)
            if (stop is not None and stop.is_set()) or (deadline and time.time() > deadline):
                break
            s = lib.songs[i]
            segs = audio._segments(s.get("duration"), depth)
            job = {"id": s["id"], "path": str(root / rel), "segments": None if segs == [None] else segs}
            for attempt in range(1, ATTEMPTS + 1):
                res = worker.ask(job)
                if res is None or not res.get("error") or attempt == ATTEMPTS or (stop is not None and stop.is_set()):
                    break
                time.sleep(RETRY_PAUSE * attempt)   # NAS share: a file being replaced is briefly unreadable
            if res is None:   # process gone
                if stop is not None and stop.is_set():
                    break
                crashes += 1
                worker.close()
                _failed(songs, vectors, s["id"], rel, depth)
                errors += 1
                later -= 1
                if crashes > 3:
                    log(_s("⚠ AI sound analysis: the analysis process keeps crashing (not enough memory?) – continuing in the next run."))
                    break
                worker.start(start_timeout())
                continue
            later -= 1
            if res.get("error"):
                errors += 1
                _failed(songs, vectors, s["id"], rel, depth)
            else:
                songs[s["id"]] = {"v": VERSION, "path": rel, "depth": depth, **res["ml"]}
                if isinstance(res.get("sv"), str) and similar.decode(res["sv"]) is not None:
                    vectors[s["id"]] = res["sv"]
                else:   # no usable sound (e.g. silence) – remembered, so the song is not due again and again
                    vectors.pop(s["id"], None)
                    songs[s["id"]]["nosv"] = 1
                done += 1
            if n % 200 == 0:
                log(_s("  … {n}/{total} ({seconds} s per song)", n=n, total=len(todo), seconds=f"{(time.time() - started) / n:.1f}"))
            if time.time() - saved > 120:   # save regularly – a restart loses at most 2 minutes of work
                with _lock:
                    save(data)
                    _save_vectors(vectors)
                saved = time.time()
    except _Canceled:
        log(_s("AI sound analysis: canceled while the models were loading."))
    except RuntimeError as e:
        log(_s("⚠ AI sound analysis: {error}", error=e))
    finally:
        worker.close()
        data["lastRun"] = time.strftime("%d.%m.%Y %H:%M")
        data["open"] = later if only is None else open_before or 0   # only the new songs: the backlog stays as it was
        with _lock:
            save(data)
            _save_vectors(vectors)
    if errors and later:
        log(_s("AI sound analysis: {done} newly analyzed, {errors} not readable – {later} follow in the next run.",
               done=done, errors=errors, later=later))
    elif errors:
        log(_s("AI sound analysis: {done} newly analyzed, {errors} not readable.", done=done, errors=errors))
    elif later:
        log(_s("AI sound analysis: {done} newly analyzed – {later} follow in the next run.", done=done, later=later))
    else:
        log(_s("AI sound analysis: {done} newly analyzed.", done=done))
    return {"analysed": done, "errors": errors, "later": later}


def stats():
    """For Settings → Intelligence."""
    ok, why = available()
    data = load()
    songs = data.get("songs") or {}
    good = [e for e in songs.values() if not e.get("error")]
    out = {"available": ok, "reason": why, "analysed": len(good), "errors": len(songs) - len(good),
           "lastRun": data.get("lastRun"), "open": data.get("open"),
           "current": sum(1 for e in good if _current(e)), "vectors": similar.count()}
    if good:
        from collections import Counter
        c = Counter(k.split("---")[-1] for e in good for k in list((e.get("g") or {}))[:1])
        out["styles"] = c.most_common(8)
        inst = Counter(x for e in good for x, v in (e.get("i") or {}).items()
                       if v >= audio.INSTRUMENT_PRESENT and x in INSTRUMENTS)
        out["instruments"] = [[_(INSTRUMENTS[x]), n] for x, n in inst.most_common(8)]   # i18n-ignore – N_ labels
        th = Counter(x for e in good for x, v in (e.get("t") or {}).items()
                     if x in THEMES and isinstance(v, (int, float)) and v >= THEME_PRESENT[x])
        out["themes"] = [[_(THEMES[x]), n] for x, n in th.most_common(8)]   # i18n-ignore – N_ labels
    return out
