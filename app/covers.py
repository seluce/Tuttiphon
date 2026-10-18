"""Design playlist covers (Pillow) and upload them to Navidrome.

Styles: "mosaik" (4 album covers + title), "band" (band photo + title), "farbe" (gradient, title, band photos).
Without Pillow only "album" (the cover of the most important album as it is) and custom images work.
Custom images ("eigenes") are also kept in state/eigene-cover/ – if Navidrome creates the playlist anew (season pause,
trash and back), refresh_auto() uploads them again.
"""
import hashlib
import io
import os
import re

from . import images, rules
from .config import STATE_DIR, load_config, write_atomic
from .i18n import N_, _, _s

OWN_DIR = STATE_DIR / "eigene-cover"

STYLES = {"mosaik": N_("Mosaic of album covers"), "band": N_("Band photo"), "farbe": N_("Gradient with band photos"),
          "album": N_("Album cover")}
SIZE = 600
FONTS = ["/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", "/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf",
         "/usr/share/fonts/TTF/DejaVuSans-Bold.ttf"]

try:
    from PIL import Image, ImageDraw, ImageFilter, ImageFont
    HAVE_PIL = True
except ImportError:   # container without Pillow: only "album" and custom images
    HAVE_PIL = False


def available_styles():
    return {k: _(v) for k, v in STYLES.items() if HAVE_PIL or k == "album"}   # i18n-ignore


def _font(size):
    for f in FONTS:
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


def signature(cfg, lib, playlist):
    """Changes when the cover material changes (for automatic renewal)."""
    pv = rules.preview(cfg, lib, playlist, sample=1)
    raw = "|".join(pv["covers"] + [str(a[2]) for a in pv["topArtists"][:4]] + [pv["name"], str(pv.get("color"))])
    return hashlib.sha1(raw.encode()).hexdigest()[:12]


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


def upload(native, navidrome_id, data, ctype=None):
    ctype = sniff(data)
    if not ctype:
        raise ValueError(_("This is not a JPG, PNG or WebP image."))
    ext = {"image/png": "png", "image/webp": "webp"}.get(ctype, "jpg")
    native.upload_playlist_image(navidrome_id, data, filename=f"cover.{ext}", ctype=ctype)


def refresh_auto(cfg, lib, native, by_file, log=print):
    """Renew designed covers whose material has changed (e.g. a Daily Mix with a new selection)."""
    changed = 0
    for p in cfg["playlists"]:
        cv = p.get("cover") or {}
        if p.get("status", "aktiv") == "aktiv" and cv.get("style") == "eigenes":
            changed += _restore_own(p, cv, by_file.get(p.get("file") or ""), native, log)
            continue
        if p.get("status", "aktiv") != "aktiv" or cv.get("style") not in available_styles():
            continue
        np = by_file.get(p.get("file") or "")
        if not np:
            continue
        try:
            sig = signature(cfg, lib, p)
            if sig == cv.get("sig") and cv.get("nid", np["id"]) == np["id"]:
                continue   # unchanged (and Navidrome has not created the playlist anew)
            fresh = next((x for x in load_config()["playlists"] if x["id"] == p["id"]), {})
            if (fresh.get("cover") or {}).get("style") != cv["style"]:
                continue   # another cover was chosen in the meantime
            upload(native, np["id"], render(cfg, lib, p, cv["style"]))
            cv["sig"], cv["nid"] = sig, np["id"]
            changed += 1
            log(_s("  🖼 Cover renewed: {name}", name=np.get('name')))
        except Exception as e:   # a cover must not stop the run
            log(_s("  ⚠ Cover for {name}: {error}", name=np.get('name'), error=e))
    try:   # clear away images of deleted playlists (freshly loaded, nothing just uploaded)
        import time
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
