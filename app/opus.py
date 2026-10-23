"""Convert lossless files (FLAC & co.) to Opus or AAC.

* Opus (.opus): small, sounds like the original already at 160 kbit/s – ideal for Android (Symfonium).
* AAC (.m4a): Apple devices play it everywhere; needs a bit more for the same sound (default 224 kbit/s).
  ffmpeg writes only the common tags into .m4a – copy_tags_mp4() carries MusicBrainz ids, ISRC, ReplayGain & co.
  over with mutagen into the fields Navidrome reads (like MusicBrainz Picard), plus the cover.

Safety rules:
* freshly imported files (younger than X minutes) are left alone – Lidarr may still be writing
  (the folder watch hands over its new files directly once they have been unchanged for a few minutes)
* the new file is created as a hidden .part file and only taken over when it holds the whole song: ffmpeg reported
  no error while converting, and the new file, decoded completely, is as long as the original says it is (FLAC:
  STREAMINFO, WAV/AIFF: the size of the audio data in the header, otherwise ffprobe) – so a file that is still being
  copied, cut off or damaged (zeros from a download that was never finished) keeps its original
* an existing Opus/AAC file is only accepted when it is complete in the same way
* ALAC (.m4a) → AAC (.m4a) has the same name: a copy of the original goes to the archive first (a second name, or a
  checked copy on another volume), then the new file takes the original's place in one step (not possible with
  "keep original" – such files are left alone then)
* nothing in the archive is ever overwritten: an identical copy (an earlier run was interrupted after copying) counts
  as archived, a different file of the same name gets a free name next to it; the archive folder itself is never
  created – when it is missing or not writable (in the container: not mounted), nothing is converted
* the archive must not be the music folder or inside it (the originals there would be converted again)
* two originals that would become the same file (Song.flac and Song.wav) are left alone with a note
* the front cover is embedded into the Opus file (Opus has no cover of its own from ffmpeg); in a folder of a single
  album without a cover image it is also saved as cover.jpg/png
"""
import base64
import errno
import json
import os
import re
import shutil
import subprocess
import tempfile
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from . import progress
from .config import is_inside, load_env, new_temp, paths, temp_copy
from .i18n import _s

EXTENSIONS = {"flac": (".flac",), "wav": (".wav",), "aiff": (".aif", ".aiff"), "ape": (".ape",), "wv": (".wv",),
              "alac": (".m4a",)}
SKIP_DIRS = ("@", "#", ".")   # Synology metadata (@eaDir), recycle bin (#recycle), hidden folders

_pending_cache = {"key": None, "at": 0.0, "files": None}
# Recently created Opus files (path -> time): the folder watch does not take them for new music
RECENT = {}
COVER_NAMES = ("cover", "folder", "front", "album")
IMAGE_EXT = (".jpg", ".jpeg", ".png", ".webp")
AUDIO_EXT = (".opus", ".mp3", ".flac", ".m4a", ".ogg", ".oga", ".wav", ".wma", ".aac", ".aiff", ".aif", ".wv", ".ape")
CODECS = {"opus": (".opus", "Opus", 160), "aac": (".m4a", "AAC", 224)}   # extension, name, default kbit/s
VERIFY_RATE = 8000    # the new file is decoded at this rate (mono, 1 byte per sample) to count its length
TOLERANCE = 0.3       # seconds the new file may differ from the length the original declares (AAC pads up to a frame)
_albums = {}          # folder -> one album only? (for cover.jpg; emptied at the start of every run)


def target(op):
    """-> (codec, extension, name, kbit/s) of the conversion according to the settings (settings.opus)."""
    codec = op.get("codec") if op.get("codec") in CODECS else "opus"
    ext, name, default = CODECS[codec]
    return codec, ext, name, int(op.get("aacBitrate" if codec == "aac" else "bitrate") or default)


def _keep_skips(path, op):
    """Keep the original and already converted? (ALAC → AAC would have the same name – then the file is left alone)"""
    return op.get("original", "archive") == "keep" and path.with_suffix(target(op)[1]).exists()


def tools():
    return {"ffmpeg": shutil.which("ffmpeg"), "ffprobe": shutil.which("ffprobe")}


def music_dir(env=None, cfg=None):
    return paths(cfg)["music"]


def archive_dir(op=None, cfg=None):
    return paths(cfg)["archive"]


def move_to_archive(src, dst):
    """Move the original to the archive. If the archive is on another volume (e.g. an HDD pool), it is copied: first as a
    hidden temporary file, the size checked, then renamed – and only then the original deleted. An interruption
    halfway (restart, disk full) thus never leaves half a file under the real name in the archive."""
    try:
        os.rename(src, dst)   # same file system: instant, needs no space
        return
    except OSError as e:
        if e.errno != errno.EXDEV:
            raise
    _copy_checked(src, dst)
    _unlink(src)   # if this fails, the next run finds the identical copy in the archive and only removes the original


def copy_to_archive(src, dst):
    """Put the original into the archive while it stays where it is (ALAC → AAC: the new file takes its place
    afterwards): a second name for the same file (hard link, instant) or, on another volume, a checked copy."""
    try:
        os.link(src, dst)
        return
    except OSError as e:
        if e.errno in (errno.EEXIST, errno.ENOENT):
            raise
    _copy_checked(src, dst)


