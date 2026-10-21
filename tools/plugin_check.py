"""End-to-end check of the Navidrome plugin (maintainers only, called by tools/plugin-check.sh): everything in a
throwaway folder – never the real Navidrome or the real data.

1. test music: 3 bands × 4 songs, generated with ffmpeg (sine tones, FLAC);
2. a fresh Navidrome (its own data folder, 127.0.0.1) with the freshly built plugin, configured and enabled through
   Navidrome's command line, as agent "tuttiphon";
3. a fresh Tuttiphon (its own data folder, 127.0.0.1, no schedules) with made-up sound vectors for those songs, a
   plugin key and a person for Navidrome's account (plays are kept only for accounts with a person);
4. questions to Navidrome's Subsonic API – getSimilarSongs2, getArtistInfo2, getSonicSimilarTracks, findSonicPath –
   whose answers have to come from Tuttiphon; plus Tuttiphon's endpoint directly (and a wrong key);
5. plays through Navidrome (scrobble, reportPlayback): a song played, the next left after 5 seconds, the one after
   played – Tuttiphon has to receive them, count the play and recognize the skip.

  python3 tools/plugin_check.py --navidrome <navidrome binary> --plugin <tuttiphon.ndp> [--keep]
"""
import argparse
import copy
import hashlib
import json
import os
import random
import secrets
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ND_PORT, TP_PORT = 4599, 8799
BANDS = {"Eisen": 0, "Stahl": 0, "Harfe": 1, "Dudel": 1, "Kita": 2, "Rassel": 2}   # band -> sound family
PER_BAND = 2
# nothing of a real setup reaches the throwaway servers – the same names tests/python/env.py removes
DROP = ("NAV_", "TUTTIPHON_", "ND_", "MUSIC_DIR", "PLAYLIST_DIR", "ARCHIVE_DIR", "BACKUP_DIR", "RATING_USERS",
        "LASTFM_API_KEY", "NTFY_TOKEN")


def say(text):
    print(text, flush=True)


def fail(text):
    raise SystemExit(f"✕ {text}")


def http(url, headers=None, data=None, method=None, timeout=30):
    req = urllib.request.Request(url, data=json.dumps(data).encode() if data is not None else None,
                                 headers={"Content-Type": "application/json", **(headers or {})}, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, json.loads(r.read() or b"null")
    except urllib.error.HTTPError as e:
        return e.code, None


def wait_port(port, proc, what, seconds=60):
    for _ in range(seconds * 4):
        if proc.poll() is not None:
            fail(f"{what} ended early (code {proc.returncode})")
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{port}/", timeout=1)
            return
        except urllib.error.HTTPError:
            return
        except OSError:
            time.sleep(0.25)
    fail(f"{what} does not answer on port {port}")


def music(folder):
    """3 sound families × 2 bands × PER_BAND songs of 125 s (more than the 120 s minimum)."""
    for b, family in BANDS.items():
        for n in range(PER_BAND):
            path = folder / b / "Album" / f"{n + 1:02d} {b} {n + 1}.flac"
            path.parent.mkdir(parents=True, exist_ok=True)
            subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-f", "lavfi", "-i",
                            f"sine=frequency={220 * (family + 1) + 20 * n}:duration=125:sample_rate=8000",
                            "-ac", "1", "-metadata", f"artist={b}", "-metadata", f"album_artist={b}",
                            "-metadata", f"album={b} Album", "-metadata", f"title={b} Song {n + 1}",
                            "-metadata", f"track={n + 1}", "-metadata", "genre=Test", str(path)], check=True)


