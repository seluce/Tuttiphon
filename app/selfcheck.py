"""Self-check after the scan: does Navidrome deliver what Tuttiphon expects?

* Smart playlists: Navidrome's song count against Tuttiphon's own evaluation of the same rules (rules.Library) – with
  the stars and favorites of the playlist owner. Counted as the owner (Subsonic getPlaylist): Navidrome evaluates a smart
  playlist fresh only for its owner, and this way missing files do not count – just like in Symfonium.
  Without the owner's password Tuttiphon only knows average ratings; such playlists are not checked
  (otherwise there would be false alarms).
* Mixes (.m3u): entries of the file against the songs Navidrome found from it – if something is missing, paths are wrong.

A difference is reported (“To review”) when it is big (> BIG) or shows up again the next time – freshly imported songs
Tuttiphon does not know yet do not raise an alarm this way. Result: state/selfcheck.json
"""
import json
import time

from . import mixer, playlists, rules
from .config import STATE_DIR, read_text, user_password, write_atomic
from .i18n import _s
from .navidrome import Navidrome

FILE = STATE_DIR / "selfcheck.json"
TOLERANCE = 2      # this many songs of difference count as equal (time rules like “in the last 30 days”)
BIG = 0.10         # report at once from a 10 % difference


def load():
    try:
        data = json.loads(read_text(FILE))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def _m3u_entries(path):
    try:
        return sum(1 for line in read_text(path).splitlines() if line.strip() and not line.startswith("#"))
    except OSError:
        return None


def owner_count(env, user, playlist_id):
    """Songs of the playlist as its owner sees them (freshly evaluated, without missing files – like in Symfonium)."""
    body = Navidrome(env["NAV_URL"], user, user_password(env, user)).call("getPlaylist", id=playlist_id)
    return len((body.get("playlist") or {}).get("entry") or [])


def run(cfg, env, ctx, log=print):
    """-> {"checked", "skipped", "problems": [...]} – writes state/selfcheck.json."""
    native = playlists.native_api(env)
    by_file = playlists.navidrome_index(native, cfg)
    previous = {x["id"]: x for x in load().get("mismatch", [])}
    checked = skipped = 0
    mismatch, problems = [], []
    folder = playlists.playlist_dir(cfg)
    for p, filename, nsp in playlists.plan(cfg, ctx):
        np = by_file.get(filename)
        if not np:
            continue   # not in Navidrome yet – the sync reports that already
        if rules.is_mix(p):
            expected = _m3u_entries(folder / filename)
            kind = "mix"
        else:
            owner = ((rules.person_of(cfg, p) or {}).get("user") or "").lower()
            plib = mixer.person_lib(cfg, p, ctx.lib)
            if not plib.ratings_exact or (owner and (plib.user or "").lower() != owner):
                skipped += 1   # owner's stars unknown – the comparison would not be meaningful
                continue
            try:
                expected = len(plib.match(nsp))
            except (ValueError, KeyError):
                skipped += 1   # a rule Tuttiphon cannot evaluate itself
                continue
            if nsp.get("limit"):
                expected = min(expected, int(nsp["limit"]))
            kind = "smart"
        if expected is None:
            continue
        try:
            if kind == "smart":
                actual = owner_count(env, plib.user, np["id"])
            else:
                actual = native.playlist_count(np["id"])
        except Exception as e:   # noqa: BLE001 – one playlist must not hold up checking the others
            log(_s("  ⚠ Self-check {name}: {error}", name=nsp["name"], error=e))
            continue
        checked += 1
        diff = actual - expected
        if abs(diff) <= TOLERANCE:
            continue
        item = {"id": p["id"], "name": nsp["name"], "kind": kind, "expected": expected, "actual": actual}
        mismatch.append(item)
        big = abs(diff) > BIG * max(expected, 1)
        if big or p["id"] in previous:
            problems.append(item)
            if kind == "mix":
                log(_s("  ⚠ {name}: Navidrome shows {actual} songs, expected {expected} – check the paths in the .m3u",
                       name=nsp["name"], actual=actual, expected=expected))
            else:
                log(_s("  ⚠ {name}: Navidrome shows {actual} songs, expected {expected}",
                       name=nsp["name"], actual=actual, expected=expected))
    write_atomic(FILE, json.dumps({"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "checked": checked, "skipped": skipped,
                                   "mismatch": mismatch, "problems": problems}, ensure_ascii=False))
    counts = {"checked": checked, "skipped": skipped, "problems": len(problems)}
    if skipped and problems:
        log(_s("Self-check: {checked} playlists checked, {skipped} skipped without the owner's stars – {problems} differ.",
               **counts))
    elif skipped:
        log(_s("Self-check: {checked} playlists checked, {skipped} skipped without the owner's stars – all as expected.",
               **counts))
    elif problems:
        log(_s("Self-check: {checked} playlists checked – {problems} differ.", **counts))
    else:
        log(_s("Self-check: {checked} playlists checked – all as expected.", **counts))
    return {"checked": checked, "skipped": skipped, "problems": problems}