def _copy_checked(src, dst):
    """Copy first as a hidden temporary file, check the size, then rename – never half a file under the real name."""
    tmp = None
    try:
        tmp = temp_copy(src, dst, "copy")   # a new file under a unique name – never through a link
        if tmp.stat().st_size != src.stat().st_size:
            raise OSError(_s("copy to the archive is incomplete"))
        os.replace(tmp, dst)
    except BaseException:
        if tmp is not None:
            tmp.unlink(missing_ok=True)
        raise


def _unlink(path, attempts=3):
    """Delete with a few attempts – on the NAS share a file is sometimes briefly not accessible."""
    for attempt in range(attempts):
        try:
            path.unlink()
            return
        except FileNotFoundError:
            return
        except OSError:
            if attempt == attempts - 1:
                raise
            time.sleep(0.5 * (attempt + 1))


def _same_content(a, b):
    """Are both files byte for byte the same? None: one of them cannot be read right now."""
    try:
        if a.stat().st_size != b.stat().st_size:
            return False
        with open(a, "rb") as fa, open(b, "rb") as fb:
            while True:
                x, y = fa.read(1 << 20), fb.read(1 << 20)
                if x != y:
                    return False
                if not x:
                    return True
    except OSError:
        return None


def archive_name(src, dst):
    """Where the original goes in the archive -> (path, already there) or None (cannot be compared right now).
    An identical copy (an earlier run was interrupted after copying) counts as archived; a different file of the same
    name is never overwritten – the original then gets a free name next to it, e.g. "Song (2).flac"."""
    cand = dst
    for n in range(2, 100):
        if not cand.exists():
            return cand, False
        same = _same_content(src, cand)
        if same is None:
            return None
        if same:
            return cand, True
        cand = dst.with_name(f"{dst.stem} ({n}){dst.suffix}")
    return None


def archive_folder(root, rel, owner):
    """Folder of the original in the archive: creates the missing subfolders (permissions and owner only for those),
    never the archive folder itself – without it (e.g. not mounted in the container) nothing is archived."""
    if not root.is_dir():
        raise OSError(errno.ENOENT, _s("archive folder {path} is missing", path=root))
    d = root
    for part in rel.parts:
        d = d / part
        try:
            d.mkdir()
        except FileExistsError:
            continue
        _own(d, owner, 0o755)
    return d


def archive_problem(music, root, write_test=True):
    """Can originals be archived? -> None or the reason (checked once before a run converts anything)."""
    if is_inside(root, music):
        return _s("The archive folder {archive} is the music folder or inside it – the originals there would be "
                  "converted again. Please choose a folder outside the music folder.", archive=root)
    if not root.is_dir():
        return _s("The archive folder {path} does not exist – please create it (in the container: mount it in "
                  "docker-compose.yaml). Nothing was converted.", path=root)
    if not os.access(root, os.W_OK | os.X_OK):
        return _s("The archive folder {path} is not writable – nothing was converted.", path=root)
    if write_test:   # NFS can say "writable" while the server refuses – try it
        try:
            fd, name = tempfile.mkstemp(prefix=".tuttiphon-test-", dir=root)
            os.close(fd)
            os.unlink(name)
        except OSError:
            return _s("The archive folder {path} is not writable – nothing was converted.", path=root)
    return None


def _codec(path):
    """Audio codec (only needed to tell ALAC from AAC in .m4a)."""
    try:
        out = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "a:0", "-show_entries", "stream=codec_name",
                              "-of", "csv=p=0", str(path)], capture_output=True, text=True, timeout=30, stdin=subprocess.DEVNULL)
        return out.stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return ""


def find_sources(op, env=None, use_cache=False):
    """All files to convert (older than minAgeMinutes)."""
    root = music_dir(env)
    exts = tuple(e for f in op.get("formats", ["flac"]) for e in EXTENSIONS.get(f, ()))
    keep = op.get("original", "archive") == "keep"
    key = (str(root), exts, op.get("minAgeMinutes"), keep, target(op)[1])
    if use_cache and _pending_cache["key"] == key and time.time() - _pending_cache["at"] < 600:
        return list(_pending_cache["files"])
    min_age = (op.get("minAgeMinutes") or 0) * 60
    now = time.time()
    files = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if not d.startswith(SKIP_DIRS)]
        for name in filenames:
            if name.startswith("._") or not name.lower().endswith(exts):
                continue
            path = Path(dirpath) / name
            try:
                st = path.stat()
            except OSError:
                continue
            if min_age and now - max(st.st_mtime, st.st_ctime) < min_age:
                continue
            if keep and _keep_skips(path, op):
                continue   # keep original: already converted
            if path.suffix.lower() == ".m4a" and _codec(path) != "alac":
                continue   # .m4a is usually AAC (lossy) – do not convert again
            files.append(path)
    files.sort()
    _pending_cache.update(key=key, at=time.time(), files=list(files))
    return files


def duration(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
                         capture_output=True, text=True, timeout=120, stdin=subprocess.DEVNULL)
    return float(out.stdout.strip())


def _flac_length(f):
    """Length from the FLAC STREAMINFO block (total samples / sample rate) or None."""
    head = f.read(10)
    start = 0
    if head[:3] == b"ID3" and len(head) == 10:   # some programs put an ID3 tag in front
        start = 10 + ((head[6] & 0x7F) << 21 | (head[7] & 0x7F) << 14 | (head[8] & 0x7F) << 7 | (head[9] & 0x7F))
        start += 10 if head[5] & 0x10 else 0
    f.seek(start)
    if f.read(4) != b"fLaC":
        return None
    block = f.read(38)
    if len(block) < 38 or block[0] & 0x7F != 0:   # the first block must be STREAMINFO
        return None
    info = block[4:]
    rate = info[10] << 12 | info[11] << 4 | info[12] >> 4
    total = (info[13] & 0x0F) << 32 | int.from_bytes(info[14:18], "big")
    return total / rate if total and rate else None


