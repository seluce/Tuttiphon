"""Lyrics like lrcget: look for missing lyrics and put them next to the songs – plus cleanup.

* Providers in an adjustable order: LRCLIB (open, like lrcget) and optionally NetEase (unofficial, many synced
  lyrics). Synced beats "text only": if the first provider only has text, Tuttiphon asks the next ones for a synced
  version.
* synced lyrics -> <song>.lrc, text only -> <song>.txt (Navidrome reads both when scanning)
* instrumental -> .lrc with "[au: instrumental]" (like lrcget), so it is not searched again and again
* fast: LRCLIB's database first (get-cached), new songs first, songs not found only again after X days, the full run
  with a time limit – the rest comes next time
* cleanup: if there is a .lrc with synced lyrics next to a .txt, the .txt goes (not next to an empty .lrc or one
  that only marks the song as instrumental)
"""
import json
import os
import re
import subprocess
import threading
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from . import progress
from .config import STATE_DIR, read_bytes, read_text, write_atomic
from .i18n import N_, _, _s, _sn
from .opus import SKIP_DIRS, music_dir

USER_AGENT = "Tuttiphon/1.0 (Navidrome-Helfer; wie lrcget)"   # sent as it is (HTTP header)
STATE_FILE = STATE_DIR / "lyrics.json"
INSTRUMENTAL = "[au: instrumental]\n"
PROVIDERS = {
    "lrclib": N_("LRCLIB – open, free lyrics database"),
    "netease": N_("NetEase – large Chinese music platform, many synced lyrics (unofficial interface)"),
}
DEFAULT_PROVIDERS = [{"id": "lrclib", "on": True}, {"id": "netease", "on": False}]
AUDIO = (".opus", ".mp3", ".flac", ".m4a", ".ogg", ".oga", ".wav", ".wma", ".aac", ".aiff", ".aif", ".wv", ".ape")


def load_state():
    try:
        data = json.loads(read_text(STATE_FILE))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def save_state(state):
    try:
        write_atomic(STATE_FILE, json.dumps(state, ensure_ascii=False))
    except OSError:
        pass


def stats():
    st = load_state()
    return {**(st.get("summary") or {}), "lastRun": st.get("lastRun"), "backlog": st.get("backlog")}


# ---------------------------------------------------------------------------- cleanup

_TIMED_LINE = re.compile(r"^\s*(?:\[\d{1,3}:\d{1,2}(?:[.:]\d{1,3})?\]\s*)+(.*)$")


def has_synced_lines(text):
    """Does a .lrc text hold at least one timed line with words? (Not: empty, only header tags like
    "[au: instrumental]" or "[ar: …]", only time stamps without text.)"""
    for line in (text or "").splitlines():
        m = _TIMED_LINE.match(line)
        if m and re.sub(r"<\d{1,3}:\d{1,2}(?:[.:]\d{1,3})?>", "", m.group(1)).strip():
            return True
    return False


def _synced_file(path):
    try:
        return has_synced_lines(read_bytes(path).decode("utf-8", "replace"))
    except OSError:
        return False   # not readable right now: keep the .txt


def cleanup(root, log=print, dry_run=False, stop=None):
    """Duplicate lyrics: delete a .txt when there is a .lrc with synced lyrics and the same name next to it."""
    deleted = 0
    for dirpath, dirnames, filenames in os.walk(root):
        if stop is not None and stop.is_set():
            break
        dirnames[:] = [d for d in dirnames if not d.startswith(SKIP_DIRS)]
        names = set(filenames)
        for name in filenames:
            if (name.lower().endswith(".txt") and (name[:-4] + ".lrc") in names
                    and _synced_file(Path(dirpath) / (name[:-4] + ".lrc"))):
                path = Path(dirpath) / name
                if dry_run:
                    log(_s("  🗑 {path} (dry run)", path=path.relative_to(root)))
                else:
                    log(f"  🗑 {path.relative_to(root)}")
                if not dry_run:
                    try:
                        path.unlink()
                    except OSError as e:
                        log(f"  ⚠ {e}")
                        continue
                deleted += 1
    log(_sn(deleted, "Cleanup: {n} duplicate .txt file deleted.", "Cleanup: {n} duplicate .txt files deleted."))
    return deleted


# ---------------------------------------------------------------------------- providers

