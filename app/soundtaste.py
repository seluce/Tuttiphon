"""Sound taste per Navidrome account – what the songs an account plays sound like, from the AI's sound vectors
(similar.py).

Not one average: a family account plays children's songs and adult music, and the mean of both sounds like neither.
Instead a few prototypes – the typical sounds of what is played:

* Liked songs: the positive weights of taste.song_scores() (plays of the last 60 days count most, then all plays,
  favorites and stars ≥ 4 given by hand; songs skipped in mixes weigh less). Disliked songs (dislikes_of()): 1 star
  by hand, 2 stars by hand, skipped often in mixes.
* Weighted spherical k-means in the centered space of similar.py (prototypes()): k = liked songs with a vector / 10,
  at most 4. Deterministic: it starts with the most important typical song, then always the important song farthest
  from the prototypes so far; ties go by order. Two prototypes closer than MERGE become one, a prototype with less
  than 10 % of the weight or fewer than 5 songs gives its songs to the others – so k follows the data. The same for
  the disliked songs (at most 2 prototypes, from 3 songs).
* Score of a song (0 … 1): its closeness to the nearest prototype – 1 from the typical closeness of that prototype's
  own songs (their weighted mean), 0 at 0 (unrelated) – minus how much more it sounds like the disliked songs than
  like the liked ones.

Computed once per account and day (and when the sound vectors change); the scores of all songs only when a mix or
the suggestions need them. taste.matcher() blends the score into the taste similarity – half of it, less while few
of the liked songs have a vector yet (the AI works through the library over several nights).
"""
import math
import threading
from array import array
from itertools import repeat
from operator import mul, sub

from . import feedback, similar

LIKE_K = 4             # at most this many prototypes for what is liked
PER_PROTOTYPE = 10     # liked songs with a vector per prototype (k = songs // 10, 1 … LIKE_K)
MIN_SONGS = 15         # fewer liked songs with a vector: no sound taste
MERGE = 0.6            # prototypes whose cosine is above this become one
MIN_SHARE = 0.1        # share of the weight a prototype needs
MIN_MEMBERS = 5        # songs a prototype needs
DISLIKE_K = 2          # prototypes for what is disliked – 2 from DISLIKE_TWO songs
DISLIKE_TWO = 20
DISLIKE_MIN = 3        # disliked songs with a vector needed at all
DISLIKE_TYP = 0.3      # disliked songs only count fully from this closeness (scattered dislikes say little)
TYP_MIN = 0.15         # lower limit of the typical closeness (a loose prototype must not make everything "typical")
ITERATIONS = 12
MAX_SONGS = 4000       # at most the most important songs – bounded time
SHARE = 0.5            # share of the sound score in the taste similarity (taste.matcher)
FULL_COVERAGE = 0.5    # from this share of the liked weight with a vector, SHARE applies in full
SKIPPED = feedback.SKIP_FACTOR ** 2   # skipped at least twice (counting the half-life): disliked
SUGGEST = 0.8          # suggestions: score bonus per point the songs sound more like the taste than the library
SUGGEST_MAX = 0.3
POOL_MIN = 10          # suggestions: songs with a vector needed for a bonus
POOL_COVER = 0.25      # … and at least this share of the songs
_lock = threading.Lock()
_memo = {}


