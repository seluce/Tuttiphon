"""Make lyrics searchable – for the search ("the song with …") and the kid-safe mode.

All lyrics of the library are in a full-text index (SQLite FTS5, state/liedtexte.db):

* sources: .lrc/.txt next to the music file (without timestamps and header lines) and lyrics embedded in the file
* update(lib): reads only what is new or has changed (modification time) and forgets what no longer exists –
  after every lyrics run, at the daily refresh and at the first search (then in the background)
* search(q): songs whose text contains all words, with the matching line
* derb(): songs with rude lyrics (kid-safe mode) – detected by a word list; what the administrator allows does not count
* languages(): language per song (German/English) – for the automatic music worlds (autowelten.py)
"""
import hashlib
import json
import os
import re
import sqlite3
import stat
import threading
import time

from .config import STATE_DIR, read_text
from .i18n import _s

DB_FILE = STATE_DIR / "liedtexte.db"
MAX_BYTES = 512 * 1024    # larger files are not lyrics
RETRY_SECONDS = 6 * 3600  # start reading in on its own at most every 6 hours
_lock = threading.Lock()
_soon_lock = threading.Lock()
_state = {"running": False, "error": None, "soon": 0, "gen": 0}
_derb_cache = {"stamp": None, "ids": frozenset()}

# Rude words: one from STRONG is enough, from MILD only two hits or more. Searched at the start of a word – "Scheißegal"
# counts, "Marsch" does not. Word lists and patterns are data (they match German and English lyrics).
# i18n-ignore-start
STRONG = ("fick", "gefickt", "fotze", "hurensohn", "hure", "nutte", "schlampe", "wichs", "arschfick", "schwuchtel",
          "missgeburt", "titten", "muschi", "porno", "fuck", "motherfuck", "cunt", "bitch", "whore", "slut", "nigga",
          "nigger", "faggot")
MILD = ("scheiß", "scheiss", "arschloch", "shit", "bullshit", "asshole", "bastard", "verpiss", "pisser", "wixer")
_STRONG_RE = re.compile(r"(?<![a-zäöüß])(?:" + "|".join(STRONG) + r")", re.I)
_MILD_RE = re.compile(r"(?<![a-zäöüß])(?:" + "|".join(MILD) + r")", re.I)
_WORD_RE = re.compile(r"(?<![a-zäöüß])(?:" + "|".join(STRONG + MILD) + r")[a-zäöüß]*", re.I)   # whole word for showing
_LRC_TIME = re.compile(r"\[\d{1,3}:\d{2}(?:[.:]\d{1,3})?\]|<\d{1,3}:\d{2}(?:[.:]\d{1,3})?>")
_LRC_TAG = re.compile(r"^\s*\[[a-z]{2,8}:[^\]]*\]\s*$", re.I)
# frequent short words – if the German ones clearly outweigh the others, the text is German (and vice versa)
DE_WORDS = frozenset("und der die das ich nicht ist ein eine du wir mit auf für im dem den zu sich mein dein wie was wenn noch "
                     "nur auch schon mal kein ja nein bin bist sind hab habe hat zum vom über unter".split())
EN_WORDS = frozenset("the and you i is not a to of in my your me we it on for be with that this love all no do don t can "
                     "will just are what so oh".split())
# i18n-ignore-end
_lang_cache = {"stamp": None, "langs": {}}
_schema_lock = threading.Lock()
_after_index = []   # functions(new rude song IDs) – called when indexing in the background found new rude songs


def on_indexed(fn):
    """Call fn(new rude song IDs) after indexing in the background (update_soon) found songs with rude lyrics that
    were not known before – e.g. after the first indexing, so the playlists of kid-safe people are written again."""
    if fn not in _after_index:
        _after_index.append(fn)


def _corrupt(e):
    """Is the index file damaged (not a database, “malformed”)? Locked or busy is not damaged."""
    return isinstance(e, sqlite3.DatabaseError) and not isinstance(
        e, (sqlite3.OperationalError, sqlite3.IntegrityError, sqlite3.ProgrammingError, sqlite3.InterfaceError))


def _set_aside(e):
    """A damaged index would leave the kid-safe mode without its list of rude songs for good: set it aside
    (liedtexte.defekt-<time>.db) – the next indexing builds it anew, right away instead of after hours."""
    with _schema_lock:
        if not DB_FILE.exists():
            return
        broken = DB_FILE.with_name(f"liedtexte.defekt-{time.strftime('%Y%m%d-%H%M%S')}.db")   # file name: data
        try:
            os.replace(DB_FILE, broken)
            for suffix in ("-wal", "-shm"):
                side = DB_FILE.with_name(DB_FILE.name + suffix)
                if side.exists():
                    os.replace(side, broken.with_name(broken.name + suffix))
        except OSError:
            return
        _state["soon"] = 0
        _derb_cache.update(stamp=None, ids=frozenset())
    from . import events
    events.say(_s("⚠ Lyrics index damaged ({error}) – set aside as {name}, it is built anew.", error=e, name=broken.name))


