"""Run maintenance steps one after another in the background, log them live, save the history."""
import datetime as dt
import json
import os
import re
import signal
import threading
import time
from pathlib import Path
import traceback

from . import deezer, events, instances, playlists, rules
from .config import LOG_DIR, STATE_DIR, load_config, load_env, read_text, update_config, write_atomic
from .i18n import N_, _, _s, _sn, english, join, said
from .library import CACHE
from .navidrome import Navidrome
from .rules import BuildContext

ANSI = re.compile(r"\x1B\[[0-?]*[ -/]*[@-~]")
HISTORY_FILE = STATE_DIR / "history.jsonl"

# Steps that continue where they stopped after an interruption – they may pause for an apply
PAUSABLE = {"flac", "lyrics", "cover", "analyse", "deezer"}
# Step titles – translated where they are used: _s() in logs and run names, _() in answers (web.py)
STEP_TITLES = {
    "flac": N_("Convert music"),
    "lyrics": N_("Find & tidy up lyrics"),
    "cover": N_("Fetch missing covers"),
    "analyse": N_("Understand music (sound, AI & Last.fm)"),
    "playlists": N_("Write playlists"),
    "scan": N_("Navidrome scan & sync"),
    "deezer": N_("Deezer rating"),
}
# How a step ended: stored as data ("ok", "warnung", "fehler", "abgebrochen"), shown as text in the log
RESULT_TEXTS = {"ok": N_("{step}: ok"), "warnung": N_("{step}: warning"), "fehler": N_("{step}: error"),
                "abgebrochen": N_("{step}: canceled")}
PIPELINE = ["flac", "lyrics", "cover", "analyse", "playlists", "scan", "deezer"]   # all steps in a fixed order
EXTRAS_EVERY = 6 * 3600   # lyrics index and new music worlds after pure playlist runs at most this often
WATCH_BUDGET = 2          # minutes for loudness and fingerprints in a folder-watch run (once the library is done, only
                          # the new songs are pending there; fingerprints take new songs first anyway)
_extras_at = 0.0


def new_song_ids(cfg, lib, files):
    """Ids of the songs behind new files of the folder watch (absolute paths in the music folder). The file may have
    been converted in the meantime (FLAC -> Opus/AAC: same name, other extension) – compared without the extension."""
    from .config import paths
    root = Path(paths(cfg)["music"])
    wanted = set()
    for f in files:
        try:
            wanted.add(Path(f).relative_to(root).with_suffix("").as_posix())
        except ValueError:   # outside the music folder
            continue
    out = set()
    if not wanted:
        return out
    for i, s in enumerate(lib.songs):
        rel = lib.real_path(i)
        if rel and Path(rel).with_suffix("").as_posix() in wanted:
            out.add(s["id"])
    return out


def pipeline(cfg=None):
    """What “Update everything” does – chosen under Settings → Automation."""
    chosen = (cfg or load_config())["settings"].get("pipeline")
    return [s for s in PIPELINE if s in chosen] if isinstance(chosen, list) else list(PIPELINE)


def tidy(now=None):
    """Tidy up once a day: logs older than 90 days, the history down to the last 2,000 runs, cached images not renewed
    for 60 days (used ones are fetched fresh every 14 days). Backups (backup/) stay – they are small and cannot be
    restored otherwise. -> number of deleted files."""
    from .images import CACHE_DIR
    now = now or time.time()
    removed = 0
    for folder, max_age in ((LOG_DIR, 90 * 86400), (CACHE_DIR, 60 * 86400)):
        if not folder.is_dir():
            continue
        for path in folder.rglob("*"):
            try:
                if path.is_file() and now - path.stat().st_mtime > max_age:
                    path.unlink()
                    removed += 1
            except OSError:
                pass
    try:
        lines = read_text(HISTORY_FILE).splitlines(keepends=True)
        if len(lines) > 2000:
            write_atomic(HISTORY_FILE, "".join(lines[-2000:]))
    except OSError:
        pass
    return removed