class SoundTaste:
    """Sound prototypes of one account. like/dislike: [(unit vector, share of the weight, songs, typical closeness)],
    biggest first; songs: liked songs with a vector; coverage: share of the liked weight they carry."""

    def __init__(self, like, dislike, songs, coverage):
        self.like, self.dislike = like, dislike
        self.songs, self.coverage = songs, coverage
        self.share = SHARE * min(1.0, coverage / FULL_COVERAGE)
        self._scores = None
        self._libs = {}

    def _all(self):
        """-> (song id -> row, array of scores, mean score) over all songs with a vector – computed on first use."""
        if self._scores is None:
            got = similar.batch()
            if got is None:
                self._scores = ({}, array("d"), 0.0)
            else:
                b = got[1]
                score = _best(b, self.like, TYP_MIN)
                if self.dislike:   # like − (dislike − like) where it sounds more like the dislikes: min(x, 2x − d)
                    worse = map(sub, map(mul, score, repeat(2.0)), _best(b, self.dislike, DISLIKE_TYP))
                    score = list(map(max, map(min, score, worse), repeat(0.0)))
                self._scores = (b.positions, array("d", score), math.fsum(score) / len(score))
        return self._scores

    def score(self, sid):
        """0 (does not sound like what is played) … 1, None without a sound vector."""
        pos, arr, _mean = self._all()
        k = pos.get(sid)
        return None if k is None else arr[k]

    def for_lib(self, lib):
        """Scores by index of this song list (None without a sound vector) – cached per song list."""
        from .ml import lib_key
        key = lib_key(lib)
        hit = self._libs.get(key)
        if hit is None:
            pos, arr, _mean = self._all()
            hit = [None if k is None else arr[k] for k in (pos.get(s["id"]) for s in lib.songs)]
            with _lock:
                if len(self._libs) > 4:
                    self._libs.clear()
                self._libs[key] = hit
        return hit

    def bonus(self, lib, ids):
        """Suggestions: how much more these songs sound like the taste than the library on average – mean score minus
        the mean of all songs, × SUGGEST and the weight of the sound, at most ± SUGGEST_MAX; 0 with too few songs with a
        vector."""
        by = self.for_lib(lib)
        vals = [x for x in map(by.__getitem__, ids) if x is not None]
        if len(vals) < POOL_MIN or len(vals) < POOL_COVER * len(ids):
            return 0.0
        diff = sum(vals) / len(vals) - self._all()[2]
        return max(-SUGGEST_MAX, min(SUGGEST_MAX, SUGGEST * diff * self.share / SHARE))


def _best(b, protos, floor):
    """Per song of the batch: the best score over the prototypes (closeness / typical closeness, 0 … 1)."""
    lists = [b.closeness(vec, 1 / max(typ, floor)) for vec, _share, _n, typ in protos]
    best = map(max, *lists) if len(lists) > 1 else lists[0]
    return list(map(min, map(max, best, repeat(0.0)), repeat(1.0)))


# ---------------------------------------------------------------------------- Signals

def dislikes_of(plib, user, today):
    """Song id -> weight of the dislike: 1 star by hand 3, 2 stars by hand 1.5, skipped often in mixes (at least two
    skips that still count) 1 … 3. Favorites and songs rated 4–5 stars by hand never count as skipped."""
    never = feedback.manual_dislikes(plib, user)
    by_deezer = feedback.deezer_stars(user)
    skip = feedback.factors(user, today)
    out = {}
    for s in plib.songs:
        sid = s["id"]
        if sid in never:
            out[sid] = 3.0
            continue
        rating = s.get("userRating") or 0
        by_hand = bool(rating) and sid in by_deezer and by_deezer[sid] != rating
        if by_hand and rating <= 2:
            out[sid] = 1.5
            continue
        f = skip.get(sid)
        if f and f <= SKIPPED + 1e-9 and not s.get("starred") and not (by_hand and rating >= 4):
            out[sid] = max(1.0, min(3.0, math.log(f) / math.log(feedback.SKIP_FACTOR) - 1))
    return out


# ---------------------------------------------------------------------------- Prototypes

def _assign(b, centers):
    """Closeness of every song to every prototype and the closest prototype per song."""
    close = [b.closeness(c) for c in centers]
    if len(centers) == 1:
        return close, [0] * len(b)
    k = range(len(centers))
    return close, [max(k, key=row.__getitem__) for row in zip(*close)]


def _seeds(b, weights, k):
    """Starting prototypes: the most important typical song, then always the important song farthest from the ones
    so far (deterministic: ties go to the earlier song)."""
    n = len(b)
    mean = similar.unit(b.sums(weights)[0])
    near = b.closeness(mean) if mean is not None else [0.0] * n
    first = max(range(n), key=lambda j: (weights[j] * (1 + near[j]), -j))
    centers = [b.centered(first)]
    near = b.closeness(centers[0])
    while len(centers) < k:
        j = max(range(n), key=lambda j: (weights[j] * (1 - near[j]), -j))
        if near[j] > 0.999:   # nothing left that sounds different
            break
        centers.append(b.centered(j))
        near = list(map(max, near, b.closeness(centers[-1])))
    return centers


