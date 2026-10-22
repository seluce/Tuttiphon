"""Life cycle of the playlists: write .nsp, sync with Navidrome, take over, back up.

Principles
  * Every playlist keeps its file (field "file"). Navidrome recognizes playlists by their file path – so the
    playlist stays the same in Navidrome/Symfonium, even when its name or rules change.
  * Navidrome reads name, comment, visibility and owner from the file only on the first import.
    After that the tool sets them through the Navidrome API (sync_navidrome).
  * Nothing simply disappears: pausing/deleting removes the playlist from Navidrome, the definition
    stays in the tool. Handmade files that are taken over are copied to backup/ first.
"""
import datetime as dt
import json
import os
import random
import re
import shutil

from . import mixer, rules
from .config import (BACKUP_DIR, MARKER, STATE_DIR, load_config, paths, plain_playlist_file, read_text, slug,
                     write_atomic)
from .i18n import N_, _, _s
from .navidrome import Navidrome, NavidromeError, native_session

MANAGED_FILE = STATE_DIR / "managed_playlists.json"
# Month abbreviations for names of saved mixes (translated where used)
MONTHS = [N_("Jan"), N_("Feb"), N_("Mar"), N_("Apr"), N_("May"), N_("Jun"), N_("Jul"), N_("Aug"), N_("Sep"),
          N_("Oct"), N_("Nov"), N_("Dec")]


DEFAULT_PLAYLIST_DIR = "00_SmartPlaylists"


def playlist_dir(cfg):
    """Playlist folder – always inside the music folder (Navidrome only reads playlists there; a bent value must not
    write anywhere else)."""
    p = paths(cfg)
    music, path = p["music"].resolve(), p["playlists"].resolve()
    if path == music or music in path.parents:
        return path
    return p["music"] / DEFAULT_PLAYLIST_DIR


def _safe_filename(name):
    name = re.sub(r'[\\/:*?"<>|\x00-\x1f\x7f]+', "-", name).strip().lstrip(".")
    while len(name.encode("utf-8")) > 180:   # file names may have at most 255 bytes (including additions)
        name = name[:-1]
    return name.rstrip(" .") or "Playlist"


def read_nsp(path):
    text = read_text(path)
    text = re.sub(r"^\s*//.*$", "", text, flags=re.M)   # Navidrome allows // comments
    return json.loads(text)


def load_managed():
    try:
        data = json.loads(read_text(MANAGED_FILE))
    except (FileNotFoundError, ValueError):
        data = {}
    if "current" not in data:   # old format {file: name}
        data = {"current": {f: None for f in data}, "ever": sorted(data)}
    return data


def save_managed(data):
    write_atomic(MANAGED_FILE, json.dumps(data, ensure_ascii=False, indent=2))


def owned_files(cfg):
    managed = load_managed()
    files = set(managed["current"]) | set(managed["ever"])
    files |= {p["file"] for p in cfg["playlists"] if p.get("file")}
    return files


# --------------------------------------------------------------------------- handmade playlists

def handmade(cfg):
    """.nsp files in the playlist folder that Tuttiphon does not manage (yet)."""
    folder = playlist_dir(cfg)
    if not folder.exists():
        return []
    taken = owned_files(cfg)
    out = []
    for path in sorted(folder.glob("*.nsp")):
        if path.name in taken:
            continue
        try:
            data = read_nsp(path)
        except Exception:   # broken or unreadable: show it anyway, but derive nothing from it
            data = {}
        if not isinstance(data, dict):
            data = {}
        if str(data.get("comment", "")).startswith(MARKER):
            continue
        out.append({"file": path.name, "name": data.get("name", path.stem), "nsp": data})
    return out


def _rule_values(node, op, field):
    out = []
    if isinstance(node, dict):
        for k, v in node.items():
            if k in ("all", "any"):
                for child in v:
                    out += _rule_values(child, op, field)
            elif k == op and isinstance(v, dict) and field in v:
                out.append(v[field])
    return out


