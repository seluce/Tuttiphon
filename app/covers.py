"""Design playlist covers (Pillow) and upload them to Navidrome.

Styles: "mosaik" (4 album covers + title), "band" (band photo + title), "farbe" (gradient, title, band photos),
"format" (the cover of a format such as “Discovered”, “Album of the week” or “Good morning”: its color, its name and a
few album covers – the formats get it by themselves, default_style()).
Without Pillow only "album" (the cover of the most important album as it is) and custom images work.
Custom images ("eigenes") are also kept in state/eigene-cover/ – if Navidrome creates the playlist anew (season pause,
trash and back), refresh_auto() uploads them again.
"""
import datetime as dt
import hashlib
import io
import os
import re
import time

from . import images, rules
from .config import STATE_DIR, load_config, write_atomic
from .i18n import N_, _, _s

OWN_DIR = STATE_DIR / "eigene-cover"

STYLES = {"format": N_("Cover of the format"), "mosaik": N_("Mosaic of album covers"), "band": N_("Band photo"),
          "farbe": N_("Gradient with band photos"), "album": N_("Album cover")}
SIZE = 600
FONTS = ["/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", "/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf",
         "/usr/share/fonts/TTF/DejaVuSans-Bold.ttf"]

try:
    from PIL import Image, ImageDraw, ImageFilter, ImageFont
    HAVE_PIL = True
except ImportError:   # container without Pillow: only "album" and custom images
    HAVE_PIL = False


def available_styles(playlist=None):
    """Designed styles here (without Pillow only the album cover) – for a given playlist the format cover only if it is
    a format."""
    return {k: _(v) for k, v in STYLES.items() if (HAVE_PIL or k == "album")   # i18n-ignore
            and (k != "format" or playlist is None or format_kind(playlist))}


def _font(size, bold=True):
    for f in (FONTS if bold else [x.replace("-Bold", "") for x in FONTS]):
        if os.path.exists(f):
            return ImageFont.truetype(f, size)
    try:
        return ImageFont.load_default(size=size)   # Pillow ≥ 10.1
    except TypeError:
        return ImageFont.load_default()


