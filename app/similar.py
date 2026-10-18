"""Sound similarity – which songs and bands sound alike, from the sound vectors of the AI sound analysis.

For every song, the analysis process (ml_worker.py) computes a compact sound vector: the mean of the Discogs-EffNet
embedding over all patches, projected to 128 dimensions with a fixed random matrix, normalized and stored as int8
(128 bytes, base64). ml.py keeps them in state/sound_vectors.json, apart from ml.json:

  {"v": VERSION, "dim": 128, "songs": {song id: base64}}

Standard library only. Similarity is the cosine after centering on the mean sound of all stored songs: what every song
shares does not count, only what sets it apart – unrelated songs come out around 0, songs of the same band mostly at
0.3–0.8. Partial coverage is normal (the AI works through the library over several nights): everything here simply
leaves out songs without a vector.

index(lib) -> Index (cached per song list and state of the file), or None without any vector:
  cos(i, j)              similarity of two songs (indices in lib.songs), None without vectors
  neighbors(i, k)        the k most similar songs [(j, score)] – about 0.1 s for 25,000 songs, cached per song
  centroids()            band (main artist) -> unit vector: mean sound of its songs (from MIN_SONGS songs)
  similar_artists(a, k)  bands that sound like band a [(band, score)], cached per band
  closeness(i, vector)   similarity of a song to a unit vector (e.g. a band's centroid)

batch(ids) -> (song ids, Batch): many songs at once with integer arithmetic (the sound taste, soundtaste.py):
  closeness(vector)      similarity of every song to a unit vector – about 7 ms for 25,000 songs
  sums(weights, groups)  weighted sums of the centered song vectors per group (the mean sound of each group)
"""
import base64
import binascii
import heapq
import json
import math
import sys
import threading
from array import array
from collections import OrderedDict
from itertools import repeat
from operator import add, mul, sub

from .config import STATE_DIR, read_text, write_atomic

STATE_FILE = STATE_DIR / "sound_vectors.json"
VERSION = 1          # belongs to ml_worker.SOUND_SEED and SOUND_DIM – vectors of another version are ignored
DIM = 128
MIN_SONGS = 2        # a band needs this many songs with a vector for its sound
_lock = threading.Lock()
_store = {"stamp": None, "ids": frozenset(), "rows": {}, "mean": None, "pos": None}
_indexes = OrderedDict()   # (song list, file state) -> Index

try:
    _dot = math.sumprod   # Python 3.12
except AttributeError:   # pragma: no cover – older Python
    def _dot(a, b):
        return sum(map(mul, a, b))


# ---------------------------------------------------------------------------- File

def _stamp():
    try:
        st = STATE_FILE.stat()
        return (st.st_mtime_ns, st.st_size)
    except OSError:
        return None


def _read():
    try:
        data = json.loads(read_text(STATE_FILE))
    except (OSError, ValueError):
        return {}
    if not isinstance(data, dict) or data.get("v") != VERSION or data.get("dim", DIM) != DIM:
        return {}
    songs = data.get("songs")
    return songs if isinstance(songs, dict) else {}


def stored():
    """Ids of the songs with a stored sound vector (in memory until the file changes)."""
    _refresh()
    return _store["ids"]


def save(songs):
    write_atomic(STATE_FILE, json.dumps({"v": VERSION, "dim": DIM, "songs": songs}, separators=(",", ":")))


def decode(text):
    """base64 -> array of DIM signed bytes, or None (broken, wrong length, all zero)."""
    try:
        raw = base64.b64decode(text, validate=True)
    except (binascii.Error, ValueError, TypeError):
        return None
    if len(raw) != DIM:
        return None
    vec = array("b", raw)
    return vec if any(vec) else None


def encode(values):
    """Floats -> base64 of the int8 vector (largest component ±127) – as the analysis process stores it (tests)."""
    top = max((abs(x) for x in values), default=0) or 1.0
    return base64.b64encode(array("b", (round(x * 127 / top) for x in values)).tobytes()).decode("ascii")