def _wav_length(f):
    """Length from the WAV header (size of the data chunk / bytes per sample frame) or None – only for PCM."""
    head = f.read(12)
    if head[:4] != b"RIFF" or head[8:12] != b"WAVE":
        return None
    fmt = None
    for _i in range(200):
        chunk = f.read(8)
        if len(chunk) < 8:
            return None
        cid, size = chunk[:4], int.from_bytes(chunk[4:], "little")
        if cid == b"fmt ":
            data = f.read(min(size, 16))
            if len(data) < 16:
                return None
            tag, rate = int.from_bytes(data[0:2], "little"), int.from_bytes(data[4:8], "little")
            align = int.from_bytes(data[12:14], "little")
            if tag not in (1, 3, 0xFFFE) or not rate or not align:
                return None   # compressed audio in a WAV container: ffprobe decides
            fmt = (rate, align)
            f.seek(size - len(data) + (size & 1), 1)
        elif cid == b"data":
            if fmt is None or size in (0, 0xFFFFFFFF):   # written as a stream: size unknown
                return None
            return size // fmt[1] / fmt[0]
        else:
            f.seek(size + (size & 1), 1)
    return None


def _aiff_length(f):
    """Length from the COMM chunk of an AIFF file (sample frames / sample rate) or None."""
    head = f.read(12)
    if head[:4] != b"FORM" or head[8:12] not in (b"AIFF", b"AIFC"):
        return None
    for _i in range(200):
        chunk = f.read(8)
        if len(chunk) < 8:
            return None
        cid, size = chunk[:4], int.from_bytes(chunk[4:], "big")
        if cid == b"COMM":
            data = f.read(18)
            if len(data) < 18:
                return None
            frames = int.from_bytes(data[2:6], "big")
            exp, mant = int.from_bytes(data[8:10], "big") & 0x7FFF, int.from_bytes(data[10:18], "big")
            rate = mant * 2.0 ** (exp - 16383 - 63) if exp else 0
            return frames / rate if frames and rate > 0 else None
        f.seek(size + (size & 1), 1)
    return None


def declared_length(path):
    """How long the original says it is (seconds) – from its header where the format has one (FLAC, WAV, AIFF:
    a file cut off or full of zeros still declares its full length), otherwise from ffprobe. None = unknown."""
    readers = {".flac": _flac_length, ".wav": _wav_length, ".aif": _aiff_length, ".aiff": _aiff_length}
    reader = readers.get(Path(path).suffix.lower())
    if reader:
        try:
            with open(path, "rb") as f:
                length = reader(f)
            if length:
                return length
        except OSError:
            return None
    try:
        out = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "a:0", "-show_entries",
                              "stream=duration:format=duration", "-of", "json", str(path)],
                             capture_output=True, text=True, timeout=120, stdin=subprocess.DEVNULL)
        data = json.loads(out.stdout or "{}")
        for value in [s.get("duration") for s in data.get("streams") or []] + [(data.get("format") or {}).get("duration")]:
            try:
                if value and float(value) > 0:
                    return float(value)
            except ValueError:
                continue
    except (OSError, subprocess.SubprocessError, ValueError):
        pass
    return None


def decoded_length(path, track=None, timeout=3600):
    """Decode the whole audio and count the samples -> (seconds, error text or ""). Unlike the length in the
    header this is what really plays – gaps (zeros in the original that ffmpeg skips) are missing here."""
    with tempfile.TemporaryFile() as err:
        proc = subprocess.Popen(["ffmpeg", "-nostdin", "-v", "error", "-i", str(path), "-map", "0:a:0", "-ac", "1",
                                 "-ar", str(VERIFY_RATE), "-f", "u8", "-"], stdout=subprocess.PIPE, stderr=err,
                                stdin=subprocess.DEVNULL, start_new_session=True)
        if track:
            track(proc, True)
        timer = threading.Timer(timeout, proc.kill)
        timer.start()
        n = 0
        try:
            while True:
                chunk = proc.stdout.read(1 << 16)
                if not chunk:
                    break
                n += len(chunk)
            proc.wait()
        finally:
            timer.cancel()
            proc.stdout.close()
            if track:
                track(proc, False)
        err.seek(0)
        text = err.read().decode("utf-8", "replace").strip()
    if proc.returncode != 0 and not text:
        text = _s("ffmpeg reports an error")
    return n / VERIFY_RATE, text


def verify(src, new, track=None):
    """Does the new file hold the whole song? -> None or the reason. Decodes the new file completely and compares
    its length with the length the original declares (when in doubt: not complete, the original stays)."""
    want = declared_length(src)
    if not want:
        return _s("the length of the original cannot be read")
    got, err = decoded_length(new, track)
    if abs(got - want) > TOLERANCE:
        return _s("length does not match ({got} s instead of {want} s)", got=f"{got:.1f}", want=f"{want:.1f}")
    return err[-300:] if err else None