def _img(cover_id, size=SIZE):
    res = images.get_image(cover_id, 600) if cover_id else None
    if not res:
        return None
    try:
        im = Image.open(io.BytesIO(res[0])).convert("RGB")
    except Exception:   # broken image -> just leave it out
        return None
    w, h = im.size
    s = min(w, h)
    return im.crop(((w - s) // 2, (h - s) // 2, (w + s) // 2, (h + s) // 2)).resize((size, size), Image.LANCZOS)


def _hex(c, fallback=(124, 58, 237)):
    try:
        c = c.lstrip("#")
        return tuple(int(c[i:i + 2], 16) for i in (0, 2, 4))
    except (AttributeError, ValueError):
        return fallback


def _mix(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def _clean(text):
    # the font has no emojis etc. -> remove them (incl. variation selectors/joiners, otherwise boxes remain)
    return re.sub(r"[\U00010000-\U0010FFFF☀-➿⬀-⯿\uFE00-\uFE0F\u200D\u20E3]", "", text or "").strip()


def _gradient(size, top, bottom):
    g = Image.new("RGB", (1, 256))
    for y in range(256):
        g.putpixel((0, y), _mix(top, bottom, y / 255))
    return g.resize(size)


def _shade(im, strength=0.85):
    """Dark gradient at the bottom so white text stays readable."""
    w, h = im.size
    mask = Image.new("L", (1, 256))
    for y in range(256):
        mask.putpixel((0, y), int(255 * strength * min(1, max(0, (y - 70) / 150)) ** 1.25))
    im.paste(Image.new("RGB", (w, h), (8, 8, 14)), (0, 0), mask.resize((w, h)))
    return im


def _wrap(draw, text, font, width, max_lines=3):
    words, lines, line = text.split(), [], ""
    for w in words:
        test = f"{line} {w}".strip()
        if draw.textlength(test, font=font) <= width:
            line = test
        else:
            if line:
                lines.append(line)
            line = w
    if line:
        lines.append(line)
    return lines[:max_lines]


def _fit_parts(draw, text, font, width):
    """Shorten "A · B · C" until it fits: drop the last parts, if need be cut the first name."""
    parts = [_clean(x).upper() for x in text.split(" · ") if _clean(x)]
    fits = lambda t: draw.textlength(t, font=font) <= width  # noqa: E731
    out = []
    for part in parts:
        short = re.split(r",| & | UND | FEAT\.? | FT\. | X ", part)[0].strip()   # i18n-ignore: "Rolf Zuckowski und seine Freunde" -> "Rolf Zuckowski"
        for cand in (part, short):
            if fits(" · ".join(out + [cand])):
                break
        else:
            cand = None
        if cand:
            out.append(cand)
            continue
        part = short
        if not out or out[0] in ("DAILY MIX", "WEEKLY MIX", "MONTHLY MIX") and len(out) == 1:   # no band name yet -> shorten letter by letter
            while part and not fits(" · ".join(out + [part + " …"])):
                part = part[:-1].rstrip()
            if part:
                out.append(part + " …")
        break
    return " · ".join(out)


def _title(im, title, subtitle, at_bottom=True):
    draw = ImageDraw.Draw(im)
    title = _clean(title)
    for size in (64, 56, 48, 42, 36, 30):
        font = _font(size)
        lines = _wrap(draw, title, font, SIZE - 72)
        if len(lines) <= 3 and all(draw.textlength(line, font=font) <= SIZE - 72 for line in lines):
            break
    sub_font = _font(24)
    line_h = int(size * 1.12)
    block = len(lines) * line_h + (40 if subtitle else 0)
    y = SIZE - 40 - block if at_bottom else 48
    if subtitle:
        draw.text((36, y), _fit_parts(draw, subtitle, sub_font, SIZE - 72), font=sub_font, fill=(232, 232, 240))
        y += 40
    for line in lines:
        draw.text((36, y), line, font=font, fill=(255, 255, 255))
        y += line_h
    return im


def _circle(im, size):
    im = im.resize((size, size), Image.LANCZOS)
    mask = Image.new("L", (size * 4, size * 4), 0)
    ImageDraw.Draw(mask).ellipse((0, 0, size * 4, size * 4), fill=255)
    return im, mask.resize((size, size), Image.LANCZOS)


def render(cfg, lib, playlist, style):
    """-> JPEG-Bytes"""
    pv = rules.preview(cfg, lib, playlist, sample=1)
    covers, color = pv["covers"], _hex(pv.get("color"))
    artists = [a for a in pv["topArtists"] if a[2]]
    person = rules.person_of(cfg, playlist)
    names = [a[0] for a in pv["topArtists"][:3]]
    from .mixer import label
    mixname = label(playlist) if rules.is_mix(playlist) else ""
    subtitle = (f"{mixname} · " if mixname else "") + " · ".join(names)
    prefix = (person or {}).get("prefix") or ""
    title = pv["name"][len(prefix):].strip(" ·:-") if prefix and pv["name"].startswith(prefix) else pv["name"]
    title = title or pv["name"]
    if rules.is_mix(playlist):
        title = title.replace(f"{mixname} · ", "")

    if style == "format" and HAVE_PIL:
        kind = format_kind(playlist) or "sound"
        im = _format_cover(cfg, lib, playlist, pv, format_title(cfg, playlist, title), kind)
        out = io.BytesIO()
        im.save(out, "JPEG", quality=90, optimize=True)
        return out.getvalue()

    if style == "album" or not HAVE_PIL:
        res = images.get_image(covers[0], 600) if covers else None
        if not res:
            raise ValueError(_("This playlist has no album cover that can be used."))
        return res[0]

    if style == "mosaik":
        tiles = [t for t in (_img(c, SIZE // 2) for c in covers[:4]) if t]
        im = _gradient((SIZE, SIZE), _mix(color, (255, 255, 255), .15), _mix(color, (0, 0, 0), .6))
        if len(tiles) >= 4:
            for k, t in enumerate(tiles[:4]):
                im.paste(t, ((k % 2) * SIZE // 2, (k // 2) * SIZE // 2))
        elif tiles:
            im = _img(covers[0]) or im
        _title(_shade(im, .93), title, subtitle)
    elif style == "band":
        photo = _img(f"ar-{artists[0][2]}") if artists else None
        im = photo or _gradient((SIZE, SIZE), color, _mix(color, (0, 0, 0), .7))
        tint = Image.new("RGB", (SIZE, SIZE), color)
        im = Image.blend(im, tint, .22)
        _title(_shade(im, .9), title, subtitle)
    else:   # farbe
        im = _gradient((SIZE, SIZE), _mix(color, (12, 8, 28), .35), _mix(color, (10, 5, 30), .82))
        glow = Image.new("RGB", (SIZE, SIZE), _mix(color, (255, 80, 200), .45)).filter(ImageFilter.GaussianBlur(4))
        mask = Image.new("L", (SIZE, SIZE), 0)
        ImageDraw.Draw(mask).ellipse((SIZE * .35, -SIZE * .25, SIZE * 1.25, SIZE * .65), fill=120)
        im.paste(glow, (0, 0), mask.filter(ImageFilter.GaussianBlur(60)))
        x = 36
        for _name, _plays, aid_ in artists[:4]:
            photo = _img(f"ar-{aid_}", 150)
            if photo:
                # white ring so overlapping photos stand apart
                ring = Image.new("RGB", (124, 124), (255, 255, 255))
                _ring, rm = _circle(ring, 124)
                im.paste(ring, (x - 4, SIZE - 160), rm)
                c, m = _circle(photo, 116)
                im.paste(c, (x, SIZE - 156), m)
                x += 100
        _title(im, title, subtitle, at_bottom=False)
    out = io.BytesIO()
    im.save(out, "JPEG", quality=88, optimize=True)
    return out.getvalue()


# Covers of the formats: colors (top, bottom) – each format looks the same every week, recognizable in Symfonium
FORMAT_COLORS = {
    "unheard": ((49, 46, 129), (139, 92, 246)),     # indigo → violet: discovered
    "album": ((17, 17, 27), (64, 56, 84)),          # dark – the album itself is the picture
    "morning": ((251, 146, 60), (219, 39, 119)),    # sunrise
    "sound": ((13, 148, 136), (67, 56, 202)),       # teal → indigo
    "fav": ((219, 39, 119), (234, 88, 12)),         # magenta → orange
    "review": ((21, 128, 61), (13, 116, 144)),      # green → petrol
    "together": ((190, 18, 60), (126, 34, 206)),    # red → purple
    "rediscover": ((180, 83, 9), (88, 28, 135)),    # amber → plum
}


def format_kind(playlist):
    """Which format a playlist is (a key of FORMAT_COLORS) – None for an ordinary playlist."""
    if playlist.get("album"):
        return "album"
    if playlist.get("unheard"):
        return "unheard"
    if playlist.get("daytime") == "morning":
        return "morning"
    if playlist.get("review"):
        return "review"
    whole = playlist.get("welt", rules.ALL) == rules.ALL   # per world (car ride, a world's favorites) the name counts
    if playlist.get("together") and whole:
        return "together"
    if playlist.get("fav") and whole:
        return "fav"
    if playlist.get("type") == "mix" and (playlist.get("mix") or {}).get("flavor") == "geschmack":
        return "sound"
    if playlist.get("stil") == "wiederentdecken" and playlist.get("welt") == rules.ALL:   # per world: the world's name counts
        return "rediscover"
    return None


def default_style(playlist):
    """The cover a playlist gets without a choice of its own: the formats their format cover, others none."""
    return "format" if HAVE_PIL and format_kind(playlist) else None


def _rounded(im, radius):
    mask = Image.new("L", (im.width * 3, im.height * 3), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, im.width * 3 - 1, im.height * 3 - 1), radius * 3, fill=255)
    return mask.resize(im.size, Image.LANCZOS)


def _shadow_paste(base, im, xy, radius=18, blur=18, strength=150):
    """Paste with rounded corners and a soft shadow below."""
    x, y = xy
    shadow = Image.new("L", base.size, 0)
    ImageDraw.Draw(shadow).rounded_rectangle((x + 6, y + 14, x + im.width + 6, y + im.height + 14), radius, fill=strength)
    base.paste(Image.new("RGB", base.size, (6, 4, 16)), (0, 0), shadow.filter(ImageFilter.GaussianBlur(blur)))
    base.paste(im, (x, y), _rounded(im, radius))


def _format_cover(cfg, lib, playlist, pv, title, kind):
    """The cover of a format: its gradient, the wordmark, album covers (the album of the week big), its name, for whom
    and how often it is new."""
    top, bottom = FORMAT_COLORS[kind]
    im = _gradient((SIZE, SIZE), top, bottom)
    glow = Image.new("L", (SIZE, SIZE), 0)
    ImageDraw.Draw(glow).ellipse((SIZE * .3, -SIZE * .35, SIZE * 1.3, SIZE * .6), fill=110)
    im.paste(Image.new("RGB", (SIZE, SIZE), _mix(top, (255, 255, 255), .35)), (0, 0), glow.filter(ImageFilter.GaussianBlur(70)))
    draw = ImageDraw.Draw(im)
    if kind == "morning":   # a sun rising behind the covers
        sun = Image.new("L", (SIZE, SIZE), 0)
        ImageDraw.Draw(sun).ellipse((SIZE * .44, SIZE * .06, SIZE * .96, SIZE * .58), fill=235)
        im.paste(Image.new("RGB", (SIZE, SIZE), (255, 214, 102)), (0, 0), sun.filter(ImageFilter.GaussianBlur(3)))
    mark = _font(17)
    x = 36
    for ch in "TUTTIPHON":   # wordmark, letter-spaced
        draw.text((x, 34), ch, font=mark, fill=_mix(top, (255, 255, 255), .78))
        x += draw.textlength(ch, font=mark) + 4
    covers = pv["covers"]
    person = rules.person_of(cfg, playlist)
    who = _s("for {name}", name=person["name"]) if person and person["id"] != cfg["settings"].get("defaultPerson") else ""
    if kind == "album" and pv["topArtists"]:
        song = (pv.get("sample") or [{}])[0]
        detail = " – ".join(x for x in (pv["topArtists"][0][0], song.get("album")) if x)
    else:
        detail = who
    from .mixer import options
    if kind == "morning":
        rhythm = _s("{n} minutes every morning", n=options(playlist).get("minutes") or 30)
    elif rules.is_mix(playlist):   # how often it is new
        rhythm = {"day": _s("new every day"), "week": _s("new every Monday"),
                  "month": _s("new every month")}.get(options(playlist).get("every"), "")
    else:
        rhythm = ""
    if kind == "album" and who:
        rhythm = f"{who} · {rhythm}" if rhythm else who
    # name: as big as fits in at most two lines, bottom left; above it the details, below the rhythm
    title = _clean(title)
    for size in (84, 74, 64, 56, 48, 42):
        font = _font(size)
        lines = _wrap(draw, title, font, SIZE - 72, max_lines=3)
        if len(lines) <= 2 and all(draw.textlength(line, font=font) <= SIZE - 72 for line in lines):
            break
    small, tiny = _font(26, bold=False), _font(19)
    text_top = SIZE - 42 - (28 if rhythm else 0) - len(lines) * int(size * 1.04) - (38 if detail else 0)
    if kind == "album" and covers:   # the album itself, as big as fits above the text
        side = max(170, min(330, text_top - 74 - 18))
        art = _img(covers[0], side)
        if art:
            _shadow_paste(im, art, (SIZE - side - 40, 70), radius=16)
    else:
        tiles = [t for t in (_img(c, 150) for c in covers[:3]) if t]
        for k, t in enumerate(reversed(tiles)):   # a fanned row at the top right, the first one in front
            _shadow_paste(im, t, (SIZE - 40 - 150 - (len(tiles) - 1 - k) * 74, 86 + (len(tiles) - 1 - k) * 18), radius=14,
                          blur=12, strength=120)
    y = text_top
    if detail:
        detail = _clean(detail)
        while detail and draw.textlength(detail, font=small) > SIZE - 72:   # too long: shorten with “…”
            detail = detail[:-2].rstrip() + "…"
        draw.text((36, y), detail, font=small, fill=(240, 236, 250))
        y += 38
    for line in lines:
        draw.text((36, y), line, font=font, fill=(255, 255, 255))
        y += int(size * 1.04)
    if rhythm:
        draw.text((36, y + 6), _clean(rhythm).upper(), font=tiny, fill=_mix(bottom, (255, 255, 255), .72))
    return im


def format_title(cfg, playlist, name):
    """The big name on a format cover – the format, not the person (that goes below)."""
    kind = format_kind(playlist)
    titles = {"unheard": _s("Discovered"), "album": _s("Album of the week"), "morning": _s("Good morning"),
              "fav": _s("New from favorite bands"), "together": _s("What everyone likes")}
    if kind in titles:
        return titles[kind]
    if kind == "rediscover":
        st = next((x for x in cfg["stile"] if x["id"] == "wiederentdecken"), {})
        return st.get("name") or name
    return name   # own sound, your month: the name says it already


def signature(cfg, lib, playlist, style=None):
    """Changes when the cover material changes (for automatic renewal) – for the format cover also its texts (language,
    for whom, rhythm)."""
    pv = rules.preview(cfg, lib, playlist, sample=1)
    parts = pv["covers"] + [str(a[2]) for a in pv["topArtists"][:4]] + [pv["name"], str(pv.get("color"))]
    if style == "format":
        from .mixer import options
        o = options(playlist)
        parts += [str(x) for x in (format_kind(playlist), format_title(cfg, playlist, pv["name"]),
                                   (rules.person_of(cfg, playlist) or {}).get("name"), cfg["settings"].get("defaultPerson"),
                                   o.get("minutes"), o.get("every"), _s("new every day"))]
    return hashlib.sha1("|".join(parts).encode()).hexdigest()[:12]


def image_name(native, navidrome_id):
    """The image Navidrome reports for a playlist (uploadedImage) – None if it does not report the field."""
    np = next((x for x in native.playlists() if x.get("id") == navidrome_id), None)
    return np.get("uploadedImage") or "" if np is not None and "uploadedImage" in np else None


def sniff(data):
    """Detect the image type from the first bytes – only JPEG, PNG, WebP (no SVG or the like)."""
    if data[:3] == b"\xff\xd8\xff":
        return "image/jpeg"
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    return None


def _own_file(pid):
    return OWN_DIR / f"{pid}.img" if re.fullmatch(r"[A-Za-z0-9_-]{1,80}", pid or "") else None


def keep_own(pid, data):
    """Keep a playlist's custom image (to upload it again)."""
    path = _own_file(pid)
    if path:
        OWN_DIR.mkdir(parents=True, exist_ok=True)
        write_atomic(path, data)


def forget_own(pid):
    path = _own_file(pid)
    if path:
        path.unlink(missing_ok=True)


def digest(data):
    """A short checksum of an uploaded image (cover.hash) – to recognize it again in Navidrome."""
    return hashlib.sha256(data).hexdigest()[:16]


def served_digest(native, navidrome_id, data):
    """The checksum of the image as Navidrome serves it right after an upload – the same as `data` unless Navidrome
    changes uploaded images; if it cannot be fetched, that of `data`."""
    try:
        return digest(native.playlist_image(navidrome_id))
    except Exception:   # noqa: BLE001 – the uploaded data is the best guess then
        return digest(data)


def set_by_hand(native, cv, np):
    """Is the image in Navidrome no longer the one Tuttiphon uploaded? Navidrome names the file after the playlist
    (<id>_<name>.<type>), so an image of the same type set there by hand keeps the name – its content tells (Navidrome
    serves the uploaded file as it is). Unknown (uploaded before checksums were kept, Navidrome briefly gone): no."""
    if not cv.get("hash") or cv.get("nid") != np["id"] or not np.get("uploadedImage"):
        return False
    try:
        return digest(native.playlist_image(np["id"])) != cv["hash"]
    except Exception:   # noqa: BLE001 – unknown: renew as before
        return False


def upload(native, navidrome_id, data, ctype=None):
    ctype = sniff(data)
    if not ctype:
        raise ValueError(_("This is not a JPG, PNG or WebP image."))
    ext = {"image/png": "png", "image/webp": "webp"}.get(ctype, "jpg")
    native.upload_playlist_image(navidrome_id, data, filename=f"cover.{ext}", ctype=ctype)


def refresh_auto(cfg, lib, native, by_file, log=print, dropped=None):
    """Renew designed covers whose material has changed (e.g. a Daily Mix with a new selection). A format without a
    cover (default_style) gets its format cover – unless it has an image in Navidrome already; it is then noted in the
    playlist as {"style": "format", "auto": true}. Removing it leaves {"style": "none"}: it does not come back.
    After an upload the image Navidrome reports and the checksum of the image are kept (cover.img, cover.hash): if
    Navidrome later reports another name – or, before a renewal, serves another image (set_by_hand()) – it was set
    there by hand and stays ({"style": "navidrome"}); none at all: it was removed there ("none"). A format cover on a
    playlist that is no longer a format goes again (its id into `dropped`)."""
    changed = 0
    uploaded = []
    today = dt.date.today().isoformat()
    for p in cfg["playlists"]:
        cv = p.get("cover") or {}
        np = by_file.get(p.get("file") or "")
        if p.get("status", "aktiv") != "aktiv" or not np:
            continue
        if cv.get("style") == "eigenes":
            changed += _restore_own(p, cv, np, native, log)
            continue
        if cv.get("style") == "navidrome" and cv.get("nid") and cv["nid"] != np["id"]:
            p.pop("cover", None)   # Navidrome created the playlist anew: the image set there is gone with it
            cv = {}
            changed += 1
        if cv.get("style") in STYLES and cv.get("img") and cv.get("nid") == np["id"] \
                and np.get("uploadedImage", cv["img"]) != cv["img"]:   # changed in Navidrome itself: it stays
            p["cover"] = {"style": "navidrome" if np.get("uploadedImage") else "none", "at": today,
                          "rev": int(time.time()), "nid": np["id"]}
            changed += 1
            log(_s("  🖼 Cover changed in Navidrome – it stays: {name}", name=np.get("name")))
            continue
        if cv.get("style") == "format" and not format_kind(p):   # no longer a format: its cover goes again
            try:
                native.delete_playlist_image(np["id"])
            except Exception:   # noqa: BLE001 – a cover must not stop the run
                pass
            p.pop("cover", None)
            if dropped is not None:
                dropped.add(p["id"])
            changed += 1
            continue
        style = cv.get("style") or (default_style(p) if not np.get("uploadedImage") else None)
        if style not in available_styles():
            continue
        try:
            sig = signature(cfg, lib, p, style)
            if sig == cv.get("sig") and cv.get("nid", np["id"]) == np["id"]:
                continue   # unchanged (and Navidrome has not created the playlist anew)
            fresh = next((x for x in load_config()["playlists"] if x["id"] == p["id"]), None)
            if fresh is None or (fresh.get("cover") or {}).get("style") != cv.get("style"):
                continue   # deleted, or another cover was chosen in the meantime
            if set_by_hand(native, cv, np):   # the same name, another image: set in Navidrome itself – it stays
                p["cover"] = {"style": "navidrome", "at": today, "rev": int(time.time()), "nid": np["id"]}
                changed += 1
                log(_s("  🖼 Cover changed in Navidrome – it stays: {name}", name=np.get("name")))
                continue
            data = render(cfg, lib, p, style)
            upload(native, np["id"], data)
            if not cv:   # the format's own cover, the first time
                cv = p["cover"] = {"style": style, "auto": True, "at": today}
            cv["sig"], cv["nid"], cv["hash"] = sig, np["id"], served_digest(native, np["id"], data)
            cv.pop("img", None)
            uploaded.append(cv)
            changed += 1
            log(_s("  🖼 Cover renewed: {name}", name=np.get('name')))
        except Exception as e:   # a cover must not stop the run
            log(_s("  ⚠ Cover for {name}: {error}", name=np.get('name'), error=e))
    if uploaded:   # what Navidrome reports now – to notice later when the image is changed there by hand
        try:
            now = {x.get("id"): x for x in native.playlists()}
            for cv in uploaded:
                img = (now.get(cv["nid"]) or {}).get("uploadedImage")
                if img:
                    cv["img"] = img
        except Exception:   # noqa: BLE001 – without it the image is only not recognized as changed by hand
            pass
    try:   # clear away images of deleted playlists (freshly loaded, nothing just uploaded)
        keep = {p["id"] for p in load_config()["playlists"] if (p.get("cover") or {}).get("style") == "eigenes"}
        for f in OWN_DIR.glob("*.img"):
            if f.stem not in keep and time.time() - f.stat().st_mtime > 3600:
                f.unlink(missing_ok=True)
    except (OSError, ValueError):
        pass
    return changed


def _restore_own(p, cv, np, native, log):
    """Upload the custom image again when Navidrome has created the playlist anew (other ID). -> 1/0"""
    if not np or cv.get("nid") == np["id"]:
        return 0
    path = _own_file(p["id"])
    if not cv.get("nid") or not path or not path.exists():   # older image without a copy: only remember the ID
        cv["nid"] = np["id"]
        return 1
    try:
        upload(native, np["id"], path.read_bytes())
    except Exception as e:   # noqa: BLE001 – a cover must not stop the run
        log(_s("  ⚠ Custom cover for {name}: {error}", name=np.get('name'), error=e))
        return 0
    cv["nid"] = np["id"]
    log(_s("  🖼 Custom cover uploaded again: {name}", name=np.get('name')))
    return 1
