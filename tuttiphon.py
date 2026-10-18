#!/usr/bin/env python3
"""Tuttiphon – smart playlists and maintenance for Navidrome.

  python3 tuttiphon.py                      start the interface (http://127.0.0.1:8765)
  python3 tuttiphon.py run                  update everything (for cron/systemd timers)
  python3 tuttiphon.py run deezer           single steps only: flac lyrics cover analyse playlists scan deezer
  python3 tuttiphon.py run deezer --deezer-mode full     rate all songs again (takes hours)
  python3 tuttiphon.py run --dry-run                     dry run: only show, change nothing
"""
import argparse
import signal
import sys
import threading
import webbrowser

sys.dont_write_bytecode = True   # no __pycache__ folders on the NAS

from app.i18n import _s, _sn  # noqa: E402
from app.tasks import PIPELINE, STEP_TITLES, TaskRunner, pipeline  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description="Tuttiphon – smart playlists and maintenance for Navidrome")
    sub = parser.add_subparsers(dest="cmd")

    p_serve = sub.add_parser("serve", help="start the web interface (default)")
    p_serve.add_argument("--host", default="127.0.0.1",
                         help="0.0.0.0 = reachable from phones on the Wi-Fi too (then set TUTTIPHON_ADMIN_PASSWORD – it turns on the login)")
    p_serve.add_argument("--port", type=int, default=8765)
    p_serve.add_argument("--no-browser", action="store_true")
    p_serve.add_argument("--unsafe-no-password", action="store_true", help="start on the network even without a password (not recommended)")

    p_run = sub.add_parser("run", help="run steps directly (without the interface)")
    p_run.add_argument("steps", nargs="*", choices=PIPELINE + ["all"], default=["all"],
                       help=", ".join(f"{k} = {v}" for k, v in STEP_TITLES.items()))
    p_run.add_argument("--deezer-mode", choices=["new", "missing", "full", "recalc"], default=None,
                       help="new = new songs only, missing = songs not found, again, full = all (can be continued), "
                            "recalc = recalculate stars from saved ranks (default: setting)")
    p_run.add_argument("--overwrite-manual", action="store_true", default=None, help="Deezer: also overwrite stars set by hand")
    p_run.add_argument("--lyrics-all", action="store_true", help="Lyrics: search again also for songs recently searched without success")
    p_run.add_argument("--full-scan", action="store_true")
    p_run.add_argument("--dry-run", action="store_true",
                       help="dry run: only show what would happen – nothing is written, Navidrome is not scanned")

    args = parser.parse_args()
    from app.config import ensure_dirs
    problem = ensure_dirs()
    if problem:
        print("✕ " + problem, flush=True)
        return 2
    if args.cmd == "run":
        steps = pipeline() if "all" in args.steps else args.steps
        from app import instances
        instances.use_cli_id()   # do not overwrite the report of a server on the same machine
        runner = TaskRunner(echo=True)
        try:
            runner.start(steps, background=False, deezer_mode=args.deezer_mode, overwrite_manual=args.overwrite_manual,
                         full_scan=args.full_scan, dry_run=args.dry_run, lyrics_all=args.lyrics_all)
        except RuntimeError as e:   # e.g. another instance is working right now
            print(f"✕ {e}", flush=True)
            return 1
        return 0 if all(r == "ok" for r in runner.results.values()) else 1

    from app.web import serve
    host = getattr(args, "host", "127.0.0.1")
    port = getattr(args, "port", 8765)
    from app.config import PASSWORD_PLACEHOLDERS, admin_password, environment, weak_password
    pw = admin_password()
    if host not in ("127.0.0.1", "localhost", "::1") and weak_password(pw):
        if not getattr(args, "unsafe_no_password", False):
            import os
            # say exactly what is wrong and where the value came from – without showing the password itself
            source = (_s("from docker-compose.yaml/environment") if admin_password(environment())
                      else _s("from the .env in the data folder"))
            if not pw:
                problem = _s("Tuttiphon is meant to be reachable on the network, but TUTTIPHON_ADMIN_PASSWORD is missing – "
                             "neither in the environment (docker-compose.yaml) nor in the .env in the data folder.")
            elif pw.strip().lower() in PASSWORD_PLACEHOLDERS:
                problem = _s("Tuttiphon is meant to be reachable on the network, but TUTTIPHON_ADMIN_PASSWORD is still the "
                             "placeholder “{placeholder}” ({source}).", placeholder=pw, source=source)
            else:
                problem = _sn(len(pw), "Tuttiphon is meant to be reachable on the network, but TUTTIPHON_ADMIN_PASSWORD has "
                                       "only {n} character ({source}).",
                              "Tuttiphon is meant to be reachable on the network, but TUTTIPHON_ADMIN_PASSWORD has only {n} "
                              "characters ({source}).", source=source)
            fix = _s("Please enter your own password with at least 8 characters in docker-compose.yaml (or in the .env "
                     "in the data folder) and restart.")
            print(f"✕ {problem} {fix}", flush=True)
            return 2
        if pw:
            print(_s("⚠ Tuttiphon is reachable on the network, but the administrator password is too short or still the "
                     "placeholder!"), flush=True)
        else:
            print(_s("⚠ Without TUTTIPHON_ADMIN_PASSWORD there is no login – Tuttiphon then only answers requests via "
                     "127.0.0.1/localhost and the names in TUTTIPHON_HOSTS."), flush=True)
    server = serve(host, port, strict=not getattr(args, "unsafe_no_password", False))
    shown = "127.0.0.1" if host == "0.0.0.0" else "[::1]" if host == "::" else f"[{host}]" if ":" in host else host
    url = f"http://{shown}:{port}/"
    from app import events
    from app.instances import IN_DOCKER
    from app.web import startup_report
    try:
        for line in startup_report():
            events.say(line)
    except Exception as e:   # noqa: BLE001 – the overview must never prevent the start
        events.say(_s("(Startup overview not possible: {error})", error=e))
    if IN_DOCKER:
        events.say(_s("Ready – port {port}", port=port))
    else:
        print(_s("Tuttiphon is running at {url}  (Ctrl+C quits)", url=url), flush=True)
    if not getattr(args, "no_browser", False):
        threading.Timer(0.8, lambda: webbrowser.open(url)).start()
    def terminate(*_args):   # docker stop / restart: like Ctrl+C – cancel the running task so it saves its progress
        raise KeyboardInterrupt
    signal.signal(signal.SIGTERM, terminate)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        from app.web import RUNNER
        if RUNNER.running():
            events.say(_s("Canceling the running task “{name}”, saving its progress …", name=RUNNER.name))
            RUNNER.cancel()
            RUNNER.thread.join(timeout=20)
        events.say(_s("Shut down."))
    return 0


if __name__ == "__main__":
    sys.exit(main())