def _own(path, owner, mode):
    try:
        os.chmod(path, mode)
    except OSError:
        pass
    if owner:
        try:
            uid, gid = (int(x) for x in str(owner).split(":"))
            os.chown(path, uid, gid)
        except (OSError, ValueError):
            pass   # without the rights (e.g. as a normal user over NFS) the owner stays as it is


def _folder_has_cover(folder):
    try:
        names = os.listdir(folder)
    except OSError:
        return True   # when in doubt, write nothing
    return any(n.lower().endswith(IMAGE_EXT) and n.lower().rsplit(".", 1)[0] in COVER_NAMES for n in names)


def _probe_json(path, *entries):
    try:
        out = subprocess.run(["ffprobe", "-v", "error", *entries, "-of", "json", str(path)], capture_output=True,
                             text=True, timeout=60, stdin=subprocess.DEVNULL)
        data = json.loads(out.stdout or "{}")
        return data if isinstance(data, dict) else {}
    except (OSError, subprocess.SubprocessError, ValueError):
        return None


def front_cover(src):
    """The front cover embedded in a file -> (image bytes, MIME type) or None. With several pictures (FLAC, ID3) the
    one marked as front cover, otherwise the first."""
    data = _probe_json(src, "-select_streams", "v", "-show_entries", "stream=index,codec_name:stream_tags=comment")
    streams = [s for s in (data or {}).get("streams") or [] if s.get("codec_name") in ("mjpeg", "png")]
    if not streams:
        return None
    pick = next((s for s in streams if ((s.get("tags") or {}).get("comment") or "").lower() == "cover (front)"),
                streams[0])
    try:
        out = subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-i", str(src), "-map", f"0:{int(pick['index'])}",
                              "-c", "copy", "-frames:v", "1", "-f", "image2pipe", "-"], capture_output=True, timeout=60,
                             stdin=subprocess.DEVNULL)
    except (OSError, subprocess.SubprocessError, KeyError, ValueError):
        return None
    if out.returncode != 0 or not out.stdout:
        return None
    return out.stdout, "image/png" if pick["codec_name"] == "png" else "image/jpeg"


def _album_of(path):
    data = _probe_json(path, "-show_entries", "format_tags=album:stream_tags=album")
    if data is None:
        return None
    tags = dict((data.get("format") or {}).get("tags") or {})
    for s in data.get("streams") or []:
        tags.update(s.get("tags") or {})
    return next((str(v).strip().casefold() for k, v in tags.items() if k.lower() == "album" and str(v).strip()), "")


def single_album(folder):
    """Do all songs in the folder belong to the same album? Only then a cover image for the folder fits – in a folder
    of singles or a mixed folder every song keeps its own cover (embedded)."""
    key = str(folder)
    if key not in _albums:
        try:
            names = [n for n in os.listdir(folder) if n.lower().endswith(AUDIO_EXT) and not n.startswith(".")]
        except OSError:
            names = []
        albums = {_album_of(Path(folder) / n) for n in names}   # untagged songs: Navidrome makes one album of them too
        _albums[key] = len(albums) == 1 and None not in albums
    return _albums[key]


def keep_cover(src, owner, log, dry_run=False):
    """Also put the embedded front cover next to the music as cover.jpg/png – only in the folder of a single album
    that has no cover image yet (in the Opus file it is embedded anyway, see embed_cover)."""
    if _folder_has_cover(src.parent) or not single_album(src.parent):
        return
    cover = front_cover(src)
    if not cover:
        return
    ext = ".png" if cover[1] == "image/png" else ".jpg"
    dst = src.parent / f"cover{ext}"
    if dry_run:
        log(_s("  (dry run) cover from the file → {name}", name=dst.name))
        return
    tmp = None
    try:
        tmp, fd = new_temp(dst, "cover")
        with os.fdopen(fd, "wb") as f:
            f.write(cover[0])
        if not _folder_has_cover(src.parent):
            os.replace(tmp, dst)
            _own(dst, owner, 0o644)
            log(_s("  ✓ Cover from the file saved as {name}.", name=dst.name))
    except OSError:
        pass
    finally:
        if tmp is not None:
            tmp.unlink(missing_ok=True)


def embed_cover(src, dst):
    """The front cover of the original into the new Opus file (METADATA_BLOCK_PICTURE, like in FLAC) – ffmpeg drops
    it. -> None or an error text (then the file does not count). Without mutagen nothing is embedded."""
    try:
        from mutagen.flac import Picture
        from mutagen.oggopus import OggOpus
    except ImportError:
        return None
    cover = front_cover(src)
    if not cover:
        return None
    try:
        pic = Picture()
        pic.type, pic.mime, pic.data = 3, cover[1], cover[0]
        f = OggOpus(str(dst))
        f["METADATA_BLOCK_PICTURE"] = [base64.b64encode(pic.write()).decode("ascii")]
        f.save()
        if not (OggOpus(str(dst)).tags or {}).get("METADATA_BLOCK_PICTURE"):
            return _s("cover not readable after writing")
        return None
    except Exception as e:   # noqa: BLE001 – a broken cover must not stop the run; the file does not count then
        return str(e) or type(e).__name__


def probe_tags(path):
    """Tags as ffmpeg reads them (also RIFF INFO in WAV and the text chunks of AIFF, which mutagen does not read)
    -> {lowercase name: value} or None."""
    data = _probe_json(path, "-select_streams", "a:0", "-show_entries", "format_tags:stream_tags")
    if data is None:
        return None
    out = {}
    for s in data.get("streams") or []:   # Ogg: the tags belong to the stream
        out.update({str(k).lower(): str(v) for k, v in (s.get("tags") or {}).items()})
    out.update({str(k).lower(): str(v) for k, v in ((data.get("format") or {}).get("tags") or {}).items()})
    return out


