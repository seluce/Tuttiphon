# 08 – Operations

This chapter describes how Tuttiphon runs on the PC and in the Docker container, where it stores its files, and how to
update it (version, changelog, release) and back it up. It also explains what happens when two instances are running,
and how to find errors (history, logs, server log).
The internal structure of the process is described in [Architecture](01-architecture.md), the content of the data files
in [Data model](02-data-model.md).

## Requirements

| Component | used for | on the PC | in the Docker image |
|---|---|---|---|
| Python 3 | server and runs (standard library only) | system package | `python:3.12-slim` |
| `ffmpeg`, `ffprobe` | Opus conversion, sound analysis, reading tags of new files | install | included |
| Pillow | designed playlist covers; without Pillow there are only “Album cover” and your own pictures | optional (`python3-pil`) | `pillow==11.3.0` |
| DejaVu Sans Bold | font on designed covers; if it is missing, Pillow uses its default font | optional | `fonts-dejavu-core` |
| Essentia (`essentia-tensorflow`, NumPy) and the AI models | AI sound analysis; without them the AI stays off, everything else works | usually not installed (models: `python3 app/ml_worker.py --download models`) | `essentia-tensorflow==2.1b6.dev1389`, `numpy==2.5.4`, models in `/app/models` |
| `fpcalc` (Chromaprint) | audio fingerprints for “Same recording twice” in Check library; without it the check stays off (“not installed”) | optional (package `libchromaprint-tools`, or `TUTTIPHON_FPCALC` = path of the program) | `libchromaprint-tools` |
| Node.js ≥ 22 with npm | building the interface (`npm run build`) | only for building | only in the build stage |
| `curl`, `xdg-open` | `tuttiphon.sh`: is a server already running? open the browser | for `tuttiphon.sh` | `curl` for the health check |
| music folder, Navidrome | reading and writing files, API | mount of the NAS share, e.g. via NFS (`TUTTIPHON_BASE`) | volumes, network |

## Running on the PC

### Starting with `tuttiphon.sh`

`./tuttiphon.sh` without arguments:

1. changes to the project folder, reads the optional file `dev.local.env` there (not in Git; e.g.
   `TUTTIPHON_BASE=/path/to/navidrome-folder`, `TUTTIPHON_TEST_USER=<account>`) and sets
   `TUTTIPHON_DATA=<project>/data` (only if it is not set yet). Without `TUTTIPHON_BASE`, the folder above the project
   folder counts as the Navidrome folder,
2. queries `http://127.0.0.1:8765/api/config`. If a server already answers there, the script only opens the browser
   and exits,
3. builds the interface if needed (see below),
4. starts `python3 tuttiphon.py serve --port 8765`. The server binds to `127.0.0.1` and opens the browser after
   0.8 s.

Without an administrator password there is no sign-in on the PC: whoever opens `http://127.0.0.1:8765` is
administrator. Once one is set – under Settings → Users & permissions, or as `TUTTIPHON_ADMIN_PASSWORD` in
`data/.env` –, sign-in is turned on on the PC as well – see [Security](07-security.md).