def lang_of(text):
    """'de', 'en' or None (too little text or mixed) – by the most frequent short words."""
    words = re.findall(r"[a-zäöüß']+", (text or "").lower())   # i18n-ignore
    de = sum(w in DE_WORDS for w in words)
    en = sum(w in EN_WORDS for w in words)
    if de + en < 6:
        return None
    return "de" if de > 1.5 * en else "en" if en > 1.5 * de else None


def plain(raw):
    """Lyrics without timestamps, header lines ([ar: …]) and empty lines – one line per line of text."""
    lines = []
    for line in raw.splitlines():
        if _LRC_TAG.match(line):
            continue
        text = _LRC_TIME.sub("", line).strip()
        if text:
            lines.append(text)
    return "\n".join(lines)


def embedded_text(value):
    """Lyrics embedded in the file, as Navidrome delivers them (JSON list with lines) -> text."""
    try:
        data = json.loads(value) if isinstance(value, str) else value
    except ValueError:
        return plain(str(value or ""))
    out = []
    for block in data if isinstance(data, list) else []:
        for line in (block or {}).get("line") or []:
            v = (line or {}).get("value")
            if v and v.strip():
                out.append(v.strip())
        if out:   # several languages: the first one with text is enough
            break
    return "\n".join(out)


def rude(text):
    """Rude text? One strong word or at least two mild ones."""
    return bool(_STRONG_RE.search(text)) or len(_MILD_RE.findall(text)) >= 2


def _connect():
    try:
        return _open()
    except sqlite3.DatabaseError as e:
        if not _corrupt(e):
            raise
        _set_aside(e)
        return _open()


def _open():
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB_FILE, timeout=30)
    with _schema_lock:   # create the tables – never two at the same time
        try:
            con.execute("PRAGMA journal_mode=WAL")   # searches keep reading while reading in
        except sqlite3.Error:
            pass
        con.execute("CREATE TABLE IF NOT EXISTS files(song TEXT PRIMARY KEY, src TEXT, stamp TEXT, rude INTEGER DEFAULT 0, lang TEXT)")
        con.execute("CREATE VIRTUAL TABLE IF NOT EXISTS texts USING fts5(song UNINDEXED, text, "
                    "tokenize='unicode61 remove_diacritics 2')")
        con.commit()
    return con


def _stamp():
    """State of the index – with WAL, changes land in liedtexte.db-wal first, so that file counts as well."""
    st = DB_FILE.stat()
    try:
        wal = DB_FILE.with_name(DB_FILE.name + "-wal").stat()
        return st.st_mtime_ns, wal.st_mtime_ns, wal.st_size
    except OSError:
        return st.st_mtime_ns, 0, 0


def status():
    """For the interface: how many lyrics are in the index, whether reading in is going on."""
    count = None
    if DB_FILE.exists():
        try:
            with _connect() as con:
                count = con.execute("SELECT COUNT(*) FROM files").fetchone()[0]
        except sqlite3.Error:
            count = None
    return {"songs": count, "running": _state["running"], "error": _state["error"]}


def compact():
    """Compact the index (once a month, langzeit.py): merge FTS segments, give back free space.
    Not while reading in. -> (size before, after) in bytes or None."""
    if not DB_FILE.exists() or not _lock.acquire(blocking=False):
        return None
    try:
        before = _size()
        con = _connect()
        try:
            con.execute("INSERT INTO texts(texts) VALUES('optimize')")
            con.commit()
            con.execute("VACUUM")
            con.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        finally:
            con.close()
        return before, _size()
    except sqlite3.Error:
        return None
    finally:
        _lock.release()


def _size():
    total = 0
    for suffix in ("", "-wal"):
        try:
            total += DB_FILE.with_name(DB_FILE.name + suffix).stat().st_size
        except OSError:
            pass
    return total


def generation():
    """Counts finished runs with changes – for caches that should only see finished states."""
    return _state["gen"]


def ready():
    return DB_FILE.exists() and (status()["songs"] or 0) > 0