class _Http:
    def __init__(self, rate):
        self._interval = 1.0 / rate
        self._next = 0.0
        self._lock = threading.Lock()

    def get(self, url):
        with self._lock:   # stay polite
            wait = self._next - time.time()
            self._next = max(time.time(), self._next) + self._interval
        if wait > 0:
            time.sleep(wait)
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
        for attempt in range(3):
            try:
                with urllib.request.urlopen(req, timeout=20) as res:
                    return json.loads(res.read().decode("utf-8"))
            except urllib.error.HTTPError as e:
                if e.code in (400, 404):
                    return None
                if e.code in (429, 500, 502, 503, 504) and attempt < 2:
                    time.sleep(3 * (attempt + 1))
                    continue
                raise
            except (urllib.error.URLError, TimeoutError, ConnectionError, ValueError):
                if attempt < 2:
                    time.sleep(2 * (attempt + 1))
                    continue
                raise
        return None


def _norm(text):
    text = unicodedata.normalize("NFKD", text or "").encode("ascii", "ignore").decode().lower()
    text = re.sub(r"\(.*?\)|\[.*?\]|feat\..*$|ft\..*$", "", text)
    return re.sub(r"[^a-z0-9]+", "", text)


def _result(synced=None, plain=None, instrumental=False):
    """Uniform result: {"synced": str|None, "plain": str|None, "instrumental": bool}"""
    synced = synced if synced and re.search(r"\[\d{1,2}:\d{2}", synced) else None
    plain = plain.strip() if plain and plain.strip() else None
    if not (synced or plain or instrumental):
        return None
    return {"synced": synced, "plain": plain, "instrumental": bool(instrumental and not synced and not plain)}


class Lrclib:
    API = "https://lrclib.net/api"

    def __init__(self):
        self.http = _Http(10.0)

    def find(self, artist, title, album, duration):
        # One request per song: the search also finds exact hits; a matching length (±3 s) decides
        results = self.http.get(f"{self.API}/search?{urllib.parse.urlencode({'artist_name': artist, 'track_name': title})}") or []
        best, best_score = None, 0
        own_inst = "instrumental" in (title or "").lower()
        for r in results:
            if duration and r.get("duration") and abs(r["duration"] - duration) > 3:
                continue
            if not own_inst and "instrumental" in (r.get("trackName") or "").lower():
                continue   # "Song (Instrumental)" with the same length is not the vocal version
            score = 3 if r.get("syncedLyrics") else 2 if r.get("plainLyrics") else 1 if r.get("instrumental") else 0
            if album and _norm(r.get("albumName")) == _norm(album):
                score += 0.5   # prefer the same album
            if score > best_score:
                best, best_score = r, score
        hit = best
        if not hit and results and duration:   # hits, but none with a matching length -> exact query in the database
            params = {"artist_name": artist, "track_name": title, "duration": int(round(duration)), **({"album_name": album} if album else {})}
            hit = self.http.get(f"{self.API}/get-cached?{urllib.parse.urlencode(params)}")
        if not hit:
            return None
        return _result(hit.get("syncedLyrics"), hit.get("plainLyrics"), hit.get("instrumental"))


class NetEase:
    """Unofficial interface of music.163.com – often synced lyrics, also for western music."""
    API = "https://music.163.com/api"
    CREDITS = re.compile(r"^\[[\d:.]+\]\s*(作词|作曲|编曲|制作人|混音|母带|和声|吉他|贝斯|鼓|录音|监制|出品|发行)\s*[:：]")

    def __init__(self):
        self.http = _Http(2.0)

    def find(self, artist, title, album, duration):
        q = urllib.parse.urlencode({"s": f"{artist} {title}", "type": 1, "limit": 8})
        res = self.http.get(f"{self.API}/search/get?{q}") or {}
        want_t, want_a = _norm(title), _norm(artist)
        best = None
        for s in (res.get("result") or {}).get("songs") or []:
            if _norm(s.get("name")) != want_t and not _norm(s.get("name")).startswith(want_t):
                continue
            if want_a and not any(want_a in _norm(a.get("name")) or _norm(a.get("name")) in want_a for a in s.get("artists") or []):
                continue
            if duration and s.get("duration") and abs(s["duration"] / 1000 - duration) > 3:
                continue
            best = s
            break
        if not best:
            return None
        data = self.http.get(f"{self.API}/song/lyric?id={best['id']}&lv=1&kv=1&tv=-1") or {}
        if data.get("nolyric") or data.get("uncollected"):
            return None
        text = (data.get("lrc") or {}).get("lyric") or ""
        lines = [line for line in text.splitlines() if not self.CREDITS.match(line)]
        text = "\n".join(lines).strip()
        if re.search(r"\[\d{1,2}:\d{2}", text):
            return _result(synced=text)
        return _result(plain=text)


