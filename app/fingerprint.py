"""Same recording twice – audio fingerprints with Chromaprint (fpcalc, the method behind AcoustID).

* Fingerprint: `fpcalc -raw -json -length 120` per song – the first two minutes as 32-bit values, one every 0.124 s –
  with low priority (nice), a time limit per file and a few attempts (files on the NAS share are sometimes briefly
  unreadable). Runs in the analyse step after sound analysis, AI and loudness: at night until the end of the window,
  otherwise with settings.analysis.budgetMinutes; new songs first. Only with settings.analysis.fingerprints (default on)
  and when fpcalc is installed (Docker image: Debian package libchromaprint-tools; TUTTIPHON_FPCALC names another
  program file). Without fpcalc it stays off and the status says "not installed".
* Stored compactly in state/fingerprints.json: song id -> [duration, packed fingerprint, path]. Packed = every value
  XOR the one before, zlib, base64 – about 3 KB per song. A song is fingerprinted again when its path or its length
  changes; songs that are gone are forgotten – right away when the song list looks complete (at least 80 % of the
  known songs, or only a few missing), otherwise only after they have been missing for 7 days (a list Navidrome
  delivered only in part must not throw away hours of work); files that cannot be read are tried again after 30 days.
* The large file is only read when something can be due: fingerprint_matches.json remembers a signature of the
  song list (ids, paths, lengths) and of the file – unchanged, and no retry due, the step is done in a moment.
* Comparison (compare()): only songs whose lengths differ by at most 3 s. Candidates come from shared fingerprint
  values (an index over the songs in the length window – 25,000 songs take seconds, not hours); then the bit error
  rate over the overlap at the best offset (up to ±6 s). Same recording = at most 15 % different bits overall and at
  most 20 % in every 10-second section but one. Measured on real copies: Opus, FLAC, MP3 and AAC of the same file
  0–8 %, the same song on a best-of or remastered 0–13 % (a heavy remaster at 15 % stays apart); karaoke and
  instrumental versions 10–30 % overall, but 22 % and more in the sections with vocals; re-recordings and other
  versions 18–37 %, live against studio 39–42 %; different songs 37–56 %.
* The result goes to state/fingerprint_matches.json (small – Check library reads only this file, pflege.py).
"""
import base64
import json
import os
import shutil
import struct
import subprocess
import threading
import time
import zlib
from concurrent.futures import ThreadPoolExecutor

from . import progress
from .config import STATE_DIR, env_var, paths, read_text, write_atomic
from .i18n import _, _s, _sn

VERSION = 1                    # stored format of state/fingerprints.json
MATCH_VERSION = 1              # comparison rules – a change compares everything again (no new fingerprints needed)
STATE_FILE = STATE_DIR / "fingerprints.json"
MATCH_FILE = STATE_DIR / "fingerprint_matches.json"
LENGTH = 120                   # seconds of each song that are fingerprinted (AcoustID uses the same); 1 value ≈ 0.124 s
TIMEOUT = 180                  # per file
RETRY_DAYS = 30                # unreadable files: try again after that many days
SAVE_EVERY = 300               # seconds – save progress regularly (a restart loses at most that much work)
HEALTHY = 0.8                  # song list at least this share of the known songs – then songs that are gone are forgotten
FEW_GONE = 100                 # … or only so many are missing (e.g. an album was converted)
GONE_DAYS = 7                  # otherwise only after they have been missing that many days

WINDOW = 3.0                   # lengths may differ by this many seconds
MAX_SHIFT = 48                 # values (≈ 6 s) – one copy may start a little earlier (other pause before the song)
MIN_OVERLAP = 80               # values (≈ 10 s) – shorter songs or overlaps are not compared
MAX_BER = 0.15                 # share of different bits over the whole overlap
SECTION = 80                   # values (≈ 10 s) per section
MAX_SECTION_BER = 0.20         # … and in every section but one
MAX_STATIC = 0.6               # share of values equal to the one before: above it (silence, a single tone) no comparison
INDEX_STEP = 2                 # every second value of a song goes into the index
MIN_VOTES = 3                  # shared values at about the same offset that make a song a candidate
_lock = threading.Lock()