def tags_lost(src, new):
    """Did title and artist get lost on the way? -> None or an error text."""
    have = probe_tags(src)
    if not have or not (have.get("title", "").strip() or have.get("artist", "").strip()):
        return None
    got = probe_tags(new)
    if got is None or not (got.get("title", "").strip() or got.get("artist", "").strip()):
        return _s("title and artist did not arrive in the new file")
    return None


# ---------------------------------------------------------------------------- Tags for AAC (.m4a)

# Vorbis name -> MP4 atom (like MusicBrainz Picard); everything else ends up as ----:com.apple.iTunes:<name>
MP4_ATOMS = {"TITLE": "©nam", "ARTIST": "©ART", "ALBUM": "©alb", "ALBUMARTIST": "aART", "DATE": "©day",
             "GENRE": "©gen", "COMPOSER": "©wrt", "COMMENT": "©cmt", "LYRICS": "©lyr", "GROUPING": "©grp",
             "COPYRIGHT": "cprt", "TITLESORT": "sonm", "ARTISTSORT": "soar", "ALBUMSORT": "soal",
             "ALBUMARTISTSORT": "soaa", "COMPOSERSORT": "soco", "WORK": "©wrk", "MOVEMENTNAME": "©mvn"}
MP4_FREEFORM = {"MUSICBRAINZ_TRACKID": "MusicBrainz Track Id", "MUSICBRAINZ_RELEASETRACKID": "MusicBrainz Release Track Id",
                "MUSICBRAINZ_ARTISTID": "MusicBrainz Artist Id", "MUSICBRAINZ_ALBUMID": "MusicBrainz Album Id",
                "MUSICBRAINZ_ALBUMARTISTID": "MusicBrainz Album Artist Id",
                "MUSICBRAINZ_RELEASEGROUPID": "MusicBrainz Release Group Id", "MUSICBRAINZ_WORKID": "MusicBrainz Work Id",
                "MUSICBRAINZ_DISCID": "MusicBrainz Disc Id", "MUSICBRAINZ_ALBUMCOMMENT": "MusicBrainz Album Comment",
                "RELEASECOUNTRY": "MusicBrainz Album Release Country", "RELEASESTATUS": "MusicBrainz Album Status",
                "RELEASETYPE": "MusicBrainz Album Type", "ACOUSTID_ID": "Acoustid Id",
                "ACOUSTID_FINGERPRINT": "Acoustid Fingerprint"}
# other spellings of the same field (APEv2, ID3 TXXX, older programs) -> Vorbis name
KEY_ALIASES = {"ALBUM ARTIST": "ALBUMARTIST", "ALBUM_ARTIST": "ALBUMARTIST", "YEAR": "DATE", "TRACK": "TRACKNUMBER",
               "DISC": "DISCNUMBER", "TOTALTRACKS": "TRACKTOTAL", "TOTALDISCS": "DISCTOTAL", "UNSYNCEDLYRICS": "LYRICS",
               "DESCRIPTION": "COMMENT", "ORGANIZATION": "LABEL", "PUBLISHER": "LABEL",
               **{v.upper(): k for k, v in MP4_FREEFORM.items()}}
ID3_FRAMES = {"TIT2": "TITLE", "TPE1": "ARTIST", "TALB": "ALBUM", "TPE2": "ALBUMARTIST", "TDRC": "DATE",
              "TDOR": "ORIGINALDATE", "TCON": "GENRE", "TCOM": "COMPOSER", "TRCK": "TRACKNUMBER", "TPOS": "DISCNUMBER",
              "TSRC": "ISRC", "TPUB": "LABEL", "TBPM": "BPM", "TCMP": "COMPILATION", "TSOT": "TITLESORT",
              "TSOP": "ARTISTSORT", "TSOA": "ALBUMSORT", "TSO2": "ALBUMARTISTSORT", "TSOC": "COMPOSERSORT",
              "TIT1": "GROUPING", "TCOP": "COPYRIGHT", "TEXT": "LYRICIST", "TPE3": "CONDUCTOR", "TPE4": "REMIXER",
              "TMED": "MEDIA", "TLAN": "LANGUAGE", "TIT3": "SUBTITLE", "TSST": "DISCSUBTITLE", "TMOO": "MOOD"}
# not carried over: technical fields, images (the cover comes separately) and what goes into trkn/disk/tmpo/cpil
SKIP_TAGS = {"ENCODER", "ENCODEDBY", "ENCODERSETTINGS", "METADATA_BLOCK_PICTURE", "COVERART", "COVERARTMIME",
             "WAVEFORMATEXTENSIBLE_CHANNEL_MASK", "TRACKNUMBER", "TRACKTOTAL", "DISCNUMBER", "DISCTOTAL", "BPM",
             "COMPILATION", "R128_TRACK_GAIN", "R128_ALBUM_GAIN"}
# what ffprobe also lists as tags, but describes the container
PROBE_SKIP = {"MAJOR_BRAND", "MINOR_VERSION", "COMPATIBLE_BRANDS", "CREATION_TIME", "HANDLER_NAME", "VENDOR_ID"}


def mp4_available():
    try:
        import mutagen.mp4  # noqa: F401
        return True
    except ImportError:
        return False