def update(lib, cfg=None, log=lambda *_: None, stop=None):
    """Bring the index up to date with the library. -> (new/changed, removed)."""
    from .config import load_config
    from .opus import music_dir
    cfg = cfg or load_config()
    root = music_dir(cfg=cfg)
    with _lock:
        _state.update(running=True, error=None)
        try:
            return _update(lib, root, log, stop)
        except (OSError, sqlite3.Error) as e:
            _state["error"] = str(e)
            if _corrupt(e):
                _set_aside(e)
            raise
        finally:
            _state["running"] = False


def _update(lib, root, log, stop):
    embedded = getattr(lib, "embedded_lyrics", lambda: {})()
    listing = {}
    base = root.resolve()

    def names_in(folder):   # one directory listing per folder instead of one query per song – only in the music folder
        if folder not in listing:   # None: outside the music folder; False: not readable right now (NAS)
            try:
                inside = folder.resolve() == base or base in folder.resolve().parents
                listing[folder] = set(os.listdir(folder)) if inside else None
            except FileNotFoundError:
                listing[folder] = None
            except OSError:
                listing[folder] = False
        return listing[folder]

    con = _connect()
    try:
        known = {song: (src, stamp) for song, src, stamp in con.execute("SELECT song, src, stamp FROM files")}
        seen, changed, t0 = set(), 0, time.time()
        for i, s in enumerate(lib.songs):
            if stop and stop():
                break
            sid = s["id"]
            text, src, stamp = None, None, None
            emb = embedded.get(sid) if isinstance(embedded, dict) else None
            if emb:
                src, stamp = "embedded", hashlib.sha1(emb.encode()).hexdigest()[:12]
                text = emb
            else:
                rel = lib.real_path(i)
                if not rel:
                    continue
                audio = root / rel
                names = names_in(audio.parent)
                if names is False:   # folder not readable right now: keep the existing entry instead of forgetting it
                    seen.add(sid)
                    continue
                if not names:
                    continue
                stem = audio.name.rsplit(".", 1)[0]
                name = next((n for n in (f"{stem}.lrc", f"{stem}.txt") if n in names), None)
                if not name:
                    continue
                path = audio.parent / name
                try:   # only real files, no links – and no huge ones
                    st = os.lstat(path)
                except FileNotFoundError:
                    continue
                except OSError:
                    seen.add(sid)
                    continue
                if not stat.S_ISREG(st.st_mode) or st.st_size > MAX_BYTES:
                    continue
                stamp = str(int(st.st_mtime))
                src = name
                if known.get(sid) == (src, stamp):
                    seen.add(sid)
                    continue
                try:
                    text = plain(read_text(path))
                except UnicodeDecodeError:
                    continue
                except OSError:   # briefly not readable: again next time
                    seen.add(sid)
                    continue
            seen.add(sid)
            if known.get(sid) == (src, stamp):
                continue
            con.execute("DELETE FROM texts WHERE song = ?", (sid,))
            if text:
                con.execute("INSERT INTO texts(song, text) VALUES (?, ?)", (sid, text))
            con.execute("INSERT OR REPLACE INTO files(song, src, stamp, rude, lang) VALUES (?, ?, ?, ?, ?)",
                        (sid, src, stamp, int(bool(text) and rude(text)), lang_of(text[:800]) if text else None))
            changed += 1
            if changed % 500 == 0:
                con.commit()
                log(_s("Lyrics index: {n} read in …", n=changed))
        gone = [] if (stop and stop()) else [sid for sid in known if sid not in seen]
        for sid in gone:
            con.execute("DELETE FROM texts WHERE song = ?", (sid,))
            con.execute("DELETE FROM files WHERE song = ?", (sid,))
        con.commit()
        if changed or gone:
            try:   # do not let the side file (WAL) grow
                con.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            except sqlite3.Error:
                pass
            _state["gen"] += 1
            log(_s("Lyrics index: {changed} new or changed, {removed} removed ({seconds:.0f} s).", changed=changed,
                   removed=len(gone), seconds=time.time() - t0))
        return changed, len(gone)
    finally:
        con.close()


def update_soon(lib, force=False):
    """Update in the background (at the first search), if no run is going on already and the last one started on its
    own was at least 6 hours ago – otherwise every search would start a whole run."""
    with _soon_lock:
        if _state["running"] or (not force and time.time() - _state.get("soon", 0) < RETRY_SECONDS):
            return
        _state.update(soon=time.time(), running=True)   # take it right away: two searches at once start no second run

    def go():
        _state["running"] = False   # update() sets it again itself
        before = derb()
        _quiet(update, lib)
        new = derb() - before
        if new:
            for fn in list(_after_index):
                _quiet(fn, new)
    threading.Thread(target=go, daemon=True, name="liedtexte").start()