def guess_mapping(cfg, nsp):
    """Map handmade rules to a music world × vibe (for "switch to the builder")."""
    artists = set(_rule_values(nsp, "is", "artist"))
    genres = {g.lower() for g in _rule_values(nsp, "is", "genre") + _rule_values(nsp, "contains", "genre")}
    albums = " ".join(_rule_values(nsp, "contains", "album")).lower()
    name = str(nsp.get("name", "")).lower()
    welt, best = "*", 0.0
    if artists:
        for w in cfg["welten"]:
            mine = set(w.get("artists", []))
            score = len(artists & mine) / max(1, len(artists))
            if score > best:
                welt, best = w["id"], score
        if best < 0.5:
            return None
    stil = "*"
    for s in cfg["stile"]:
        if s.get("kind") == "season":
            continue
        if s["name"].lower() in name or (s.get("albums") and any(k.lower() in albums for k in s["albums"])
                                         and s.get("excludeElsewhere", {}).get("albums")):
            stil = s["id"]
            break
    if genres and stil == "*":
        best = 0
        for s in cfg["stile"]:
            sg = {g.lower() for g in s.get("genres", [])}
            score = len(genres & sg) / max(1, len(genres))
            if score > best:
                stil, best = s["id"], score
        if best < 0.5:
            stil = "*"
    if welt == "*" and stil == "*":
        return None
    gt = _rule_values(nsp, "gt", "rating")
    mapping = {"welt": welt, "stil": stil}
    if gt:
        mapping["minRating"] = int(max(gt)) + 1
    return mapping


def takeover_preview(cfg, file, lib):
    hm = next((h for h in handmade(cfg) if h["file"] == file), None)
    if not hm:
        raise ValueError(_("{file} is not a handmade playlist (any more)", file=file))
    nsp = hm["nsp"]
    try:
        original = len(lib.match(nsp)) if ("all" in nsp or "any" in nsp) else 0
    except (ValueError, KeyError, TypeError):   # rules the tool cannot recompute
        original = None
    mapping = guess_mapping(cfg, nsp)
    out = {"file": file, "name": hm["name"], "originalCount": original, "limit": nsp.get("limit"), "mapping": None}
    if mapping:
        p = {"person": None, "name": hm["name"], **mapping}   # neutral: nobody's dislikes
        out["mapping"] = {**mapping, "count": rules.count(cfg, lib, p, rules.BuildContext(lib)),
                          "describe": rules.describe(cfg, p)}
    return out


def takeover(cfg, file, mode, lib=None, person=None):
    """Take a handmade .nsp over into the tool for `person` (an id). File & Navidrome playlist stay the same."""
    hm = next((h for h in handmade(cfg) if h["file"] == file), None)
    if not hm:
        raise ValueError(_("{file} is not a handmade playlist (any more)", file=file))
    if not any(x["id"] == person for x in cfg["personen"]):
        raise ValueError(_("Please add a person first – every playlist belongs to one."))
    nsp = hm["nsp"]
    base = slug(hm["name"])
    pid, n = base, 2
    while any(p["id"] == pid for p in cfg["playlists"]):
        pid, n = f"{base}-{n}", n + 1
    p = {"id": pid, "name": hm["name"], "person": person, "status": "aktiv",
         "file": file, "created": dt.date.today().isoformat(), "source": "handgemacht",
         "takeover": {"original": file, "date": dt.date.today().isoformat(), "backup": None}}
    mapping = guess_mapping(cfg, nsp) if mode == "baukasten" else None
    if mode == "baukasten" and mapping:
        p.update(mapping)
        if nsp.get("limit"):
            p["limit"] = nsp["limit"]
    else:
        op = "all" if "all" in nsp else "any"
        p.update({"welt": "*", "stil": "*", "rules": nsp.get(op, []), "rulesOp": op,
                  "sortRaw": nsp.get("sort", "random"), "limit": nsp.get("limit"), "originalName": hm["name"]})
        extra = {k: v for k, v in nsp.items() if k not in ("name", "comment", "public", "all", "any", "sort", "limit")}
        if extra:   # e.g. "order": "desc" – otherwise "unchanged" would not be unchanged
            p["rulesExtra"] = extra
    cfg["playlists"].append(p)
    return p