def _clients(ly):
    order = ly.get("providers") or DEFAULT_PROVIDERS
    made = {"lrclib": Lrclib, "netease": NetEase}
    return [(p["id"], made[p["id"]]()) for p in order if p.get("on") and p.get("id") in made]


def _clean_artist(name):
    # "A feat. B" is often only found under "A"
    low = name.lower()
    for sep in (" feat. ", " feat ", " ft. ", " featuring ", " & ", ", "):
        if sep in low:
            return name[:low.index(sep)]
    return name


def lookup(clients, artist, title, album, duration):
    """Ask the providers one after the other; synced wins, then text, last "instrumental".
    -> (result, provider) or (None, None)"""
    fallback = (None, None)
    rank = lambda r: 2 if r["plain"] else 1 if r["instrumental"] else 0   # noqa: E731
    for name, client in clients:
        for a in dict.fromkeys([artist, _clean_artist(artist)]):
            res = client.find(a, title, album, duration)
            if res:
                if res["synced"]:
                    return res, name
                if not fallback[0] or rank(res) > rank(fallback[0]):
                    fallback = (res, name)
                break
    return fallback


# ---------------------------------------------------------------------------- search & save

def _write(ly, audio, stem, res, dry_run):
    """-> kind ("synced"/"plain"/"instrumental"/"none"/"plain-had"/"skip") and whether a .txt was replaced."""
    lrc, txt = audio.parent / f"{stem}.lrc", audio.parent / f"{stem}.txt"
    if res and res["synced"]:
        kind, path, text = "synced", lrc, res["synced"]
    elif res and res["instrumental"]:
        if ly.get("instrumental", "mark") != "mark":
            return "skip", False   # instrumental, but it should not be marked – nothing is written
        if txt.exists():
            return "plain-had", False   # never replace existing text with an instrumental marker
        kind, path, text = "instrumental", lrc, INSTRUMENTAL
    elif res and res["plain"] and ly.get("savePlain", True):
        if txt.exists():
            return "plain-had", False
        kind, path, text = "plain", txt, res["plain"]
    else:
        return "none", False
    had_txt = kind != "plain" and txt.exists()
    if not dry_run:
        write_atomic(path, text if text.endswith("\n") else text + "\n")
        if had_txt and ly.get("cleanup", True) and has_synced_lines(text):
            try:
                txt.unlink()   # synced found -> the duplicate .txt goes
            except OSError:
                pass
    return kind, had_txt


def _plan(cfg, lib, everything):
    """Which songs have to be searched (newest first) + numbers for the overview."""
    ly = cfg["settings"].get("lyrics") or {}
    root = music_dir(cfg=cfg)
    songs_state = load_state().get("songs", {})
    retry = (ly.get("retryDays") or 30) * 86400
    now = time.time()
    listing = {}

    def present(folder):   # one directory listing per folder instead of two queries per song
        if folder not in listing:
            try:
                listing[folder] = set(os.listdir(folder))
            except OSError:
                listing[folder] = None
        return listing[folder]

    embedded = getattr(lib, "embedded_lyrics", lambda: set())()
    todo, have_synced, have_plain, total = [], 0, 0, 0
    for i, s in enumerate(lib.songs):
        rel = lib.real_path(i)
        if not rel:
            continue
        audio = root / rel
        names = present(audio.parent)
        if names is None or audio.name not in names:
            continue   # file not there (any more)
        total += 1
        stem = audio.name.rsplit(".", 1)[0]
        last = songs_state.get(s["id"])
        # spread new attempts over the days (±20 %), so that not everything is due on the same day
        spread = 0.8 + (int.from_bytes(s["id"].encode()[-4:], "big") % 40) / 100
        recent = last and now - last[0] < retry * spread and not everything
        if f"{stem}.lrc" in names or s["id"] in embedded:
            have_synced += 1
            continue
        if f"{stem}.txt" in names:
            have_plain += 1
            if not ly.get("upgradePlain", True) or recent:
                continue
        elif recent:
            continue
        todo.append((s.get("created") or "", i, audio, stem))
    todo.sort(reverse=True)   # new songs first
    return [(i, audio, stem) for _, i, audio, stem in todo], have_synced, have_plain, total


