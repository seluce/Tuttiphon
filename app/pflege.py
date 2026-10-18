"""Check library (administrator): what helps with tidying up. Read only – nothing is changed.

* duplicate in the same album: the same title twice, often the old FLAC file next to the converted Opus file
* same song on several albums (single, best-of …) – usually intended, helps with clearing out
* the same recording twice, recognized by the sound (audio fingerprints, fingerprint.py) – also across formats,
  folders and albums; only once the analyse step has compared the songs
* albums without a cover, albums with gaps in the track numbers
* very short files (often incomplete or broken), songs without a genre, low-quality MP3

The check ids ("doppelt", "luecken" …) are data: the interface and the tests use them.
"""
import re
from collections import defaultdict

from . import fingerprint
from .i18n import _, _n

LIMIT = 60


# additions that only name another edition of the same song – "(Playback)", "(Live)" or "(Remix)" stay
_EDITION = re.compile(r"[\(\[][^\)\]]*\b(remaster\w*|single|album|radio edit|mono|stereo|bonus|deluxe|version)\b[^\)\]]*[\)\]]"
                      r"|\s[-–]\s(\d{4}\s)?remaster\w*.*$")


def _norm(title, edition=False):
    """Title in lower case without punctuation; edition=True also without edition additions like "(Remastered 2011)"."""
    t = (title or "").lower()
    if edition:
        t = _EDITION.sub("", t)
    return re.sub(r"[^0-9a-zäöüß]+", " ", t).strip()   # i18n-ignore