def _norm_key(key):
    k = KEY_ALIASES.get(key.strip().upper(), key.strip().upper())
    if k.startswith("MUSICBRAINZ ") and k.endswith(" ID"):   # e.g. TXXX "MusicBrainz Composer Id"
        k = "MUSICBRAINZ_" + k[12:].replace(" ", "")
    return k


def source_tags(f):
    """Tags of a source file opened with mutagen as {VORBIS-NAME: [values]} – FLAC, APE/WavPack, WAV/AIFF with ID3."""
    from mutagen.apev2 import APEv2, APETextValue
    from mutagen.id3 import ID3
    out = {}

    def add(key, value):
        value = str(value).strip()
        if value:
            out.setdefault(_norm_key(key), []).append(value)
    tags = getattr(f, "tags", None)
    if tags is None:
        return out
    if isinstance(tags, ID3):
        for frame in tags.values():
            fid = frame.FrameID
            if fid == "TXXX":
                for t in frame.text:
                    add(frame.desc, t)
            elif fid == "UFID" and frame.owner == "http://musicbrainz.org":
                add("MUSICBRAINZ_TRACKID", frame.data.decode("ascii", "replace"))
            elif fid == "USLT":
                add("LYRICS", frame.text)
            elif fid == "COMM" and not frame.desc:
                add("COMMENT", " ".join(frame.text))
            elif fid in ID3_FRAMES:
                for t in frame.text:
                    add(ID3_FRAMES[fid], t)
    elif isinstance(tags, APEv2):
        for k, v in tags.items():
            if isinstance(v, APETextValue):
                for t in v:
                    add(k, t)
    else:   # Vorbis comments (FLAC): list of (name, value), repeats allowed
        for k, v in tags:
            add(k, v)
    return out


def _pair(values, totals):
    """"3/12" or "3" + total -> (3, 12) for trkn/disk."""
    m = re.match(r"\s*(\d+)(?:\s*/\s*(\d+))?", (values or [""])[0])
    if not m:
        return None
    total = m.group(2) or next((t for t in (totals or []) if t.strip().isdigit()), "0")
    return int(m.group(1)), int(total)


def mp4_items(tags):
    """{VORBIS-NAME: [values]} -> {MP4 atom: value} for mutagen."""
    from mutagen.mp4 import MP4FreeForm
    out = {}
    for key, values in tags.items():
        if key in SKIP_TAGS:
            continue
        if key in MP4_ATOMS:
            out[MP4_ATOMS[key]] = values
            continue
        m = re.fullmatch(r"MUSICBRAINZ_(\w+?)ID", key)
        name = MP4_FREEFORM.get(key) or (f"MusicBrainz {m.group(1).title()} Id" if m else key)
        out[f"----:com.apple.iTunes:{name}"] = [MP4FreeForm(v.encode("utf-8")) for v in values]
    for atom, num, total in (("trkn", "TRACKNUMBER", "TRACKTOTAL"), ("disk", "DISCNUMBER", "DISCTOTAL")):
        pair = _pair(tags.get(num), tags.get(total))
        if pair:
            out[atom] = [pair]
    bpm = (tags.get("BPM") or [""])[0].split(".")[0]
    if bpm.isdigit() and int(bpm) < 65536:
        out["tmpo"] = [int(bpm)]
    if (tags.get("COMPILATION") or ["0"])[0].strip() == "1":
        out["cpil"] = True
    return out


def _cover(src, f):
    """The cover of the source as MP4Cover (for FLAC the front cover picture, otherwise the first embedded one)."""
    from mutagen.mp4 import MP4Cover
    fmt = {"image/jpeg": MP4Cover.FORMAT_JPEG, "image/jpg": MP4Cover.FORMAT_JPEG, "image/png": MP4Cover.FORMAT_PNG}
    pics = getattr(f, "pictures", None)
    if pics:
        pic = next((p for p in pics if p.type == 3), pics[0])
        return MP4Cover(pic.data, imageformat=fmt[pic.mime.lower()]) if pic.mime.lower() in fmt else None
    cover = front_cover(src)
    if not cover:
        return None
    return MP4Cover(cover[0], imageformat=MP4Cover.FORMAT_PNG if cover[1] == "image/png" else MP4Cover.FORMAT_JPEG)


def copy_tags_mp4(src, dst):
    """Tags and cover from src into the freshly created .m4a dst. -> None or an error text (then the file does not count)."""
    import mutagen
    from mutagen.mp4 import MP4
    try:
        f = mutagen.File(str(src))
        out = MP4(str(dst))
        if out.tags is None:
            out.add_tags()
        for k in list(out.tags.keys()):   # what ffmpeg entered itself (encoder) comes from the source
            if k != "©too":
                del out.tags[k]
        if isinstance(f, MP4):   # ALAC: the same fields, simply carry them over
            wanted = {k: v for k, v in (f.tags or {}).items() if k != "©too"}
        else:
            tags = source_tags(f) if f is not None else {}
            if not (tags.get("TITLE") or tags.get("ARTIST")):   # e.g. WAV with RIFF INFO, AIFF text chunks: ffmpeg reads them
                for k, v in (probe_tags(src) or {}).items():
                    key = _norm_key(k)
                    if v.strip() and key not in tags and key not in PROBE_SKIP:
                        tags[key] = [v.strip()]
            wanted = mp4_items(tags)
            cover = _cover(src, f)
            if cover:
                wanted["covr"] = [cover]
        out.tags.update(wanted)
        out.save()
        check = MP4(str(dst)).tags or {}
        for k in ("©nam", "©ART", "----:com.apple.iTunes:MusicBrainz Track Id"):   # spot check: is it really in there?
            if k in wanted and list(check.get(k) or []) != list(wanted[k]):
                return _s("tag {tag} not readable after writing", tag=k)
        return None
    except Exception as e:   # noqa: BLE001 – broken tags must not stop the run; the file does not count then
        return str(e) or type(e).__name__