def fetch(cfg, lib, log=print, stop=None, dry_run=False, everything=False, budget=None):
    """Look for missing lyrics. everything=True: also again those searched without success recently.
    budget: at most this many minutes (None = setting "budgetMinutes", 0 = no limit)."""
    ly = cfg["settings"].get("lyrics") or {}
    clients = _clients(ly)
    if not clients:
        log(_s("No lyrics provider turned on (Settings → Lyrics)."))
        return {"synced": 0, "plain": 0, "instrumental": 0, "notFound": 0, "errors": 0}
    todo, have_synced, have_plain, total = _plan(cfg, lib, everything)
    minutes = ly.get("budgetMinutes", 5) if budget is None else budget
    deadline = time.time() + minutes * 60 if minutes else None
    numbers = {"total": total, "synced": have_synced, "plain": have_plain, "without": total - have_synced - have_plain,
               "todo": len(todo), "minutes": minutes, "providers": ", ".join(n for n, _ in clients)}
    if minutes and dry_run:
        log(_s("{total} songs · {synced} with synced lyrics · {plain} with text only · {without} without. To search now: "
               "{todo} (at most {minutes} min) · providers: {providers} – dry run, nothing is saved", **numbers))
    elif minutes:
        log(_s("{total} songs · {synced} with synced lyrics · {plain} with text only · {without} without. To search now: "
               "{todo} (at most {minutes} min) · providers: {providers}", **numbers))
    elif dry_run:
        log(_s("{total} songs · {synced} with synced lyrics · {plain} with text only · {without} without. To search now: "
               "{todo} · providers: {providers} – dry run, nothing is saved", **numbers))
    else:
        log(_s("{total} songs · {synced} with synced lyrics · {plain} with text only · {without} without. To search now: "
               "{todo} · providers: {providers}", **numbers))
    state = load_state()
    songs_state = state.setdefault("songs", {})
    result = {"synced": 0, "plain": 0, "instrumental": 0, "notFound": 0, "errors": 0, "upgraded": 0,
              "stopped": False, "later": 0, "by": {}}
    unprocessed = 0
    lock = threading.Lock()

    def one(item):
        i, audio, stem = item
        if stop is not None and stop.is_set():
            return ("stop", i, None, None)
        if deadline and time.time() > deadline:
            return ("later", i, None, None)
        s = lib.songs[i]
        try:
            res, by = lookup(clients, s.get("artist") or s.get("displayArtist") or "", s.get("title", ""), s.get("album", ""), s.get("duration"))
            kind, up = _write(ly, audio, stem, res, dry_run)
        except Exception as e:   # network gone or the like
            return ("error", i, str(e), None)
        return (kind + ("+up" if up else ""), i, by, None)

    progress.part("lyrics", len(todo), until=deadline)
    try:
        with ThreadPoolExecutor(max_workers=max(1, int(ly.get("workers") or 6))) as pool:
            for n, (kind, i, extra, _) in enumerate(pool.map(one, todo), 1):
                progress.at(n)
                if kind == "stop":
                    result["stopped"] = True
                    unprocessed += 1
                    continue
                if kind == "later":
                    result["later"] += 1
                    continue
                if kind.endswith("+up"):
                    kind = kind[:-3]
                    result["upgraded"] += 1
                s = lib.songs[i]
                label = f"{s.get('artist', '')} – {s.get('title', '')}"
                with lock:
                    if kind == "error":
                        result["errors"] += 1
                        log(f"  ⚠ {label}: {extra}")
                        continue
                    if kind in ("synced", "plain", "instrumental"):
                        result[kind] += 1
                        result["by"][extra] = result["by"].get(extra, 0) + 1
                        if kind == "plain":
                            line = _s("  📝 {song} (text only)", song=label)
                        elif kind == "instrumental":
                            line = _s("  🎻 {song} (instrumental)", song=label)
                        else:
                            line = f"  🎤 {label}"
                        log(line + (f" · {extra}" if len(clients) > 1 else ""))
                    elif kind != "plain-had":   # "plain-had": the text was there already, only nothing synced found
                        result["notFound"] += 1
                    if not dry_run:
                        songs_state[s["id"]] = [int(time.time()), kind]
                    if n % 250 == 0:
                        log(f"  … {n}/{len(todo)}")
                        if not dry_run:
                            save_state(state)
    finally:
        if not dry_run:
            synced = have_synced + result["synced"] + result["instrumental"]
            plain = have_plain + result["plain"] - result["upgraded"]
            state["lastRun"] = time.strftime("%d.%m.%Y %H:%M")
            state["backlog"] = result["later"] + unprocessed   # what is still due in the next run
            state["summary"] = {"total": total, "synced": synced, "plain": plain, "missing": max(0, total - synced - plain)}
            save_state(state)
    numbers = {"synced": result["synced"], "plain": result["plain"], "instrumental": result["instrumental"],
               "not_found": result["notFound"], "errors": result["errors"], "later": result["later"]}
    if result["errors"] and result["later"]:
        log(_s("Lyrics: {synced} synced, {plain} text only, {instrumental} instrumental, {not_found} not found, "
               "{errors} errors – {later} more follow in the next run (time limit).", **numbers))
    elif result["errors"]:
        log(_s("Lyrics: {synced} synced, {plain} text only, {instrumental} instrumental, {not_found} not found, "
               "{errors} errors.", **numbers))
    elif result["later"]:
        log(_s("Lyrics: {synced} synced, {plain} text only, {instrumental} instrumental, {not_found} not found – "
               "{later} more follow in the next run (time limit).", **numbers))
    else:
        log(_s("Lyrics: {synced} synced, {plain} text only, {instrumental} instrumental, {not_found} not found.",
               **numbers))
    return result