def deezer_pipeline_mode(cfg):
    """Deezer mode from the settings: "missing" there means “new + not found” (internally "both")."""
    return {"missing": "both"}.get((cfg["settings"].get("deezer") or {}).get("pipelineMode"), "new")


def admin_client(env):
    return Navidrome(env["NAV_URL"], env.get("NAV_ADMIN_USER"), env.get("NAV_ADMIN_PASS"))


def history(limit=30):
    out = []
    if HISTORY_FILE.exists():
        for line in read_text(HISTORY_FILE).splitlines():
            try:
                out.append(json.loads(line))
            except ValueError:
                pass
    out.sort(key=lambda e: e["start"], reverse=True)
    return out[:limit]


class _InstanceLock:
    """Lock across processes and machines (PC and Docker container): reports of the other instances
    (instances.busy_elsewhere) plus a POSIX lock on task.lock in the shared folder (<playlist folder>/.tuttiphon/,
    see app/instances.py). If the file system cannot lock, only the reports decide."""

    def __init__(self):
        self.fd = None

    def acquire(self):
        if instances.busy_elsewhere():
            return False
        try:
            import fcntl
        except ImportError:
            return True
        path = instances.shared_dir() / "task.lock"
        # the shared folder is writable for everyone: never follow a link someone put there (O_NOFOLLOW, fchmod)
        flags = os.O_RDWR | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0)
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            if path.is_symlink():
                path.unlink()
            try:
                fd = os.open(path, flags, 0o666)
            except PermissionError:   # e.g. permissions 000 from the NAS share -> repair and try again
                if path.is_symlink():
                    raise
                os.chmod(path, 0o666)
                fd = os.open(path, flags, 0o666)
            try:
                os.fchmod(fd, 0o666)   # PC and container may run as different users
            except OSError:
                pass
        except OSError:
            return True   # lock file not usable -> carry on without a lock instead of blocking everything
        try:
            fcntl.lockf(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            self.fd = fd
            return True
        except (BlockingIOError, PermissionError):   # EAGAIN/EACCES: another instance is working right now
            os.close(fd)
            return False
        except OSError:   # e.g. ENOLCK: no locks possible
            os.close(fd)
            return True

    def release(self):
        if self.fd is not None:
            try:
                os.close(self.fd)   # releases the lock
            except OSError:
                pass
            self.fd = None


class TaskRunner:
    def __init__(self, echo=False):
        self.echo = echo
        self.lines = []
        self.seq = 0
        self.lock = threading.Lock()
        self.start_lock = threading.Lock()
        self.stop = threading.Event()
        self.thread = None
        self.children = set()   # running subprocesses (e.g. ffmpeg) – ended when stopping
        self.name = None
        self.steps = []
        self.step = None
        self.results = {}
        self.finished_at = None
        self.logfile = None
        self._opts = {}
        self._pos = 0      # index of the running step (steps can appear twice, e.g. "scan")
        self._chain = []   # start one after another after the end: [(steps, opts, name), …] (pause for an apply)

    # ------------------------------------------------------------------ Log
    def log(self, text=""):
        stamp = time.strftime("%H:%M:%S")
        lines = ANSI.sub("", str(text)).splitlines() or [""]
        en = ANSI.sub("", english(text)).splitlines() or [""]   # the server log is always English
        if len(en) != len(lines):
            en = lines
        for line, line_en in zip(lines, en):
            with self.lock:
                self.seq += 1
                self.lines.append((self.seq, stamp, line))
                if len(self.lines) > 4000:
                    del self.lines[:1000]
            if self.logfile:
                self.logfile.write(f"[{stamp}] {line}\n")
                self.logfile.flush()
            if self.echo:
                print(line_en, flush=True)
            elif line.strip() and not line[0].isspace():   # server: headings and results into the server log
                events.say(line_en)

    def status(self, since=0):
        with self.lock:
            lines = [{"n": n, "t": t, "text": x} for n, t, x in self.lines if n > since]
        return {"running": self.running(), "name": self.name, "steps": self.steps, "step": self.step,
                "results": self.results, "finishedAt": self.finished_at, "lines": lines}

    def running(self):
        return self.thread is not None and self.thread.is_alive()

    # ------------------------------------------------------------------ Run
    def start(self, steps, background=True, name=None, **opts):
        unknown = [s for s in steps if s not in STEP_TITLES]
        if unknown or not steps:
            raise ValueError(_("Unknown steps: {steps}", steps=unknown))
        with self.start_lock:   # check and start in one go – otherwise double clicks start two runs
            if self.running():
                raise RuntimeError(_("A task is already running."))
            # Take the lock against other instances here (not only in the run): every caller learns right away that
            # nothing was started – auto-apply plans again, the daily refresh tries again in a minute, the folder
            # watch keeps the new files for the next round.
            lock = _InstanceLock()
            if not lock.acquire():
                raise RuntimeError(_("Another Tuttiphon instance (PC or Docker) is working right now – please try again later."))
            instances.heartbeat(running=True)   # the other instance should see it at once, not only in a minute
            try:
                return self._start(steps, background, name, lock, **opts)
            except BaseException:
                lock.release()
                instances.heartbeat(running=False)
                raise

    def _start(self, steps, background, name, lock, **opts):
        self.stop.clear()
        self.steps = list(steps)
        if not name:
            if steps == pipeline():
                name = _s("Update everything")
            elif steps == ["playlists", "scan"]:
                name = _s("Apply playlists in Navidrome")
            elif steps == ["deezer"]:
                mode = opts.get("deezer_mode") or deezer_pipeline_mode(load_config())
                name = {"new": _s("Deezer: new songs"), "missing": _s("Deezer: songs not found, once more"),
                        "full": _s("Deezer: full check"), "recalc": _s("Deezer: recalculate stars"),
                        "both": _s("Deezer: new + not found"), "refresh": _s("Deezer: refresh")}.get(mode, "Deezer: ")
            else:
                name = join(" + ", (_s(STEP_TITLES[s]) for s in steps))   # i18n-ignore
        self.name = name
        self.results = {}
        self.finished_at = None
        self._opts = dict(opts)
        self._pos = 0
        if background:
            self.thread = threading.Thread(target=self._run, args=(steps, opts, lock), daemon=True)
            self.thread.start()
        else:
            self._run(steps, opts, lock)
        return self.status()

    def can_pause(self):
        """Can the current run be paused for an apply? (see pause_for)"""
        remaining = self.steps[self._pos:]
        return self.running() and not self.stop.is_set() and not self._chain and bool(remaining) and set(remaining) <= PAUSABLE

    def pause_for(self, steps, name, **opts):
        """Pause a running task briefly, slip `steps` in between and continue the rest afterwards – e.g. so that playlist
        changes do not wait hours for an analysis. Only for steps that continue where they stopped on the next start
        (PAUSABLE), and only if the run does not write playlists itself later on.
        -> True if it was paused."""
        with self.start_lock:
            if not self.can_pause():
                return False
            remaining = self.steps[self._pos:]
            continued = (self.name if self.name.endswith(("(continued)", "(fortgesetzt)"))   # i18n-ignore
                         else _s("{name} (continued)", name=self.name))
            self._chain = [(list(steps), dict(opts), name), (remaining, dict(self._opts), continued)]
            self.log("")
            self.log(_s("⏸ Short pause for “{name}” – this run continues afterwards.", name=name))
            self.cancel()
        return True

    def _continue(self, chain):
        """After this run ends, start the queued runs one after another (own thread)."""
        current = threading.current_thread()

        def go():
            current.join()
            for steps, opts, name in chain:
                for _attempt in range(180):   # up to half an hour, e.g. if another run came in between
                    try:
                        self.start(steps, name=name, **opts)
                        break
                    except RuntimeError:
                        time.sleep(10)
                else:
                    self.log(_s("⚠ “{name}” could not be continued – the next run catches up.", name=name))
                    return
                self.thread.join()
        threading.Thread(target=go, daemon=True).start()

    def cancel(self):
        self.stop.set()
        for proc in list(self.children):
            if proc and proc.poll() is None:
                try:   # end the whole process group (bash + ffmpeg), otherwise ffmpeg keeps running
                    os.killpg(proc.pid, signal.SIGTERM)
                except OSError:
                    proc.terminate()

    def _track(self, proc, running):
        (self.children.add if running else self.children.discard)(proc)
        if running and self.stop.is_set():
            self.cancel()

    def _run(self, steps, opts, lock):
        done = threading.Event()

        def keep_reporting():   # long runs (e.g. full Deezer check): report every minute, otherwise they count as ended
            while not done.wait(60):
                instances.heartbeat()
        threading.Thread(target=keep_reporting, daemon=True).start()
        try:
            self._run_locked(steps, opts)
        finally:
            done.set()
            lock.release()
            instances.heartbeat(running=False)
            chain, self._chain = self._chain, []
            if chain:
                self._continue(chain)

    def _run_locked(self, steps, opts):
        LOG_DIR.mkdir(exist_ok=True)
        started = dt.datetime.now()
        path = LOG_DIR / f"{started:%Y-%m-%d_%H%M%S}_{'-'.join(steps)}.log"
        self.logfile = path.open("w", encoding="utf-8")
        ctx = {"summary": {}, "steps": list(steps)}
        try:
            self.log("▶ " + self.name + f" – {started:%d.%m.%Y %H:%M}")   # + keeps the English form of the name
            self._langzeit(opts)
            for pos, step in enumerate(steps):
                if self.stop.is_set():
                    self.results[step] = "abgebrochen"
                    continue
                self._pos = pos
                self.step = step
                self.log("")
                self.log("━━ " + _s(STEP_TITLES[step]) + " ━━")   # i18n-ignore
                t0 = time.time()
                try:
                    ok = getattr(self, f"_step_{step}")(ctx, **opts)
                    self.results[step] = "abgebrochen" if self.stop.is_set() else "ok" if ok is not False else "warnung"
                except Exception as e:   # one step must not prevent the others
                    self.results[step] = "fehler"
                    self.log("❌ " + said(e))
                    if not isinstance(e, RuntimeError):
                        self.log(traceback.format_exc().strip().splitlines()[-1])
                self.log(f"   ({int(time.time() - t0)} s)")
            self.step = None
            self.log("")
            done = join(", ", (_s(RESULT_TEXTS[r], step=_s(STEP_TITLES[s])) for s, r in self.results.items()))   # i18n-ignore
            self.log(_s("■ Done. {results}", results=done))
        finally:
            ended = dt.datetime.now()
            self.finished_at = ended.strftime("%d.%m.%Y %H:%M")
            self.logfile.close()
            self.logfile = None
            entry = {"start": started.isoformat(timespec="seconds"), "end": ended.isoformat(timespec="seconds"),
                     "name": self.name, "steps": steps, "results": self.results, "summary": ctx["summary"],
                     "log": path.name, "dryRun": bool(opts.get("dry_run"))}
            STATE_DIR.mkdir(exist_ok=True)
            with HISTORY_FILE.open("a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
            try:
                os.chmod(HISTORY_FILE, 0o664)
                os.chmod(path, 0o664)
            except OSError:
                pass
            try:   # errors, new music, newly classified bands to the phone (if turned on)
                from . import notify
                notify.after_run(entry)
            except Exception:   # noqa: BLE001 – a notification must never disturb a run
                pass

    # ------------------------------------------------------------------ Steps
    def _step_flac(self, ctx, dry_run=False, flac_files=None, **_):
        from . import opus
        # flac_files: folder watch – exactly these new files (they have been unchanged for a few minutes)
        res = opus.run(load_config(), log=self.log, stop=self.stop, track=self._track, dry_run=dry_run,
                       files=None if flac_files is None else [Path(f) for f in flac_files])
        ctx["summary"]["flac"] = res
        return res.get("errors", 0) == 0

    def _step_lyrics(self, ctx, dry_run=False, lyrics_all=False, lyrics_full=False, lyrics_files=None, **_):
        from . import lyrics
        cfg = load_config()
        if lyrics_files is not None:   # folder watch: only the new files (tags straight from the file)
            files = []
            for f in map(Path, lyrics_files):   # converted in the meantime (Opus or AAC)? Then take the new file
                files.append(next((g for g in (f, f.with_suffix(".opus"), f.with_suffix(".m4a")) if g.exists()), f))
            res = lyrics.fetch_files(cfg, [f for f in dict.fromkeys(files) if f.exists()], log=self.log, stop=self.stop, dry_run=dry_run)
            ctx["summary"]["lyrics"] = res
            return True
        res = lyrics.run(cfg, CACHE.get(), log=self.log, stop=self.stop, dry_run=dry_run, everything=lyrics_all,
                         budget=0 if (lyrics_full or lyrics_all) else None)
        ctx["summary"]["lyrics"] = res
        return not res.get("errors")

    def _step_cover(self, ctx, dry_run=False, **_):
        from . import albumcover
        res = albumcover.run(load_config(), CACHE.get(), log=self.log, stop=self.stop.is_set, dry_run=dry_run)
        ctx["summary"]["cover"] = res
        return True

    def _step_analyse(self, ctx, dry_run=False, analyse_full=False, night_until=None, new_files=None, **_):
        """Fetch Last.fm knowledge, analyze the sound (own measurement, then AI), classify new bands – all with a time limit.
        night_until: night analysis – no time limit, but until then at the latest (time.time() value).
        new_files: folder watch – only these new files (Last.fm for their bands, sound and AI for their songs, loudness
        and fingerprints with a small time limit): the playlists after it must not wait for the whole backlog, that
        follows in the regular runs."""
        from . import audio, classify, lastfm, ml
        cfg = load_config()
        an = cfg["settings"].get("analysis") or {}
        lib = CACHE.get()
        out = {}
        only = None if new_files is None or dry_run else new_song_ids(cfg, lib, new_files)
        small = WATCH_BUDGET if only is not None else None   # minutes for loudness and fingerprints in a watch run
        if dry_run:   # dry run: measure nothing, save nothing – only say what the classification would suggest
            n = len([x for x in classify.suggestions(cfg, lib) if x["score"] >= 0.6])
            self.log(_sn(n, "(dry run) Last.fm and sound analysis skipped. Classification: {n} confident suggestion.",
                         "(dry run) Last.fm and sound analysis skipped. Classification: {n} confident suggestions."))
            ctx["summary"]["analyse"] = out
            return True
        if only is not None:
            self.log(_sn(len(only), "Only the new music: {n} song.", "Only the new music: {n} songs."))
        if lastfm.api_key() and only != set():
            count, _, _, _ = rules.artist_stats(lib.songs)
            known = {a for w in cfg["welten"] for a in rules.welt_artists(w, rules.BuildContext(lib))}
            names = sorted(count, key=lambda a: (a in known, -count[a]))   # bands without a world first, then the big ones
            if only is not None:   # folder watch: the bands of the new songs
                bands = {lib._main_artist(s) for s in lib.songs if s["id"] in only}
                names = [a for a in names if a in bands]
            try:
                out["lastfm"] = lastfm.refresh(names, log=self.log, stop=self.stop, budget=0 if analyse_full else an.get("lastfmBudget", 3))
            except Exception as e:   # noqa: BLE001 – Last.fm must never prevent sound analysis and AI
                self.log("⚠ Last.fm: " + said(e))
        else:
            self.log(_s("Last.fm: no key entered – similar bands and tags are missing (Settings → Intelligence)."))
        if self.stop.is_set():
            return False
        if an.get("enabled", True) and only != set():
            unlimited = analyse_full or bool(night_until)
            out["audio"] = audio.run(cfg, lib, log=self.log, stop=self.stop, budget=0 if unlimited else None,
                                     until=night_until, track=self._track, only=only)
            if an.get("ml", True) and not self.stop.is_set():
                out["ml"] = ml.run(cfg, lib, log=self.log, stop=self.stop, budget=0 if unlimited else None,
                                   until=night_until, track=self._track, only=only)
        from . import lautstaerke
        if lautstaerke.settings(cfg)["enabled"] and not self.stop.is_set():   # even out loudness (ReplayGain)
            try:
                out["loudness"] = lautstaerke.run(cfg, lib, log=self.log, stop=self.stop.is_set,
                                                  budget=0 if (analyse_full or night_until) else small,
                                                  until=night_until, track=self._track)
            except Exception as e:   # noqa: BLE001 – must never prevent the classification afterwards
                self.log(_s("⚠ Loudness: {error}", error=e))
        mode = an.get("classify", "suggest")
        if mode == "auto":
            made = []

            def apply(fresh):
                made.extend(classify.auto_assign(fresh, lib, an.get("autoThreshold", 0.75), log=self.log))
            update_config(apply)
            out["assigned"] = len(made)
            out["assignedBands"] = [[x["artist"], x["welt"]] for x in made][:20]
            self.log(_sn(len(made), "Classification: {n} band automatically assigned to a music world.",
                         "Classification: {n} bands automatically assigned to a music world."))
        elif mode == "suggest":
            made = []
            if an.get("autoNew", True):   # classify new bands (e.g. from Lidarr) right away if the match is confident
                def apply_new(fresh):
                    threshold = max(0.75, an.get("autoThreshold", 0.75))   # a stricter setting counts here too
                    made.extend(classify.auto_assign(fresh, lib, threshold, log=self.log, new_only=True))
                update_config(apply_new)
                out["assigned"] = len(made)
                out["assignedBands"] = [[x["artist"], x["welt"]] for x in made][:20]
            n = len([x for x in classify.suggestions(load_config(), lib) if x["score"] >= 0.6])
            if made:
                self.log(_s("Classification: {made} new band(s) classified automatically, {n} confident suggestions – "
                            "see “To review” on the home page.", made=len(made), n=n))
            else:
                self.log(_sn(n, "Classification: {n} confident suggestion – see “To review” on the home page.",
                             "Classification: {n} confident suggestions – see “To review” on the home page."))
        from . import fingerprint
        if fingerprint.enabled(cfg) and not self.stop.is_set():   # same recording twice (Check library) – last: only a hint
            try:
                out["fingerprints"] = fingerprint.run(cfg, lib, log=self.log, stop=self.stop.is_set,
                                                      budget=0 if (analyse_full or night_until) else small,
                                                      until=night_until, track=self._track)
            except Exception as e:   # noqa: BLE001 – a hint must never break the step
                self.log(_s("⚠ Audio fingerprints: {error}", error=e))
        ctx["summary"]["analyse"] = out
        if not self.stop.is_set() and not dry_run:   # new tags and styles: maybe a new music world comes up
            self._autowelten(ctx, lib)
        return not self.stop.is_set()

    def _build_ctx(self):
        return BuildContext(CACHE.get())

    def _step_playlists(self, ctx, dry_run=False, **_):
        cfg = load_config()
        if not dry_run:   # first: evaluate finished mix periods (skipped/played) so the new mixes learn
            from . import feedback
            try:
                feedback.learn(log=self.log)
                feedback.forget_removed({p["id"] for p in cfg["playlists"]})
            except Exception as e:   # learning must never prevent writing
                self.log(_s("⚠ Learning from mixes: {error}", error=e))
        before = {p["id"]: p.get("file") for p in cfg["playlists"]}
        result = playlists.write(cfg, self._build_ctx(), log=self.log, dry_run=dry_run)
        if not dry_run:   # carry new file names / backups over into the *current* configuration
            learned = {p["id"]: {k: p[k] for k in ("file", "takeover") if k in p} for p in cfg["playlists"]}

            def apply(fresh):
                for p in fresh["playlists"]:
                    for k, v in learned.get(p["id"], {}).items():
                        if k == "file":
                            if p.get("file") != before.get(p["id"]):
                                continue   # decided differently during the run
                            if not v.endswith(".m3u" if rules.is_mix(p) else ".nsp"):
                                continue   # kind changed in the meantime -> new on the next run
                        p[k] = v
            update_config(apply)
        ctx["summary"]["playlists"] = {k: len(v) for k, v in result.items()}
        return True

    def _step_scan(self, ctx, full_scan=False, dry_run=False, **_):
        full_scan = full_scan or (load_config()["settings"].get("navidrome") or {}).get("scan") == "full"
        if dry_run:   # dry run: do not touch Navidrome
            self.log(_s("(dry run) Full Navidrome scan and sync skipped.") if full_scan
                     else _s("(dry run) Navidrome scan and sync skipped."))
            return True
        env = load_env()
        nav = admin_client(env)
        if nav.scan_status().get("scanning"):
            self.log(_s("Navidrome is already scanning – waiting for it."))
        else:
            nav.start_scan(full=full_scan)
            self.log(_s("Scan started (full).") if full_scan else _s("Scan started (changes only)."))
        if not nav.wait_for_scan(log=self.log, stop=self.stop):
            return False
        after = nav.scan_status()
        self.log(_s("Scan finished: {files} files, {folders} folders.", files=after.get("count"), folders=after.get("folderCount")))
        CACHE.invalidate()
        bctx = self._build_ctx()
        result = playlists.sync_navidrome(load_config(), env, bctx, log=self.log)
        if result["missing"] and not self.stop.is_set():   # missing playlists: files were touched -> a second, short scan
            self.log(_s("Some playlists are missing in Navidrome – having them read in again."))
            nav.start_scan(full=False)
            if nav.wait_for_scan(log=self.log, stop=self.stop):
                result = playlists.sync_navidrome(load_config(), env, bctx, log=self.log)
        ctx["summary"]["scan"] = {"files": after.get("count"), **result}
        self._refresh_covers(env, bctx)
        # Lyrics index and new music worlds: after runs that touched music or lyrics – otherwise (e.g. after saving a
        # playlist) at most every 6 hours
        global _extras_at
        if {"flac", "lyrics", "cover", "analyse"} & set(ctx.get("steps", ())) or time.time() - _extras_at > EXTRAS_EVERY:
            _extras_at = time.time()
            if not self.stop.is_set():
                self._lyrics_index(ctx, env, bctx, nav)
            if not self.stop.is_set():
                self._autowelten(ctx, bctx.lib)
        if not self.stop.is_set():
            try:   # news from favorite bands, “your October is here” – to each person's phone
                from . import notify
                notify.for_persons(load_config(), bctx.lib)
            except Exception as e:   # noqa: BLE001
                self.log(_s("⚠ Notifications: {error}", error=e))
        if not self.stop.is_set():   # does Navidrome deliver what Tuttiphon expects? (differences -> “To review”)
            from . import selfcheck
            try:
                ctx["summary"]["selfcheck"] = {"checked": (sc := selfcheck.run(load_config(), env, bctx, log=self.log))["checked"],
                                               "problems": len(sc["problems"])}
            except Exception as e:   # the check must never make the run fail
                self.log(_s("⚠ Self-check: {error}", error=e))
        return result["missing"] == 0

    def _langzeit(self, opts):
        """Once a week: trash, vanished songs, old marks, lyrics index (langzeit.py) – at the start of a run, while it holds
        the lock and no step writes the files. Never in a dry run."""
        from . import langzeit
        if opts.get("dry_run") or not langzeit.due():
            return
        try:
            langzeit.run(CACHE.get(), log=self.log)
        except Exception as e:   # noqa: BLE001 – must never prevent the run; again next time
            self.log(_s("⚠ Long-term maintenance: {error}", error=e))

    def _autowelten(self, ctx, lib):
        """Create the music worlds the collection now offers on its own (autowelten.py)."""
        from . import autowelten
        try:
            made = autowelten.sync(lib, log=self.log)
        except Exception as e:   # noqa: BLE001 – must never make the run fail
            self.log(_s("⚠ Music worlds: {error}", error=e))
            return
        if made:
            ctx["summary"].setdefault("welten", []).extend(m["name"] for m in made)

    def _lyrics_index(self, ctx, env, bctx, nav):
        """Bring lyrics search and kid-safe mode up to date. If this finds new explicit lyrics and someone has kid-safe
        mode on, write the playlists again right away and have them read in."""
        from . import liedtext
        if liedtext.status()["running"]:   # indexing in the background right now – do not wait for it
            self.log(_s("Lyrics are already being indexed."))
            return
        if not liedtext.ready():   # the very first indexing takes a while – in the background, without holding up the run
            self.log(_s("Lyrics are being indexed in the background (for search and kid-safe mode)."))
            liedtext.update_soon(bctx.lib, force=True)
            return
        cfg = load_config()
        allow = (cfg["settings"].get("kinderschutz") or {}).get("allow", [])
        before = liedtext.derb(allow)
        try:
            liedtext.update(bctx.lib, cfg, log=self.log, stop=self.stop.is_set)
        except Exception as e:   # noqa: BLE001 – the search must never make the run fail
            self.log(_s("⚠ Lyrics index: {error}", error=e))
            return
        new = liedtext.derb(allow) - before
        if not new or not any(p.get("clean") for p in cfg["personen"]) or self.stop.is_set():
            return
        self.log(_sn(len(new), "Kid-safe mode: {n} new song with explicit lyrics found – adjusting the playlists.",
                     "Kid-safe mode: {n} new songs with explicit lyrics found – adjusting the playlists."))
        # like the step “Write playlists” (file names end up in the configuration), then read in and sync
        self._step_playlists({"summary": {}})
        if self.stop.is_set():
            return
        nav.start_scan(full=False)
        if nav.wait_for_scan(log=self.log, stop=self.stop):
            playlists.sync_navidrome(load_config(), env, bctx, log=self.log)

    def _refresh_covers(self, env, bctx):
        """Renew designed covers when their material has changed (e.g. a new Daily Mix)."""
        from . import covers
        cfg = load_config()
        if not any((p.get("cover") or {}).get("style") for p in cfg["playlists"]):
            return
        try:
            native = playlists.native_api(env)
            n = covers.refresh_auto(cfg, bctx.lib, native, playlists.navidrome_index(native, cfg), log=self.log)
        except Exception as e:
            self.log(_s("⚠ Covers: {error}", error=e))
            return
        if n:
            done = {p["id"]: p["cover"] for p in cfg["playlists"] if isinstance(p.get("cover"), dict)}

            def apply(fresh):
                for p in fresh["playlists"]:
                    cv, new = p.get("cover"), done.get(p["id"])
                    if isinstance(cv, dict) and new and cv.get("style") == new.get("style"):   # not over a cover that is new by now
                        cv.update({k: new[k] for k in ("sig", "nid") if k in new})
            update_config(apply)

    def _step_deezer(self, ctx, deezer_mode=None, dry_run=False, overwrite_manual=None, **_):
        cfg = load_config()
        deezer_mode = deezer_mode or deezer_pipeline_mode(cfg)
        result = deezer.run(load_env(), mode=deezer_mode, dry_run=dry_run, log=self.log, stop=self.stop,
                            overwrite_manual=overwrite_manual, cfg=cfg)
        ctx["summary"]["deezer"] = {"mode": deezer_mode, **result}
        if result.get("set"):
            CACHE.invalidate()
        return not result.get("stopped")