def _quiet(fn, *args):
    try:
        fn(*args)
    except Exception:   # noqa: BLE001 – background: the error is in status()
        pass


def text_of(song_id):
    """Lyrics of a song from the index (without timestamps) or None."""
    if not DB_FILE.exists():
        return None
    try:
        con = _connect()
        try:
            row = con.execute("SELECT text FROM texts WHERE song = ?", (song_id,)).fetchone()
        finally:
            con.close()
    except sqlite3.Error:
        return None
    return row[0] if row and row[0] else None


def _words(q):
    return [w for w in re.findall(r"[^\W_']+(?:'[^\W_']+)*", q.lower()) if len(w) >= 2][:12]   # letters of every language


def search(q, limit=6):
    """Songs whose text contains all words (the last one also just begun) -> [{"song", "line"}].
    Only from two words or one long word on – otherwise almost every text matches."""
    words = _words(q)
    if not words or (len(words) < 2 and len(words[0]) < 5) or not DB_FILE.exists():
        return []
    match = " ".join(f'"{w}"' for w in words[:-1]) + f' "{words[-1]}"*'
    try:
        con = _connect()
        try:
            rows = con.execute("SELECT song, text FROM texts WHERE texts MATCH ? ORDER BY bm25(texts) LIMIT ?",
                               (match, limit * 4)).fetchall()
        finally:
            con.close()
    except sqlite3.Error:
        return []
    phrase = " ".join(words)
    out = []
    for song, text in rows:
        lines = text.splitlines() or [text]
        low = [_fold(x) for x in lines]
        # the line with the most words; if the input is there in one piece, that line wins
        best = max(range(len(lines)), key=lambda k: (phrase in low[k], sum(w in low[k] for w in words)))
        out.append({"song": song, "line": lines[best][:140], "exact": phrase in _fold(text)})
    out.sort(key=lambda x: not x["exact"])   # literal hits first, otherwise as found
    return out[:limit]


def _fold(text):
    return " ".join(re.findall(r"[^\W_']+(?:'[^\W_']+)*", text.lower()))   # letters of every language


def derb(allow=()):
    """Song IDs with rude lyrics (without those the administrator allowed). Cached until the index changes."""
    if not DB_FILE.exists():
        return frozenset()
    try:
        stamp = (_stamp(), tuple(sorted(allow)))
    except OSError:
        return frozenset()
    if _derb_cache["stamp"] != stamp:
        try:
            con = _connect()
            try:
                ids = {row[0] for row in con.execute("SELECT song FROM files WHERE rude = 1")}
            finally:
                con.close()
        except sqlite3.Error as e:   # locked or the like: the last result stays valid, try again next time
            if _corrupt(e):
                _set_aside(e)
            return _derb_cache["ids"]
        _derb_cache.update(stamp=stamp, ids=frozenset(ids - set(allow)))
    return _derb_cache["ids"]


def languages():
    """Song ID -> 'de'/'en' for all songs with a recognizable language. Cached until the index changes."""
    if not DB_FILE.exists():
        return {}
    try:
        stamp = _stamp()
    except OSError:
        return {}
    if _lang_cache["stamp"] != stamp:
        try:
            con = _connect()
            try:
                langs = dict(con.execute("SELECT song, lang FROM files WHERE lang IS NOT NULL"))
            finally:
                con.close()
        except sqlite3.Error:
            return _lang_cache["langs"]
        _lang_cache.update(stamp=stamp, langs=langs)
    return _lang_cache["langs"]


def rude_words(text, n=3):
    """Rude words found in a text, most frequent first -> [[word, count], …] (for the settings)."""
    from collections import Counter
    found = Counter(m.group(0).lower() for m in _WORD_RE.finditer(text or ""))
    return [[w, k] for w, k in found.most_common(n)]


def derb_details():
    """Song ID -> words found, for all songs detected as rude (also allowed ones)."""
    if not DB_FILE.exists():
        return {}
    try:
        con = _connect()
        try:
            rows = con.execute("SELECT f.song, t.text FROM files f LEFT JOIN texts t ON t.song = f.song WHERE f.rude = 1").fetchall()
        finally:
            con.close()
    except sqlite3.Error:
        return {}
    return {song: rude_words(text) for song, text in rows}


def derb_list():
    """For the settings: all songs detected as rude (also the allowed ones) -> [song ID]."""
    if not DB_FILE.exists():
        return []
    try:
        con = _connect()
        try:
            return [row[0] for row in con.execute("SELECT song FROM files WHERE rude = 1")]
        finally:
            con.close()
    except sqlite3.Error:
        return []
