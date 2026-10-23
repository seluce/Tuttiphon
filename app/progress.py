"""Progress of the running task for the interface (GET /api/task → "progress"): which part of a step is at work and how
many of how many – so "Progress" can say at a glance how far a run is instead of only the live log.

The steps' modules report as they go: part() when a part begins (an id from PARTS – the interface names it in its
language), at() for every item done. The task runner clears it at every step. One run at a time (tasks.TaskRunner), so
one state is enough; outside a run nobody reads it.
"""
import threading
import time

PARTS = ("maintenance", "flac", "lyrics", "cover", "lastfm", "audio", "ml", "loudness", "classify", "fingerprints",
         "learn", "playlists", "scan", "sync", "lyricsindex", "selfcheck", "deezer")
MIN_SECONDS = 20   # a remaining time only once the part has run this long …
MIN_DONE = 3       # … and done this many items

_lock = threading.Lock()
_state = {}


def clear():
    with _lock:
        _state.clear()


def part(pid, total=None, until=None):
    """A part of the step begins: pid (from PARTS), total items (None: not known), until: time.time() by which it stops
    at the latest (night analysis)."""
    with _lock:
        _state.clear()
        _state.update(part=pid, done=0, total=total if total is None else max(0, int(total)), since=time.time(),
                      until=until)


def at(done, total=None):
    """Items of the current part done so far (and the total, if it changed)."""
    with _lock:
        if not _state:
            return
        _state["done"] = max(0, int(done))
        if total is not None:
            _state["total"] = max(0, int(total))


def get(now=None):
    """-> {"part", "done", "total", "elapsed", "left", "until"} or None. left: seconds still to go at the pace so far
    (None while there is too little to go by or without a total)."""
    now = now or time.time()
    with _lock:
        if not _state:
            return None
        st = dict(_state)
    elapsed = max(0, now - st.pop("since"))
    left = None
    done, total = st["done"], st["total"]
    if total and MIN_DONE <= done < total and elapsed >= MIN_SECONDS:
        left = round(elapsed / done * (total - done))
        if st["until"]:
            left = min(left, max(0, round(st["until"] - now)))
    return {**st, "elapsed": round(elapsed), "left": left, "until": st["until"] and round(st["until"])}