# --------------------------------------------------------------------------- writing

def _has_marker(path):
    """Does the file carry the Tuttiphon marker? (.nsp: the comment starts with it, .m3u: header line)"""
    try:
        if path.suffix == ".m3u":
            head = read_text(path)[:400]
            return f"# {MARKER}" in head
        data = read_nsp(path)
        return isinstance(data, dict) and str(data.get("comment", "")).startswith(MARKER)
    except Exception:
        return False


def _is_ours(cfg, filename, managed, path):
    """May the tool change or delete this file? Only its own files or takeovers that were backed up."""
    if filename in managed["current"] or _has_marker(path):
        return True
    owner = next((p for p in cfg["playlists"] if p.get("file") == filename), None)
    return bool(owner and (owner.get("takeover") or {}).get("backup"))


def _backup(path, log, dry_run):
    BACKUP_DIR.mkdir(exist_ok=True)
    backup = BACKUP_DIR / f"{dt.datetime.now():%Y-%m-%d_%H%M%S}_{path.name}"
    if not dry_run:
        shutil.copy2(path, backup)
        os.chmod(backup, 0o640)   # in the data folder: not for other users of the NAS
    log(_s("  💾 Original backed up: backup/{name}", name=backup.name))
    return backup.name


BROKEN = (KeyError, ValueError, TypeError, OverflowError, AttributeError, IndexError, RuntimeError)   # a broken playlist


def plan(cfg, ctx, log=None, failed=None):
    """Active playlists -> (playlist, file name, nsp). Assigns missing file names on the way (stable).
    A playlist whose rules cannot be built (say, a value an older version let through) is left out – one broken
    playlist must not stop writing the others. failed: list that gets (playlist, error) of those; log: says so."""
    folder = playlist_dir(cfg)
    taken = {p["file"] for p in cfg["playlists"] if p.get("file")}
    hand = {h["file"] for h in handmade(cfg)}
    known = {pid: f for f, pid in load_managed()["current"].items() if pid}
    out = []
    for p in cfg["playlists"]:
        try:
            if p.get("status", "aktiv") != "aktiv" or rules.resting(cfg, p, ctx.today):
                continue   # paused, deleted – or a seasonal playlist whose time is not now
            nsp = rules.build_nsp(cfg, p, ctx)
        except BROKEN as e:
            if failed is not None:
                failed.append((p, e))
            if log:
                log(_s("  ⚠ {name}: cannot be built ({error}) – left out", name=p.get("name") or p.get("id"),
                       error=f"{type(e).__name__}: {e}"))
            continue
        ext = ".m3u" if rules.is_mix(p) else ".nsp"
        if p.get("file") and not plain_playlist_file(p["file"]):
            p.pop("file")   # not a plain file name in the playlist folder: never use it, assign a new one
        if p.get("file") and not p["file"].endswith(ext):
            p.pop("file")   # kind changed (smart <-> mix): new file, the old one is tidied up
        if not p.get("file") and known.get(p["id"]) and known[p["id"]] not in taken and known[p["id"]].endswith(ext):
            p["file"] = known[p["id"]]   # written before -> keep using the same file
            taken.add(p["file"])
        if not p.get("file"):
            stem = cfg["settings"].get("filePrefix", "") + _safe_filename(nsp["name"])
            name, n = f"{stem}{ext}", 2
            # Reuse an own file that belongs to nobody (e.g. after a canceled run) instead of "(2)"
            while name in taken or name in hand or ((folder / name).exists() and not
                                                    (name not in known.values() and _has_marker(folder / name))):
                name, n = f"{stem} ({n}){ext}", n + 1
            p["file"] = name
            taken.add(name)
        out.append((p, p["file"], nsp))
    return out


def music_root_rel(cfg):
    """Path from the playlist folder to the music root (for relative paths in .m3u)."""
    # both resolved – playlist_dir() already is; through a symlink the path would otherwise lead out of the library
    return os.path.relpath(paths(cfg)["music"].resolve(), playlist_dir(cfg)).replace(os.sep, "/")