The script passes all other calls on to `tuttiphon.py` (`./tuttiphon.sh run …`). Options and exit codes:
[Command line](01-architecture.md#command-line).

### Building the interface

`tuttiphon.sh` builds the interface only when started without arguments, as follows:

- If `web/index.html` exists and nothing in `frontend/`, `package.json`, `package-lock.json` or
  `vite.config.js` is newer, it builds nothing.
- Without `npm`, an existing build stays in use. If there is none, the script aborts with “Tuttiphon: the interface
  needs Node.js (npm run build).”
- If `node_modules/` is missing or `package-lock.json` is newer than `node_modules/.package-lock.json`,
  `npm ci --no-audit --no-fund` runs first.
- Then `npm run build` (Vite builds `frontend/` into `web/`).

By hand: `npm ci` once, then `npm run build` or `npm run watch`. If the build is missing, the server answers `/`
with HTTP 503 and a note to build the interface. Structure of the frontend: [Interface](09-interface.md).

### Menu entry

`./tuttiphon.sh install-launcher` creates `~/.local/share/applications/tuttiphon.desktop`. Name “Tuttiphon”, icon
`multimedia-player`, `Exec` points to `tuttiphon.sh` in the project folder, `Terminal=false`. A server started this way
has no visible terminal; its output cannot be seen (the logs of the runs are still written to `logs/`).

### Directly with `python3`

`python3 tuttiphon.py …` without `tuttiphon.sh` works as well. The data folder is then also `data/` in the project
folder (created if it is missing – never the project folder itself). `dev.local.env` is not read, so `TUTTIPHON_BASE` falls back to the folder **above the project folder**
unless it is set in the environment. The default music
folder then points nowhere (unless the storage locations are set with absolute paths in the settings; relative paths
are also resolved relative to `TUTTIPHON_BASE`). So set it beforehand:

```bash
TUTTIPHON_BASE=/path/to/navidrome-folder python3 tuttiphon.py run playlists --dry-run
```

### Scheduled runs without the interface

`tuttiphon.py run` is meant for cron or a systemd timer, for example:

```bash
# crontab -e: update everything every morning at 04:00
0 4 * * * /path/to/Tuttiphon/tuttiphon.sh run >/dev/null 2>&1
```

If a server or another instance is currently working on a run, `run` does not start: it prints “✕ Another Tuttiphon
instance (PC or Docker) is working right now – please try again later.” and exits with code 1 (see
[Multiple instances](#multiple-instances)). A running server does the daily refresh on its own anyway
([Schedule](01-architecture.md#the-schedule-daily_loop)).

### Stopping

In the terminal with Ctrl+C. `SIGTERM` (e.g. `kill <pid>` or `docker stop`) has the same effect: if a run is in
progress, `tuttiphon.py` cancels it (“Canceling the running task “<name>”, saving its progress …”) and waits up to
20 s for it to save its progress; then the process ends with “Shut down.” in the server log. Otherwise, look up the
process ID via the port and stop exactly that process:

```bash
ss -ltnp | grep :8765      # shows users:(("python3",pid=12345,…))
kill 12345
```

Do not use `pkill -f`/`pgrep -f` with a pattern like `tuttiphon`: it also hits your own shell if its command line
contains the pattern.

## Docker

### The image (`Dockerfile`)

The ready-made image `ghcr.io/seluce/tuttiphon` is built by GitHub Actions (`.github/workflows/docker.yaml`) when a
release is published on GitHub – tags: the version number (e.g. `1.0.0`) and `latest`, for `linux/amd64` only.
`latest` moves only when the tag is GitHub's newest release (`gh api repos/…/releases/latest` – never a pre-release or
a draft); a pre-release, or an older version built again by hand, gets only its version tag. The workflow only builds
from a version tag that matches `VERSION` in `app/version.py` (with or without a leading `v`); a manual run (“Run
workflow”) must also be started from such a tag, otherwise it stops with an error. The version reaches the shell steps
via `env:` (not inserted into the script text), and the `concurrency` group `docker-image` lets only one build run at
a time (a running one is not canceled). It builds with `MODELS_REQUIRED=1`, so a published image never lacks the AI
models. Building it yourself uses the same `Dockerfile` (see [Updates](#updates)).

**Publishing the first time:** GitHub creates the package `tuttiphon` as **private** with the first push. Set it to
public once (package settings on GitHub → “Change visibility”), otherwise `docker compose pull` asks for a sign-in.

The image is built in two stages:

1. **Build stage `ui`** (`node:22-slim`): copies `package.json`, `package-lock.json`, `vite.config.js`, runs
   `npm ci`, copies `frontend/` (including `svelte.config.js`, which compiles every component with runes) and runs
   `npm run build`. Result: `/src/web`, with `third-party-licenses.md` – the licenses of the bundled packages, which
   the minified files no longer carry (`build.license` in `vite.config.js`).
2. **Runtime** (`python:3.12-slim`): installs `ffmpeg`, `curl`, `tzdata`, `fonts-dejavu-core`, `libchromaprint-tools`
   (`fpcalc` for the audio fingerprints), Pillow 11.3.0, NumPy 2.5.4 and `essentia-tensorflow` (AI sound analysis,
   about 700 MB extra in the image). In a layer of its own,
   only `app/ml_worker.py` goes into the image first and downloads the AI models (`python3 app/ml_worker.py --download
   /app/models`, about 30 MB, with checksums) – so they are not downloaded again on updates. Each file gets three
   attempts with pauses of 10 and 30 s (`WAITS`); if essentia.upf.edu does not answer even then, the remaining files
   come from the copy in the pre-release `ai-models-v1` of the repository (`MIRROR`, one zip, the same checksums;
   made once by hand with the workflow “AI models copy”, `.github/workflows/models.yaml`; `TUTTIPHON_MODELS_MIRROR`
   overrides the address, empty = no copy). If the download fails,
   a build of your own still finishes (note “⚠ AI models not loaded …” in the build log); the AI sound analysis then
   reports “AI models missing”. With the build argument `MODELS_REQUIRED=1` (the published image) the build stops
   instead. After that the build copies `tuttiphon.py`, `CHANGELOG.md` (for `GET /api/changelog` and “What’s new?”),
   `LICENSE`, `THIRD-PARTY-NOTICES.md`, `app/` and the built folder `web/` to `/app` and makes everything there
   readable for everyone (`chmod -R a+rX /app`). Node, `frontend/` and `node_modules/` are not in the finished image.

| Entry | Value |
|---|---|
| Environment | `TUTTIPHON_DOCKER=1`, `TUTTIPHON_DATA=/config`, `TUTTIPHON_BASE=/nas`, `TUTTIPHON_MODELS=/app/models`, `TZ=Europe/Berlin`, `HOME=/tmp`, `PYTHONDONTWRITEBYTECODE=1`, `PYTHONUNBUFFERED=1` |
| Folders | `/config`, `/music`, `/archive` and `/backup` are created; `/config` is writable for everyone in the image (`chmod 777`); `/app/models` with the AI models |
| `USER` | `1000:1000` – the image doesn't run as root by default; `user:` in `docker-compose.yaml` overrides it |
| `VOLUME` | `/config` (music folder, archive and backups are mounted via `docker-compose.yaml`) |
| `EXPOSE` | `8765` |
| `HEALTHCHECK` | every 60 s `curl -fs -o /dev/null http://127.0.0.1:8765/login.html`, timeout 5 s, start period 60 s |
| `CMD` | `python3 tuttiphon.py serve --host 0.0.0.0 --port 8765 --no-browser` |

`.dockerignore` lets only `Dockerfile`, `tuttiphon.py`, `CHANGELOG.md`, `LICENSE`, `THIRD-PARTY-NOTICES.md`, `app/`,
`frontend/`, `package.json`, `package-lock.json` and `vite.config.js` into the build context, without `__pycache__` and `node_modules`. Data,
credentials and a build from the PC thus never get into the image.

### `docker-compose.yaml`

| Key | Value in the template | Meaning |
|---|---|---|
| `image` | `ghcr.io/seluce/tuttiphon:latest` | the ready-made image; a version number instead of `latest` stays on that version. Building it yourself: `build: .` with `image: tuttiphon:local` instead (noted in the template; `release/` from `npm run release` has it switched already, with `pull_policy: build`) |
| `container_name` | `tuttiphon` | |
| `restart` | `unless-stopped` | restart after a crash and after a NAS reboot |
| `init` | `true` | an init process as PID 1 (clean shutdown, subprocesses such as `ffmpeg` are cleaned up) |
| `stop_grace_period` | `30s` | how long `docker stop` waits after `SIGTERM` before killing the container – time for Tuttiphon to cancel a running run and save its progress (up to 20 s, see [Stopping](#stopping)) |
| `hostname` | `tuttiphon` | fixed identifier of the instance (`docker:tuttiphon`, see [Multiple instances](#multiple-instances)); without it, every newly created container – e.g. after an update – would get a new identifier (the notice “Tuttiphon is running twice” still recognizes it by the installation ID) |
| `user` | `"1000:1000"` | UID:GID that Tuttiphon runs as – the owner of the music files (`ls -n` in the music folder shows the numbers); overrides the image's default `USER 1000:1000` |
| `ports` | `8765:8765` | interface at `http://<NAS-IP>:8765` |
| `logging` | `json-file`, `max-size 10m`, `max-file 3` | container output at most 30 MB (Tuttiphon has its own logs in `config/logs/`) |
| `mem_limit` | `2g` | upper limit; in operation about 130–300 MB, during the night analysis with the AI up to about 1.6 GB (see [Memory and CPU](#memory-and-cpu)) |
| `volumes` | see below | |
| `environment` | `TZ`, `NAV_URL` (example `http://192.168.1.10:4533`), `MUSIC_DIR=/music`, `ARCHIVE_DIR=/archive`, `BACKUP_DIR=/backup` – no password: it is set in the browser at the first start ([below](#first-start-administrator-password)); optional (listed in [Installation → Configuration](installation.md#configuration)): `TUTTIPHON_ADMIN_PASSWORD`, `NAV_ADMIN_USER`, `NAV_ADMIN_PASS`, `NAV_PUBLIC_URL`, `LASTFM_API_KEY`, `TUTTIPHON_TRUSTED_PROXIES` (example `172.16.0.0/12`, see [Reverse proxy](#reverse-proxy-https)) | all variables: [Environment variables](01-architecture.md#environment-variables) |

Values set in `environment` take precedence over `/config/.env`, and the interface cannot change them (the fields are
locked). Empty values such as `NAV_ADMIN_PASS: ""` do not count; then the `.env` applies.

### Volumes

| In the container | Content | Template | Note |
|---|---|---|---|
| `/config` | data folder: `config.json`, `.env`, `state/`, `logs/`, `backup/`, `sicherungen/` | `./config` (next to `docker-compose.yaml`) | must be writable for `user:` |
| `/music` | the music folder Navidrome reads (`MUSIC_DIR`), containing the playlist folder `00_SmartPlaylists/` | `/path/to/music` (to change) | Navidrome scans it. Tuttiphon writes playlists, lyrics, Opus and cover files there, and the instance status and run lock in the hidden folder `00_SmartPlaylists/.tuttiphon/`. Enter the admin access under Settings → Navidrome after the first start |
| `/archive` | archive of the originals after conversion to Opus/AAC (`ARCHIVE_DIR`) | `/path/to/music-archive` (to change) | an existing folder, writable for `user:`, **outside the music folder**. Tuttiphon never creates it: if it is missing (not mounted) or not writable, the conversion with “original to the archive” converts nothing and says why. It may be on a different volume from the music: `opus.move_to_archive` copies as `.…part`, checks the size, renames and only then deletes the original |
| `/backup` | daily backups (`BACKUP_DIR`) | `./backups` (next to `docker-compose.yaml`) | create beforehand, writable for `user:`; better a folder on a different disk |

The image also sets `TUTTIPHON_BASE=/nas`. It only matters for defaults and relative paths: without `MUSIC_DIR` the
music folder is `/nas/Music` (without `ARCHIVE_DIR` the archive `/nas/Archiv`), and relative paths for the music
folder and the backup folder refer to `/nas`. The template sets all three folders with absolute paths, so `/nas` plays
no role there.
Installations that mount the whole Navidrome folder at `/nas` (e.g. with `MUSIC_DIR=/nas/Music`) work as well.
If the music is on another device, an NFS volume works (example in [Installation](installation.md#music-on-another-device)).

Navidrome must see the playlist folder as part of its library. The folder name must be the same for Tuttiphon and
Navidrome ([Architecture](01-architecture.md#what-tuttiphon-creates-and-changes-in-navidrome)).

### Users and permissions

- Tuttiphon runs as the `user:` from the compose file (without `user:` as `1000:1000` from the image, never as root).
  New files belong to this user. Find the UID/GID on the NAS with `id <user>` or `ls -n` in the music folder.
- A mounted folder keeps the NAS permissions; `chmod 777` from the image has no effect there. So create the folder for
  `/config` beforehand and give `user:` write access. Otherwise the start ends with “The data folder /config is not
  writable …” (code 2), and `restart: unless-stopped` restarts the container over and over.
- `user:` needs read and write access to the music folder (`/music`), the archive (`/archive`) and the backup folder
  (`/backup`).
- Tuttiphon creates the shared folder `<playlist-folder>/.tuttiphon/` with permissions `0777`, the files in it with
  `0666`. That way the PC (via NFS) and the container can both write to it even when they run as different users.
  Because everyone may write there, Tuttiphon never follows links in it
  ([Shared folder](#shared-folder-of-the-instances)).
- New Opus/AAC files and archive folders belong to the user Tuttiphon runs as (`user:`). If the setting `opus.owner`
  is set (`UID:GID`; default empty, installations from before 0.17.1 keep `1000:10`), Tuttiphon applies it via `chown` –
  this only works with sufficient permissions; otherwise the owner silently stays as it is.

### Memory and CPU

| Part | Memory | CPU |
|---|---|---|
| Server at rest | about 130–300 MB with 25,000 songs: without AI data at the lower end; with AI results (about 75 MB in memory), sound vectors and the song lists of the accounts in use (about 10–20 MB each, released after 10 minutes) towards the upper end. For a moment up to about 100 MB more, e.g. when the AI results are read again after a save of the run (once, even with parallel requests) | low at rest. Opening the playlists the first time after a start or a new song list takes a few seconds (the rules of all music worlds are evaluated once per song list and shared with the account lists); the sound analysis uses `analysis.workers` simultaneous ffmpeg calls with `nice 10` (0 = half the number of cores) |
| AI sound analysis | about 850 MB extra, only while the analysis process runs (TensorFlow and models; freed again afterwards) | separate process with `nice 10`, bound to at most `analysis.mlThreads` cores (default 2) |
| Audio fingerprints | while the `analyse` step works on them, about 2–3 × the size of `state/fingerprints.json` extra (about 70 MB for 22,000 songs: the file, the comparison, saving) – given back afterwards | `analysis.workers` simultaneous `fpcalc` calls with `nice 19`; comparing 22,000 songs takes about 10 s |
| Night analysis (worst case) | server as above plus the AI process and the fingerprint comparison – up to about 1.6 GB of the 2 GB of the template | |

The template limits the container with `mem_limit: 2g`. If memory runs out and the analysis process crashes,
Tuttiphon restarts it; after more than three crashes the AI stops for this run (“… keeps crashing (not enough
memory?) …”) – the server itself is not affected, because it never loads TensorFlow. The big first pass is done by the
night analysis (default 01:00–05:00), so that Navidrome stays smooth during the day
([Maintenance](05-maintenance.md#night-analysis)). One song takes a few seconds on the NAS; the first pass over the
whole library spans several nights.

### First start: administrator password

The container starts with `--host 0.0.0.0`, so it never runs without sign-in. The password of the
[local administrator](07-security.md#local-administrator) – Tuttiphon's own administrator account, the way in when
Navidrome cannot be reached – is set in the browser at the first start; the template `docker-compose.yaml` contains
none:

1. Without any administrator password the server starts in [setup mode](07-security.md#setup-mode) and writes a
   one-time setup code to the container log (`docker logs tuttiphon`, or the log of the container in the Docker app of
   the NAS): “No administrator password yet – open Tuttiphon in the browser and set it with the setup code.” and on a
   line of its own “Setup code: XXXX-XXXX  (also in setup-code.txt in the data folder)” – search the log for
   “Setup code:”. The same code is in `/config/setup-code.txt` (`./config/setup-code.txt` next to
   `docker-compose.yaml`); it stays the same across restarts and is written to the log again at every start and
   whenever the setup page is opened (at most every 2 minutes, `localadmin.remind()`), so it is near the end of the log.
   The setup page explains both places.
2. `http://<NAS-IP>:8765` shows the setup form: setup code, new password (at least 8 characters) twice. Afterwards the
   browser is signed in as local administrator, only a hash of the password is kept (`/config/state/admin_password.json`),
   and `setup-code.txt` is gone. The code proves that whoever sets the password has access to the server – otherwise
   the first stranger to open the page would become administrator.
3. Changing it later: Settings → Users & permissions, card “Local administrator” (current password, new one twice).
   Forgotten: delete `config/state/admin_password.json` – within about 10 s Tuttiphon waits for the setup again and
   logs a new code. User-facing description: [Installation](installation.md#installation).

Alternatively the password can be set in plain text as `TUTTIPHON_ADMIN_PASSWORD` in `environment` or in
`/config/.env` (`$` written as `$$` in the compose file). It wins over one set in the browser and can then only be
changed there (the interface shows a note instead of the form). It must not be weak: `tuttiphon.py` refuses the start
(code 2) if it is shorter than 8 characters or the placeholder `change-me` (`config.PASSWORD_PLACEHOLDERS`) in any
spelling – `Change-Me`, `CHANGE-ME`, also with spaces around it (`config.weak_password()`). The message is in the
container log and names the placeholder or the number of characters and whether the value comes from
`docker-compose.yaml` or from the `.env`.

If the variable becomes weak while the container is running (e.g. the `.env` in `/config` was edited), Tuttiphon
answers every request with HTTP 503 “Tuttiphon is locked: TUTTIPHON_ADMIN_PASSWORD is too short or still the
placeholder – please set at least 8 characters.” until a proper password is back – within 10 s, without a restart
([Security](07-security.md#running-without-a-password)). Meanwhile the health check fails as well (`curl -f` on
`/login.html` gets the 503), so Docker shows the container as unhealthy. In setup mode the health check stays green:
`/login.html` is public.

### Setup

1. Create a project folder on the NAS (e.g. `/volume1/docker/tuttiphon`) and put the template `docker-compose.yaml`
   into it. To build the image yourself instead, the files from `.dockerignore` go there as well (or the contents of
   `release/`, see [Updates](#updates)); Node on the NAS is not needed.
2. In `docker-compose.yaml`, adjust the lines marked `CHANGE`: `user:`, the music folder and the archive, `TZ` and
   `NAV_URL`. A password doesn't go there (step 5).
3. Create the folders for `/config` (`./config`), `/backup` (`./backups`) and the archive beforehand and give `user:`
   write access – a folder that Docker creates for a missing bind mount belongs to `root:root`, and the container
   then ends with code 2 and restarts over and over. In the project folder, with the numbers from `user:`:
   `mkdir -p config backups /path/to/music-archive && chown 1000:1000 config backups /path/to/music-archive`.
4. Start the project: `docker compose up -d` (pulls the image; building it yourself: `docker compose up -d --build`).
   UGREEN: Docker → Project → Create; Synology: Container Manager → Project → Create.
5. Open `http://<NAS-IP>:8765`: the sign-in page asks for the **setup code** and the new password of the local
   administrator ([above](#first-start-administrator-password)); the code is in the container log and in
   `config/setup-code.txt`. With `TUTTIPHON_ADMIN_PASSWORD` in the compose file, sign in as “Local administrator”
   instead. On a new installation the **setup assistant** opens next: it checks the connection to
   Navidrome (enter the admin access there if it is not in the compose file) and asks step by step what Tuttiphon
   should do – conversion (off until you choose it), lyrics, the sound analysis, Deezer stars, what runs by itself.
   Nothing but the connection is saved before “Finish”; a first run only starts if you ask for it. Skipped or closed,
   it is under Settings → General ([Interface](09-interface.md#setup-assistant)). Existing installations don't get
   it after an update – they keep their settings.

### Reverse proxy (https)

For https, put a reverse proxy in front (e.g. pointing to `http://<NAS-IP>:8765`) – notifications through the app need
it. Then also set `TUTTIPHON_TRUSTED_PROXIES` in `environment` (or in `/config/.env`): the address from which the
proxy connects to Tuttiphon, or its network, comma-separated, e.g. `172.16.0.0/12` for the usual Docker networks.

- Only then does the sign-in lockout count each person's own address (from `X-Forwarded-For`). Without it, every
  request seems to come from the proxy: failed attempts of strangers then also block sign-in for the family.
- Sign-ins via https (`X-Forwarded-Proto: https`) get a session cookie with `Secure` – the browser never sends it
  unencrypted.
- The proxy must append the client address to `X-Forwarded-For` and set `X-Forwarded-Proto`. Name it as narrowly as
  possible: whoever connects from a listed address can claim any address.

Details: [Security](07-security.md#behind-a-reverse-proxy).

## Storage locations

### Data folder

`TUTTIPHON_DATA`, otherwise always `data/` in the project folder – never the project folder itself (otherwise backups
with credentials could end up in Git). On the PC `tuttiphon.sh` sets `<project>/data`, in the container it is
`/config`. At startup, `config.ensure_dirs()` creates the folder with `state/`, `logs/` and `backup/`, checks with `.schreibtest` whether the folder is writable, and sets `.env`,
`state/secret` and `state/sessions.json` to permissions `0600` (if that fails, e.g. because of a different owner,
Tuttiphon runs anyway).

### Music, playlists, archive – `config.paths()`

For each of the three folders: **environment > settings > default**.

| Folder | 1. Environment | 2. Setting | 3. Default | a relative path refers to |
|---|---|---|---|---|
| Music | `MUSIC_DIR` | `settings.paths.music` | `<TUTTIPHON_BASE>/Music` | the Navidrome folder `TUTTIPHON_BASE` |
| Playlists | `PLAYLIST_DIR` | `settings.paths.playlists` | `settings.playlistDir`, default `Music/00_SmartPlaylists` → `<music>/00_SmartPlaylists` | the music folder |
| Archive | `ARCHIVE_DIR` | `settings.paths.archive`, then `settings.opus.archiveDir` | `Archiv` | the folder above the music folder |

```json
"paths": { "music": "/volume1/Musik", "playlists": "00_SmartPlaylists", "archive": "Musik-Archiv" }
```

Empty values (`""`) mean “not set”. Older values of `playlistDir` without `Music/` at the beginning are relative to
`TUTTIPHON_BASE`. The settings validation rejects relative paths containing `..`.

In addition: the playlist folder is always **inside the music folder**. If the setting points elsewhere,
`playlists.playlist_dir()` writes to `<music>/00_SmartPlaylists`, because that is the only place where Navidrome
reads the playlists. The archive, on the contrary, must lie **outside the music folder** (neither the music folder
itself nor a folder inside it – the originals there would be converted again): the settings validation refuses it
(`config.archive_in_music()`), and if the environment sets such an archive, the conversion does not run.

Under Settings → Storage locations, the interface shows for each folder its path, its source (`docker` = from the
environment, `einstellung` = from the settings, `standard` = default) and whether it exists and is writable
(`config.paths_info()`). `POST /api/paths/check` checks new values before saving, including whether the playlist
folder is inside the music folder (`insideMusic`) and the archive is not (`archive.insideMusic`; such an archive is
answered with an error).

### Shared folder of the instances

Instance status files and the run lock are not in the data folder, but in a folder that all instances can see
(`instances.shared_dir()`):

1. `TUTTIPHON_SHARED_DIR`, if set (`tools/testserver.sh` sets `<work-dir>/shared`),
2. otherwise `<playlist-folder>/.tuttiphon/` (the playlist folder as determined by `playlists.playlist_dir()`),
3. if this folder cannot be created or is not writable (or the settings cannot be read):
   `state/` in the data folder.

The folder is created when needed (permissions `0777`) and determined anew at most once a minute. Navidrome does not
read hidden folders as music or playlists.

Everyone may write into this folder, so Tuttiphon never follows a link there: if `.tuttiphon/` itself is a symlink,
it falls back to `state/`; the permissions are set through the opened folder and the opened files (`fchmod`), never
via the path; `task.lock` is opened with `O_NOFOLLOW`, a link in its place is removed first; status files are
written with `write_atomic()` (`O_EXCL | O_NOFOLLOW`). Status files that are broken (e.g. `ts` not a number) are
skipped.

## Updates

**On the PC:**

1. Stop the running Tuttiphon. Otherwise `tuttiphon.sh` only opens the browser to the old version that is still running.
2. Replace the files (e.g. `git pull`).
3. Start `./tuttiphon.sh`. The script rebuilds the interface if the sources are newer, and runs `npm ci` if
   `package-lock.json` has changed.

**Version and changes:** The program version is in `app/version.py` (`VERSION`). Between releases it is the last
released version with `+dev`, and new items are collected in `CHANGELOG.md` under `## Unreleased` (`npm run release`
then marks the folder as not released; the image workflow never builds such a version). For a release the version is
set and the section becomes `## <version>` – without a date – with items `- …`; if `docker-compose.yaml` has to be replaced during the update, this is stated there explicitly. The version
appears in the first line of the [server log](#server-log), in `GET /api/status` (`version`, also for users)
and under Settings → General → “About Tuttiphon”; there, “What’s new?” shows administrators the last five
sections (`GET /api/changelog`). It has nothing to do with the version of the configuration (`CONFIG_VERSION`, below).

**Docker with the ready-made image:** in the project folder `docker compose pull && docker compose up -d` (or, in the
Docker app of the NAS, pull the image and recreate the project). `/config` is kept. A version number instead of
`latest` in `image:` stays on that version.

**Docker, building it yourself:** `npm run release` builds `release/` with exactly the files for the server
(`tools/release.sh`: fixed list – `frontend/` goes in as a whole without `node_modules`, like `COPY frontend` in the
`Dockerfile`, so `svelte.config.js` is never missing –, `LICENSE` and `THIRD-PARTY-NOTICES.md`, `docker-compose.example.yaml`
from the template switched to `build: .` with `image: tuttiphon:local` and `pull_policy: build`, and a `README.txt`
with date, Git state, the lines marked `CHANGE` including `user:` and `TZ`, the folders to create for `user:` before
the first start, and the section of the current version from `CHANGELOG.md`). Beforehand, the script
checks the following and aborts on any error: `VERSION` from `app/version.py` present, `CHANGELOG.md` has a section
`## <VERSION> …`, `py_compile` for `app/*.py` and `tuttiphon.py`, translations complete, Python tests green,
interface builds without errors and without warnings. The logs of these checks go into a private temporary folder
(`mktemp -d`, `tuttiphon-release.XXXXXX` under `$TMPDIR` or `/tmp`); an error message names the log file. Copy the content except `first-install/` into the project folder (your own `docker-compose.yaml` or `.yml`
stays – the release names its template `docker-compose.example.yaml` on purpose: Docker Compose prefers a
`docker-compose.yaml` over a `docker-compose.yml` in the same folder) and recreate the project (or `docker compose up -d --build`). `/config`
is kept. Only for moving an existing installation (e.g. from a PC), `npm run release:with-data` additionally creates
`release/first-install/config/` from `data/` – the same selection as a backup, without `secret` and the old
`instances.json`; that is why `release/` is in `.gitignore`. Docker only rebuilds the layers with the packages and the
AI models when `Dockerfile` or `app/ml_worker.py` has changed.

**Going back to an older version (downgrade):** there is no migration backwards. Before the update, “Back up now”
under Settings → Backup is the safe point to return to. To go back: stop the container and set `image:` to the older
version number (e.g. `ghcr.io/seluce/tuttiphon:0.16.0`; building it yourself: the `release/` folder of that version).
If the newer version migrated `config.json` (`CONFIG_VERSION` went up – the update then left
`backup/config_v<old>_<YYYYMMDD_HHMMSS>.json` in the data folder), copy that file back as `config.json`, or restore the
backup from before the update ([Built-in backup](#built-in-backup-appbackuppy)); settings changed since the update are
lost. Then start the container again. Without a migration the older version reads `config.json` as it is. From 0.17.1
on, the validation ignores sound filter keys it doesn't know yet (e.g. written by a newer version); older versions
refuse to save settings that contain such keys.

**Configuration:** If `config.json` is older than the current version (`CONFIG_VERSION`), `load_config()` migrates it
by itself on the first load. Before that, it uses `write_atomic()` to save a copy as
`backup/config_v<old>_<YYYYMMDD_HHMMSS>.json` ([Data model](02-data-model.md)). It adds missing settings
from `app/default_config.json`.

**Browser:** The server delivers `index.html` and `login.html` with `Cache-Control: no-cache`, and files under
`/assets/` (content hash in the name) as `immutable` for one year. The service worker (`sw.js`) loads from the server
first and falls back to the last loaded interface only when offline. So after an update, reloading is enough.

## Notifications

Tuttiphon sends short messages to your phone (`app/notify.py`) – through the app itself and, if you like, additionally
through [ntfy](https://ntfy.sh). Both are turned on under Settings → Notifications; there is also a switch per event
there.

| Event | to | when |
|---|---|---|
| `failed` | administrators' devices, the administrator's topic | a step of a run ends with an error (`notify.after_run()`) |
| `newMusic` | administrators' devices, the administrator's topic | folder watch has finished processing new music |
| `autoAssigned` | administrators' devices, the administrator's topic | bands were automatically assigned to a music world |
| `favorites` | devices of the person's account, their topic (`person.push`) | an album by a favorite band was added in the last 3 days (after the scan, once per album) |
| `review` | devices of the person's account, their topic | in the first three days of the month, if the person has a recap playlist “Your month” |
| `weekly` | devices of the person's account, their topic | “New for you this week” on Monday (still on Tuesday if no run came on Monday), if the person has an active “Discovered for you” or “Album of the week” that renews weekly and was renewed this week: how many never played songs and which album – to the topic once per person and week; the devices of an account once per week with what is new for all its people (own people first); tapping opens the first of them |

Each event is sent only once (`state/notified.json`). If two people share the same Navidrome account (such as
“Familie” and the administrator), each device still gets the message only once: `favorites` once per album and
account (`favpush|…`), `review` once per month and account (`reviewpush|…`, the first person's recap), `weekly` once
per week and account (`weeklypush|…`, with what is new for all its people); every person's own ntfy topic gets its
own message. A playlist without `person` counts for the default person.

### Via the app (web push)

No extra app and no third-party account (`app/webpush.py`): each device signs up once – administrators under
Settings → Notifications → “This device”, everyone else in their profile under “To your phone” → “Turn on for this
device”. The browser asks for permission.

- **https required:** browsers only allow this when Tuttiphon is opened via `https` (or as `localhost`). So use the
  address via the reverse proxy, not `http://<NAS>:8765`.
- **iPhone/iPad** (iOS 16.4 and later): only if Tuttiphon has been added to the home screen and is opened from there.
  **Android:** in the browser and as an installed app.
- **Message path:** Tuttiphon sends the message to the browser's push service (Google for Chrome/Android, Mozilla,
  Apple, Microsoft), which delivers it. It is end-to-end encrypted – the service only sees that something is coming.
  The container needs internet access for this; the `cryptography` package is in the Docker image.
- Tapping opens Tuttiphon on the matching page (at the address through which the device was signed up).
- At most 10 devices per account are remembered (`state/push.json`). If the push service reports a device as expired
  (app deleted, permission revoked), it is dropped. Tuttiphon creates the sender key (`state/push_keys.json`) the
  first time; it is included in the backup – if it is lost, every device has to be turned on again.

### Via ntfy

Free via ntfy.sh or your own ntfy server, e.g. as another container on the NAS.

1. Install the ntfy app on the phone.
2. Settings → Notifications → “Via ntfy”: keep the server or enter your own, choose a topic of your own
   (only letters, digits, `-`, `_`) and “Send test”. Under “Tuttiphon address”, enter the address at which
   Tuttiphon can be reached from the phone – tapping the message then opens the matching page.
3. Subscribe to the same topic in the app. People enter their own topic in their profile under “Or via the ntfy app”.

Messages are sent as JSON to the server address (`{"topic", "title", "message", "tags", "click"}`). Anyone who knows a
topic on ntfy.sh can read it – so choose one that is hard to guess. For protected topics on your own
server, enter the access token as `NTFY_TOKEN` in the `.env` or in `docker-compose.yaml` under `environment:`.

## Navidrome plugin

With the Tuttiphon plugin, Navidrome asks Tuttiphon for similar songs and similar artists – and passes every play on
(as a scrobbler: exact listening times, real skips for the mixes, and for accounts without a stored password the
plays in the recap, [Playlists](04-playlists.md#mixes-that-learn-appfeedbackpy)): Instant Mix in Navidrome's
web interface, “similar songs”, song and artist radio in Symfonium and other apps (`getSimilarSongs2`,
`getArtistInfo2`) and the OpenSubsonic extension `sonicSimilarity` (`getSonicSimilarTracks`, `findSonicPath`) then
follow the sound of the own files ([Intelligence](06-intelligence.md#for-navidrome-the-plugin-appsonicpy)). Needs
Navidrome 0.64 or later (plugins, Instant Mix and the `sonicSimilarity` extension); the answers come from the AI
sound analysis, so the Docker image – without it, the plugin answers with the radio (Last.fm, genres).

1. **Key:** Settings → Navidrome → “Navidrome plugin” → “Create key” (shown once – copy it).
2. **Plugin file:** “Download the plugin” there (`/plugin/tuttiphon.ndp`, part of the image) or `tuttiphon.ndp` from
   the GitHub release. Put it as it is – not unpacked; an `.ndp` is a zip of `manifest.json` and `plugin.wasm` – into
   Navidrome's plugins folder: `<DataFolder>/plugins`, in the Navidrome container usually `/data/plugins`.
3. **Navidrome's agents:** `tuttiphon` first, in front of the list Navidrome uses so far – in `navidrome.toml`
   `Agents = "tuttiphon,deezer,lastfm,listenbrainz"`, in its `docker-compose.yaml`
   `ND_AGENTS=tuttiphon,deezer,lastfm,listenbrainz` (`deezer,lastfm,listenbrainz` are Navidrome 0.64's defaults; the
   environment variable wins over the toml; a second `Agents` line in the toml is an error). Where Tuttiphon has no
   answer (an empty list), Navidrome asks the next agent. Plugins are on by default (`Plugins.Enabled`). Restart
   Navidrome.
4. **In Navidrome:** Settings → Plugins → “Tuttiphon”: turn on, enter the address of Tuttiphon as Navidrome reaches it
   and the key, and allow it all users (“Users” – Navidrome only hands on the plays of the users assigned to it).
   Best the address in the home network, e.g. `http://<NAS>:8765` – or, if both containers share a Docker network,
   the name of Tuttiphon's container (`http://tuttiphon:8765`); never `localhost` (inside the Navidrome container that
   is Navidrome itself), and not an https address through a reverse proxy: such a proxy may turn the requests from the
   Navidrome container away (Navidrome's log then says “Tuttiphon answered 403: …”). The file name stays exactly
   `tuttiphon.ndp` – Navidrome takes it as the plugin's name in the list of agents.
5. **Symfonium:** in the settings of the Navidrome server (Settings → Media providers → the server), turn on “Use
   similar tracks for Radio Mix” – Instant Mix, song radio and the smart queue then come from Tuttiphon.

Check: Settings → Navidrome in Tuttiphon shows “Last request from Navidrome” after an Instant Mix – with the person
the answer was for, or “for the family” – and “Plays from Navidrome” after a song (with the accounts). The answers
follow the one listening only with the plays: the plugin needs all users allowed
([Intelligence](06-intelligence.md#for-navidrome-the-plugin-appsonicpy)). Problems: in
Navidrome's log lines with `plugin=tuttiphon` (more with `ND_PLUGINS_LOGLEVEL=debug`) – “Tuttiphon not reachable”
(address, network between the containers), “Tuttiphon answered 401” (key: create a new one and enter it), “answered
429” (too many wrong keys from this address – wait 10 minutes). “Last request” counts only Navidrome's questions, not
the plays.

**When Tuttiphon is not reachable** (being updated, restarting, the NAS asleep): for questions the plugin tells
Navidrome to try again in 2 minutes (`retry_later`) – Navidrome asks its next agents meanwhile; plays (scrobbles)
Navidrome keeps and hands on again later, with a wrong key after 15 minutes; starts and reports are only of use right
away and are dropped. Nothing needs to be done after Tuttiphon is back.

**Building it:** `tools/build-plugin.sh` (Go and TinyGo – in `PATH` or `TUTTIPHON_GO_TOOLS` in `dev.local.env`) writes
`navidrome-plugin/dist/tuttiphon.ndp` (manifest with Tuttiphon's version + `plugin.wasm`); `npm run release` and the
image workflow build it, the Dockerfile copies it to `/app/plugin/`, the workflow also attaches it to the GitHub
release. `tools/plugin-check.sh` (maintainers) runs the whole way end to end: test music made with ffmpeg, a throwaway
Navidrome (`TUTTIPHON_NAVIDROME` or in `PATH`, port 4599) with the plugin, a throwaway Tuttiphon (port 8799) with
made-up sound vectors, then `getSimilarSongs2`, `getSonicSimilarTracks`, `findSonicPath` and `getArtistInfo2` through
Navidrome and a play (`scrobble`, `reportPlayback`) passed on, then `getSimilarSongs2` for the song playing, which has
to leave out the songs just heard (the answer for the one listening, also proving that Navidrome keeps no answer) –
never the real Navidrome or the real data. The
`.ndp` carries the licenses of the parts compiled into it (`LICENSES.txt`, `GPL-3.0.txt`).

## Backup

Only the data folder needs to be backed up. Tuttiphon recreates the playlist files in the music folder from
`config.json`. Lyrics and Opus files are part of the music backup.

### Built-in backup (`app/backup.py`)

Tuttiphon backs up by itself – once a day from the time `dailyAt` on (schedule, `web._backup_daily()`; only the
responsible instance, so not on the PC while a container is running) and on demand under Settings → Backup:

- **Content:** `config.json`, `.env`, `state/` without `cache/`, `sessions.json`, `task.lock`, `install_id`
  (`backup.SKIP_STATE` – a restored copy elsewhere is another installation) and instance status files, plus `backup/` (only backed-up original playlists `*.nsp`/`*.m3u` and configurations from before a migration `config_v*.json`, `backup.KEEP_BACKUP`). Excluded is what rebuilds itself or has been set aside
  (`backup.SKIP_NAMES`: `liedtexte.db*`, `watch_files.json`, `*.defekt-*`), every `*.zip` (Tuttiphon keeps none in
  `state/` or `backup/` – it could only be an earlier backup) and everything in a backup folder that is a subfolder of
  `state/` or `backup/`. So a backup never contains the earlier ones. No logs. The list of backups is cached
  until the folder changes (the schedule asks every minute).
- **File:** `tuttiphon-sicherung-YYYY-MM-DD_HHMMSS.zip`, about 0.7 MB. It contains credentials and is therefore
  created with permissions 600 right away (temporary file `.<name>.<pid>.<random>.tmp`, created via
  `os.open(…, O_EXCL | O_NOFOLLOW, 0o600)` – always a new file of its own, never through a link –, then renamed).
- **Errors:** a file of `state/` that can't be read right now (e.g. being replaced on NFS) is skipped. If
  `config.json` or `.env` exists but can't be read, the backup fails instead of being written without settings or
  credentials: the temporary file is removed, “Back up now” reports the error, and the daily backup tries again in the
  next minute.
- **Location:** `settings.backup.dir` – empty = environment variable `BACKUP_DIR` (in the template `docker-compose.yaml` `/backup`, mounted from `./backups` next to it), otherwise `<data-folder>/sicherungen`; absolute or relative to the Navidrome folder
  (`TUTTIPHON_BASE`). Recommendation: a folder on a different disk, or one that is backed up
  externally – then the backup also survives a disk failure. Not inside `state/` or `backup/` of the data folder: the
  setting refuses it (“every backup would contain the earlier ones”); `BACKUP_DIR` pointing there still works, the
  rules above keep the backups from nesting.
- **Retention:** the newest `settings.backup.keep` (default 14); `backup.prune()` deletes older ones.
- **Download:** Settings → Backup (`GET /api/backups/file`, admin only).
- **Restore** (deliberately by hand): stop Tuttiphon or the container, unzip the ZIP into the data folder (`/config`),
  overwriting existing files, and start again. Afterwards everyone signs in again once.

### What belongs in the data folder

| Path in the data folder | Content | Back up? |
|---|---|---|
| `config.json` | people, music worlds, vibes, playlists, settings, roles | **yes** – the most important |
| `.env` | credentials (permissions 0600) | **yes**, keep it protected |
| `state/plays/` | daily counter snapshots for the recap; Navidrome stores no history | **yes** – cannot be restored |
| `state/deezer.json` | Deezer ranks per song | **yes** – rebuilding takes about 45–60 min |
| `state/audio.json` | raw measurements of the sound analysis | **yes** – rebuilding takes hours |
| `state/ml.json` | results of the AI sound analysis | **yes** – rebuilding takes several nights on the NAS |
| `state/feedback/` | what the mixes have learned per account | **yes** – cannot be restored |
| `state/managed_playlists.json` | which playlist files belong to Tuttiphon | **yes** |
| `backup/` | originals of taken-over handmade playlists, overwritten third-party files, copies of `config.json` before a migration (`config_v*.json`) | yes |
| `state/history.jsonl`, `logs/` | history and logs of the runs | optional |
| `state/lyrics.json` | when each song was last searched | optional (without it: searched again) |
| `state/lastfm.json` | Last.fm responses, valid for 30 days | optional (fetched again) |
| `state/mixes.json`, `daily.json`, `watch.json`, `watch_files.json` | today's mix selection, last daily refresh, state of the folder watch and the files it has seen | optional |
| `state/auto_assigned.json` | bands that the classification has already assigned to a music world automatically | optional – without it, a band that was taken out again can be classified automatically again |
| `state/audio.defekt-….json`, `state/ml.defekt-….json` | damaged result files of the sound analysis or the AI, set aside | no – for rescuing by hand, can be deleted afterwards |
| `state/mix_history.json` | selection of the last periods per mix (otherwise those not yet evaluated are missing for learning) | optional |
| `state/selfcheck.json` | result of the last self-check | optional (recreated at the next scan) |
| `state/secret` | key for the session cookies (permissions 0600) | optional – without it Tuttiphon creates a new one, and everyone has to sign in again |
| `state/sessions.json` | valid sessions (permissions 0600) | optional – without it everyone has to sign in again |
| `state/admin_password.json` | hash of the password of the local administrator set in the browser (permissions 0600) | **yes** – without it the server waits for the setup with a new code again |
| `setup-code.txt` | one-time setup code, only until the password is set (permissions 0600) | no – not in the built-in backup; a new one is created when needed |
| `state/navidrome_users.json` | account list last read from Navidrome (roles when Navidrome is not reachable) | no – fetched again |
| `state/install_id` | ID of this installation ([Multiple instances](#multiple-instances)) | no – not in the built-in backup; created again |
| `state/cache/` | image cache, artist info | no – pure cache |

Not to be backed up are the instance status files (`instance-*.json`) and the lock file `task.lock` in the shared
folder – normally `<playlist-folder>/.tuttiphon/`, so not in the data folder at all; as a fallback `state/`.

In the container, `docker-compose.yaml` is also part of the backup, because it contains paths and possibly
`TUTTIPHON_ADMIN_PASSWORD`.

Tuttiphon tidies up logs, history and image cache once a day by itself (`tasks.tidy()`): logs older than
90 days and cached images not renewed for 60 days are deleted, `history.jsonl` is shortened to the last 2000
lines. `backup/` is left untouched. See [Maintenance](05-maintenance.md#daily-tidy-up). You may also empty `logs/`
by hand; the history then no longer shows a log for old runs.

### Migration

Copy `config.json`, `.env` and `state/` into the new data folder (e.g. from `data/` on the PC to `/config`). If the
target runs a **different** Navidrome with a new database, the stored song IDs no longer match. This affects,
among others, `deezer.json`, `audio.json`, `ml.json`, `lyrics.json`, `mixes.json`, `mix_history.json`, `feedback/` and
`plays/`. Afterwards, run Deezer “Check everything again” and Lyrics “Search all missing now” once; the night analysis
catches up on the sound analysis and AI sound analysis.

## Multiple instances

An **instance** is a running Tuttiphon server, on the PC or in the container. PC and container usually have separate
data folders (PC: `data/`, container: `/config`), but write to the same playlist folder and the same Navidrome.
That is why the status files and the lock are in the **shared folder** `<playlist-folder>/.tuttiphon/` on the NAS
share (see [Shared folder](#shared-folder-of-the-instances)); `app/instances.py` and `tasks._InstanceLock` implement
this. That way PC and container see and lock each other even with separate data folders.

**Instance status** (`instances.heartbeat()`): each instance writes its own file `instance-<id>.json` (permissions
`0666`) – at startup, then every minute in the schedule, immediately at the start and end of each run, and every
minute during a run (`TaskRunner._run()`), so that long runs are not considered finished either.

```json
{"id": "docker:tuttiphon", "ts": 1791808925.0, "host": "tuttiphon", "docker": true, "running": false,
 "install": "8d41c07e9b2a65f3"}
```

- The ID is `pc:<hostname>` or `docker:<hostname>` (in the container the container hostname, fixed in the template as
  `hostname: tuttiphon`), without a process ID – so a restart is not a second instance. Without a fixed hostname,
  a newly created container (e.g. after an update) gets a new ID; its old status file then still counts as another
  instance for up to 180 s – for the run lock, not for the notice (see `install` below). In the file name, characters
  other than letters, digits, `_`, `.` and `-` become `_` (`instance-pc_rechner.json`). `tuttiphon.py run` reports with its own ID `<id>:run-<process>`
  (`instances.use_cli_id()`), so that it does not overwrite the status of a server on the same computer; its file
  is removed at the end of the run.
- `running` says whether the instance is currently working on a run.
- `install` is the ID of the installation (`instances.install_id()`): 16 random hex characters per data folder in
  `state/install_id`, created on first use and kept across restarts, updates and a new host name. A new ID only comes
  if the file is missing or contains no valid ID; if it is briefly unreadable (NFS), `install_id()` returns an empty
  value for the moment and reads it again later – a new ID would look like another installation. It is not part of
  backups (`backup.SKIP_STATE`): a copy restored elsewhere is another installation and gets its own ID.
- `instances.others()` reads the files of the others: an instance counts as active if its status is younger than 180 s.
  Files older than 7 days are deleted in the process; broken or foreign files (no JSON object, `ts` not a number) are
  skipped. With `foreign_only=True` it also skips status files with the
  own installation ID under another instance ID – the own installation is not “a second Tuttiphon”, e.g. the container
  from before an update with a different host name or a `tuttiphon.py run` of the same installation.
- Consequences: administrators see the warning “Tuttiphon is running twice” under “To review”. `GET /api/status` lists
  the other instances (`instance.others` with `host`, `docker`, `running`). Both use `others(foreign_only=True)`.
  A PC instance leaves the recap, folder watch and daily refresh to the container as long as the container is active;
  it still tidies up its own data
  folder itself.
- Without a schedule (`TUTTIPHON_NO_SCHEDULER=1`) and with `tuttiphon.py run`, a process only reports its status during
  a run.

**Run lock** (`tasks._InstanceLock`, acquired in `TaskRunner.start()`): a run only starts if

1. no other active instance reports `running: true` (`instances.busy_elsewhere()` – this counts the own installation
   under another ID as well, so a command-line run of the same installation still blocks) and
2. the process gets an exclusive POSIX lock (`fcntl.lockf`) on `task.lock` in the shared folder without waiting.

Otherwise nothing starts at all: the caller gets the message “Another Tuttiphon instance (PC or Docker) is working
right now – please try again later.”, and neither a log nor a history entry is created. The interface shows the message,
auto-apply tries again after 20 s, the daily refresh and folder watch in the next minute, and `tuttiphon.py run`
exits with code 1 ([Maintenance](05-maintenance.md#lock-against-concurrent-runs)).

- The lock is tied to the open file handle and ends with the run or the process. The empty file `task.lock` stays.
  It is opened with `O_NOFOLLOW` (a link in its place is removed first) and gets `0666` via `fchmod`. If it cannot be
  opened because it has permissions 000, Tuttiphon sets `0666` and tries again.
- If the file system cannot lock at all (e.g. `ENOLCK`), only the status of the other instances decides.
- Over NFS, the POSIX lock only works if the NFS server supports locks.

**Limits:** PC and container only see each other if both reach the same shared folder. If they point to
different playlist folders, if `TUTTIPHON_SHARED_DIR` is set differently, or if the playlist folder is not writable for
one instance (it then falls back to its own `state/`), they do not lock each other. Use only one instance for
editing anyway: with a shared data folder, configurations overwrite each other; with separate data folders,
two different configurations write to the same playlist folder. The lock only protects runs, not saving the
configuration.

## Troubleshooting

### Where to look

| Source | Content |
|---|---|
| History (interface, `GET /api/history`) | the last 60 runs from `state/history.jsonl`: name, steps, result per step, summary, log file, dry run. `history()` reconstructs runs without an entry (e.g. after a hard stop) from their log file. |
| Logs (`logs/`, `GET /api/log?file=…`) | one file per run: `<YYYY-MM-DD_HHMMSS>_<steps>.log`, lines `[HH:MM:SS] …`. Starts with “▶ <name> – <time>”, per step “━━ <title> ━━” and the duration, at the end “■ Done. …”. The API returns at most the last 400,000 characters. |
| Live log (`GET /api/task`) | the current run with step and new lines; for users without lines |
| Status (`GET /api/status`) | Navidrome reachable?, version, scan state, storage locations (present/writable), other instances (with `running`), daily refresh, folder watch |
| Server log (standard output; Docker: `docker logs tuttiphon` or UGOS → Container → Log) | short lines with date and time: startup with version and storage locations, runs in short form, sign-ins, unexpected errors, daily backup, shutdown – see [below](#server-log). The server does not log requests. With `tuttiphon.py run`, the whole log of the run (without timestamps) goes to standard output. |

History, logs and live lines are visible to administrators only.

**Result per step:** `ok` · `warnung` (warning: the step reports a partial problem, e.g. Opus errors for individual
files, or playlists still missing after the scan) · `fehler` (error: an exception; in the log “❌ <message>”) ·
`abgebrochen` (canceled: also the step that was running when the run was canceled – or paused briefly for a takeover;
the continuation is then called “… (continued)”). A failed step does not hold up the following ones. A run
that the lock against other instances prevents does not appear in the history at all.

**API errors** come as JSON `{"error": "…"}`: 400 for invalid input, Navidrome errors and runs that cannot
start; 401 without sign-in; 403 without permission; 413 for a request that is too large (over 2 MB, cover upload over
10 MB); 429 after too many failed sign-ins; 503 when a file on the share was briefly not accessible, or for every
request while a server on the network has a weak `TUTTIPHON_ADMIN_PASSWORD`; 500 with the error type.

### Server log

`app/events.py`, function `say(text)`, writes each line as `[DD.MM. HH:MM:SS] <text>` to standard output
(under a lock, with `flush`; in the image, `PYTHONUNBUFFERED=1` makes sure nothing gets stuck). On the PC this ends up
in the terminal – a server started via the menu entry has none, so it cannot be seen there.

The server log is **always English**, whatever the server language: every translated text carries its English form
(`i18n.Text`, `.en`), and `say()` as well as the console output of `tuttiphon.py` print it (`i18n.english()`). The run
logs in `logs/` and in the interface stay in the server language. Lines glued together with `+` keep both forms;
`i18n.join()` and `i18n.said()` (message of an exception) do the same for lists and errors.

| When | Lines | Code |
|---|---|---|
| Startup | “Tuttiphon <version> is starting[ in the Docker container]”, then indented per storage location “Data/Music/Playlists/Archive/Backups: <path> – writable \| NOT writable \| created when needed \| MISSING”, “Navidrome: <NAV_URL>” (or “address missing …”, possibly with “– admin access not entered yet”), “AI sound analysis: ready” or the reason, “Daily at <dailyAt>: <mode> · night analysis <from>–<to> · folder watch on” (the last two only if turned on). In the container then “Ready – port 8765”; on the PC instead (without timestamp) “Tuttiphon is running at http://…/ (Ctrl+C quits)”. If the overview fails: “(Startup overview not possible: …)” | `tuttiphon.py`, `web.startup_report()` |
| Run | every non-indented, non-empty line of the run log, in English: “▶ <name> – <date time>”, “━━ <step> ━━”, messages from the steps (e.g. “Scan finished: …”, “Classification: …”), “❌ …”, “⏸ Short pause for “…” …”, “■ Done. <step>: <result>, …”. Indented detail lines are only in `logs/` | `TaskRunner.log()` (only in the server, not with `run`) |
| Sign-in | “Signed in: <account>”, “Sign-in failed: <name>” (only failed attempts that count), “Sign-in blocked (too many failed attempts): <name>”; the local administrator is called “Local administrator” (`web._who()`), a wrong setup code “setup code” | `Handler._login()`, `Handler._limited()` |
| Setup | “No administrator password yet – open Tuttiphon in the browser and set it with the setup code.” followed by a line of its own “Setup code: XXXX-XXXX  (also in setup-code.txt in the data folder)” – at every start while the setup is pending, as soon as setup mode begins while running (e.g. after deleting `state/admin_password.json`) and when the setup page is opened (at most every 2 minutes); “Setup: the password of the local administrator is set.”; “The password of the local administrator was changed.” (Settings → Users & permissions) | `tuttiphon.py`, `localadmin.announce()`, `Handler._setup()`, `Handler._admin_password()` |
| Error | “⚠ Error at <method> <path>: <type>: <text>” for every request that ends with `500` | `Handler._handle()` |
| Backup | “Backup created: <file> (<n> KB) in <folder>” – only the daily one, not “Back up now” | `web._backup_daily()` |
| Shutdown | “Canceling the running task “<name>”, saving its progress …” (only if a run is in progress), “Shut down.” | `tuttiphon.py` |

`tuttiphon.py` prints warnings before the start (with `--unsafe-no-password`: password missing or too short) and
aborts with code 2 without a timestamp.

### Common errors

| Message / symptom | Cause | Fix |
|---|---|---|
| “The data folder … is not writable” at startup, code 2 | data folder missing or with wrong permissions; in the container, `/config` is not writable for `user:` | create the folder, set permissions for the UID:GID from `user:` |
| “Tuttiphon is meant to be reachable on the network, but TUTTIPHON_ADMIN_PASSWORD is still the placeholder “change-me” (…)” or “… has only n characters (…)”, followed by “Please enter your own password with at least 8 characters in docker-compose.yaml (or remove the line and set the password in the browser) and restart.”, code 2 | start with `--host` ≠ loopback with a weak `TUTTIPHON_ADMIN_PASSWORD`; the brackets say whether it comes from `docker-compose.yaml`/environment or from the `.env` | your own password (≥ 8 characters) there – or remove the line and set the password in the browser with the setup code |
| HTTP 503 “Tuttiphon is locked: TUTTIPHON_ADMIN_PASSWORD is too short or still the placeholder – please set at least 8 characters.” for every page | the server is bound to a network address and `TUTTIPHON_ADMIN_PASSWORD` became weak while it runs (e.g. `.env` edited) | set your own password (≥ 8 characters) in `docker-compose.yaml` or `.env` – in `.env` it takes effect within 10 s – or remove the line ([First start](#first-start-administrator-password)) |
| HTTP 421 “Access only via 127.0.0.1 – or set an administrator password (Settings → Users & permissions).” | without a password and not bound to a network address, only the host `127.0.0.1`/`localhost`/`::1` is allowed | open via `127.0.0.1`, set a password (Settings → Users & permissions), or add the name to `TUTTIPHON_HOSTS` |
| Sign-in page asks for a setup code – where is it? | no administrator password yet ([setup mode](07-security.md#setup-mode)) | in the container log (`docker logs tuttiphon`, line “No administrator password yet – … setup code XXXX-XXXX …”, repeated at every start) and in `setup-code.txt` in the data folder (`config/` next to `docker-compose.yaml`) |
| Password of the local administrator forgotten | – | set in the browser: delete `state/admin_password.json` in the data folder – within about 10 s Tuttiphon is back in setup mode and logs a new code (on the PC without network binding: no sign-in until a new one is set). From `docker-compose.yaml`: look it up there, or change it and recreate the container |
| HTTP 503 “the interface has not been built yet” | `web/index.html` is missing | `npm run build` or `./tuttiphon.sh` |
| “Tuttiphon: the interface needs Node.js (npm run build).” | no `npm` and no build present | install Node.js ≥ 22 |
| “Another Tuttiphon instance (PC or Docker) is working right now – please try again later.” (interface: HTTP 400; `run`: code 1) | another instance reports `running` or holds `task.lock` in the shared folder | wait; check whether a `run` or a second instance is still running (`GET /api/status`, “To review”). The status of a crashed instance no longer counts after 180 s, and its lock ends with its process ([Multiple instances](#multiple-instances)). |
| HTTP 400 “A task is already running.” | a run is already in progress in this process | wait for it to finish or cancel it |
| “Navidrome address missing – Settings → Navidrome”, “Navidrome address invalid (…) – it starts with http:// or https://” / “Navidrome admin access missing” | `NAV_URL` is missing or does not start with `http(s)://`, or the admin access is not set. `navidrome._check_url()` reports this as `NavidromeError` before a connection is attempted; the interface runs anyway | enter the address (with `http://`) and the admin under Settings → Navidrome, or `NAV_URL` in `docker-compose.yaml` |
| “Navidrome API POST /auth/login: HTTP 429” or “… too many requests” | Navidrome rate-limits sign-ins; every new Tuttiphon process (restart, test server, `run`) signs in again | wait a few minutes, don't restart constantly. Tuttiphon itself waits and retries up to three times. |
| HTTP 429 “Too many failed attempts – please try again in a few minutes.” | Tuttiphon's own lock within 10 minutes: 10 failed sign-ins for the same account from the same address, 30 from the same address, or 50 for the same account from all addresses; for the setup code 10 from the same address or 50 from all addresses. “Navidrome not reachable” and an empty password do not count. Behind a reverse proxy without `TUTTIPHON_TRUSTED_PROXIES`, everyone shares the proxy's address | wait ([Security](07-security.md#sign-in-lockout)); behind a proxy set `TUTTIPHON_TRUSTED_PROXIES` ([Reverse proxy](#reverse-proxy-https)) |
| “Navidrome not reachable (…)” | `NAV_URL` wrong, Navidrome off, network | test the address under Settings → Navidrome |
| “Credentials incomplete for user '…'” | `NAV_URL`, admin name or admin password missing | Settings → Navidrome or `.env`/compose |
| “Navidrome error 40: … (user …)” | wrong password for this account | enter the password again |
| “Music folder missing: … (Settings → Storage locations)”, “Music folder … not found” | music folder not mounted or wrong path | check the NFS mount or the volume for `/music` (and `MUSIC_DIR`), [Storage locations](#storage-locations) |
| “ffmpeg, ffprobe missing – please install” | not installed on the PC | install `ffmpeg` |
| Settings → Intelligence: “Essentia is not installed (included in the Docker image).” | AI sound analysis on the PC without `essentia-tensorflow` | normal on the PC; the AI runs in the container |
| “AI models missing (n files) – rebuild the image.” | the download during the image build (partly) failed | rebuild the image, check the build log for “⚠ …: checksum does not match” or network errors |
| “⚠ AI sound analysis: the analysis process keeps crashing (not enough memory?) …” | the AI process was killed more than three times, usually by the memory limit – or by the watchdog because it hung on one song for longer than 600 s | check `mem_limit` (the AI needs about 850 MB extra), lower `analysis.mlThreads`; the rest follows in the next run |
| “To review”: ““…”: Navidrome shows n instead of m songs” | the [self-check](05-maintenance.md#self-check) after the scan: for mixes, Navidrome does not find entries of the `.m3u` (paths); for smart playlists, Navidrome evaluates the rules differently from Tuttiphon | mix: check the folder name of the playlist folder and the paths, have it rewritten; smart playlist: look at the rules, save again; if it persists, compare the evaluation in `rules.Library` with Navidrome |
| “⚠ not in Navidrome yet: …”, “Some playlists are missing in Navidrome – having them read in again.” | Navidrome has not read in the file (yet). Tuttiphon resets the file's modification time and scans a second time. | if it persists: is the playlist folder in Navidrome's library? Does the folder have the same name? |
| “Could not read file paths from Navidrome”, “No file paths were found for the mix …” | mixes need the real paths from the native API | check the admin access and reachability |
| “No password for “…””, “No user available for rating” (Deezer) | `NAV_PASS_<ACCOUNT>` is missing for the accounts | enter the password under Settings → Navidrome |
| “No accounts selected for rating” (Deezer) | no account is checked under Settings → Deezer stars (`settings.deezer.users` empty) | check at least one account |
| Reading on the share briefly fails with `PermissionError`/EACCES; API response HTTP 503 “A file was not accessible just now – please try again in a moment.” | NFS briefly reports EACCES while a file is being replaced | `read_text()`/`read_bytes()` try four times (pauses 0.15/0.3/0.45 s); if it still fails, the API answers with 503 instead of 403. If the error persists, the permissions really are wrong. |
| Files on the share with permissions `---------` (000), unreadable afterwards | happens on the NAS share when a file is written without explicit permissions | Tuttiphon writes with `write_atomic()`: create the temporary file `.<name>.<pid>.<thread>.tmp` right away with the target permissions (0664 on the music share, 0640 in the data folder, `.env` 0600), write, set permissions, rename, set permissions again. Your own code must do the same. Repair affected files with `chmod 664`. |
| hidden `.….tmp`, `.….opus.part` or `.cover-….part` files are left behind | writing or converting was interrupted hard (crash, power failure, `docker kill`, or `docker stop` after `stop_grace_period` has expired) | they may be deleted. Opus converts again in the next run; Deezer saves every 200 songs, the sound analysis and the AI every 2 minutes. |
| “⚠ Sound analysis: the results file was damaged – set aside as audio.defekt-….json, starting over.” (likewise “⚠ AI sound analysis: …” with `ml.defekt-….json`) | `state/audio.json` or `state/ml.json` did not contain valid JSON | Tuttiphon sets the file aside instead of overwriting it, and analyzes again. To rescue the work: stop Tuttiphon, copy the file back from the last [backup](#backup), start again. |
| “⚠ Deezer: the file with the ranks was damaged – set aside as deezer.defekt-….json.” (the step stops), likewise “⚠ Recap: …”, “⚠ Mixes learn: …”, “⚠ Lyrics index damaged …” | `state/deezer.json`, a file in `state/plays/<account>/`, `state/feedback/`, `state/mix_history.json` or `state/liedtexte.db` was damaged | set aside instead of overwritten ([Data model](02-data-model.md)); the next run starts with a fresh state – the lyrics index is built anew right away. To rescue: copy the file back from the last [backup](#backup) |
| at startup “✕ The configuration …/config.json is damaged and cannot be read (…)”, Tuttiphon does not start | `config.json` is no valid JSON (e.g. edited by hand) or has the wrong structure | correct the file, or replace it with `backup/config_v*.json` or the `config.json` of a backup (`tuttiphon-sicherung-*.zip`), then start again. If it happens while Tuttiphon is running, it keeps working with the last good state, copies the damaged file to `config.defekt-….json` and writes the good state back with the next save |
| “⚠ Playlist “…” cannot be built: …” in the server log, the playlist shows an error | a playlist has a value an older version let through (e.g. a minimum length as text) | open the playlist and save it again with a valid value, or delete it; the other playlists are written as usual, its file stays |

### Testing without risk

Never test against the real data. `tools/testserver.sh <port> <work-dir> [--auth [--user <account>]] [--web <dir>]`
copies `data/` once into the work folder (in a Git worktree without `data/`, the data of the main folder),
turns off auto-apply and folder watch there, and starts a server with `TUTTIPHON_NO_SCHEDULER=1` on
`127.0.0.1:<port>`. It puts the instance status and run lock into the work folder with
`TUTTIPHON_SHARED_DIR=<work-dir>/shared`, not into the real playlist folder. With `--auth` it sets
a random `TUTTIPHON_ADMIN_PASSWORD` in the copy's `.env` if that has no such line yet (it only checks
`TUTTIPHON_ADMIN_PASSWORD`; a password set in the browser in the copy is then overridden – the environment wins) and
prints session cookies for the local administrator and a user account
(`--user <account>`, otherwise `TUTTIPHON_TEST_USER` from `dev.local.env`, otherwise the first account with the role
“user” in the copied configuration).

The test server works with a copy of the data, but talks to the **real** Navidrome and the **real**
music folder. So don't trigger any writing actions there: no runs, no “Apply now”, no takeover,
no “Keep this mix”, no covers, no Deezer without dry run. Because the test server has its own shared folder,
no real instance locks it either. Stop it via the PID (see [Stopping](#stopping)).
The browser tests use the same approach ([Interface](09-interface.md)).
