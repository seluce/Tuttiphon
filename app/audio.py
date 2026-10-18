"""Sound analysis – local, without extra packages and without a cloud: ffmpeg delivers loudness and spectral values
every 23 ms, and from them Tuttiphon computes tempo, energy, danceability, brightness and a mood.

Depending on the analysis depth (settings.analysis.depth), one or more excerpts of each song or the whole song are
measured. Results are kept in state/audio.json (song id -> features) and are only computed again when the file
changes, a more thorough depth is set – or after 30 days if the file was not readable. A file that cannot be read is
tried ATTEMPTS times; if it fails while an earlier measurement exists, that one stays ("retry": time of the attempt)
and the song is tried again after 30 days. ffmpeg runs with lower priority (nice).

Features (0–1, except bpm):
  bpm, beat (confidence of the tempo), energy (loudness/density), dance (steady pulse),
  bright (bright timbre), rough (distorted/noisy), dyn (dynamics), arousal (how wound up),
  valence (basic mood, refined by Last.fm tags)
"""
import json
import math
import os
import shutil
import subprocess
import threading
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor

from .config import STATE_DIR, paths, read_text, write_atomic
from .i18n import N_, _s

VERSION = 2
SR, HOP = 22050, 512
FPS = SR / HOP                     # ≈ 43 analysis steps per second
STATE_FILE = STATE_DIR / "audio.json"
INSTRUMENT_PRESENT = 0.2           # an instrument of the AI counts as "in the song" from this strength (sound filters)
CHAIN = (f"aformat=sample_fmts=flt:channel_layouts=mono:sample_rates={SR},asetnsamples=n={HOP}:p=0,"
         "aspectralstats=win_size=1024:overlap=0.5:measure=centroid+flatness+flux,"
         "astats=metadata=1:reset=1:measure_perchannel=RMS_level:measure_overall=none,ametadata=print:file=-")
NICE = 10                          # ffmpeg with lower priority (like the AI process) – playback goes first
ATTEMPTS = 3                       # a file that cannot be read is tried this often (the NAS share is sometimes briefly
RETRY_PAUSE = 0.3                  # unreadable), with a pause of RETRY_PAUSE × attempt seconds in between
RETRY_DAYS = 30
_lock = threading.Lock()           # reading and writing audio.json during a run
_features_lock = threading.Lock()  # reading it into memory (features()): once, even with parallel requests


class _TooLong(RuntimeError):
    """ffmpeg took far too long – not tried again."""


# ---------------------------------------------------------------------------- State

def load():
    try:
        data = json.loads(read_text(STATE_FILE))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def save(data):
    try:
        write_atomic(STATE_FILE, json.dumps(data, separators=(",", ":")))
    except OSError:
        pass


_cache = {"stamp": None, "songs": {}}


def _stamp():
    try:
        st = STATE_FILE.stat()
        return (st.st_mtime_ns, st.st_size)
    except OSError:
        return None


def features():
    """Song id -> features (kept in memory until the file changes; read only once even with parallel requests)."""
    stamp = _stamp()
    if stamp is None:
        return {}
    if _cache["stamp"] != stamp:
        with _features_lock:
            stamp = _stamp()
            if stamp is None:
                return {}
            if _cache["stamp"] != stamp:   # not read by another request in the meantime
                raw = load().get("songs", {})
                _cache.update(stamp=stamp, songs={k: d for k, d in ((k, derive(v)) for k, v in raw.items()) if d})
    return _cache["songs"]


# ---------------------------------------------------------------------------- Measuring

# How thoroughly to analyze: excerpts (position as a share of the song length, length in s); None = whole song.
# The keys are stored in settings.analysis.depth and in state/audio.json.
DEPTHS = {
    "schnell": [(0.5, 30)],
    "standard": [(0.5, 60)],
    "gruendlich": [(0.2, 40), (0.5, 40), (0.8, 40)],
    "tief": None,
}
DEPTH_ORDER = ["schnell", "standard", "gruendlich", "tief"]
DEPTH_NAMES = {"schnell": N_("fast"), "standard": N_("standard"), "gruendlich": N_("thorough"),
               "tief": N_("deep – whole song")}   # for the run log