def _lloyd(b, weights, centers):
    """Spherical k-means: every song to the closest prototype, every prototype = normalized weighted sum of its songs
    – until nothing changes. -> (prototypes, group per song, closeness of each song to its prototype)"""
    groups, stable = None, False
    for _ in range(ITERATIONS):
        close, new = _assign(b, centers)
        used = sorted(set(new))
        if len(used) < len(centers):   # a prototype without songs: drop it
            centers, groups = [centers[g] for g in used], None
            continue
        if new == groups:
            stable = True
            break
        groups = new
        centers = [similar.unit(s) or c for s, c in zip(b.sums(weights, groups, len(centers)), centers)]
    if not stable:
        close, groups = _assign(b, centers)
        used = sorted(set(groups))
        if len(used) < len(centers):
            renum = {g: x for x, g in enumerate(used)}
            centers, close, groups = [centers[g] for g in used], [close[g] for g in used], [renum[g] for g in groups]
    return centers, groups, [close[g][j] for j, g in enumerate(groups)]


def prototypes(b, weights, k, min_members=MIN_MEMBERS):
    """Weighted spherical k-means with up to k prototypes; prototypes that sound alike are merged, weak ones dropped.
    -> [(unit vector, share of the weight, songs, typical closeness)], biggest first."""
    total = sum(weights) or 1.0
    centers = _seeds(b, weights, k)
    while True:
        centers, groups, own = _lloyd(b, weights, centers)
        k = len(centers)
        pair = max(((similar.cosine(centers[x], centers[y]), y) for x in range(k) for y in range(x + 1, k)), default=None)
        if pair and pair[0] > MERGE:
            del centers[pair[1]]
            continue
        wsum, count, csum = [0.0] * k, [0] * k, [0.0] * k
        for j, g in enumerate(groups):
            wsum[g] += weights[j]
            count[g] += 1
            csum[g] += weights[j] * own[j]
        weak = min(range(k), key=lambda g: (wsum[g], g))
        if k > 1 and (wsum[weak] / total < MIN_SHARE or count[weak] < min_members):
            del centers[weak]
            continue
        out = [(centers[g], round(wsum[g] / total, 4), count[g], csum[g] / wsum[g] if wsum[g] else 0.0) for g in range(k)]
        return sorted(out, key=lambda p: -p[1])


def _protos_of(weighted, k_of, min_members, at_least):
    """weighted: song id -> weight. -> (prototypes, songs with a vector, their share of the weight) or None."""
    total = sum(weighted.values())
    order = sorted(weighted, key=lambda sid: (-weighted[sid], sid))   # most important first, ties by id
    got = similar.batch(order[:MAX_SONGS]) if total > 0 else None
    if got is None or len(got[0]) < at_least:
        return None
    sids, b = got
    weights = [weighted[sid] for sid in sids]
    return prototypes(b, weights, k_of(len(sids)), min_members), len(sids), sum(weights) / total


def compute(plib, user, today, scores):
    """Sound taste of the account (plib: its song list, scores: taste.song_scores() by index), or None."""
    songs = plib.songs
    dislikes = dislikes_of(plib, user, today)
    like = {}
    for i, sc in scores.items():
        sid = songs[i]["id"]
        if sc > 0 and sid not in dislikes:
            like[sid] = sc
    liked = _protos_of(like, lambda n: max(1, min(LIKE_K, n // PER_PROTOTYPE)), MIN_MEMBERS, MIN_SONGS)
    if liked is None:
        return None
    disliked = _protos_of(dislikes, lambda n: DISLIKE_K if n >= DISLIKE_TWO else 1, DISLIKE_MIN, DISLIKE_MIN)
    return SoundTaste(liked[0], disliked[0] if disliked else [], liked[1], liked[2])


def of(plib, user, today, scores):
    """Sound taste of this account for the day – cached per account, day and state of the sound vectors – or None
    (no sound vectors, too few liked songs with one). scores: function -> taste.song_scores() of the account, only
    called when it is computed."""
    if not user:
        return None
    stamp = similar.stamp()
    if stamp is None:
        return None
    key = (user.lower(), today, stamp)
    with _lock:
        if key in _memo:
            return _memo[key]
    st = compute(plib, user, today, scores())
    with _lock:
        if len(_memo) > 16:
            _memo.clear()
        _memo[key] = st
    return st