def _refresh():
    """Decode the vectors and precompute what the centered cosine needs (once per state of the file).

    v = q / |q| (the stored direction), m = mean direction, u = (v − m) / |v − m| (centered, length 1). Then
    u_i · u_j = (q_i · q_j) · s_i · s_j − (h_i + h_j) · w_i · w_j with s = 1 / (|q| · |v − m|), h = v · m − |m|² / 2 and
    w = 1 / |v − m| – one dot product of the int8 values per pair, everything else is precomputed."""
    stamp = _stamp()
    if stamp == _store["stamp"]:
        return
    with _lock:
        if stamp == _store["stamp"]:
            return
        raw = _read()
        vecs = {}
        for sid, text in raw.items():
            vec = decode(text) if isinstance(text, str) else None
            if vec is not None:
                vecs[sid] = vec
        rows, mean = {}, None
        if vecs:
            norms = {sid: math.sqrt(_dot(v, v)) for sid, v in vecs.items()}
            # mean direction from the column sums (fast: slices of one byte string); dividing by the mean length
            # instead of each song's own is close enough – any fixed m is a valid centre, the formulas stay exact
            big = b"".join(v.tobytes() for v in vecs.values())
            scale = len(vecs) * (sum(norms.values()) / len(vecs))
            mean = [sum(array("b", big[d::DIM])) / scale for d in range(DIM)]
            mm = _dot(mean, mean)
            for sid, v in vecs.items():
                n = norms[sid]
                p = _dot(v, mean) / n
                c = math.sqrt(max(1e-9, 1 - 2 * p + mm))
                rows[sid] = (v, 1 / (n * c), p - mm / 2, 1 / c)
        _indexes.clear()
        _store.update(stamp=stamp, ids=frozenset(raw), rows=rows, mean=mean, pos=None)


def stamp():
    _refresh()
    return _store["stamp"]


def count():
    """Number of songs with a usable sound vector."""
    _refresh()
    return len(_store["rows"])


# ---------------------------------------------------------------------------- Index per song list

def index(lib):
    """Index for this song list, or None if none of its songs has a sound vector yet."""
    _refresh()
    if not _store["rows"]:
        return None
    from .ml import MEMO_SIZE, songs_key
    key = (songs_key(lib), _store["stamp"])
    with _lock:
        idx = _indexes.get(key)
        if idx is not None:
            _indexes.move_to_end(key)
    if idx is None:
        idx = Index(lib, _store["rows"], _store["mean"])
        if not idx.rows:
            idx = False
        from .ml import gone
        with _lock:   # a few song lists at once (default list, account lists): one index each instead of thrashing
            for k in [k for k in _indexes if gone(k[0])]:   # song lists that are gone
                del _indexes[k]
            _indexes[key] = idx
            while len(_indexes) > MEMO_SIZE:
                _indexes.popitem(last=False)
    return idx or None


def unit(vec):
    """Vector -> unit vector (array of floats), None for a zero vector."""
    n = math.sqrt(_dot(vec, vec))
    return array("d", (x / n for x in vec)) if n > 1e-12 else None


def cosine(a, b):
    """Cosine of two unit vectors (centroids)."""
    return _dot(a, b)


def mean_unit(vectors):
    """Mean direction of several unit vectors (e.g. the bands of a music world) – None without any."""
    acc = None
    for v in vectors:
        acc = list(v) if acc is None else list(map(add, acc, v))
    return unit(acc) if acc else None