def _tags(path):
    """Artist, title, album, duration straight from the file (for new files Navidrome does not know yet)."""
    try:
        out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration:format_tags=artist,title,album",
                              "-of", "json", str(path)], capture_output=True, text=True, timeout=60, stdin=subprocess.DEVNULL)
        fmt = json.loads(out.stdout or "{}").get("format", {})
    except (OSError, ValueError, subprocess.SubprocessError):
        return None
    tags = {k.lower(): v for k, v in (fmt.get("tags") or {}).items()}
    if not tags.get("title") or not tags.get("artist"):
        return None
    return tags["artist"], tags["title"], tags.get("album", ""), float(fmt.get("duration") or 0)


def fetch_files(cfg, files, log=print, stop=None, dry_run=False):
    """Lyrics for particular (new) files – reads the tags itself, does not need Navidrome."""
    ly = cfg["settings"].get("lyrics") or {}
    out = {"synced": 0, "plain": 0, "instrumental": 0, "notFound": 0}
    if not ly.get("fetch", True):
        log(_s("Lyrics search is turned off in the settings."))
        return out
    clients = _clients(ly)
    progress.part("lyrics", len(files))
    for k, audio in enumerate(files):
        progress.at(k)
        if stop is not None and stop.is_set():
            break
        stem = audio.name.rsplit(".", 1)[0]
        if not clients or (audio.parent / f"{stem}.lrc").exists():
            continue
        tags = _tags(audio)
        if not tags:
            continue
        try:
            res, by = lookup(clients, *tags)
            kind, _ = _write(ly, audio, stem, res, dry_run)
        except Exception as e:
            log(f"  ⚠ {audio.name}: {e}")
            continue
        if kind in ("synced", "plain", "instrumental"):
            out[kind] += 1
            log(f"  {'🎤' if kind == 'synced' else '📝' if kind == 'plain' else '🎻'} {tags[0]} – {tags[1]}")
        elif kind in ("none", "skip"):
            out["notFound"] += 1   # "plain-had": the text was there already – neither newly found nor missing
    return out


def run(cfg, lib, log=print, stop=None, dry_run=False, everything=False, budget=None):
    ly = cfg["settings"].get("lyrics") or {}
    root = music_dir(cfg=cfg)
    if not root.exists():
        raise RuntimeError(_("Music folder {path} not found", path=root))
    out = {}
    if ly.get("cleanup", True):
        out["deleted"] = cleanup(root, log, dry_run, stop)
    if ly.get("fetch", True):
        out.update(fetch(cfg, lib, log, stop, dry_run, everything, budget))
    if not ly.get("cleanup", True) and not ly.get("fetch", True):
        log(_s("Lyrics search and cleanup are turned off in the settings."))
    return out