def render(cfg, ctx, p, nsp, keep=False, order=None):
    """File content: .nsp (JSON rules) or, for mixes, .m3u with today's selection (keep: remember the selection;
    order: a selection already chosen)."""
    if rules.is_mix(p):
        if ctx.lib is None:
            raise RuntimeError(_("Mixes need the library"))
        if order is None:
            order, _unused = mixer.pick(cfg, ctx.lib, p, nsp, ctx.today, keep=keep)
        return mixer.m3u(ctx.lib, order, nsp["name"], music_root_rel(cfg), kind=mixer.label(p))
    return json.dumps(nsp, ensure_ascii=False, indent=2) + "\n"


def file_state(cfg, p, nsp, ctx=None, order=None):
    """-> "neu", "aktuell" or "geändert" (state values for the interface – data)."""
    # i18n-ignore-start
    path = playlist_dir(cfg) / p["file"] if plain_playlist_file(p.get("file")) else None
    if not path or not path.exists():
        return "neu"
    if rules.is_mix(p):
        try:
            return "aktuell" if read_text(path) == render(cfg, ctx, p, nsp, order=order) else "geändert"
        except (OSError, RuntimeError):
            return "geändert"
    try:
        current = read_nsp(path)
    except ValueError:
        return "geändert"
    if p.get("takeover") and not p["takeover"].get("backup"):
        return "geändert"
    if not isinstance(current, dict):
        return "geändert"
    strip = lambda d: {k: v for k, v in d.items() if k not in ("name", "comment", "public")}  # noqa: E731
    return "aktuell" if strip(current) == strip(nsp) else "geändert"
    # i18n-ignore-end


def write(cfg, ctx, log=print, dry_run=False):
    folder = playlist_dir(cfg)
    if not folder.exists():
        if not paths(cfg)["music"].is_dir():
            raise FileNotFoundError(_("Music folder missing: {path} (Settings → Storage locations)", path=paths(cfg)["music"]))
        folder.mkdir(parents=True, exist_ok=True)   # e.g. fresh in the container: create 00_SmartPlaylists
    managed = load_managed()
    broken = []
    plans = plan(cfg, ctx, log=log, failed=broken)
    written, unchanged, removed, failed = [], [], [], []
    keep_current = {}   # file -> playlist id: everything the tool manages after this run
    for p, _e in broken:   # cannot be built right now: its file stays as it is (nothing is removed from Navidrome)
        failed.append(p.get("name") or p["id"])
        f = p.get("file")
        if plain_playlist_file(f) and (folder / f).exists() and (f in managed["current"] or _has_marker(folder / f)):
            keep_current[f] = p["id"]
    try:
        for p, filename, nsp in plans:
            path = folder / filename
            try:   # an error in one playlist must not hold up the others
                content = render(cfg, ctx, p, nsp, keep=not dry_run)
                if path.exists() and read_text(path) == content:
                    unchanged.append(nsp["name"])
                    keep_current[filename] = p["id"]
                    continue
                if path.exists():
                    if p.get("takeover") and not p["takeover"].get("backup"):
                        name = _backup(path, log, dry_run)   # first takeover: back up the original
                        if not dry_run:
                            p["takeover"]["backup"] = name
                    elif not _is_ours(cfg, filename, managed, path):
                        _backup(path, log, dry_run)   # someone else's file with the same name (e.g. newly created): never overwrite without a backup
                written.append(nsp["name"])
                log(_s("  ✎ {name} (dry run)", name=nsp["name"]) if dry_run else f"  ✎ {nsp['name']}")
                if not dry_run:
                    write_atomic(path, content)   # rename -> folder mtime changes, Navidrome's quick scan sees it
                keep_current[filename] = p["id"]
            except Exception as e:
                failed.append(nsp["name"])
                log(f"  ⚠ {nsp['name']}: {e}")
                if path.exists() and (filename in managed["current"] or _has_marker(path)):
                    keep_current[filename] = p["id"]

        active = {f for _, f, _ in plans} | {p.get("file") for p, _e in broken if p.get("file")}
        for filename in sorted(set(managed["current"]) | {p["file"] for p in cfg["playlists"] if p.get("file")}):
            if filename in active or not plain_playlist_file(filename):
                continue
            path = folder / filename
            if not path.exists():
                continue
            owner = next((p for p in cfg["playlists"] if p.get("file") == filename), None)
            if owner and isinstance(owner.get("takeover"), dict) and not owner["takeover"].get("backup") and not dry_run:
                # taken over, but paused/deleted before the tool ever wrote it: back up the original first
                owner["takeover"]["backup"] = _backup(path, log, dry_run)
            if not _is_ours(cfg, filename, managed, path):
                continue
            label = rules.playlist_name(cfg, owner) if owner else filename
            log(_s("  ⏸ removed from Navidrome: {name} (dry run)", name=label) if dry_run
                else _s("  ⏸ removed from Navidrome: {name}", name=label))
            try:
                if not dry_run:
                    path.unlink()
                removed.append(label)
            except OSError as e:
                log(f"  ⚠ {label}: {e}")
                keep_current[filename] = managed["current"].get(filename)   # try again next time
    finally:
        if not dry_run:   # record what was written even after an error – otherwise duplicates would appear
            save_managed({"current": keep_current, "ever": sorted(set(managed["ever"]) | set(keep_current))})
    counts = {"written": len(written), "unchanged": len(unchanged), "removed": len(removed), "failed": len(failed)}
    if failed:
        log(_s("Playlists: {written} written, {unchanged} unchanged, {removed} removed from Navidrome, {failed} with errors.",
               **counts))
    else:
        log(_s("Playlists: {written} written, {unchanged} unchanged, {removed} removed from Navidrome.", **counts))
    if failed and not written and not unchanged:
        raise RuntimeError(_("No playlist could be written."))
    return {"written": written, "unchanged": unchanged, "removed": removed, "failed": failed}