class Index:
    """Sound vectors of one song list (indices into lib.songs) with neighbors and band centroids. Keeps no reference to
    the song list itself (only the bands of its songs with a vector) – an index in the cache must not hold an old,
    reloaded song list in memory."""

    def __init__(self, lib, rows, mean):
        self.mean = mean
        self.rows = {}
        self._artists = []   # main artist of each song in self.rows, in the same order (for the centroids)
        for i, s in enumerate(lib.songs):
            r = rows.get(s["id"])
            if r is not None:
                self.rows[i] = r
                self._artists.append(lib._main_artist(s))
        self._order = list(self.rows)
        self._neighbors = {}
        self._centroids = None
        self._similar = {}

    def __len__(self):
        return len(self.rows)

    def has(self, i):
        return i in self.rows

    def cos(self, i, j):
        a, b = self.rows.get(i), self.rows.get(j)
        if a is None or b is None:
            return None
        return _dot(a[0], b[0]) * a[1] * b[1] - (a[2] + b[2]) * a[3] * b[3]

    def centered(self, i):
        """Centered unit vector of a song (array of floats) or None."""
        r = self.rows.get(i)
        if r is None:
            return None
        v, s, _h, w = r
        return array("d", (x * s - m * w for x, m in zip(v, self.mean)))

    def closeness(self, i, vec):
        """Similarity of a song to a unit vector in the centered space (e.g. a band's centroid), None without vector."""
        r = self.rows.get(i)
        if r is None or vec is None:
            return None
        v, s, _h, w = r
        return _dot(v, vec) * s - _dot(self.mean, vec) * w

    def neighbors(self, i, k=50, within=None):
        """The k most similar songs to song i [(j, score)], best first; within: only these indices (set)."""
        r = self.rows.get(i)
        if r is None:
            return []
        key = (i, k)
        if within is None and key in self._neighbors:
            return self._neighbors[key]
        q, si, hi, wi = r
        dot = _dot
        cands = self._order if within is None else [j for j in within if j in self.rows]
        rows = self.rows

        def scores():
            for j in cands:
                if j != i:
                    v, s, h, w = rows[j]
                    yield dot(q, v) * si * s - (hi + h) * wi * w, j
        best = [(j, round(sc, 4)) for sc, j in heapq.nlargest(k, scores())]
        if within is None:
            if len(self._neighbors) > 512:
                self._neighbors.clear()
            self._neighbors[key] = best
        return best

    def centroids(self):
        """Band (main artist) -> (unit vector of its mean sound, songs with a vector) – from MIN_SONGS songs."""
        if self._centroids is not None:
            return self._centroids
        acc, wsum, n = {}, {}, {}
        for (v, s, _h, w), a in zip(self.rows.values(), self._artists):
            if not a:
                continue
            prev = acc.get(a)
            part = map(mul, v, repeat(s))
            acc[a] = list(part) if prev is None else list(map(add, prev, part))
            wsum[a] = wsum.get(a, 0.0) + w
            n[a] = n.get(a, 0) + 1
        out = {}
        for a, vec in acc.items():
            if n[a] < MIN_SONGS:
                continue
            u = unit([x - m * wsum[a] for x, m in zip(vec, self.mean)])   # sum of the centered song vectors
            if u is not None:
                out[a] = (u, n[a])
        self._centroids = out
        return out

    def centroid(self, artist):
        c = self.centroids().get(artist)
        return c[0] if c else None

    def similar_artists(self, artist, k=12):
        """Bands whose mean sound is closest to the band's [(band, score)], best first."""
        if artist in self._similar and len(self._similar[artist]) >= k:
            return self._similar[artist][:k]
        cents = self.centroids()
        me = cents.get(artist)
        if me is None:
            return []
        best = heapq.nlargest(k, ((_dot(me[0], c), a) for a, (c, _n) in cents.items() if a != artist))
        out = [(a, round(sc, 4)) for sc, a in best]
        self._similar[artist] = out
        return out


# ---------------------------------------------------------------------------- Many songs at once

_FLIP = bytes(b ^ 0x80 for b in range(256))   # int8 (two's complement) -> unsigned byte = value + 128
_SCALE = 2 ** 15        # components of a unit vector as integers: −1 … 1 -> 0 … 2¹⁶
_ROW_BYTES = 6          # bytes per dimension when summing songs (48 bits: room for millions of songs)
_U32 = next(t for t in "IL" if array(t).itemsize == 4)


def _lanes(number, count, width, kind):
    """Big integer -> array of `count` unsigned values of `width` bytes each (little-endian lanes)."""
    out = array(kind)
    out.frombytes(number.to_bytes(count * width, "little"))
    if sys.byteorder == "big":
        out.byteswap()
    return out