def _measure(path, start=None, length=None, track=None):
    """One ffmpeg pass -> lists (flux, centroid, flatness, rms_db) per 23 ms step. start/length=None: whole song.
    track(proc, running): the run remembers the process – "Cancel" ends it right away."""
    cmd = ["ffmpeg", "-nostdin", "-v", "error"]
    if start is not None:
        cmd += ["-ss", f"{start:.1f}", "-t", f"{length:.1f}"]
    else:
        cmd += ["-t", "900"]   # at most 15 min (audio plays, live recordings)
    cmd += ["-i", str(path), "-af", CHAIN, "-f", "null", "-"]
    nice = _nice()
    if nice:
        cmd = [nice, "-n", str(NICE), *cmd]
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, stdin=subprocess.DEVNULL, text=True,
                            errors="replace", start_new_session=True)
    if track:
        track(proc, True)
    try:
        stdout, _ = proc.communicate(timeout=600)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.communicate()
        raise _TooLong(_s("measurement took too long"))   # never save half a measurement – counts as not readable
    finally:
        if track:
            track(proc, False)
    flux, cent, flat, rms = [], [], [], []
    for line in stdout.splitlines():
        if not line.startswith("lavfi."):
            continue
        key, _, val = line.partition("=")
        try:
            v = float(val)
        except ValueError:
            continue
        if key.endswith(".flux"):
            flux.append(v if math.isfinite(v) else 0.0)
        elif key.endswith(".centroid"):
            cent.append(v if math.isfinite(v) else 0.0)
        elif key.endswith(".flatness"):
            flat.append(v if math.isfinite(v) else 0.0)
        elif key.endswith(".RMS_level"):
            rms.append(v if math.isfinite(v) else -120.0)
    return flux, cent, flat, rms


_NICE_TOOL = []


def _nice():
    """Path of the nice program (None if missing) – looked up once."""
    if not _NICE_TOOL:
        _NICE_TOOL.append(shutil.which("nice"))
    return _NICE_TOOL[0]


def _segments(duration, depth):
    """Excerpts (start, length) for an analysis depth – short songs always whole."""
    plan = DEPTHS.get(depth, DEPTHS["standard"])
    if plan is None or not duration or duration <= sum(l for _, l in plan) + 10:
        return [None]
    out = []
    for frac, length in plan:
        start = min(max(0.0, duration * frac - length / 2), max(0.0, duration - length))
        out.append((start, length))
    return out


def _consensus(tempi):
    """Tempo from several sections: the group of similar values (±4 %) with the highest confidence wins."""
    tempi = [(b, c) for b, c in tempi if b]
    if not tempi:
        return None, 0.0
    best, best_w = None, -1
    for b0, _ in tempi:
        group = [(b, c) for b, c in tempi if abs(b / b0 - 1) <= 0.04]
        w = sum(c + 0.05 for _, c in group)
        if w > best_w:
            best, best_w = group, w
    total = sum(c + 0.05 for _, c in tempi)
    bpm = sum(b * (c + 0.05) for b, c in best) / sum(c + 0.05 for _, c in best)
    conf = (sum(c for _, c in best) / len(best)) * (best_w / total)   # confident when the sections agree
    return round(bpm, 1), round(conf, 3)


def _pct(values, p):
    if not values:
        return 0.0
    s = sorted(values)
    k = (len(s) - 1) * p
    lo, hi = math.floor(k), math.ceil(k)
    return s[lo] + (s[hi] - s[lo]) * (k - lo)


def _clip(x, lo=0.0, hi=1.0):
    return lo if x < lo else hi if x > hi else x