# ---------------------------------------------------------------------------- Availability and settings

def tool():
    """Path of fpcalc or None."""
    own = env_var("FPCALC")
    if own:
        return own if os.path.isfile(own) and os.access(own, os.X_OK) else None
    return shutil.which("fpcalc")


def available():
    """-> (ok, reason)"""
    return (True, "") if tool() else (False, _("not installed"))


def enabled(cfg):
    return (cfg["settings"].get("analysis") or {}).get("fingerprints", True) is not False


# ---------------------------------------------------------------------------- Packing

def _big(values):
    """Values -> one large integer (value i in bits 32·i … 32·i+31) – XOR and bit counting then run in C."""
    return int.from_bytes(struct.pack(f"<{len(values)}I", *values), "little")


def _popcount(x):
    return x.bit_count() if hasattr(x, "bit_count") else bin(x).count("1")   # bit_count from Python 3.10


def pack(values):
    """Fingerprint (list of uint32) -> text: XOR with the previous value (mostly few bits), zlib, base64."""
    n = len(values)
    if not n:
        return ""
    big = _big(values)
    delta = (big ^ (big << 32)) & ((1 << (32 * n)) - 1)
    return base64.b64encode(zlib.compress(delta.to_bytes(4 * n, "little"), 9)).decode("ascii")


def unpack(text):
    """Text from pack() -> tuple of uint32."""
    if not text:
        return ()
    raw = zlib.decompress(base64.b64decode(text))
    n = len(raw) // 4
    x, step = int.from_bytes(raw, "little"), 32
    mask = (1 << (32 * n)) - 1
    while step < 32 * n:   # prefix XOR in log2(n) steps
        x ^= (x << step) & mask
        step *= 2
    return struct.unpack(f"<{n}I", x.to_bytes(4 * n, "little"))


# ---------------------------------------------------------------------------- Fingerprinting

def parse(text):
    """fpcalc -raw -json output -> (duration in s, [uint32 …]) or None."""
    try:
        data = json.loads(text or "")
        values = [int(v) & 0xFFFFFFFF for v in data["fingerprint"]]
        duration = float(data.get("duration") or 0)
    except (ValueError, TypeError, KeyError, AttributeError):
        return None
    return (duration, values) if values else None


def _command(path):
    cmd = [tool() or "fpcalc", "-raw", "-json", "-length", str(LENGTH), str(path)]
    nice = shutil.which("nice")
    return [nice, "-n", "19", *cmd] if nice else cmd


def measure(path, track=None, stop=None, attempts=3, timeout=TIMEOUT):
    """Fingerprint of a file -> (duration, values) or None (not readable). track(proc, running): the run remembers the
    process – "Cancel" ends it right away."""
    for attempt in range(attempts):
        if stop and stop():
            return None
        proc = subprocess.Popen(_command(path), stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                stdin=subprocess.DEVNULL, text=True, errors="replace", start_new_session=True)
        if track:
            track(proc, True)
        try:
            out, _err = proc.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.communicate()
            return None   # far too long for two minutes of audio: counts as not readable
        finally:
            if track:
                track(proc, False)
        res = parse(out) if proc.returncode == 0 else None
        if res:
            return res
        if attempt < attempts - 1:
            time.sleep(0.3 * (attempt + 1))   # NAS share: a file being replaced is briefly unreadable
    return None


# ---------------------------------------------------------------------------- State

def _read(path):
    try:
        data = json.loads(read_text(path))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def load():
    """state/fingerprints.json – large (about 3 KB per song); only the run and pending() read it."""
    return _read(STATE_FILE)


def load_matches():
    return _read(MATCH_FILE)


def _save(path, data):
    try:
        write_atomic(path, json.dumps(data, separators=(",", ":")))
    except OSError:
        pass


def _changed(entry, duration):
    """Is the file of this fingerprint probably a different one now (another length)?"""
    return bool(entry[0] and duration and abs(entry[0] - duration) > 5)