class Batch:
    """Sound vectors of many songs at once – for the sound taste (soundtaste.py), which compares thousands of songs
    with a few vectors. With the standard library only, one dot product per song costs about 3 µs; here big integers
    serve as lanes instead: per dimension one integer holding the value of every song (shifted to 0 … 255) in its own
    32 bits. Multiplying these 128 integers by a vector's components (as integers 0 … 2¹⁶) and adding them up yields
    the dot product of every song at once – without a carry between the lanes, as 128 · 255 · 2¹⁶ < 2³². The other
    direction (weighted sums of songs) packs each song into one integer with 48 bits per dimension. Rounding the
    components costs less than 0.001 in the cosine.

    rows: [(v, s, h, w)] as in _store["rows"]; mean: the mean direction (the centre)."""

    def __init__(self, rows, mean):
        self.n = len(rows)
        self.mean = mean
        self._rows = rows
        self._s = [r[1] for r in rows]
        self._w = [r[3] for r in rows]
        self._cols = None
        self._packed = None
        self.positions = None   # batch() of all songs: song id -> row

    def __len__(self):
        return self.n

    def centered(self, j):
        """Centered unit vector of the song in row j (array of floats)."""
        v, s, _h, w = self._rows[j]
        return array("d", (x * s - m * w for x, m in zip(v, self.mean)))

    def _columns(self):
        """Per dimension the values of all songs as lanes of 32 bits; per song the factors that turn a lane into the
        centered cosine."""
        if self._cols is None:
            n = self.n
            big = b"".join(r[0].tobytes() for r in self._rows)
            cols, total = [], 0
            for d in range(DIM):
                buf = bytearray(4 * n)
                buf[0::4] = big[d::DIM].translate(_FLIP)
                col = int.from_bytes(buf, "little")
                cols.append(col)
                total += col
            # lane = Σ (v + 128)(q + S) = v·q + S·Σv + 128·Σq + 128·S·DIM, cosine = v·q / S · s − (m·vec) · w
            sv = map(sub, _lanes(total, n, 4, _U32), repeat(128 * DIM))   # Σv per song
            a = [x / _SCALE for x in self._s]
            self._cols = (cols, a, list(map(mul, map(mul, sv, self._s), repeat(-1.0))))
        return self._cols

    def closeness(self, vec, scale=1.0):
        """Centered cosine of every song to a unit vector (list in the order of the rows) – as Index.closeness() –,
        multiplied by scale."""
        cols, a, b = self._columns()
        q = [max(-_SCALE, min(_SCALE, round(x * _SCALE))) for x in vec]
        acc = 0
        for col, x in zip(cols, q):
            acc += col * (x + _SCALE)
        const = 128 * sum(q) + 128 * _SCALE * DIM
        mp = _dot(self.mean, vec)
        # a · (lane − const) + b − mp · w, in C loops (map) instead of Python per song
        out = map(sub, map(add, map(mul, a, map(sub, _lanes(acc, self.n, 4, _U32), repeat(const))), b),
                  map(mul, self._w, repeat(mp)))
        return list(out if scale == 1.0 else map(mul, out, repeat(scale)))

    def sums(self, weights, groups=None, k=1):
        """Weighted sums of the centered song vectors: [vector (list of floats) per group]. weights ≥ 0 per row,
        groups: group 0 … k−1 per row (without: all in one). Normalized, a sum is the mean sound of its group."""
        if self._packed is None:
            packed = []
            for r in self._rows:
                buf = bytearray(_ROW_BYTES * DIM)
                buf[0::_ROW_BYTES] = r[0].tobytes().translate(_FLIP)
                packed.append(int.from_bytes(buf, "little"))
            self._packed = packed
        coef = list(map(mul, weights, self._s))
        top = max(coef, default=0.0) or 1.0
        q = [round(c * (65536 / top)) for c in coef]
        cw = list(map(mul, weights, self._w))
        out, b = [], _ROW_BYTES
        for g in range(k):
            rows = range(self.n) if groups is None else [j for j, x in enumerate(groups) if x == g]
            qg = list(map(q.__getitem__, rows))
            acc = sum(map(mul, qg, map(self._packed.__getitem__, rows)))
            units, centre = sum(qg), math.fsum(map(cw.__getitem__, rows))
            raw = acc.to_bytes(b * DIM, "little")
            vals = [int.from_bytes(raw[b * d:b * (d + 1)], "little") for d in range(DIM)]
            out.append([(x - 128 * units) * top / 65536 - m * centre for x, m in zip(vals, self.mean)])
        return out

def batch(ids=None):
    """Batch of the stored sound vectors: of these song ids (those with a vector, in this order) or of all – then
    Batch.positions is song id -> row (shared, in memory until the file changes). -> (song ids, Batch) or None
    without any vector."""
    _refresh()
    rows, mean = _store["rows"], _store["mean"]
    sids = list(rows) if ids is None else [sid for sid in ids if sid in rows]
    if not sids:
        return None
    out = Batch([rows[sid] for sid in sids], mean)
    if ids is None:
        pos = _store["pos"]
        if pos is None or pos[0] is not rows:
            pos = _store["pos"] = (rows, {sid: k for k, sid in enumerate(sids)})
        out.positions = pos[1]
    return sids, out