# ---------------------------------------------------------------------------- Converting

def _encode_cmd(src, tmp, codec, rate):
    if codec == "aac":   # copy_tags_mp4() writes the tags; +faststart: playback can start right away
        return ["ffmpeg", "-nostdin", "-v", "error", "-y", "-i", str(src), "-map", "0:a:0", "-map_metadata", "-1",
                "-c:a", "aac", "-b:a", f"{rate}k", "-movflags", "+faststart", "-f", "ipod", str(tmp)]
    return ["ffmpeg", "-nostdin", "-v", "error", "-y", "-i", str(src), "-map", "0:a:0", "-c:a", "libopus",
            "-b:a", f"{rate}k", "-f", "opus", str(tmp)]


def convert(src, op, env, log, track=None, dry_run=False):
    """Convert one file. -> "ok" | "fehler" (with a message in the log)."""
    root = music_dir(env)
    codec, ext, name, rate = target(op)
    dst = src.with_suffix(ext)
    inplace = dst == src   # ALAC .m4a -> AAC .m4a: the new file takes the place of the original
    rel_dir = src.parent.relative_to(root)
    arch_root = archive_dir(op)
    archive = arch_root / rel_dir
    mode = op.get("original", "archive")
    owner = op.get("owner")
    log(f"• {src.relative_to(root)}")
    if inplace and mode == "keep":
        log(_s("  ✕ {format} would have the same name as the original – not possible with “keep original”. The original stays.", format=name))
        return "fehler"
    twin = _twin(src, op)
    if twin:
        log(_s("  ✕ {other} would become the same {format} file – please rename one of the two. The original stays.",
               other=twin.name, format=name))
        return "fehler"
    arch_file, archived = None, False
    if mode == "archive":
        if not arch_root.is_dir():
            log(_s("  ✕ The archive folder {path} is missing – the original stays.", path=arch_root))
            return "fehler"
        found = archive_name(src, archive / src.name)
        if found is None:
            log(_s("  ✕ {path} already exists in the archive – the original stays.", path=archive / src.name))
            return "fehler"
        arch_file, archived = found
        if not archived and arch_file.name != src.name:
            log(_s("  ⚠ A different file named {name} is already in the archive – the original goes there as {new}.",
                   name=src.name, new=arch_file.name))
    if dry_run:
        log({"archive": _s("  (dry run) → {name}, original to the archive", name=dst.name),
             "delete": _s("  (dry run) → {name}, delete original", name=dst.name),
             "keep": _s("  (dry run) → {name}", name=dst.name)}[mode])
        if not dst.exists() or inplace:
            keep_cover(src, owner, log, dry_run=True)
        return "ok"
    tmp = None
    if dst.exists() and not inplace:
        if _codec(dst) != codec:
            log(_s("  ✕ {name} already exists, but it is no {format} file – the original stays.", name=dst.name, format=name))
            return "fehler"
        if verify(src, dst, track):
            other = _archived_twin(src, archive)
            if other:
                log(_s("  ✕ {name} belongs to another original ({other} in the archive) – please rename this file, then "
                       "it is converted. The original stays.", name=dst.name, other=other.name))
            else:
                log(_s("  ✕ The existing {format} file is incomplete or does not match – please check/delete it, then it is created again.", format=name))
            return "fehler"
        log(_s("  ✓ {format} already existed (complete).", format=name))
    else:
        keep_cover(src, owner, log)
        tmp, fd = new_temp(src.parent / f"{src.name}{ext}", "encode")   # unique, a new file – never through a link
        os.close(fd)   # ffmpeg writes into it (-y)
        proc = subprocess.Popen(_encode_cmd(src, tmp, codec, rate), stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
                                stdin=subprocess.DEVNULL, text=True, errors="replace", start_new_session=True)
        if track:
            track(proc, True)
        try:
            _out, err = proc.communicate()
        finally:
            if track:
                track(proc, False)
        err = (err or "").strip()
        problem = None
        if proc.returncode != 0:
            problem = err[-300:] or _s("ffmpeg reports an error")
        elif err:   # -v error: every message is a read or decoding error – the original may be damaged
            problem = err[-300:]
        elif codec == "aac":
            problem = copy_tags_mp4(src, tmp)
        else:
            problem = embed_cover(src, tmp)
        if problem is None:
            problem = tags_lost(src, tmp) or verify(src, tmp, track)
        if problem:
            tmp.unlink(missing_ok=True)
            log(_s("  ✕ Conversion failed: {problem} – the original stays.", problem=problem))
            return "fehler"
        if not inplace:
            _place(tmp, dst, owner)
            tmp = None
        log(_s("  ✓ {format} created ({rate} kbit/s).", format=name, rate=rate))
    try:
        if mode == "archive":
            made = False
            try:
                if not archived:
                    archive_folder(arch_root, rel_dir, owner)
                    if arch_file.exists():
                        raise OSError(_s("now exists in the archive"))
                    if inplace:   # a copy into the archive first, the original stays until the new file replaces it
                        copy_to_archive(src, arch_file)
                        made = True
                    else:
                        move_to_archive(src, arch_file)
                elif not inplace:   # an identical copy is already in the archive: only remove the original here
                    _unlink(src)
            except OSError as e:
                log(_s("  ✕ The original could not be moved to the archive: {error}", error=e))
                return "fehler"
            if tmp is not None:   # ALAC -> AAC: now into the place of the original, in one step
                try:
                    _place(tmp, src, owner)
                    tmp = None
                except OSError as e:
                    if made:   # the original is still in its place – take back the copy made just now
                        arch_file.unlink(missing_ok=True)
                    log(_s("  ✕ The new file could not take the place of the original: {error} – the original stays.", error=e))
                    return "fehler"
            log(_s("  ✓ Original archived (an identical copy was already there).") if archived else _s("  ✓ Original archived."))
        elif mode == "delete":
            try:
                if tmp is not None:   # ALAC -> AAC: the new file replaces the original in one go
                    _place(tmp, src, owner)
                    tmp = None
                else:
                    _unlink(src)
            except OSError as e:
                log(_s("  ✕ The original could not be deleted: {error}", error=e))
                return "fehler"
            log(_s("  ✓ Original deleted."))
    finally:
        if tmp is not None:
            tmp.unlink(missing_ok=True)
    return "ok"