def _todo(lib, songs, failed):
    """Songs that need a (new) fingerprint – new ones first."""
    now = time.time()
    todo = []
    for i, s in enumerate(lib.songs):
        rel = lib.real_path(i)
        if not rel:
            continue
        cur = songs.get(s["id"])
        if cur and cur[2] == rel and not _changed(cur, s.get("duration")):
            continue
        bad = failed.get(s["id"])
        if bad and bad[0] == rel and now - bad[1] < RETRY_DAYS * 86400:
            continue
        todo.append((s.get("created") or "", i, rel))
    todo.sort(reverse=True)
    return todo


def _lib_signature(lib):
    """Changes when a song with a file path is added, removed, moved or gets another length – cheap, without the large
    file."""
    crc = n = 0
    for i, s in enumerate(lib.songs):
        rel = lib.real_path(i)
        if rel:
            crc = zlib.crc32(f"{s['id']}\0{rel}\0{int(s.get('duration') or 0)}\0".encode("utf-8"), crc)
            n += 1
    return f"{n}:{crc:08x}"


def _file_stamp():
    try:
        st = STATE_FILE.stat()
        return [st.st_mtime_ns, st.st_size]
    except OSError:
        return None


def _settled(matches, lib_sig):
    """Nothing can be due since the last run (same song list, the large file unchanged, compared, no retry due)?"""
    q = matches.get("quick") or {}
    return (matches.get("v") == MATCH_VERSION and q.get("lib") == lib_sig and q.get("file") == _file_stamp()
            and time.time() < (q.get("until") or 0))


def _forget(data, present, now=None):
    """Forget the songs that are gone -> changed anything? Right away when the song list looks complete; a list that
    holds far fewer songs than known (Navidrome delivered only part of it) keeps them – they are only forgotten after
    GONE_DAYS of missing."""
    now = now or time.time()
    songs, failed = data["songs"], data["failed"]
    known = set(songs) | set(failed)
    gone = known - present
    since = data.get("missing") if isinstance(data.get("missing"), dict) else {}
    if len(gone) <= FEW_GONE or len(present) >= HEALTHY * len(known):
        drop, keep = gone, {}
    else:
        keep = {sid: since.get(sid, int(now)) for sid in gone}
        drop = {sid for sid, t in keep.items() if now - t >= GONE_DAYS * 86400}
        keep = {sid: t for sid, t in keep.items() if sid not in drop}
    for store in (songs, failed):
        for sid in drop:
            store.pop(sid, None)
    changed = bool(drop) or keep != since
    if keep:
        data["missing"] = keep
    else:
        data.pop("missing", None)
    return changed


def pending(cfg, lib):
    """How many songs still need a fingerprint (0 if turned off or fpcalc is missing)."""
    if not enabled(cfg) or not available()[0]:
        return 0
    if _settled(load_matches(), _lib_signature(lib)):
        return 0   # without reading the large file
    data = load()
    n = len(_todo(lib, data.get("songs") or {}, data.get("failed") or {}))
    del data
    from .library import release_memory
    release_memory()   # the whole file was in memory for a moment
    return n


def _signature(songs):
    """Changes whenever a fingerprint is added, replaced or removed – then the comparison is due again."""
    crc = 0
    for sid in sorted(songs):
        crc = zlib.crc32(f"{sid}\0{songs[sid][2]}\0".encode("utf-8"), crc)
    return f"{len(songs)}:{crc:08x}"


# ---------------------------------------------------------------------------- Comparing

def _static(values):
    """Share of values equal to the one before (silence and a sustained tone stay the same)."""
    return sum(1 for a, b in zip(values, values[1:]) if a == b) / max(1, len(values) - 1)