def report(cfg, lib):
    songs = lib.songs
    aid = lib.artist_ids()
    albums = lib.albums()

    def row(s, detail=""):
        a = lib._main_artist(s)
        return {"artist": a, "artistId": aid.get(a), "album": s.get("album"), "albumId": s.get("albumId"),
                "title": s.get("title"), "detail": detail}

    checks = []

    def check(cid, title, text, items, total=None):
        checks.append({"id": cid, "title": title, "text": text, "count": total if total is not None else len(items),
                       "items": items[:LIMIT]})

    # the same title twice in the same album (same CD)
    in_album = defaultdict(list)
    for s in songs:   # same title and same length – "Song" and "Song (Playback)" are two songs
        if s.get("albumId") and _norm(s.get("title")):
            in_album[(s["albumId"], s.get("discNumber") or 1, _norm(s.get("title")), round((s.get("duration") or 0) / 3))].append(s)
    dup = [v for v in in_album.values() if len(v) > 1]
    check("doppelt", _("Duplicate in the same album"),
          _("The same title appears twice in the album – often the old FLAC file next to the converted Opus file."),
          [row(v[0], _(" and ").join(sorted({(x.get("suffix") or "?").upper() for x in v})) + f" · {len(v)}×") for v in dup])

    # same song on several albums
    across = defaultdict(list)
    for s in songs:
        if _norm(s.get("title")):
            across[(lib._main_artist(s) or "").lower(), _norm(s.get("title"), True), round((s.get("duration") or 0) / 5)].append(s)
    multi = sorted((v for v in across.values() if len({x.get("albumId") for x in v}) > 1), key=lambda v: -len(v))
    check("mehrfach", _("Same song on several albums"),
          _("For example as a single and on the album. Usually intended – helps with clearing out."),
          [row(v[0], _("on {albums}", albums=", ".join(sorted({x.get("album") or "?" for x in v})[:3]))) for v in multi])

    # the same recording twice – by the sound (fingerprint.py); only once the analyse step has compared the songs
    fp = fingerprint.stats(cfg, lib)
    if fp["comparedAt"]:
        same = []
        for g in fingerprint.groups(lib):
            copies = sorted(g["songs"], key=lambda m: (m[2] or "", m[1]["id"]))
            formats = sorted({(s.get("suffix") or "?").upper() for _i, s, _p in copies})
            on = sorted({s.get("album") or "?" for _i, s, _p in copies})   # not `albums` – that is needed below
            where = _(" and ").join(formats) if len(formats) > 1 else _("on {albums}", albums=", ".join(on[:3]))
            same.append({**row(copies[0][1], f"{where} · {len(copies)}×"), "similarity": g["sim"],
                         "copies": [{"id": s["id"], "title": s.get("title"), "artist": lib._main_artist(s),
                                     "album": s.get("album"), "albumId": s.get("albumId"),
                                     "format": (s.get("suffix") or "").upper() or None, "bitRate": s.get("bitRate"),
                                     "duration": s.get("duration"), "path": path} for _i, s, path in copies]})
        same.sort(key=lambda x: ((x["artist"] or "").lower(), (x["title"] or "").lower()))
        check("aufnahme", _("Same recording twice"),
              _("The same audio as more than one file – also across formats, folders and albums, for example a FLAC "
                "file still next to its converted Opus file, or a song on an album and on a best-of. One copy is "
                "enough; a lossless original that has already been converted belongs in the archive."), same)
        checks[-1].update(level="info", progress={"done": fp["songs"], "total": len(songs)})

    # albums without a cover (only if Navidrome tells)
    if getattr(lib, "album_meta", None):
        bare = sorted((a for a in albums.values() if not a.get("hasArt")), key=lambda a: (a.get("artist") or "", a.get("name") or ""))
        check("cover", _("Albums without a cover"),
              _("There is no image in the folder or in the files. Tuttiphon fetches it with “Update everything” and once a week at night."),
              [{"artist": a.get("artist"), "artistId": a.get("artistId"), "album": a.get("name"), "albumId": a.get("id"),
                "title": None, "detail": _n(a.get("songs"), "{n} song", "{n} songs")} for a in bare])

    # gaps in the track numbers
    tracks = defaultdict(set)
    first = {}
    for s in songs:
        if s.get("albumId") and isinstance(s.get("track"), int) and 0 < s["track"] <= 999:   # 2024 or the like is not a number
            tracks[(s["albumId"], s.get("discNumber") or 1)].add(s["track"])
            first.setdefault(s["albumId"], s)
    gaps = []
    for (album, disc), have in sorted(tracks.items(), key=lambda kv: (first[kv[0][0]].get("album") or "")):
        missing = [n for n in range(1, max(have) + 1) if n not in have]
        if missing and len(have) >= 3 and len(missing) <= len(have):
            numbers = ", ".join(map(str, missing[:6])) + (" …" if len(missing) > 6 else "")
            gaps.append(row(first[album], _("CD {disc}: missing {numbers}", disc=disc, numbers=numbers) if disc != 1
                            else _("missing {numbers}", numbers=numbers)))
    for g in gaps:
        g["title"] = None
    check("luecken", _("Albums with gaps"), _("Some track numbers are missing, for example 1, 2 and 4."), gaps)

    short = [s for s in songs if 0 < (s.get("duration") or 0) < 20]
    check("kurz", _("Very short files"), _("Under 20 seconds – often incomplete or broken files."),
          [row(s, f"{s.get('duration')} s") for s in sorted(short, key=lambda s: s.get("duration") or 0)])

    nogenre = [s for s in songs if not s.get("genre") and not s.get("genres")]
    by_artist = defaultdict(list)
    for s in nogenre:
        by_artist[lib._main_artist(s)].append(s)
    check("genre", _("Songs without a genre"), _("Without a genre, vibes such as Rock or Pop do not apply to these songs."),
          [{**row(v[0], _n(len(v), "{n} song", "{n} songs")), "title": None, "album": None}
           for _, v in sorted(by_artist.items(), key=lambda kv: -len(kv[1]))], total=len(nogenre))

    low = [s for s in songs if (s.get("suffix") or "").lower() == "mp3" and 0 < (s.get("bitRate") or 999) < 128]
    check("qualitaet", _("Low quality"), _("MP3 files below 128 kbit/s – audibly worse than the rest."),
          [row(s, f"{s.get('bitRate')} kbit/s") for s in sorted(low, key=lambda s: s.get("bitRate") or 0)])

    return {"songs": len(songs), "albums": len(albums), "checks": checks, "fingerprints": fp}