def _twin(src, op):
    """Another original in the same folder that would become the same file (Song.flac and Song.wav) or None."""
    exts = {e for f in op.get("formats", ["flac"]) for e in EXTENSIONS.get(f, ())}
    try:
        names = os.listdir(src.parent)
    except OSError:
        return None
    for n in sorted(names):
        p = src.parent / n
        if (n != src.name and not n.startswith(".") and p.stem == src.stem and p.suffix.lower() in exts
                and not (p.suffix.lower() == ".m4a" and (target(op)[0] == "aac" or _codec(p) != "alac"))):
            return p
    return None


def _archived_twin(src, archive):
    """An original with the same name but another format in the archive (it made the existing Opus/AAC file)."""
    for exts in EXTENSIONS.values():
        for e in exts:
            p = archive / f"{src.stem}{e}"
            if e != src.suffix.lower() and p.exists():
                return p
    return None


def _place(tmp, dst, owner):
    os.replace(tmp, dst)
    RECENT[str(dst)] = time.time()
    if len(RECENT) > 2000:   # only the last 24 h count (watch.py) – do not grow endlessly without the watch either
        for k in [k for k, t in list(RECENT.items()) if time.time() - t > 86400]:
            RECENT.pop(k, None)
    _own(dst, owner, 0o644)


def run(cfg, log=print, stop=None, track=None, dry_run=False, files=None):
    """files: only these files (folder watch) instead of all files to convert in the music folder."""
    op = cfg["settings"].get("opus") or {}
    if not op.get("enabled", True):
        log(_s("Conversion is turned off in the settings."))
        return {"converted": 0, "errors": 0, "skipped": True}
    missing = [k for k, v in tools().items() if not v]
    if missing:
        raise RuntimeError(_s("{tools} missing – please install (included in the Docker image).", tools=", ".join(missing)))
    if target(op)[0] == "aac" and not mp4_available():
        raise RuntimeError(_s("AAC needs the package mutagen (it carries the tags over) – included in the Docker image."))
    env = load_env()
    if not music_dir(env).exists():
        raise RuntimeError(_s("Music folder {path} not found", path=music_dir(env)))
    _albums.clear()
    if files is None:
        files = find_sources(op, env)
    else:   # only matching formats that are still there (ALAC rather than AAC; with "keep" not converted yet)
        exts = tuple(e for f in op.get("formats", ["flac"]) for e in EXTENSIONS.get(f, ()))
        files = sorted(f for f in files if f.name.lower().endswith(exts) and f.exists()
                       and not (f.suffix.lower() == ".m4a" and _codec(f) != "alac")
                       and not _keep_skips(f, op))
    if files and op.get("original", "archive") == "archive":   # before converting anything: otherwise every song
        problem = archive_problem(music_dir(env), archive_dir(op), write_test=not dry_run)   # would exist twice
        if problem:
            raise RuntimeError(problem)
    formats = ", ".join(f.upper() for f in op.get("formats", ["flac"]))
    codec, _, name, rate = target(op)
    original = {"archive": _s("to the archive"), "keep": _s("keep"), "delete": _s("delete")}[op.get("original", "archive")]
    log(_s("{n} file(s) to convert ({formats} → {format} {rate} kbit/s, original: {original}).",
           n=len(files), formats=formats, format=name, rate=rate, original=original))
    ok = failed = 0
    progress.part("flac", len(files))

    def one(path):
        if stop is not None and stop.is_set():
            return "stop"
        try:
            return convert(path, op, env, log, track, dry_run)
        except Exception as e:   # one file must not hold up the rest
            log(f"  ✕ {path.name}: {e}")
            return "fehler"

    with ThreadPoolExecutor(max_workers=max(1, int(op.get("jobs") or 1))) as pool:
        for k, res in enumerate(pool.map(one, files), 1):
            ok += res == "ok"
            failed += res == "fehler"
            progress.at(k)
    _pending_cache["key"] = None
    log(_s("Done: {ok} converted, {failed} errors.", ok=ok, failed=failed))
    return {"converted": ok, "errors": failed}