def similarity(a, na, b, nb, shift):
    """Fingerprints as large integers (a with na values …), b shifted by `shift` values (a[i] ~ b[i + shift])
    -> similarity 0–1 (1 − 2 × bit error rate) or None if it is not the same recording."""
    if shift >= 0:
        x, y, n = a, b >> (32 * shift), min(na, nb - shift)
    else:
        x, y, n = a >> (-32 * shift), b, min(na + shift, nb)
    if n < MIN_OVERLAP:
        return None
    diff = (x ^ y) & ((1 << (32 * n)) - 1)
    ber = _popcount(diff) / (32 * n)
    if ber > MAX_BER:
        return None
    starts = list(range(0, n, SECTION))
    if len(starts) > 1 and n - starts[-1] < SECTION // 2:
        starts.pop()   # a short rest belongs to the last section
    bad = 0
    for k, s in enumerate(starts):
        end = starts[k + 1] if k + 1 < len(starts) else n
        part = (diff >> (32 * s)) & ((1 << (32 * (end - s))) - 1)
        if _popcount(part) / (32 * (end - s)) > MAX_SECTION_BER:
            bad += 1
    if bad > (1 if len(starts) >= 3 else 0):   # e.g. karaoke: same music, but the vocals are missing in places
        return None
    return round(1 - 2 * ber, 3)


def _best(a, na, b, nb, shift):
    """Best similarity around the shift found by the index (the values can lie half a step apart)."""
    found = [s for s in (similarity(a, na, b, nb, k) for k in (shift - 1, shift, shift + 1)) if s is not None]
    return max(found) if found else None