# --------------------------------------------------------------------------- sync with Navidrome

def native_api(env):
    return native_session(env["NAV_URL"], env.get("NAV_ADMIN_USER"), env.get("NAV_ADMIN_PASS"))


def navidrome_index(native, cfg=None):
    """File name -> Navidrome playlist – only playlists from our own folder (namesakes elsewhere do not count)."""
    folder = playlist_dir(cfg or load_config()).name
    out = {}
    for p in native.playlists():
        path = (p.get("path") or "").replace("\\", "/")
        if path and os.path.basename(os.path.dirname(path)) == folder:
            out[os.path.basename(path)] = p
    return out


def sync_navidrome(cfg, env, ctx, log=print):
    """After the scan: set name/comment/visibility/owner, remove orphans."""
    native = native_api(env)
    users = {u["userName"].lower(): u["id"] for u in native.users()}
    by_file = navidrome_index(native, cfg)
    plans = plan(cfg, ctx)
    active = {f for _, f, _ in plans}
    changed = missing = 0
    for p, filename, nsp in plans:
        np = by_file.get(filename)
        if not np:
            missing += 1
            path = playlist_dir(cfg) / filename
            if path.exists():   # e.g. deleted by hand in Navidrome: "touch" the file so the next scan reads it in again
                try:
                    os.utime(path)
                except OSError:
                    pass
            log(_s("  ⚠ not in Navidrome yet: {name}", name=nsp["name"]))
            continue
        person = rules.person_of(cfg, p)
        want = {"name": nsp["name"], "comment": nsp["comment"], "public": nsp["public"]}
        owner = (person or {}).get("user")
        if owner and owner.lower() in users:
            want["ownerId"] = users[owner.lower()]
        elif owner:
            log(_s("  ⚠ User '{user}' does not exist in Navidrome ({name})", user=owner, name=nsp["name"]))
        diff = {k: v for k, v in want.items() if np.get(k) != v}
        if diff:
            try:
                native.update_playlist(np["id"], diff)
            except NavidromeError as e:   # one playlist must not hold up the sync of the others
                log(_s("  ⚠ {name}: not updated in Navidrome ({error})", name=nsp["name"], error=e))
                continue
            changed += 1
            what = ", ".join({"name": _s("name"), "comment": _s("description"), "public": _s("visibility"),
                              "ownerId": _s("owner")}[k] for k in diff)
            log(_s("  ↻ {name}: {fields} updated", name=nsp["name"], fields=what))
    ever = owned_files(cfg)
    deleted = 0
    for filename, np in by_file.items():
        if filename in active:
            continue
        ours = filename in ever or str(np.get("comment", "")).startswith(MARKER)
        if ours and not (playlist_dir(cfg) / filename).exists():
            try:
                native.delete_playlist(np["id"])
            except NavidromeError as e:
                log(_s("  ⚠ {name}: not removed from Navidrome ({error})", name=np.get("name"), error=e))
                continue
            deleted += 1
            log(_s("  ⏸ deleted in Navidrome: {name}", name=np.get("name")))
    log(_s("Navidrome: {present} playlists present, {changed} updated, {deleted} removed.",
           present=len(plans) - missing, changed=changed, deleted=deleted))
    return {"changed": changed, "deleted": deleted, "missing": missing}