def _tempo(flux):
    """Tempo from the onset curve: autocorrelation with a preference for 80–160 BPM. -> (bpm, confidence)"""
    n = len(flux)
    if n < FPS * 8:
        return None, 0.0
    # emphasize onsets: subtract a moving average (0.4 s), keep only increases
    w = int(FPS * 0.4)
    pre = [0.0]
    for v in flux:
        pre.append(pre[-1] + v)
    env = []
    for i in range(n):
        a, b = max(0, i - w), min(n, i + w + 1)
        env.append(max(0.0, flux[i] - (pre[b] - pre[a]) / (b - a)))
    for _ in range(2):   # smooth slightly: peaks get wider, so fast tempos do not fall between two measuring points
        env = [0.25 * env[max(0, i - 1)] + 0.5 * env[i] + 0.25 * env[min(n - 1, i + 1)] for i in range(n)]
    mean = sum(env) / n
    env = [v - mean for v in env]
    e0 = sum(v * v for v in env) / n or 1e-12

    def acf(lag):
        return sum(env[i] * env[i + lag] for i in range(n - lag)) / ((n - lag) * e0)

    lo, hi = int(FPS * 60 / 210), int(FPS * 60 / 50) + 1
    raw = {lag: acf(lag) for lag in range(lo, min(hi * 2 + 2, n // 2))}
    best, best_score = None, -1e9
    for lag in range(lo, hi):
        bpm = 60 * FPS / lag
        prior = math.exp(-0.5 * (math.log2(bpm / 120) / 0.9) ** 2)   # soft preference for ~120 BPM
        score = (raw[lag] + 0.5 * raw.get(lag * 2, 0)) * prior   # twice the distance has to fit as well
        if score > best_score:
            best, best_score = lag, score
    if best is None:
        return None, 0.0
    # fine adjustment (parabola through the neighbors)
    y0, y1, y2 = raw.get(best - 1, 0), raw[best], raw.get(best + 1, 0)
    d = (y0 - y2) / (2 * (y0 - 2 * y1 + y2)) if (y0 - 2 * y1 + y2) else 0
    lag = best + _clip(d, -0.5, 0.5)
    bpm = 60 * FPS / lag
    peaks = sorted(raw.values(), reverse=True)
    conf = _clip(raw[best] / (abs(peaks[0]) + 1e-9)) * _clip(raw[best] * 3)
    return round(bpm, 1), round(conf, 3)


def analyse_file(path, duration=None, depth="standard", track=None):
    """-> raw measurements (dict) or None (file not readable / too short). derive() computes the 0–1 values –
    so the scales can be improved later without analyzing the whole library again."""
    flux, cent, flat, rms, tempi = [], [], [], [], []
    for seg in _segments(duration, depth):
        f, c, fl, r = _measure(path, *(seg or (None, None)), track=track)
        flux += f
        cent += c
        flat += fl
        rms += r
        if seg is None and len(f) > FPS * 45:   # whole song: tempo in 30 s windows, then reconcile
            win, step = int(FPS * 30), int(FPS * 15)
            tempi += [_tempo(f[k:k + win]) for k in range(0, len(f) - win + 1, step)]
        else:
            tempi.append(_tempo(f))
    if len(rms) < FPS * 5:
        return None
    active = [r for r in rms if r > -60] or rms
    loud = 10 * math.log10(sum(10 ** (r / 10) for r in active) / len(active))   # power mean ≈ RMS
    bpm, beat = tempi[0] if len(tempi) == 1 else _consensus(tempi)
    return {"v": VERSION, "depth": depth, "bpm": bpm, "beat": beat, "loud": round(loud, 2),
            "dyn": round(_pct(active, 0.95) - _pct(active, 0.10), 2), "cent": round(_pct(cent, 0.5)),
            "flat": round(_pct(flat, 0.5), 3), "flux": round(_pct(flux, 0.5) * 1000, 2)}


def derive(raw):
    """Raw measurements -> features 0–1. Calibrated on our own library (lullabies ≈ 0.2 energy, metal ≈ 0.9)."""
    if not raw or raw.get("error"):
        return None
    bpm, beat = raw.get("bpm"), raw.get("beat") or 0
    loud_n = _clip((raw["loud"] + 14) / 7)            # -14 dB … -7 dB
    flux_n = _clip((raw["flux"] - 25) / 70)           # onset strength
    flat_n = _clip((raw["flat"] - 0.12) / 0.4)        # rough/distorted
    energy = 0.4 * loud_n + 0.35 * flux_n + 0.25 * flat_n
    bright = _clip((raw["cent"] - 900) / 2000)
    dance, arousal, valence = _with_bpm(bpm, beat, energy, bright, flat_n)
    return {"bpm": bpm, "beat": beat, "energy": round(energy, 3), "dance": round(dance, 3), "bright": round(bright, 3),
            "rough": round(flat_n, 3), "arousal": round(arousal, 3), "valence": round(valence, 3)}


def _with_bpm(bpm, beat, energy, bright, rough):
    """The features that depend on the tempo -> (dance, arousal, valence)."""
    tempo_n = _clip(((bpm or 100) - 70) / 90)
    dance = _clip((beat - 0.4) / 0.55) * (1 if bpm and 90 <= bpm <= 145 else 0.6) * (0.4 + 0.6 * energy)
    arousal = _clip(0.55 * energy + 0.25 * tempo_n + 0.2 * dance)
    # the basic mood from the sound is only a rough estimate – Last.fm tags refine it (classify.py)
    valence = _clip(0.3 * bright + 0.3 * tempo_n + 0.4 * dance - 0.25 * max(0.0, rough - 0.6))
    return dance, arousal, valence


def with_tempo(f, bpm):
    """Features with another tempo – the AI's, which is more reliable than our own estimate: danceability, arousal and
    basic mood are computed again with it (bsrc: "ml"). The confidence of the beat stays our own measurement."""
    dance, arousal, valence = _with_bpm(bpm, f.get("beat") or 0, f["energy"], f["bright"], f["rough"])
    return {**f, "bpm": bpm, "dance": round(dance, 3), "arousal": round(arousal, 3), "valence": round(valence, 3),
            "bsrc": "ml"}


# ---------------------------------------------------------------------------- Moods

# Mood keys (stored in style filters and compared everywhere) -> label; translate where shown: _(MOODS[m])
MOODS = {
    "ruhig": N_("calm & gentle"), "energie": N_("energetic"), "tanzbar": N_("danceable"),
    "froh": N_("cheerful"), "melancholisch": N_("thoughtful"), "schlaf": N_("for falling asleep"),
    "instrumental": N_("no vocals"), "akustisch": N_("acoustic"),   # only with AI sound analysis (ml.py)
}


def moods(f):
    """Mood keys from the features."""
    if not f:
        return []
    out = []
    a, v, e = f.get("arousal", .5), f.get("valence", .5), f.get("energy", .5)
    if a < 0.33:
        out.append("ruhig")
    if a > 0.6:
        out.append("energie")
    if f.get("dance", 0) > 0.55:
        out.append("tanzbar")
    if v > 0.6 and a > 0.35:
        out.append("froh")
    if v < 0.35 and a < 0.55 and f.get("vsrc") in ("tags", "ml"):   # only when confirmed by Last.fm tags or the AI
        out.append("melancholisch")
    if a < 0.3 and e < 0.3 and (f.get("bpm") or 100) < 118 and f.get("dance", 0) < 0.45:   # no steady groove
        out.append("schlaf")
    if f.get("inst", 0) >= 0.8:
        out.append("instrumental")
    if f.get("acoustic", 0) >= 0.75 and f.get("electronic", 1) < 0.4:
        out.append("akustisch")
    return out


# ranges of a sound filter [lo, hi]; approachable and engaging only with the AI (ml.scores(), from its VERSION 3)
RANGE_KEYS = ("energy", "bpm", "arousal", "valence", "dance", "approachable", "engaging")


def matches(f, sound):
    """Does a song fit a sound filter? sound = {"energy": [lo, hi], "bpm": [lo, hi], "arousal": [...],
    "valence": [...], "dance": [lo, hi], "approachable": [...], "engaging": [...], "moods": [...],
    "instruments": [...], "themes": [...]} – no analysis = does not fit (also a missing value for a required range,
    e.g. a song the AI has not analyzed again yet). moods, instruments and themes: at least one of each (instruments
    from the AI, strength ≥ INSTRUMENT_PRESENT; themes from the AI as classify.song_features() delivers them – only
    those from their strength ml.THEME_PRESENT)."""
    if not f:
        return False
    for key in RANGE_KEYS:
        rng = sound.get(key)
        if rng and f.get(key) is not None and not (rng[0] <= f[key] <= rng[1]):
            return False
        if rng and f.get(key) is None:
            return False
    instruments = sound.get("instruments")
    if instruments:
        have = f.get("instr") or {}
        if not any(have.get(x, 0) >= INSTRUMENT_PRESENT for x in instruments):
            return False
    themes = sound.get("themes")
    if themes:
        have = f.get("themes") or {}
        if not any(x in have for x in themes):
            return False
    want = sound.get("moods")
    return not want or bool(set(want) & set(moods(f)))


# ---------------------------------------------------------------------------- Run

def _depth(cfg):
    an = cfg["settings"].get("analysis") or {}
    return an.get("depth", "standard") if an.get("depth") in DEPTHS else "standard"


def _todo(lib, songs, depth, everything=False):
    """Songs that are due (again) – new ones first."""
    todo = []
    for i, s in enumerate(lib.songs):
        rel = lib.real_path(i)
        if not rel:
            continue
        cur = songs.get(s["id"])
        if cur and not everything and _good(cur) and cur.get("retry") \
                and time.time() - cur["retry"] < RETRY_DAYS * 86400:
            continue   # the last attempt failed: the earlier measurement stays until the next try
        deep_enough = DEPTH_ORDER.index(cur.get("depth", "standard")) >= DEPTH_ORDER.index(depth) if cur and cur.get("depth", "standard") in DEPTH_ORDER else False
        # was not readable: try again only after 30 days (the file may have been replaced by then)
        failed = cur and cur.get("error")
        failed_recently = failed and time.time() - (cur.get("t") or 0) < RETRY_DAYS * 86400
        if (cur and cur.get("v") == VERSION and cur.get("path") == rel and not everything
                and ((deep_enough and not failed) or failed_recently)):
            continue
        todo.append((s.get("created") or "", i, rel))
    todo.sort(reverse=True)
    return todo


def _good(entry):
    """A usable measurement (not a "not readable" mark)."""
    return bool(entry) and not entry.get("error") and entry.get("loud") is not None


def pending(cfg, lib):
    """How many songs the sound analysis would still measure."""
    return len(_todo(lib, load().get("songs") or {}, _depth(cfg)))


def run(cfg, lib, log=print, stop=None, budget=None, until=None, everything=False, track=None, only=None):
    """Analyze songs not analyzed yet (new ones first). budget in minutes (0 = no limit), until = at the latest by
    (a time.time() value, for the night analysis). only: song ids – just these (folder watch: the new songs; the rest
    follows in the regular runs)."""
    an = cfg["settings"].get("analysis") or {}
    root = paths(cfg)["music"]
    depth = _depth(cfg)
    try:
        with _lock:
            data = json.loads(read_text(STATE_FILE)) if STATE_FILE.exists() else {}
    except ValueError:   # damaged: set it aside instead of silently overwriting the work of many nights
        broken = STATE_FILE.with_name(f"audio.defekt-{time.strftime('%Y%m%d-%H%M%S')}.json")   # file name: data
        os.replace(STATE_FILE, broken)
        log(_s("⚠ Sound analysis: the results file was damaged – set aside as {name}, starting over.", name=broken.name))
        data = {}
    except OSError as e:
        log(_s("⚠ Sound analysis: results file not readable ({error}) – skipped.", error=e))
        return {"analysed": 0, "errors": 0, "later": 0}
    data = data if isinstance(data, dict) else {}
    songs = data.setdefault("songs", {})
    todo = _todo(lib, songs, depth, everything)
    if only is not None:
        todo = [t for t in todo if lib.songs[t[1]]["id"] in only]
    open_before = data.get("open")
    minutes = an.get("budgetMinutes", 10) if budget is None else budget
    deadline = time.time() + minutes * 60 if minutes else None
    if until:
        deadline = min(deadline or until, until)
    workers = max(1, int(an.get("workers") or max(1, (os.cpu_count() or 2) // 2)))
    counts = {"depth": _s(DEPTH_NAMES[depth]), "done": len(lib.songs) - len(todo), "open": len(todo), "workers": workers}   # i18n-ignore
    if only is not None:
        log(_s("Sound analysis ({depth}): {open} of the new songs pending, {workers} at a time.", **counts))
    elif deadline and todo:
        log(_s("Sound analysis ({depth}): {done} songs done, {open} pending (until {time}), {workers} at a time.",
               time=time.strftime("%H:%M", time.localtime(deadline)), **counts))
    else:
        log(_s("Sound analysis ({depth}): {done} songs done, {open} pending, {workers} at a time.", **counts))
    done = errors = later = 0
    started = saved = time.time()

    def one(item):
        _, i, rel = item
        if stop is not None and stop.is_set():
            return i, rel, "stop"
        if deadline and time.time() > deadline:
            return i, rel, "later"
        for attempt in range(1, ATTEMPTS + 1):
            try:
                res = analyse_file(root / rel, lib.songs[i].get("duration"), depth, track)
            except _TooLong as e:   # far too long: trying again would not help
                res = e
                break
            except Exception as e:   # one broken file must not hold up the rest
                res = e
            if (res is not None and not isinstance(res, Exception)) or attempt == ATTEMPTS \
                    or (stop is not None and stop.is_set()):
                break
            time.sleep(RETRY_PAUSE * attempt)   # NAS share: a file being replaced is briefly unreadable
        if stop is not None and stop.is_set():
            return i, rel, "stop"   # cancelled: do not save half a measurement
        return i, rel, res

    try:
        with ThreadPoolExecutor(max_workers=workers) as pool:
            for n, (i, rel, res) in enumerate(pool.map(one, todo), 1):
                if res in ("stop", "later"):
                    later += 1
                    continue
                if isinstance(res, Exception) or res is None:
                    errors += 1
                    sid = lib.songs[i]["id"]
                    if _good(songs.get(sid)):   # an earlier measurement stays – only the attempt is noted
                        songs[sid]["retry"] = int(time.time())
                    else:
                        songs[sid] = {"v": VERSION, "path": rel, "error": True, "depth": depth, "t": int(time.time())}
                    continue
                res["path"] = rel
                songs[lib.songs[i]["id"]] = res
                done += 1
                if n % 500 == 0:
                    rate = n / max(1e-6, time.time() - started)
                    log(_s("  … {n}/{total} ({rate} songs/s)", n=n, total=len(todo), rate=f"{rate:.1f}"))
                if time.time() - saved > 120:   # save regularly – a restart loses at most 2 minutes of work
                    with _lock:
                        save(data)
                    saved = time.time()
    finally:
        data["lastRun"] = time.strftime("%d.%m.%Y %H:%M")
        data["open"] = later if only is None else open_before or 0   # only the new songs: the backlog stays as it was
        with _lock:
            save(data)
    if errors and later:
        log(_s("Sound analysis: {done} newly analyzed, {errors} not readable – {later} follow in the next run.",
               done=done, errors=errors, later=later))
    elif errors:
        log(_s("Sound analysis: {done} newly analyzed, {errors} not readable.", done=done, errors=errors))
    elif later:
        log(_s("Sound analysis: {done} newly analyzed – {later} follow in the next run.", done=done, later=later))
    else:
        log(_s("Sound analysis: {done} newly analyzed.", done=done))
    return {"analysed": done, "errors": errors, "later": later}


def stats(feats=None):
    """feats: merged features (classify.song_features) – otherwise only our own measurement."""
    data = load()
    songs = data.get("songs", {})
    errors = sum(1 for f in songs.values() if f.get("error"))
    ok = [d for d in (derive(f) for f in songs.values()) if d] if feats is None else list(feats)
    out = {"analysed": len(ok), "errors": errors, "lastRun": data.get("lastRun"), "open": data.get("open"),
           "depths": dict(Counter(f.get("depth", "standard") for f in songs.values() if not f.get("error")))}
    if ok:
        c = Counter(m for f in ok for m in moods(f))
        out["moods"] = {k: c.get(k, 0) for k in MOODS}
        bpms = [f["bpm"] for f in ok if f.get("bpm")]
        out["bpm"] = {"median": round(_pct(bpms, .5)), "p10": round(_pct(bpms, .1)), "p90": round(_pct(bpms, .9))} if bpms else None
    return out