def compare(items, stop=None):
    """items: [(song id, duration, packed fingerprint)] -> [{"ids": [...], "sim": lowest similarity}] – groups of
    songs that are the same recording, or None if stopped.

    Songs are taken in order of their length. Every second value of a song goes into the index of its length bucket
    (WINDOW seconds wide); a song looks up its values in its own bucket and the one below – so only songs of about
    the same length meet, and old buckets are simply dropped. Shared values at the same offset make a candidate,
    similarity() decides."""
    order = sorted((float(d or 0), sid, fp) for sid, d, fp in items)
    buckets = {}        # length bucket -> {value: slot << 12 | position} (the last song with this value is enough)
    members = {}        # length bucket -> [slot]
    slots = {}          # slot -> (song id, duration, large integer, number of values)
    parent, low = {}, {}

    def root(x):
        while parent.get(x, x) != x:
            parent[x] = parent.get(parent[x], parent[x])
            x = parent[x]
        return x

    for slot, (dur, sid, fp) in enumerate(order):
        if stop and slot % 500 == 0 and stop():
            return None
        b = int(dur // WINDOW)
        for old in [k for k in buckets if k < b - 1]:   # too short from here on
            del buckets[old]
            for s in members.pop(old):
                slots.pop(s, None)
        try:
            values = unpack(fp)
        except (ValueError, zlib.error, struct.error):
            continue
        n = len(values)
        if n < MIN_OVERLAP or n >= 4096 or _static(values) > MAX_STATIC:
            continue
        votes = {}
        for k in (b - 1, b):
            idx = buckets.get(k)
            if not idx:
                continue
            for v in filter(idx.__contains__, set(values)):
                e = idx[v]
                other, j = e >> 12, e & 4095
                if dur - slots[other][1] > WINDOW:
                    continue
                i = -1
                while True:   # every place where the value starts (a held value counts once)
                    try:
                        i = values.index(v, i + 1)
                    except ValueError:
                        break
                    shift = j - i
                    if (i == 0 or values[i - 1] != v) and -MAX_SHIFT <= shift <= MAX_SHIFT:
                        votes[(other, shift)] = votes.get((other, shift), 0) + 1
        big = _big(values)
        best = {}
        for (other, shift), c in votes.items():
            c += votes.get((other, shift - 1), 0) + votes.get((other, shift + 1), 0)
            if c > best.get(other, (0, 0))[0]:
                best[other] = (c, shift)
        for other, (c, shift) in best.items():
            if c < MIN_VOTES:
                continue
            osid, _dur, obig, on = slots[other]
            sim = _best(big, n, obig, on, shift)
            if sim is None:
                continue
            ra, rb = root(sid), root(osid)
            parent.setdefault(rb, rb)
            if ra != rb:
                parent[ra] = rb
                low[rb] = min(low.get(ra, 1.0), low.get(rb, 1.0), sim)
            else:
                low[ra] = min(low.get(ra, 1.0), sim)
        buckets.setdefault(b, {}).update(zip(values[::INDEX_STEP], range(slot << 12, (slot << 12) + n, INDEX_STEP)))
        members.setdefault(b, []).append(slot)
        slots[slot] = (sid, dur, big, n)
    groups = {}
    for sid in list(parent):
        groups.setdefault(root(sid), set()).add(sid)
    return [{"ids": sorted(ids), "sim": low.get(r, 1.0)} for r, ids in groups.items() if len(ids) > 1]


# ---------------------------------------------------------------------------- Run

def run(cfg, lib, log=print, stop=None, budget=None, until=None, track=None):
    """Fingerprint what is missing, forget what is gone, then compare (if anything changed).
    budget in minutes (None = settings.analysis.budgetMinutes, 0 = none), until = at the latest by (time.time() value).
    stop: callable. -> {"fingerprinted", "errors", "later", "groups"}"""
    out = {"fingerprinted": 0, "errors": 0, "later": 0}
    if not enabled(cfg) or not available()[0]:
        return out   # like the AI: no note in the log – the status shows why
    an = cfg["settings"].get("analysis") or {}
    minutes = an.get("budgetMinutes", 10) if budget is None else budget
    deadline = time.time() + minutes * 60 if minutes else None
    if until:
        deadline = min(deadline or until, until)
    workers = max(1, int(an.get("workers") or max(1, (os.cpu_count() or 2) // 2)))
    root = paths(cfg)["music"]
    lib_sig = _lib_signature(lib)
    with _lock:
        matches = load_matches()
        if _settled(matches, lib_sig):   # nothing changed since the last run: the large file stays unread
            log(_s("Audio fingerprints: {done} songs done, {open} pending.", done=matches.get("songs", 0), open=0))
            matches.update(open=0, lastRun=time.strftime("%d.%m.%Y %H:%M"))
            _save(MATCH_FILE, matches)
            out["groups"] = len(matches.get("groups") or [])
            return out
        try:
            data = json.loads(read_text(STATE_FILE)) if STATE_FILE.exists() else {}
        except ValueError:   # damaged: set it aside instead of silently overwriting it
            broken = STATE_FILE.with_name(f"fingerprints.defekt-{time.strftime('%Y%m%d-%H%M%S')}.json")   # file name: data
            os.replace(STATE_FILE, broken)
            log(_s("⚠ Audio fingerprints: the file was damaged – set aside as {name}, starting over.", name=broken.name))
            data = {}
        except OSError as e:
            log(_s("⚠ Audio fingerprints: file not readable ({error}) – skipped.", error=e))
            return out
        data = data if isinstance(data, dict) and data.get("v", VERSION) == VERSION else {}
        data["v"] = VERSION
        songs, failed = data.setdefault("songs", {}), data.setdefault("failed", {})
        present = {s["id"] for i, s in enumerate(lib.songs) if lib.real_path(i)}
        # songs that are gone are forgotten – without any file path (Navidrome briefly away) nothing
        dirty = _forget(data, present) if present else False
        todo = _todo(lib, songs, failed)
        counts = {"done": len(songs), "open": len(todo)}
        if deadline and todo:
            log(_s("Audio fingerprints: {done} songs done, {open} pending (until {time}).",
                   time=time.strftime("%H:%M", time.localtime(deadline)), **counts))
        else:
            log(_s("Audio fingerprints: {done} songs done, {open} pending.", **counts))
        saved = time.time()
        progress.part("fingerprints", len(todo), until=deadline)

        def one(item):
            _created, i, rel = item
            if (stop and stop()) or (deadline and time.time() > deadline):
                return item, "later"
            return item, measure(root / rel, track=track, stop=stop)

        try:
            with ThreadPoolExecutor(max_workers=workers) as pool:
                for k, ((_created, i, rel), res) in enumerate(pool.map(one, todo), 1):
                    progress.at(k)
                    sid = lib.songs[i]["id"]
                    if res == "later" or (res is None and stop and stop()):   # canceled: not a broken file
                        out["later"] += 1
                        continue
                    if res is None:
                        out["errors"] += 1
                        failed[sid] = [rel, int(time.time())]
                        songs.pop(sid, None)
                        dirty = True
                        continue
                    songs[sid] = [round(res[0], 2), pack(res[1]), rel]
                    failed.pop(sid, None)
                    out["fingerprinted"] += 1
                    dirty = True
                    if time.time() - saved > SAVE_EVERY:
                        _save(STATE_FILE, data)
                        saved = time.time()
        finally:
            if dirty:   # the file is large – only written when something changed
                _save(STATE_FILE, data)
        if out["errors"]:
            log(_s("  {n} fingerprinted, {errors} not readable.", n=out["fingerprinted"], errors=out["errors"]))
        elif out["fingerprinted"]:
            log(_s("  {n} fingerprinted.", n=out["fingerprinted"]))
        matches = load_matches()
        sig = _signature(songs)
        due = matches.get("v") != MATCH_VERSION or matches.get("sig") != sig
        found = None
        if due and not (stop and stop()):
            t0 = time.time()
            found = compare([(sid, e[0], e[1]) for sid, e in songs.items()], stop=stop)
        if found is not None:
            dup = sum(len(g["ids"]) - 1 for g in found)
            log(_sn(len(found), "Audio fingerprints: {n} recording is there more than once ({dup} extra files, "
                                 "compared in {secs} s) – see Settings → Check library.",
                    "Audio fingerprints: {n} recordings are there more than once ({dup} extra files, "
                    "compared in {secs} s) – see Settings → Check library.", dup=dup, secs=int(time.time() - t0)))
            ids = {sid for g in found for sid in g["ids"]}
            matches = {"v": MATCH_VERSION, "sig": sig, "at": time.strftime("%d.%m.%Y %H:%M"), "groups": found,
                       "paths": {sid: songs[sid][2] for sid in ids}}
        matches.update(songs=len(songs), errors=len(failed), open=out["later"], lastRun=time.strftime("%d.%m.%Y %H:%M"))
        if not out["later"] and matches.get("sig") == sig and not (stop and stop()):
            # the next run can skip the large file until the song list changes or a retry is due
            due = ([t + RETRY_DAYS * 86400 for _rel, t in failed.values()]
                   + [t + GONE_DAYS * 86400 for t in (data.get("missing") or {}).values()])
            matches["quick"] = {"lib": lib_sig, "file": _file_stamp(), "until": min(due) if due else time.time() + 180 * 86400}
        else:
            matches.pop("quick", None)
        _save(MATCH_FILE, matches)
        del data, songs
    from .library import release_memory
    release_memory()   # the fingerprints of all songs were in memory for a moment
    out["groups"] = len(matches.get("groups") or [])
    return out


# ---------------------------------------------------------------------------- For Check library and the status

def stats(cfg, lib=None):
    """Status for the interface (Settings → Intelligence / Check library)."""
    ok, why = available()
    m = load_matches()
    groups = m.get("groups") or []
    out = {"available": ok, "why": why, "enabled": enabled(cfg), "songs": m.get("songs", 0), "errors": m.get("errors", 0),
           "open": m.get("open"), "lastRun": m.get("lastRun"), "comparedAt": m.get("at"), "groups": len(groups),
           "extra": sum(len(g["ids"]) - 1 for g in groups)}
    if lib is not None:
        out["total"] = len(lib.songs)
    return out


def groups(lib):
    """Groups of the last comparison that still exist -> [{"songs": [(index, song, path)], "sim"}]."""
    m = load_matches()
    where = m.get("paths") or {}
    index = lib.index_of()
    out = []
    for g in m.get("groups") or []:
        members = [(index[sid], lib.songs[index[sid]], where.get(sid)) for sid in g.get("ids", []) if sid in index]
        if len(members) > 1:
            out.append({"songs": members, "sim": g.get("sim")})
    return out