_broken_said = set()


def _say_broken(p, e):
    """Server log: a playlist that cannot be built – once per playlist and error (the list is computed often)."""
    key = (p.get("id"), type(e).__name__, str(e)[:200])
    if key in _broken_said:
        return
    if len(_broken_said) > 500:
        _broken_said.clear()
    _broken_said.add(key)
    from . import events
    events.say(_s("⚠ Playlist “{name}” cannot be built: {error}", name=p.get("name") or p.get("id"),
                  error=f"{type(e).__name__}: {e}"))


def status(cfg, ctx, native=None):
    """State of every playlist for the interface (status and state values are data)."""
    by_file, users = {}, None
    nav_error = None
    if native is not None:
        try:
            by_file = navidrome_index(native, cfg)
            users = {u["userName"].lower() for u in native.users()}
        except Exception as e:   # Navidrome briefly gone: show local information anyway
            nav_error = str(e)
    lib = ctx.lib
    managed = load_managed()

    def row(p):
        st = p.get("status", "aktiv")
        order = None
        nsp = rules.build_nsp(cfg, p, ctx)
        ids = lib.match(nsp) if lib else frozenset()
        if rules.is_mix(p) and lib:
            if st == "aktiv" and not rules.resting(cfg, p, ctx.today):   # only what is really written
                order = mixer.pick(cfg, lib, p, nsp, ctx.today)[0]
                ids = frozenset(order)
            else:   # paused, in the trash or season over: pool instead of mix – saves the picking
                ids = frozenset(sorted(ids)[:int(mixer.options(p)["size"])])
        np = by_file.get(p.get("file") or "")
        state = st
        path = playlist_dir(cfg) / p["file"] if plain_playlist_file(p.get("file")) else None
        if st != "aktiv" and (np or (path and path.exists() and _is_ours(cfg, p["file"], managed, path))):
            state = "entfernen"   # paused/deleted, but still in Navidrome (the tool does not touch other people's files)
        back = rules.resting(cfg, p, ctx.today) if st == "aktiv" else None
        if back:   # season over: not in Navidrome until next time
            state = "entfernen" if (np or (path and path.exists() and _is_ours(cfg, p["file"], managed, path))) else "ruht"
        elif st == "aktiv":
            state = file_state(cfg, p, nsp, ctx, order=order)
            if state == "aktuell" and native is not None and not nav_error:
                if not np:
                    state = "scan"
                else:
                    owner = ((rules.person_of(cfg, p) or {}).get("user") or "").lower()
                    owner_wrong = owner and users is not None and owner in users and owner != (np.get("ownerName") or "").lower()
                    if np.get("name") != nsp["name"] or np.get("public") != nsp["public"] or owner_wrong:
                        state = "geändert"   # i18n-ignore
        return {
            "id": p["id"], "name": nsp["name"], "status": st, "state": state, "count": len(ids),
            "limit": len(ids) if rules.is_mix(p) else nsp.get("limit"), "describe": rules.describe(cfg, p),
            "mix": rules.is_mix(p), "back": back.isoformat() if back else None,
            "topArtists": lib.artist_rows(ids, 6) if lib else [], "covers": lib.covers(ids) if lib else [],
            "navidrome": {"id": np["id"], "owner": np.get("ownerName"), "public": np.get("public"),
                          "songCount": np.get("songCount")} if np else None,
            "cover": {"style": p["cover"]["style"], "v": f'{p["cover"].get("rev", "")}{p["cover"].get("sig") or p["cover"].get("at") or ""}' or "1"}
            if np and isinstance(p.get("cover"), dict) and p["cover"].get("style") not in (None, "none") else None,
        }

    out = []
    for p in cfg["playlists"]:
        try:
            out.append(row(p))
        except BROKEN as e:   # one broken playlist must not break the list (for everyone)
            _say_broken(p, e)
            out.append({"id": p["id"], "name": p.get("name") or p["id"], "status": p.get("status", "aktiv"),
                        "state": "fehler", "error": str(e), "count": None, "topArtists": [], "covers": [],
                        "navidrome": None, "cover": None, "mix": rules.is_mix(p)})
    active = {p.get("file") for p in cfg["playlists"] if p.get("status", "aktiv") == "aktiv"}
    orphans = [f for f in load_managed()["current"] if f not in active and (playlist_dir(cfg) / f).exists()]
    return {"playlists": out, "navidromeError": nav_error, "orphans": orphans}