def vectors(songs):
    """Made-up sound vectors: per family a direction, a large common part and a little noise (as test_similar.py)."""
    sys.path.insert(0, str(ROOT))
    from app import similar
    rnd = random.Random(7)
    common = [rnd.gauss(0, 1) for _ in range(similar.DIM)]
    families = [[rnd.gauss(0, 1) for _ in range(similar.DIM)] for _ in range(3)]
    out = {}
    for k, s in enumerate(songs):
        r = random.Random(k)
        fam = families[BANDS[s["artist"]]]
        out[s["id"]] = similar.encode([1.5 * c + f + 0.35 * r.gauss(0, 1) for c, f in zip(common, fam)])
    similar.STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    similar.STATE_FILE.write_text(json.dumps({"v": similar.VERSION, "dim": similar.DIM, "songs": out}))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--navidrome", required=True)
    ap.add_argument("--plugin", required=True)
    ap.add_argument("--keep", action="store_true", help="keep the throwaway folder")
    args = ap.parse_args()
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(1))   # a stopped run still stops both servers (finally)
    for port in (ND_PORT, TP_PORT):
        if subprocess.run(["ss", "-ltn"], capture_output=True, text=True).stdout.count(f":{port} "):
            fail(f"port {port} is in use")

    work = Path(tempfile.mkdtemp(prefix="tuttiphon-plugin-check-"))
    procs = []
    clean = {k: v for k, v in os.environ.items() if not k.startswith(DROP)}
    nd_pass, nd_user = "check-" + secrets.token_hex(8), "admin"
    nd_env = {**clean, "ND_MUSICFOLDER": str(work / "music"), "ND_DATAFOLDER": str(work / "nd"),
              "ND_CACHEFOLDER": str(work / "nd" / "cache"), "ND_PORT": str(ND_PORT), "ND_ADDRESS": "127.0.0.1",
              "ND_PLUGINS_ENABLED": "true", "ND_PLUGINS_FOLDER": str(work / "nd" / "plugins"),
              "ND_AGENTS": "tuttiphon", "ND_ENABLEINSIGHTSCOLLECTOR": "false", "ND_LOGLEVEL": "info",
              "ND_DEVARTISTINFOTIMETOLIVE": "1s"}
    tp_env = {**clean, "TUTTIPHON_DATA": str(work / "tp"), "TUTTIPHON_BASE": str(work / "base"),
              "TUTTIPHON_SHARED_DIR": str(work / "shared"), "TUTTIPHON_NO_SCHEDULER": "1",
              "TUTTIPHON_WEB": str(ROOT / "web")}
    try:
        say(f"▶ throwaway folder {work}")
        music(work / "music")
        (work / "nd" / "plugins").mkdir(parents=True)
        (work / "base" / "Music" / "00_SmartPlaylists").mkdir(parents=True)
        shutil.copy(args.plugin, work / "nd" / "plugins" / "tuttiphon.ndp")

        # Tuttiphon's data first (this process uses the throwaway folder from here on): key, config, credentials
        for k in [k for k in os.environ if k.startswith(DROP)]:
            del os.environ[k]
        os.environ.update(tp_env)
        sys.path.insert(0, str(ROOT))
        from app import config, sonic
        assert str(work) in str(config.DATA_DIR), "not the throwaway folder"
        key = sonic.new_key()
        cfg = config.load_config()
        cfg["settings"].update(autoApply=False, minDuration=0)
        cfg["personen"].append({**copy.deepcopy(cfg["personen"][0]), "id": "check", "name": "Check", "user": nd_user,
                                "public": False})   # plays are kept only for accounts with a person
        config.save_config(cfg)
        (work / "tp" / ".env").write_text(f"NAV_URL=http://127.0.0.1:{ND_PORT}\nNAV_ADMIN_USER={nd_user}\n"
                                          f"NAV_ADMIN_PASS={nd_pass}\n")

        # Navidrome: start, first user, then discover, configure and enable the plugin through its admin API
        nd = [args.navidrome, "--nobanner"]
        procs.append(subprocess.Popen(nd, env=nd_env, cwd=work, stdout=open(work / "navidrome.log", "w"),
                                      stderr=subprocess.STDOUT))
        wait_port(ND_PORT, procs[-1], "Navidrome")
        status, _r = http(f"http://127.0.0.1:{ND_PORT}/auth/createAdmin", data={"username": nd_user, "password": nd_pass})
        if status != 200:
            fail(f"creating Navidrome's first user: HTTP {status}")
        status, login = http(f"http://127.0.0.1:{ND_PORT}/auth/login", data={"username": nd_user, "password": nd_pass})
        if status != 200 or not (login or {}).get("token"):
            fail(f"signing in to Navidrome: HTTP {status}")
        native = {"X-ND-Authorization": f"Bearer {login['token']}"}
        http(f"http://127.0.0.1:{ND_PORT}/api/plugin/rescan", native, data={}, method="POST")
        status, _r = http(f"http://127.0.0.1:{ND_PORT}/api/plugin/tuttiphon", native, method="PUT", data={
            "config": json.dumps({"url": f"http://127.0.0.1:{TP_PORT}", "key": key}), "enabled": True, "allUsers": True})
        if status != 200:
            fail(f"configuring the plugin in Navidrome: HTTP {status} (see navidrome.log)")
        status, plugins = http(f"http://127.0.0.1:{ND_PORT}/api/plugin", native)
        mine = next((x for x in plugins or [] if x.get("id") == "tuttiphon"), None)
        if not mine or not mine.get("enabled"):
            fail(f"the plugin is not enabled in Navidrome: {mine}")
        salt = secrets.token_hex(6)
        auth = {"u": nd_user, "t": hashlib.md5((nd_pass + salt).encode()).hexdigest(), "s": salt, "v": "1.16.1",
                "c": "plugin-check", "f": "json"}

        def subsonic(method, **params):
            url = f"http://127.0.0.1:{ND_PORT}/rest/{method}?" + urllib.parse.urlencode({**auth, **params}, doseq=True)
            status, body = http(url)
            res = (body or {}).get("subsonic-response") or {}
            if status != 200 or res.get("status") != "ok":
                fail(f"{method}: HTTP {status} {res.get('error')}")
            return res

        for _ in range(120):   # the scan at the start
            st = subsonic("getScanStatus")["scanStatus"]
            if not st.get("scanning") and st.get("count", 0) >= len(BANDS) * PER_BAND:
                break
            time.sleep(0.5)
        songs = [{"id": s["id"], "artist": s["artist"], "title": s["title"], "artistId": s.get("artistId")}
                 for s in subsonic("search3", query="", songCount=100).get("searchResult3", {}).get("song", [])]
        if len(songs) != len(BANDS) * PER_BAND:
            fail(f"Navidrome found {len(songs)} songs")
        vectors(songs)
        say(f"✓ Navidrome 127.0.0.1:{ND_PORT}: {len(songs)} test songs, plugin enabled")

        procs.append(subprocess.Popen([sys.executable, "tuttiphon.py", "serve", "--port", str(TP_PORT), "--no-browser"],
                                      env={**clean, **tp_env}, cwd=ROOT, stdout=open(work / "tuttiphon.log", "w"),
                                      stderr=subprocess.STDOUT))
        wait_port(TP_PORT, procs[-1], "Tuttiphon")

        by_id = {s["id"]: s for s in songs}
        seed = next(s for s in songs if s["artist"] == "Eisen")
        family = {b for b, f in BANDS.items() if f == BANDS["Eisen"]}
        bearer = {"Authorization": f"Bearer {key}"}
        status, direct = http(f"http://127.0.0.1:{TP_PORT}/api/sonic/similar?id={seed['id']}&count=5", bearer, timeout=120)
        if status != 200 or not direct or not direct.get("songs"):
            fail(f"Tuttiphon /api/sonic/similar: HTTP {status} {direct}")
        if by_id[direct["songs"][0]["id"]]["artist"] not in family:
            fail(f"Tuttiphon's nearest song is not of the same sound: {direct['songs'][0]}")
        status, _r = http(f"http://127.0.0.1:{TP_PORT}/api/sonic/similar?id={seed['id']}", {"Authorization": "Bearer tp_wrong"})
        if status != 401:
            fail(f"a wrong key gets HTTP {status} instead of 401")
        say(f"✓ Tuttiphon 127.0.0.1:{TP_PORT}: answers with the key ({direct['ms']} ms), refuses a wrong one")

        similar = subsonic("getSimilarSongs2", id=seed["id"], count=5).get("similarSongs2", {}).get("song", [])
        if not similar:
            fail("getSimilarSongs2: no songs – the plugin did not answer (see navidrome.log)")
        if by_id[similar[0]["id"]]["artist"] not in family:
            fail(f"getSimilarSongs2: the first song is not of the same sound: {similar[0].get('artist')}")
        say(f"✓ getSimilarSongs2 (Instant Mix): {len(similar)} songs, first {similar[0]['artist']} – {similar[0]['title']}")

        sonic_tracks = subsonic("getSonicSimilarTracks", id=seed["id"], count=5)
        matches = next((v for k, v in sonic_tracks.items() if isinstance(v, (dict, list)) and k not in ("openSubsonic",)), None)
        if not matches:
            fail(f"getSonicSimilarTracks: nothing ({list(sonic_tracks)})")
        say(f"✓ getSonicSimilarTracks: {json.dumps(matches)[:160]} …")

        end = next(s for s in songs if BANDS[s["artist"]] == 1)
        path = subsonic("findSonicPath", startSongId=seed["id"], endSongId=end["id"], count=5)
        found = next((v for k, v in path.items() if isinstance(v, (dict, list)) and k not in ("openSubsonic",)), None)
        if not found:
            fail(f"findSonicPath: nothing ({list(path)})")
        say(f"✓ findSonicPath: {json.dumps(found)[:160]} …")

        artist_id = next(a["id"] for idx in subsonic("getArtists")["artists"].get("index", [])
                         for a in idx.get("artist", []) if a["name"] == "Eisen")
        for _ in range(10):   # the artist info is fetched in the background the first time
            info = subsonic("getArtistInfo2", id=artist_id, count=5).get("artistInfo2", {})
            if info.get("similarArtist"):
                break
            time.sleep(1)
        names = [a["name"] for a in info.get("similarArtist", [])]
        say(f"✓ getArtistInfo2 (similar artists): {names}" if names else "• getArtistInfo2: no similar artists (yet)")

        # plays: song z is playing, then a starts and is left after 5 s, b starts and is played to the end (the first
        # song after a pause is never judged – so z first)
        a, b = [s for s in songs if s["artist"] == "Harfe"][:2]
        z = next(s for s in songs if s["artist"] != "Harfe")
        subsonic("reportPlayback", mediaId=z["id"], mediaType="song", positionMs=100000, state="playing")
        time.sleep(1)
        subsonic("scrobble", id=a["id"], submission="false")
        subsonic("reportPlayback", mediaId=a["id"], mediaType="song", positionMs=5000, state="playing")
        time.sleep(1)
        subsonic("scrobble", id=b["id"], submission="false")
        subsonic("reportPlayback", mediaId=b["id"], mediaType="song", positionMs=0, state="starting")
        subsonic("reportPlayback", mediaId=b["id"], mediaType="song", positionMs=120000, state="playing")
        subsonic("scrobble", id=b["id"], submission="true", time=int(time.time() * 1000) - 120000)
        from app import listen, rueckblick
        import datetime as dt
        today = dt.date.today()
        for _ in range(40):   # Navidrome hands plays on in the background
            evs = listen.events(nd_user, today - dt.timedelta(days=1), today)
            if any(e["k"] == "play" for e in evs):
                break
            time.sleep(0.5)
        kinds = sorted({e["k"] for e in evs})
        if "play" not in kinds or "start" not in kinds:
            fail(f"Tuttiphon did not receive the plays (got {kinds}) – see navidrome.log")
        skipped = listen.skips(nd_user, today - dt.timedelta(days=1), today)
        if a["id"] not in skipped or b["id"] in skipped:
            fail(f"skip not recognized: {skipped}")
        counted, _days = rueckblick.plays_between(nd_user, today - dt.timedelta(days=2), today)
        if counted.get(b["id"]) != 1:
            fail(f"the play is not in the recap: {dict(counted)}")
        say(f"✓ plays through Navidrome: {len(evs)} events ({', '.join(kinds)}), the left song counts as skipped, "
            "the played one in the recap")

        status, plugin_status = http(f"http://127.0.0.1:{TP_PORT}/api/plugin")
        if status != 200 or not plugin_status.get("lastCall"):
            fail(f"Tuttiphon does not show the plugin's last request: {status} {plugin_status}")
        say(f"✓ Tuttiphon saw {plugin_status['calls']} requests of the plugin")
        say("✓ plugin check passed")
    finally:
        for p in procs:
            if p.poll() is None:
                p.send_signal(signal.SIGTERM)
                try:
                    p.wait(10)
                except subprocess.TimeoutExpired:
                    p.kill()
        if args.keep:
            say(f"  kept: {work}")
        else:
            shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    main()
