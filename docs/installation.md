# Installation and configuration

Step by step from an empty folder to a running Tuttiphon, plus all settings that live outside the interface. What
Tuttiphon does: [Features](features.md). Operation in depth (Docker image, updates, backups, troubleshooting):
[Operations](08-operations.md).

- [Requirements](#requirements)
- [Installation](#installation)
- [Updating](#updating)
- [Configuration](#configuration)
- [Reverse proxy](#reverse-proxy)
- [Music on another device](#music-on-another-device)
- [Language](#language)

## Requirements

- **Navidrome** with an admin account (tested with 0.64). Tuttiphon needs **write access to the music folder** – it
  writes the playlist files (`00_SmartPlaylists/`), lyrics, converted files and covers there.
- **Docker** with Compose on **x86-64 (amd64) only** – there is no image for ARM, because the AI analysis exists for
  x86-64 only.
- **Memory**: about 130–300 MB in normal use (more with a large library and many accounts), up to about 1.6 GB while
  the AI listens at night – the template allows 2 GB.

## Installation

1. Create a folder (e.g. `/volume1/docker/tuttiphon` on a NAS) and put
   [`docker-compose.yaml`](../docker-compose.yaml) into it.
2. Adjust the lines marked `CHANGE`:
   - `user` – user and group ID that own your music files (`ls -n` in the music folder),
   - the music folder Navidrome reads → `/music`, an archive folder for the originals → `/archive`,
   - `NAV_URL` – the address of Navidrome as seen from the container, and `TZ`.

   There is no password in the file: you set it in the browser at the first start (step 5).
3. Create the folders before the first start and give them to the user from `user`. Otherwise Docker creates them
   for root, Tuttiphon cannot write there and the container keeps restarting. In the folder from step 1 (with your
   numbers and archive path; `sudo` if needed):
   ```bash
   mkdir -p config backups /path/to/music-archive
   chown 1000:1000 config backups /path/to/music-archive
   ```
4. `docker compose up -d` – or create a project in the Docker app of your NAS.
5. Open `http://<server>:8765`. Tuttiphon asks for the **setup code** and the password of the **local
   administrator** – Tuttiphon's own administrator, the way in when Navidrome cannot be reached. The code is in the
   container log (`docker logs tuttiphon`, or the log of the container in the Docker app of your NAS) and in
   `config/setup-code.txt`; it proves that whoever sets the password has access to the server. Only a hash of the
   password is kept (`config/state/admin_password.json`). Keep the password in a password manager.
6. The **setup assistant** opens: it connects to Navidrome (enter the admin account if it is not in
   `docker-compose.yaml`) and asks what Tuttiphon should do – convert lossless files or not, lyrics, sound analysis,
   Deezer stars, what runs by itself –, each with a short explanation and a sensible default. You can skip it and
   open it again later under **Settings → General**. Afterwards: **Settings → Storage locations** to check the
   folders, **Settings → Users & permissions** to check the roles.

From then on everyone signs in with their own Navidrome account. New users get a short welcome assistant that creates
their profile – one per account – and a tour. For playlists everyone shares, set up the family under **People → Set up
the family**: Tuttiphon creates a Navidrome account for it and shows its password once, for shared devices in
Symfonium.
The password of the local administrator can be changed under **Settings → Users & permissions**.

**Password forgotten?** Delete `config/state/admin_password.json`. Within a few seconds Tuttiphon waits for the setup
again and writes a new setup code to the container log.

## Updating

```bash
docker compose pull && docker compose up -d
```

In a NAS Docker app: pull the image again and recreate the project. Settings and history stay in `config/` and are
migrated automatically – read the changelog first: if a version asks for something to be done before the update
(say, one Navidrome account per person), a configuration that does not fit keeps Tuttiphon from starting until it is
put right in the earlier version. With the Navidrome plugin: its file lives in Navidrome's plugins folder – when the changelog
says so, put the new `tuttiphon.ndp` there and restart Navidrome. What changed: [CHANGELOG.md](../CHANGELOG.md). Going
back to an older version: [Operations → Updates](08-operations.md#updates).

## Configuration

Almost everything is set in the interface. Environment variables in `docker-compose.yaml` take precedence (except
`BACKUP_DIR`):

| Variable | Meaning |
|---|---|
| `TUTTIPHON_ADMIN_PASSWORD` | optional: the password of the local administrator in plain text instead of setting it in the browser – then it can only be changed here (at least 8 characters, `$` written as `$$`). Without it and without a password set in the browser, the container waits for the setup with the code – which also takes the language of your browser as the server language; with it, the server starts in English (change it under Settings → General) |
| `NAV_URL` | Navidrome as seen from the container |
| `NAV_PUBLIC_URL` | Navidrome address for "Open in Navidrome" links, if different |
| `NAV_ADMIN_USER`, `NAV_ADMIN_PASS` | Navidrome admin – better entered in the interface (stored in `config/.env`) |
| `NAV_PASS_<ACCOUNT>` | password of a family member's Navidrome account, account name in capitals (e.g. `NAV_PASS_ALEX`) – for stars, statistics and taste; better entered in the interface, or by each person at sign-in (the family's account gets its password when Tuttiphon creates it) |
| `MUSIC_DIR`, `PLAYLIST_DIR`, `ARCHIVE_DIR` | folders inside the container (playlists default to `<music>/00_SmartPlaylists`) |
| `BACKUP_DIR` | backup folder inside the container – used while Settings → Backup has no folder of its own (there the setting wins) |
| `LASTFM_API_KEY` | Last.fm key for similar bands and tags (free at [last.fm/api](https://www.last.fm/api)) |
| `NTFY_TOKEN` | access token for a protected ntfy server (notifications) |
| `TUTTIPHON_TRUSTED_PROXIES` | address or network of your reverse proxy, e.g. `172.16.0.0/12` – then the sign-in lock counts each person's own address and the session cookie is only sent via https |
| `TUTTIPHON_HOSTS` | without a password: further host names Tuttiphon answers to |
| `TZ` | time zone for the daily runs |

## Reverse proxy

For push notifications and a "real" app on the phone, put an https reverse proxy in front (e.g. Nginx Proxy Manager →
`http://<server>:8765`) and set `TUTTIPHON_TRUSTED_PROXIES`.

## Music on another device

Mount it via NFS: replace `/path/to/music:/music` with `music:/music` and add

```yaml
volumes:
  music:
    driver: local
    driver_opts: { type: nfs, o: "addr=<IP>,nfsvers=3,rw,hard", device: ":/path/to/music" }
```

## Language

Everyone chooses the language of the interface for their own device (Settings → General – users too) and it
switches instantly; the sign-in page follows that choice, otherwise the browser's language. The server language – for
playlist names in Navidrome, notifications and the run logs – is set there too, by administrators only. The container
log (`docker logs`) is always English. Languages: English, German, French, Dutch, Spanish, Italian, Portuguese and
Polish. A new installation takes the server language from the browser of its first administrator.