# --------------------------------------------------------------------------- keep a mix

def snapshot(cfg, env, ctx, playlist_id):
    """Save the current mix as a normal (fixed) playlist in Navidrome."""
    p = next(x for x in cfg["playlists"] if x["id"] == playlist_id)
    nsp = rules.build_nsp(cfg, p, ctx)
    if rules.is_mix(p):
        picks = mixer.pick(cfg, ctx.lib, p, nsp, ctx.today)[0]
    else:
        ids = sorted(ctx.lib.match(nsp))
        n = min(nsp.get("limit") or 100, len(ids))
        sort = str(nsp.get("sort") or "random")
        field = sort.lstrip("+-").lower()
        keyf = {"dateadded": lambda i: ctx.lib.songs[i].get("created") or "",
                "rating": lambda i: ctx.lib.songs[i].get("userRating") or 0,
                "lastplayed": lambda i: ctx.lib.songs[i].get("played") or ""}.get(field)
        if keyf:   # save "newest/most popular first" that way too
            desc = sort.startswith("-") or str(nsp.get("order", "")).lower() == "desc"
            picks = sorted(ids, key=keyf, reverse=desc)[:n]
        else:
            picks = random.sample(ids, n)
    if not picks:
        raise ValueError(_("The playlist is empty right now – nothing to save."))
    today = dt.date.today()
    name = f"{nsp['name']} – {_s(MONTHS[today.month - 1])} {today.year}"   # i18n-ignore
    comment = _s("Saved mix from {month}/{day}/{year} (from “{name}”, Tuttiphon)", day=f"{today:%d}", month=f"{today:%m}",
                 year=today.year, name=nsp["name"])
    save_fixed(env, rules.person_of(cfg, p), name, [ctx.lib.songs[i]["id"] for i in picks], comment, nsp["public"])
    return {"name": name, "count": len(picks)}


def save_fixed(env, person, name, song_ids, comment, public):
    """Create a fixed playlist in Navidrome that never changes again – in the person's account."""
    admin = Navidrome(env["NAV_URL"], env.get("NAV_ADMIN_USER"), env.get("NAV_ADMIN_PASS"))
    created = admin.call("createPlaylist", post=True, name=name, songId=list(song_ids)).get("playlist", {})
    native = native_api(env)
    fields = {"comment": comment, "public": bool(public)}
    owner = (person or {}).get("user")
    users = {u["userName"].lower(): u["id"] for u in native.users()}
    if owner and owner.lower() in users:
        fields["ownerId"] = users[owner.lower()]
    native.update_playlist(created["id"], fields)
    return created.get("id")
