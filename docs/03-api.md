# 03 – API (HTTP)

This chapter describes all HTTP endpoints of the Tuttiphon server (`app/web.py`, class `Handler`): who may call them,
which parameters they expect and what they return. The interface uses this API exclusively.
How sign-in, roles and the filters for users work in detail is described in
[07 – Security](07-security.md); the formats of the stored files are in [02 – Data model](02-data-model.md).

## General rules

### Server and methods

- `ThreadingHTTPServer` from the standard library, each request in its own thread. There is no access log
  (`log_message()` is empty); only sign-ins and unexpected errors (`500`) go into the server log, see
  [08 – Server log](08-operations.md#server-log). Hanging connections are closed after 30 s
  (`Handler.timeout`).
- `GET`, `POST` and `PUT` are supported, `HEAD` like `GET` without the content (e.g. for uptime checks). Other methods
  (`OPTIONS`, `DELETE` …) are answered by `http.server` itself with `501` and an HTML error page – so there are no CORS
  preflight requests either.
- Every answer carries `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`,
  `Content-Security-Policy: frame-ancestors 'none'` and `Referrer-Policy: same-origin`; `Server: Tuttiphon` without
  the Python version ([07](07-security.md#further-safeguards)).
- JSON bodies: `NaN`, `Infinity` and numbers beyond the float range (`1e999`) are refused with `400 "invalid request"`.
- Routes live in three tables of the `Handler` class: `GET_ROUTES`, `POST_ROUTES`, `PUT_ROUTES`. In addition there are
  special paths that `_handle()` intercepts first: `/api/login`, `/api/setup`, `/api/logout`, `/img/…`, `/live/…`,
  `/cover`, `/api/admin-password`, `/api/cover/upload` and the static files.
- Query parameters become a simple dictionary (`parse_qsl`); with duplicate names the last one wins, all values
  are strings.

### Requests with a body (POST/PUT)

| Rule | Value |
|---|---|
| Required header | `X-Tuttiphon: 1` – otherwise `403 {"error": "forbidden"}`. This includes `POST /api/login` and `POST /api/setup`; the only exception is `POST /api/logout`. |
| Language | `X-Lang: en` or `de` (the interface sends it with every request): error messages and texts in the response come in this language, otherwise in the server's language (`settings.language`). Cached responses (`_memoized`) are kept per language. |
| Body | a JSON **object** in UTF-8; an empty body counts as `{}`. The `Content-Type` is not evaluated. |
| Size | at most 2,000,000 bytes (`MAX_BODY`), 10 MiB for a cover upload. Above that: `413`, and the connection is closed. |
| invalid | not JSON, not an object or a broken `Content-Length` → `400 {"error": "invalid request"}` or `"invalid length"` |

`GET` requests don't need the header. They don't change the configuration; some do fill caches or
state files, though (e.g. `/api/rueckblick` records the current play counts, `/api/deezer/ranks` migrates old ranks once,
`/img/…` stores images in the image cache, `/api/status` and `/api/inbox` create the shared folder
`.tuttiphon/` if needed, a changed account list from Navidrome ends up in `state/navidrome_users.json`).

### Responses

- JSON responses: `Content-Type: application/json; charset=utf-8`, `Cache-Control: no-store`, non-ASCII characters
  unescaped (`ensure_ascii=False`).
- Some endpoints report errors **with status 200** in the body (the interface shows them as a result):
  `/api/env/test` and `/api/lastfm/test` (`{"ok": false, "error": …}`), `/api/opus/info` (key `error`) and
  `/api/status` (`navidrome.ok = false`).
- `_memoized()` caches expensive results: the keys are name, modification time of `config.json`, load time of the
  library, date and optional extra values. This way `/api/playlists` shows Navidrome data at most 20 s old. What gets
  cached is always the admin view; filtering happens afterwards (see [07](07-security.md#what-the-server-filters-for-users)).

### Errors

All errors from routes come as `{"error": "<text>"}`; `_handle()` does the mapping:

| Status | Trigger |
|---|---|
| `400` | `ValueError`, `KeyError`, `RuntimeError`, `NavidromeError`, `StopIteration` – domain errors (“Playlist not found”, “A task is already running.”, “Another Tuttiphon instance … is working right now …”), missing required fields (with `KeyError` the key is in the text, e.g. `"'id'"`), errors from Navidrome |
| `401` | no valid session for `/api/…`, `/img/…`, `/live/…`, `/cover` → `{"error": "login"}` (also after signing out, for an account with role `none` and in setup mode); wrong credentials at `/api/login`; wrong setup code or weak password at `/api/setup` |
| `302` | no valid session for all other non-public paths → `Location: /login.html` |
| `403` | path in `ADMIN_ONLY` without the admin role (`"Only administrators may do this."`), `PermissionError` without an error number (someone else's person/playlist), missing `X-Tuttiphon` header (`"forbidden"`, also at `/api/login` and `/api/setup`) |
| `404` | unknown API path or missing static file (`{"error": "not found"}`); image not available (empty body) |
| `413` | body too large (`"Request too large"`) |
| `409` | `POST /api/setup` outside setup mode (`"Tuttiphon is already set up – sign in as local administrator."`) |
| `421` | called via a foreign host name without an administrator password and not bound to a network address (`"Access only via 127.0.0.1 – or set an administrator password (Settings → Users & permissions)."`) |
| `429` | sign-in lockout after too many failed attempts (per account and address, per address, per account; setup code; current password at `/api/admin-password`) |
| `500` | any other exception – the answer only says `"Something went wrong – the details are in the server log."`; the server log shows “⚠ Error at <method> <path>: <type>: <text>” |
| `503` | `PermissionError` from the file system (`"A file was not accessible just now – please try again in a moment."`); `index.html` is missing, i.e. the interface hasn't been built (plain text instead of JSON); bound to a network address while `TUTTIPHON_ADMIN_PASSWORD` is weak – for **every** request, before all other checks (`"Tuttiphon is locked: TUTTIPHON_ADMIN_PASSWORD is too short or still the placeholder – please set at least 8 characters."`, [07](07-security.md#running-without-a-password)) |

`PermissionError` is also the class the file system raises for missing permissions (e.g. briefly on the
NFS share). `_handle()` tells the two cases apart by `errno`: if an error number is set, the error comes from the
file system → `503`; the server's permission checks raise `PermissionError` with a text only → `403`. Aborted
connections (`BrokenPipeError`, `ConnectionResetError`, `TimeoutError`) are silently discarded.

### Static files

All `GET` paths except `/api/…` (which includes `/api/stream`, audio instead of JSON), `/img/…`, `/live/…` and `/cover` are served by `_static()` from the build folder
`web/` (`WEB_DIR`, switchable for tests via `TUTTIPHON_WEB`). `/` is `index.html`. The resolved path must lie inside
`WEB_DIR`, otherwise `404`.

| File | `Cache-Control` | Reason |
|---|---|---|
| `/assets/…` | `public, max-age=31536000, immutable` | Vite build with a content hash in the file name |
| everything else (`index.html`, `login.html`, `sw.js` …) | `no-cache` | new references take effect immediately after an update |

MIME types come from `mimetypes`; `.js` is always `text/javascript`, `.webmanifest` `application/manifest+json`,
text types get `; charset=utf-8`. Only `/login.html`, `/favicon.svg`, `/manifest.webmanifest`, `/sw.js`, `/icons/…`
and `/assets/…` are reachable without a session. The check uses the normalized path
(`posixpath.normpath()` after `unquote()`) – so `/assets/../index.html` or `/assets/%2e%2e/…` are not public.

### Legend “Access”

| Abbreviation | Meaning |
|---|---|
| public | reachable without a session |
| signed in | any valid session (role `admin` or `user`). Without an administrator password (neither `TUTTIPHON_ADMIN_PASSWORD` nor one set in the browser) and bound to loopback, every access via localhost is a local admin; on the network that is setup mode, where only the public paths work until the setup ([07](07-security.md#setup-mode)). |
| Admin | path is in `Handler.ADMIN_ONLY` → otherwise `403` |
| Admin (function) | path is open to everyone, the function calls `auth.require_admin()` |
| own | signed in, but only for one's own people or playlists (`_own_person()`, `_own_playlist_id()`) – otherwise `403` |

The “Users” column in the tables below lists what the server leaves out for the role `user`.

## Overview

| Method | Path | Access | Section |
|---|---|---|---|
| GET | `/api/login` | public | [Session](#session) |
| POST | `/api/login` | public | [Session](#session) |
| POST | `/api/setup` | public (only in setup mode) | [Session](#session) |
| POST | `/api/logout` | public | [Session](#session) |
| GET | `/api/me` | signed in | [Session](#session) |
| POST | `/api/me/password` | signed in | [Session](#session) |
| POST | `/api/seen` | signed in (own account only) | [Session](#session) |
| POST | `/api/tour/seen` | signed in (own account only) | [Session](#session) |
| GET | `/api/config` | signed in (filtered) | [Configuration](#configuration) |
| PUT | `/api/config` | signed in (filtered) | [Configuration](#configuration) |
| GET | `/api/status` | signed in (filtered) | [Library & status](#library--status) |
| GET | `/api/home` | signed in | [Library & status](#library--status) |
| GET | `/api/library` | signed in | [Library & status](#library--status) |
| GET | `/api/welt` | signed in (filtered) | [Library & status](#library--status) |
| GET | `/api/artist` | signed in (filtered) | [Library & status](#library--status) |
| GET | `/api/welt/neu` | Admin | [Library & status](#library--status) |
| GET | `/api/song` | signed in (filtered) | [Songs & listening in](#songs--listening-in) |
| GET | `/api/song/more` | signed in | [Songs & listening in](#songs--listening-in) |
| GET | `/api/sound/catalog` | signed in | [Songs & listening in](#songs--listening-in) |
| GET | `/api/instruments` | signed in | [Songs & listening in](#songs--listening-in) |
| GET | `/api/stream` | signed in | [Songs & listening in](#songs--listening-in) |
| GET | `/api/playlists` | signed in (filtered) | [Playlists](#playlists) |
| GET | `/api/playlist` | signed in (filtered) | [Playlists](#playlists) |
| POST | `/api/preview` | signed in | [Playlists](#playlists) |
| POST | `/api/counts` | signed in | [Playlists](#playlists) |
| POST | `/api/snapshot` | own | [Playlists](#playlists) |
| POST | `/api/takeover/preview` | Admin | [Playlists](#playlists) |
| POST | `/api/takeover` | Admin | [Playlists](#playlists) |
| POST | `/api/mapping` | Admin | [Playlists](#playlists) |
| GET | `/api/suggestions` | signed in (filtered) | [Suggestions](#suggestions) |
| GET | `/api/taste` | signed in | [Suggestions](#suggestions) |
| GET | `/api/search` | signed in | [Suggestions](#suggestions) |
| GET | `/api/changelog` | signed in | [Suggestions](#suggestions) |
| GET | `/api/inbox` | signed in (filtered) | [Suggestions](#suggestions) |
| GET | `/api/matrix` | signed in | [Suggestions](#suggestions) |
| GET | `/api/missing` | own | [Suggestions](#suggestions) |
| GET | `/api/task` | signed in (filtered) | [Runs](#runs) |
| POST | `/api/task` | Admin (function) | [Runs](#runs) |
| POST | `/api/task/cancel` | Admin | [Runs](#runs) |
| POST | `/api/apply/now` | signed in | [Runs](#runs) |
| GET | `/api/history` | Admin | [Runs](#runs) |
| GET | `/api/log` | Admin | [Runs](#runs) |
| GET | `/api/stats` | own | [Statistics](#statistics) |
| GET | `/api/rueckblick` | own | [Statistics](#statistics) |
| POST | `/api/rueckblick/keep` | own | [Statistics](#statistics) |
| PUT | `/api/env` | Admin | [Settings & credentials](#settings--credentials) |
| POST | `/api/env/test` | Admin | [Settings & credentials](#settings--credentials) |
| POST | `/api/paths/check` | Admin | [Settings & credentials](#settings--credentials) |
| POST | `/api/lastfm/test` | Admin | [Settings & credentials](#settings--credentials) |
| GET | `/api/users` | Admin | [Settings & credentials](#settings--credentials) |
| GET | `/api/accounts` | Admin | [Settings & credentials](#settings--credentials) |
| PUT | `/api/accounts` | Admin | [Settings & credentials](#settings--credentials) |
| POST | `/api/admin-password` | Admin | [Settings & credentials](#settings--credentials) |
| GET | `/api/intel` | Admin | [Settings & credentials](#settings--credentials) |
| GET | `/api/opus/info` | Admin | [Settings & credentials](#settings--credentials) |
| GET | `/api/lyrics/stats` | Admin | [Settings & credentials](#settings--credentials) |
| GET | `/api/deezer/ranks` | Admin | [Settings & credentials](#settings--credentials) |
| GET | `/api/backups` | Admin | [Settings & credentials](#settings--credentials) |
| POST | `/api/backups/now` | Admin | [Settings & credentials](#settings--credentials) |
| GET | `/api/backups/file` | Admin | [Settings & credentials](#settings--credentials) |
| GET | `/api/kinderschutz` | Admin | [Settings & credentials](#settings--credentials) |
| POST | `/api/liedtexte/update` | Admin | [Settings & credentials](#settings--credentials) |
| GET | `/api/pflege` | Admin | [Settings & credentials](#settings--credentials) |
| POST | `/api/notify/test` | Admin or own | [Settings & credentials](#settings--credentials) |
| GET | `/api/push/key` | signed in | [Notifications through the app](#notifications-through-the-app) |
| POST | `/api/push/subscribe` | signed in | [Notifications through the app](#notifications-through-the-app) |
| POST | `/api/push/unsubscribe` | signed in | [Notifications through the app](#notifications-through-the-app) |
| POST | `/api/push/status` | signed in | [Notifications through the app](#notifications-through-the-app) |
| POST | `/api/push/test` | signed in | [Notifications through the app](#notifications-through-the-app) |
| GET | `/img/<id>` | signed in | [Images & covers](#images--covers) |
| GET | `/live/<id>` | signed in | [Images & covers](#images--covers) |
| GET | `/cover` | own | [Images & covers](#images--covers) |
| GET | `/api/cover/styles` | signed in | [Images & covers](#images--covers) |
| POST | `/api/cover/apply` | own | [Images & covers](#images--covers) |
| POST | `/api/cover/remove` | own | [Images & covers](#images--covers) |
| POST | `/api/cover/upload` | own | [Images & covers](#images--covers) |
| GET | all other paths | public or signed in | [Static files](#static-files) |

## Session

| Endpoint | Access | Parameters | Response |
|---|---|---|---|
| `GET /api/login` | public | – | `{"setup": bool, "navidrome": bool}` (`api_login_info()`) – `setup`: setup mode, no administrator password yet on the network; the sign-in page then shows only the setup form, and the request writes the code to the server log once more (at most every 2 minutes, `localadmin.remind()`). `navidrome`: whether people can sign in with their Navidrome account yet (`NAV_URL` and the admin access are set); with `false` the sign-in page offers only the local administrator |
| `POST /api/login` | public, header `X-Tuttiphon: 1` required (otherwise `403`) | Body `{"username", "password", "remember"}` – `remember` defaults to `true`; an empty user name or `notfall` = [local administrator](07-security.md#local-administrator) | `{"ok": true, "user": "<name>"}` and `Set-Cookie: tuttiphon=…` (new session in `state/sessions.json`; `Secure` via https through a trusted reverse proxy); errors `401 {"error": <message>}`, `429` when locked out |
| `POST /api/setup` | public, header `X-Tuttiphon: 1` required (otherwise `403`); only in [setup mode](07-security.md#setup-mode) (bound to a network address, no administrator password), otherwise `409` | Body `{"code", "password"}` – the setup code from the server log or `setup-code.txt` (case and `-` don't matter) and the new password of the local administrator | `{"ok": true, "user": "@notfall"}` and `Set-Cookie: tuttiphon=…` (`Secure` via https through a trusted reverse proxy); the hash goes to `state/admin_password.json`, `setup-code.txt` is deleted. Errors `401` (wrong code – counts toward the lockout –, weak password), `409`, `429` |
| `POST /api/logout` | public, no `X-Tuttiphon` needed | Cookie `tuttiphon` | ends the session of this token on the server (`auth.end_session()`) – afterwards the token is no longer valid, not even as a copy; response `{"ok": true}` and a cookie `tuttiphon=` with `Max-Age=0` |
| `GET /api/me` | signed in | – | `{"user", "name", "fullName", "role", "local", "persons", "own", "notfall", "passwordStored", "passwordRejected", "tourSeen", "welcomeSeen"}` – `passwordRejected`: a password is stored, but Navidrome no longer accepts it ([07](07-security.md#turn-on-statistics--stars)); without sign-in (local): `{"user": null, "name": "", "role": "admin", "local": true, "persons", "own", "tourSeen", "welcomeSeen": true}` |
| `POST /api/me/password` | signed in with a Navidrome account (not the local administrator, not local) | Body `{"password": "…"}` stores it, `{"password": null}` (or no field) forgets it | `{"ok": true}` |
| `POST /api/seen` | signed in, affects only one's own account | Body `{"what": "tour"}` or `{"what": "welcome"}` | `{"ok": true}`; any other value → `400 "Unknown"` |
| `POST /api/tour/seen` | signed in, own account only | – | `{"ok": true}` – older form of `{"what": "tour"}` |

- `persons` are the people the account sees (admin: all), `own` its own people (people whose `user` is the account;
  the default person comes last).
- `tourSeen` / `welcomeSeen`: has the account already completed the tour or the welcome assistant? Stored on the
  server in `state/seen.json` (`auth.mark_seen()`), so it applies on all devices and under every address; without
  sign-in the account is `""`, and `welcomeSeen` is then always `true`. `POST /api/seen` records the **signed-in** account
  (`auth.current()["user"]`) – an account can't set it for others this way. The interface calls it at the end of the
  tour (also when skipping) or at the end of the assistant or on “Later – look around first”
  ([09](09-interface.md#tour-and-welcome)).
- `/api/me/password` first checks the password with a ping to Navidrome (`400 "The password is wrong."`),
  stores it as `NAV_PASS_<NAME>` in `.env` and clears the library cache. Flow and messages of
  `/api/login`: [07 – Sign-in](07-security.md#sign-in).
- Sign-in lockout: in 10 minutes at most 10 failed attempts per account (user name in lowercase, empty = local
  administrator) from the same address, 30 per address and 50 per account from all addresses together, then `429`.
  “Navidrome is not reachable right now” and an empty password don't count. The address is the direct peer – behind a
  reverse proxy listed in `TUTTIPHON_TRUSTED_PROXIES` the one from `X-Forwarded-For`. A wrong setup code at
  `/api/setup` counts separately: 10 per address and 50 from all addresses together. Details:
  [07 – Sign-in lockout](07-security.md#sign-in-lockout).
- `/api/login` writes “Signed in: <account>” to the server log, for counting failed attempts “Sign-in
  failed: <entered name, lowercase>” and for a lockout “Sign-in blocked (too many
  failed attempts): …”; the local administrator appears there as “Local administrator” (`web._who()`). Passwords never
  appear. `/api/setup` writes “Setup: the password of the local administrator is set.”, a wrong code “Sign-in failed:
  setup code”.
- `/api/setup` (`Handler._setup()`): wrong code → `401` “The setup code is wrong – look for the line “Setup code:” in
  the container log, or open setup-code.txt in the data folder.”, a weak password (`config.weak_password()`) → `401` “The administrator password
  needs at least 8 characters.” (doesn't count toward the lockout). Of two requests at the same moment only the first
  sets the password (`_setup_lock`); the second gets `401` “Tuttiphon is already set up …”. Afterwards the server is
  no longer in setup mode, and the setup assistant follows as usual ([07 – Setup mode](07-security.md#setup-mode)).

## Configuration

| Endpoint | Access | Parameters | Response |
|---|---|---|---|
| `GET /api/config` | signed in | – | the configuration as in `config.json` ([02](02-data-model.md)), prepared by `auth.view_config()` |
| `PUT /api/config` | signed in | Body: the **complete** configuration | `{"ok": true}` |

On `GET`, users get (`auth.view_config()`):

| Part | Content |
|---|---|
| `playlists` | visible ones only: their own and those of people with `public: true` (without `person`, the default person counts) |
| `personen` | their own people in full; other people only with `public: true` and only with `id`, `name`, `icon`, `color`, `prefix`, `public` (`auth.PUBLIC_PERSON_FIELDS`); other people's private profiles are missing entirely |
| `settings` | only `autoApply`, `defaultPerson`, `namePattern`, `allName`, `limit`, `minDuration`, `allMinRating`, `public` (`auth.USER_SETTINGS`) |
| `accounts` | missing |
| `dismissed`, `ignored` | their own lists from `accounts.<account>` |
| `dismissedAt` | missing (the dates of the administrator's hidden suggestions) |
| other keys | unchanged (e.g. `welten`, `stile`, `version`) |

On `PUT`, the server applies:

- **Admin:** everything via `save_from_ui()`. In doing so, `merge_server_fields()` resets the fields that only the
  server maintains to the current state: `accounts` entirely, and `file`, `takeover` and `cover` of each existing playlist.
- **Users:** only their own things: `save_from_ui()` applies `auth.merge_user_changes()` under the lock to
  the current server state (details in [07](07-security.md#writing-merge_user_changes)). Anything they didn't
  receive (other people, the remaining settings) therefore stays unchanged. More than 200 playlists or 20 people for
  one account → `400` (“You can have at most …”).

In both cases `normalize_playlists()` then turns every playlist with a sound filter into a mix
([02](02-data-model.md#playlists)). Then `validate_config()` checks the result (`400` with `"config: …"` or
`"Settings: …"`). After saving, `AutoApply.schedule()` schedules the auto-apply in 8 s (only if
`settings.autoApply` is on), and `schedule_warm()` precomputes the expensive pages in the background.

## Library & status

| Endpoint | Access | Parameters | Response | Users |
|---|---|---|---|---|
| `GET /api/status` | signed in | – | `env` (`url`, `webUrl`, `admin`, `adminOk`, `users[{name, ok, key, rejected}]`, `auth`, `adminPassword`, `publicUrl`, `lastfm`, `locked`), `deezer`, `steps`, `allSteps`, `daily`, `watch`, `paths`, `instance{docker, others[{host, docker, running}]}`, `navidrome{ok, version, scan}` or `{ok: false, error}` | only `navidrome{ok, version, scan}`, `env{users (own accounts only), auth, webUrl, lastfm}`, `daily`, `instance{docker, others: []}`; `steps`/`allSteps` empty |
| `GET /api/home` | signed in | – | `{"newAlbums", "favNew", "songs", "albums", "artists", "playlists", "personen"}` (numbers, `playlists` = active playlists of all people). Each album carries `fav`: by a favorite band of the signed-in person (administrators: of the default person and of their own account, `rules.favorite_artists()`); those from the last 45 days come first, `favNew` counts them | `fav` from one's own people |
| `GET /api/library` | signed in | `refresh=1` reloads the library from Navidrome | Index: `artists[[name, songs, id]]`, `genres`, `albums`, `songs`, `suffix`, `mp3Albums`, `loved`, `played`, `similar`, `untagged`, `autoArtists`, `weltInfo`, `scenes`, `ratingsExact`, `ratingSource`, `deezer` | unfiltered |
| `GET /api/welt` | signed in | `id` of the music world | `members`, `songs`, `covers`, `artists`, `memberList[{name, id, songs, auto}]`, `similar`, `playlists`, `excluded`, `scene`, `forMe` | `playlists` visible ones only; `forMe` always from one's own account |
| `GET /api/welt/neu` | Admin | `id` of the music world | Preview for “Rebuild”: `name`, `icon` (from the scene), `before`, `after` (bands), `dropped`, `added`, `renamed[[old, new]]` – changes nothing; without a scene `400` | – |
| `GET /api/artist` | signed in | `name` | `name`, `id`, `songs`, `albums`, `genres`, `welten[{id, state}]`, `stile`, `likedBy`, `dislikedBy`, `playlists`, `bio`, `similar`, `plays`, `tags`, `missing`, `sound`, `soundsLike`, `lastfm`, `scenes`, `rating`, `top` (the five most played songs as song rows, see [below](#songs--listening-in)) | `playlists` only visible active ones; `likedBy`/`dislikedBy` only one's own people; `top` without songs hidden by kid-safe mode |

- `env.users` in `/api/status` are the accounts for which stars are set (`rating_users()`); `ok` means “password
  stored”, `rejected` “stored, but Navidrome no longer accepts it” (checked in the background, at most every 6 hours;
  unknown counts as `false`), `key` is the `.env` key. `locked` lists the keys the interface could otherwise set (`config.EDITABLE_ENV`,
  see [below](#settings--credentials)) that are set non-empty in the environment – they take precedence over `.env`
  and can't be changed in the interface. Other variables (`TUTTIPHON_DATA`, `TUTTIPHON_BASE` …) don't appear.
  Passwords themselves are in no response. `auth`: the local administrator has a password, so sign-in is on
  (`localadmin.configured()`); `adminPassword` says where it comes from (`localadmin.source()`): `"env"`
  (`TUTTIPHON_ADMIN_PASSWORD` in `docker-compose.yaml` or `.env`), `"stored"` (set in the browser, a hash in
  `state/admin_password.json`) or `""` (none) – Settings → Users & permissions shows the matching form.
- `instance.others` are the other instances that have checked in within the last 180 s – only other installations
  (`instances.others(foreign_only=True)`: announcements with the own installation ID from `state/install_id` don't
  count); `running` = a run is in progress there ([02](02-data-model.md#shared-folder-tuttiphon),
  [08](08-operations.md#multiple-instances)).
- `forMe` in `/api/welt`: `{bands: [{name, id}], share}` from the taste profile of the **signed-in** account
  (`taste.profile()`) – up to 8 of the most played bands that belong to this world (in profile order), and the
  world's share of what was played (0–1). `null` without sign-in, for the local administrator, without the account's password,
  with too little listening (`enough: false`) or if the profile can't be computed. The music world page for
  users shows “Your favorites here” from it ([09](09-interface.md#music-world-for-users)).
- `welten[].state` in `/api/artist`: `manuell` (assigned by hand), `herausgenommen` (taken out), `automatisch`
  (automatic) or `null`.
- `sound` in `/api/artist` (`classify.artist_profile()`, `null` without analyzed songs): `{songs, bpm, energy, dance,
  valence, moods, styles}` – medians over the band's songs (merged features; songs without the value don't
  count), the up to three most frequent
  moods and up to four music styles from the AI sound analysis (strength ≥ 0.4) in the models' spelling (e.g.
  “Alternative Rock”, `ml.style_label()`); the artist panel shows them as “Sounds like: …”.
- `soundsLike` in `/api/artist`: `[{name, id, score}]` – up to 8 bands of the library whose mean sound (AI sound
  vectors, `similar.Index.similar_artists()`) is closest to the band's, `score` = cosine 0–1 (only from 0.35,
  `classify.SOUNDS_LIKE_MIN`), best first; `id` = Navidrome artist ID or `null`. Empty without sound vectors or with
  fewer than 2 analyzed songs of the band ([06](06-intelligence.md#sound-similarity-appsimilarpy)).
- Errors: `/api/welt` → `400 "Music world not found"`, `/api/artist` → `400` “… is not in the library”.

## Playlists

| Endpoint | Access | Parameters | Response | Users |
|---|---|---|---|---|
| `GET /api/playlists` | signed in | – | `playlists[{id, name, status, state, count, limit, describe, mix, topArtists, covers, navidrome, cover}]`, `navidromeError`, `orphans`, `handmade[{file, name}]`, `webUrl` | visible playlists only; `handmade` and `orphans` empty |
| `GET /api/playlist` | signed in | `id` | preview (see below, 25 sample songs) plus `own`, `state`, `navidrome`, `webUrl` | someone else's private playlist → `400 "Playlist not found"`; for other people's visible playlists, `nsp` and the line “Never included: …” in `summary` are missing (the person's dislikes stay private) |
| `POST /api/preview` | signed in | Body: a playlist definition (fields as in `config.json`), plus optionally `config` (the whole configuration instead of the stored one), `date` (`YYYY-MM-DD`, reference date), `sampleSize` (default 15) | preview | computed with the server state; from `config` only one's own people count, other people without `likes`/`dislikes` (`_preview_config()`) |
| `POST /api/counts` | signed in | Body: `welt`, `person`, `hits`, `minRating`, optional `config` | `{"*": n, "<style-id>": n, …}` – song count per vibe | like `/api/preview` |
| `POST /api/snapshot` | own | Body `{"id"}` | `{"name", "count"}` | own playlists only |
| `POST /api/takeover/preview` | Admin | Body `{"file"}` (handmade `.nsp`) | `{"file", "name", "originalCount", "limit", "mapping"}` | – |
| `POST /api/takeover` | Admin | Body `{"file", "mode"}`, `mode` = `unveraendert` (default, keeps the original rules) or `baukasten` (maps them to music world × vibe) | `{"ok": true, "playlist": {…}}` | – |
| `POST /api/mapping` | Admin | Body `{"rules", "name", "person"}` | `{"mapping": null}` or `{"mapping": {…, "count", "describe"}}` | – |

- **Preview** (`rules.preview()`): `name`, `count`, `limit`, `nsp`, `topArtists`, `artistCount`, `covers`, `color`,
  `sample`, `summary`; for mixes additionally `pool` and `mix: true`.
- `config` in `/api/preview` and `/api/counts` (`_preview_config()`): admins compute with the configuration sent
  along, i.e. including changes that haven't been saved yet. Users compute with the stored state;
  from their `config` the server takes only their own people, other people enter the calculation without `likes` and `dislikes`
  – so song counts reveal no preferences or dislikes of others.
- `state` per playlist: `neu` (new), `aktuell` (up to date), `geändert` (changed), `scan`, `entfernen` (remove),
  `fehler` (error) – or, for playlists that aren't active, the status itself. `navidrome` is `{id, owner, public, songCount}`
  or `null`, `cover` `{style, v}` or `null`. Meaning of the states: [04 – Playlists](04-playlists.md).
- `/api/snapshot` creates a new, fixed playlist in Navidrome with the current selection (via the admin account,
  owner = the person's account). Empty playlist → `400`.
- `/api/takeover` changes `config.json` and schedules the auto-apply. Errors: `400` “… is not a handmade playlist
  (any more)”.

## Suggestions

| Endpoint | Access | Parameters | Response | Users |
|---|---|---|---|---|
| `GET /api/suggestions` | signed in | optional `person` | list of suggestions (`key`, `kind`, `person`, `group`, `score`, `title`, `name`, `count` …) | without `person`: only suggestions for their own people, no new music worlds (`kind: scene`), without the ones they hid; with `person`: own person only (`403`), their own hide list |
| `GET /api/inbox` | signed in | – | “To review”: list `{key, level, title, text, actions[]}` ([04](04-playlists.md#to-review-inbox)); if another installation's instance has checked in, an `instance` entry comes first | their own, simple list from `user_inbox()` (create profile, preferences, first playlist, store password) without the items they ignored |
| `GET /api/matrix` | signed in | optional `date` (`YYYY-MM-DD`) | `{"counts": {"<world>\|<style>": n}, "activeSeason": [...]}` | unfiltered |
| `GET /api/missing` | own | optional `person` (default: first own person or the default person) | `{"seeds", "missing[{artist, score, because}]", "lastfm"}` | own person only |
| `GET /api/taste` | signed in | `person` or `me=1` | `{available, enough, basis, artists, welten, moods, styles, disliked, sound, hasAccount}` – taste from plays, favorites and stars set by hand ([Intelligence](06-intelligence.md#taste-per-account-apptastepy)); `sound`: the [sound taste](06-intelligence.md#sound-taste-appsoundtastepy) is active | own person or own account only |
| `GET /api/search` | signed in | `q` (at least 2 characters, otherwise everything is empty) | `{songs, styles, moods, instruments, themes, combos, lyrics}` – songs by title, AI music styles with bands, moods with song count and matching sound vibe, AI instruments and themes with song count, combo suggestions as a mix, matches in the lyrics | `combos` with one's own person |
| `GET /api/changelog` | signed in | – | sections from `CHANGELOG.md`: `[{version, date, items, levels}]`, newest first; file missing → `[]` | unfiltered (the interface shows them to administrators only) |

`level` is `info` or `warn`; `actions` describes buttons for the interface (`do`: `goto`, `edit`, `addToWelt`,
`undoAssign`, `artist` (opens the band window of `artist`) …). The entries `auto|<band>` (“‘Band’ is now in World”, action `undoAssign` with `welt` and `artist`)
name bands that the classification assigned to a music world on its own within the last 14 days
([04](04-playlists.md#to-review-inbox)).

**`/api/search` in detail** (`api_search()`; the interface searches bands, playlists, music worlds and people itself):

| Part | Content |
|---|---|
| `songs` | up to 8 songs whose title contains `q` (case-insensitive); titles starting with `q` first, then by plays. Per song `{id, title, artist, album, albumId, artistId}` |
| `styles` | up to 4 AI music styles whose ID contains `q`, with up to 8 bands in which the style has a strength of at least 0.4: `{style, bands: [{name, id}]}` |
| `moods` | moods from `audio.MOODS` whose label or key contains `q`: `{id, label, count, stil, stilName}` – `stil` is a sound vibe whose sound filter requires exactly this one mood, otherwise `null` |
| `instruments` | from 3 characters: up to 4 instruments of the AI whose search word (`ml.INSTRUMENT_WORDS`, German and English, e.g. “Klavier”, “Gitarre”, “strings”), label or ID fits `q`: `{id, label, ids, count}` – `ids` = the instruments searched for together (e.g. all guitars), `count` = songs that clearly contain one of them (strength ≥ 0.2); instruments without songs are left out (`ml.search_instruments()`) |
| `themes` | from 3 characters: up to 4 themes of the AI whose search word (`ml.THEME_WORDS`, German and English, e.g. „Weihnachten“, „Filmmusik“, „episch“, “dark”), label or ID fits `q`: `{id, label, ids, count}` – `count` = songs in which the AI hears the theme (`ml.THEME_PRESENT`); themes without songs are left out (`ml.search_themes()`). Empty when a music world's name contains `q` (the world wins). If a vibe stands for the theme (the delivered one linked by `ml.THEME_VIBES` or one whose name fits the search word: „Weihnachten“, „Sommer“), also `stil`, `stilName` and as `count` the songs of a mix of that vibe over the whole library (`web._search_themes()`) |
| `combos` | up to 3 mix suggestions from a recognized mood, music world, vibe, instrument and theme: `{title, playlist, count}` – with an instrument, `playlist.sound.instruments` holds its `ids`, with a theme `playlist.sound.themes` (`_search_combos()`, see [04](04-playlists.md#combined-search)) |
| `lyrics` | up to 5 songs whose lyrics contain all the words (the last one also as a prefix), literal matches first, the same song on several albums only once: `{id, title, artist, album, artistId, line}` – `line` is the matching line (`liedtext.search()`). Only from two words on, or one word with at least five letters. If there is no index yet, the first search starts reading the lyrics in the background and `lyrics` stays empty |

**`/api/changelog`** (`api_changelog()`) reads `CHANGELOG.md` from the program folder (`config.ROOT`, `/app` in the
container): each heading `## <version>` (older ones with ` – <date>`, en dash or hyphen; `## Unreleased` with
`"unreleased": true`, shown as “Not released yet”) starts a section, each line
`- …` is an item (level 0), an indented `  - …` is an item of its own with level 1 (it belongs to the item above it),
other indented lines are appended to the previous item. `levels` runs parallel to `items`.


## Runs

| Endpoint | Access | Parameters | Response | Users |
|---|---|---|---|---|
| `GET /api/task` | signed in | `since` = last known line number | `{"running", "name", "steps", "step", "results", "finishedAt", "lines[{n, t, text}]", "auto": {"due", "waiting"}}` | `lines` empty |
| `POST /api/task` | Admin (function) | Body: `steps` (default: the steps of “Update everything”), optional `deezer_mode` (`new`, `missing`, `full`, `recalc`), `dry_run`, `full_scan`, `overwrite_manual`, `lyrics_all`, `lyrics_full`, `analyse_full` | run status like `GET /api/task` | `403` |
| `POST /api/task/cancel` | Admin | – | `{"ok": true}` | – |
| `POST /api/apply/now` | signed in (deliberately open to everyone: this is how users apply their own changes) | – | run status | `lines` empty |
| `GET /api/history` | Admin | – | up to 60 runs `{start, end, name, steps, results, summary, log, dryRun}` | – |
| `GET /api/log` | Admin | `file` = name of a log file from the history | `{"file", "text"}` (the last 400,000 characters) | – |

- `POST /api/task` cancels a scheduled auto-apply before starting. `/api/apply/now` starts the steps
  `playlists` + `scan` (“Apply playlists in Navidrome”). If a run is in progress whose remaining steps can all be
  paused (`flac`, `lyrics`, `analyse`, `deezer`), it briefly halts that run with `RUNNER.pause_for()`: the response is
  then the status of the still running, now pausing run; the apply starts right after it, and then
  the paused run continues as “… (continued)” ([05](05-maintenance.md#short-pause-for-an-apply-pause_for)).
  It cancels the auto-apply only once the run has actually started or the pause is queued – if the
  start fails (run can't be paused, another instance), the auto-apply stays scheduled. `/api/task/cancel` stops the current run including
  its subprocesses and cancels the auto-apply.
- `deezer_mode` `missing` rates only songs that weren't found so far; without `deezer_mode` the setting
  `settings.deezer.pipelineMode` applies (where `missing` is called “new + not found”).
- Errors: unknown steps or Deezer mode → `400`; something is already running → `400 "A task is already running."`;
  another instance (PC or Docker) is working right now → `400` “Another Tuttiphon instance (PC or Docker) is working
  right now – please try again later.” – then nothing has started and there is no history entry;
  `/api/log` with a name outside the log folder → `400 "Log not found"`.
- `auto.due` = seconds until the scheduled auto-apply, or `null`. `auto.waiting: true` (only present then): an
  auto-apply is scheduled, but a run is in progress – it follows afterwards, or pauses the run when its time comes
  (`due` is then `null`). Steps and runs: [05 – Maintenance](05-maintenance.md#auto-apply).

## Statistics

| Endpoint | Access | Parameters | Response |
|---|---|---|---|
| `GET /api/stats` | own | optional `person` | `user`, `totals`, `topArtists`, `topSongs`, `topAlbums`, `recent`, `welten`, `decades`, `genres`, `forgotten`, `neverPlayed`, plus `person` and `personsSameUser` |
| `GET /api/rueckblick` | own | optional `person`, `kind` = `woche` (week, default), `monat` (month), `jahr` (year); `year` for `jahr` | `kind`, `title`, `from`, `to`, `user`, `since`, `lastSnapshot`, `totals`, `topArtists`, `topSongs`, `topAlbums`, `series`, `busiest`, `discoveries`, `welten`, `decades`, `person` |

- Without `person`, users get their first own person, admins `settings.defaultPerson`.
- Both need the Navidrome password of the person's account (unless it is the account of the default person, with which
  the library is loaded anyway); otherwise `400` “No password is stored for ‘…’ …”. Unknown person or
  period → `400`.
- `/api/rueckblick` first records the current play counts if the last snapshot is older than 30 minutes. Background:
  [06 – Intelligence](06-intelligence.md).
- `POST /api/rueckblick/keep` (body `person`, `kind` = `woche`, `monat` or `jahr`, optional `year`) saves up
  to 50 of the most played songs of the period as a fixed playlist in Navidrome, in the person's account and with their
  visibility (`playlists.save_fixed()`): “<prefix>Recap 09/14–10/13/2026” or “<prefix>Recap 2026” →
  `{name, count}`. Nothing played → `400 "Nothing has been played in this period yet."`

## Settings & credentials

All endpoints in this section are admin-only – except `POST /api/notify/test` with one's own person (see below).

| Endpoint | Parameters | Response |
|---|---|---|
| `PUT /api/env` | Body `{"<KEY>": "value" \| null}` | `{"ok": true}` |
| `POST /api/env/test` | Body optional `url`, `user`, `password` (if missing: the stored values; a stored password only together with the stored `NAV_URL`) | `{"ok": true, "version"}` or `{"ok": false, "error"}` |
| `POST /api/paths/check` | Body `{"music", "playlists", "archive"}` (proposed locations) | per folder `{path, source, exists, writable}`, for `playlists` and `archive` additionally `insideMusic`; an archive that is the music folder or inside it → 400 with `error` |
| `POST /api/lastfm/test` | Body optional `key` (otherwise the stored key) | `{"ok": true, "tags"}` or `{"ok": false, "error"}` |
| `GET /api/users` | – | `[{name, admin, fullName}]` of the Navidrome accounts; Navidrome unreachable → `400 {"error"}` |
| `GET /api/accounts` | – | `[{name, fullName, navidromeAdmin, role, override, lastLogin, persons, passwordStored, passwordRejected}]` |
| `PUT /api/accounts` | Body `{"user", "role"}`, `role` = `admin`, `user`, `none` or `null` (remove the override) | `{"ok": true}` |
| `POST /api/admin-password` | Body `{"current", "password"}` – `current` only needed when the password was set in the browser | `{"ok": true}`, for the local administrator itself (and on the PC without sign-in) with `Set-Cookie: tuttiphon=…` – see below |
| `GET /api/intel` | – | `{"lastfm", "audio", "ml", "classify", "stile", "moods", "fingerprints"}` – status of Last.fm, sound analysis, AI sound analysis, classification and audio fingerprints (see below) |
| `GET /api/opus/info` | `refresh=1` searches anew instead of using the cache | `{"ffmpeg", "aac", "musicDir", "archiveDir", "pending", "sample"}` – `aac`: whether mutagen is available (needed for AAC) or with `error` |
| `GET /api/lyrics/stats` | – | summary of the last lyrics run plus `lastRun`, `backlog` |
| `GET /api/deezer/ranks` | – | `{"bucket", "counts", "notFound", "defaults"}` – rank distribution for the star levels |
| `GET /api/backups` | – | `{"enabled", "keep", "dir", "path", "exists", "writable", "items": [{name, size, time}], "last"}` – built-in backup |
| `POST /api/backups/now` | – | `{"name", "size", "files"}` – back up now |
| `GET /api/backups/file` | `name` (only `tuttiphon-sicherung-…zip` from the backup folder) | the ZIP file as a download (`Content-Disposition: attachment`); unknown name → `400` |
| `GET /api/kinderschutz` | – | `{"index": {songs, running, error}, "songs": [{id, title, artist, album, artistId, allowed, words}], "persons": [names with kid-safe mode]}` – all songs detected as explicit, including allowed ones; `words` = the words found `[[word, count], …]` (most frequent first, at most 3, `liedtext.rude_words()`) |
| `POST /api/liedtexte/update` | – | `{"ok": true}` – read lyrics in the background (`liedtext.update_soon()`) |
| `GET /api/pflege` | – | `{"songs", "albums", "checks": [{id, title, text, count, items: [{artist, artistId, album, albumId, title, detail}]}], "fingerprints"}` – check the library (`pflege.report()`), up to 60 entries per check. The check `aufnahme` (same recording twice, only after a comparison) also has `level: "info"`, `progress: {done, total}` and per item `similarity` and `copies: [{id, title, artist, album, albumId, format, bitRate, duration, path}]` ([06](06-intelligence.md#check-library-apppflegepy)); `fingerprints` = `fingerprint.stats()` as in `/api/intel` |
| `POST /api/notify/test` | Body optional `topic`; with `person` for that person's topic | `{"ok": true}` or `{"ok": false, "error"}` – test message via ntfy |

- `PUT /api/env` writes only the keys the interface may set via `save_env()` (`config.EDITABLE_ENV`: `NAV_URL`,
  `NAV_PUBLIC_URL`, `NAV_ADMIN_USER`, `NAV_ADMIN_PASS`, `NAV_PASS_*`, `RATING_USERS`, `LASTFM_API_KEY`,
  `NTFY_TOKEN`). Empty string = unchanged, `null` = delete. Errors: `400 "Unknown key: …"` – also for
  `TUTTIPHON_ADMIN_PASSWORD`, which goes through `/api/admin-password` –, `400` for line breaks/control characters.
  Beforehand, `api_env_save()` checks: `NAV_URL` and `NAV_PUBLIC_URL` must start with `http://` or `https://` (`400`
  “Please enter the address with http:// or https:// …”; `null` deletes it). After that the library is reloaded.
  This endpoint doesn't check passwords for `NAV_PASS_*` – the interface does that beforehand with `/api/env/test`.
- `POST /api/admin-password` (`Handler._admin_password()`, in `ADMIN_ONLY`, header `X-Tuttiphon` as for every
  `POST`) sets or changes the password of the [local administrator](07-security.md#local-administrator); only its hash
  is stored. By source (`env.adminPassword`): `"env"` → `400` “The password of the local administrator is set in
  docker-compose.yaml – change it there.”; `"stored"` → `current` must match, otherwise `400` “The current password is
  wrong.” (`400` rather than `401`, so the interface doesn't jump to the sign-in; it counts under the lockout keys of
  the local administrator, `u:@notfall|<address>`, `ip:<address>` and `u:@notfall`, then `429`); `""` (none yet: on
  the PC without network binding, where there is no sign-in yet – or in setup mode for an administrator signed in with
  a Navidrome account) → no current password needed, and from now on sign-in is required. A weak new password →
  `400` “The administrator password needs at least 8 characters.” On success the server log says “The password of the
  local administrator was changed.”, all sessions of the local administrator end (`auth._notfall_mark()`), and if the
  caller is the local administrator or the PC without sign-in, the answer carries a new session cookie for `@notfall`
  – this browser stays signed in.
- `POST /api/env/test`: the address must start with `http://` or `https://`. If it differs from the
  stored `NAV_URL` and `password` is missing, the server responds `{"ok": false, "error": "For a new address, please
  enter the password as well."}` – stored passwords are only sent to the configured address. Without `user`,
  `NAV_ADMIN_USER` applies.
- `PUT /api/accounts`: for one's own account the server refuses with `400` to set the role to `user`/`none` and –
  if the account is not an administrator in Navidrome – to remove the override (`role: null`); both would cost the
  account its own admin role. Unknown role → `400`. The role `none` additionally ends all sessions of the account
  (`auth.end_sessions_of()`).
- `POST /api/notify/test` is the only endpoint in this section that is also open to users – but only with
  `person` set to one of their own people (`_own_person()`, otherwise `403`) and only to that person's topic (`topic`
  or the stored one): the administrator's topic or one another person uses → `403`, no topic → `400 "No topic
  entered."` (no fallback to the administrator's); without `person` only for admins. If notifications are off, it
  responds `400 "Notifications are turned off."`
- `source` in `/api/paths/check`: `docker` (environment variable), `einstellung` (setting) or `standard` (default). Format of the entries in
  [`.env`](02-data-model.md#env--credentials) and [`accounts`](02-data-model.md#accounts).
- `/api/intel`: `audio` = `audio.stats()` over the **merged** features (`classify.song_features()`: own
  measurement + AI + Last.fm) – so `audio.moods` also counts “no vocals” and “acoustic” –, plus `total` (songs in the
  library). `ml` = `ml.stats()`: `{available, reason, analysed, errors, lastRun, open, current, vectors, styles,
  instruments, themes}`; `reason` says why the AI is not available (Essentia missing, models missing), `current` = songs
  analyzed with the current version (the rest still lack instruments, key, tempo and sound vector), `vectors` = songs
  with a sound vector, `styles` the up to 8 most frequent strongest styles per song as `[name, songs]`, `instruments`
  the up to 8 most frequent instruments (strength ≥ 0.2) as `[label, songs]`, `themes` the same for the offered
  themes (from their threshold). `moods` = `audio.MOODS` (ID → label). The response is cached via `_memoized()`; it is
  additionally recomputed as soon as `state/audio.json`, `state/ml.json` or `state/lastfm.json` change. Calculation:
  [06 – Intelligence](06-intelligence.md). `fingerprints` = `fingerprint.stats()`, read fresh with every request
  (not cached): `{available, why, enabled, songs, total, errors, open, lastRun, comparedAt, groups, extra}` – `songs` =
  songs with a fingerprint, `total` = songs in the library, `groups`/`extra` = recordings that are there more than
  once / files beyond the first copy ([06](06-intelligence.md#same-recording-twice-appfingerprintpy)).

## Notifications through the app

Each device registers itself (`lib/push.js`); the signed-in account always applies, never one sent along.

| Endpoint | Parameters | Response |
|---|---|---|
| `GET /api/push/key` | – | `{"available", "why", "key", "enabled"}` – whether the server supports it (package `cryptography`), its public key (base64url) for `pushManager.subscribe()` and whether notifications are turned on |
| `POST /api/push/subscribe` | Body `{"subscription": {endpoint, keys: {p256dh, auth}}, "origin"}` | `{"ok": true, "devices": n}` – remember the device for one's own account; administrators' devices also get the notifications meant for administrators. `origin` (only `https://…`) is the target when the notification is tapped. Push address of an unknown service or invalid keys → `400` |
| `POST /api/push/unsubscribe` | Body `{"endpoint"}` | `{"ok": true}` – only from one's own account |
| `POST /api/push/status` | Body `{"endpoint"}` | `{"known", "devices"}` – whether this device is registered with one's own account and how many devices there are |
| `POST /api/push/test` | – | `{"ok": true}` or `{"ok": false, "error"}` – test message to one's own devices; at most one per 30 seconds, only when notifications are on |

## Songs & listening in

| Endpoint | Access | Parameters | Response |
|---|---|---|---|
| `GET /api/song` | signed in | `id` (song ID) | song row with `track`, `suffix`, `albumId`, `lyrics` (text or `null`), `playlists[{id, name, mix}]` and – with the AI sound analysis – `key`, `camelot`, `keyStrength`, `bpmSource`, `instruments`, `themes` |
| `GET /api/song/more` | signed in | `id` | `{"artist", "songs": [song row …]}` – up to 20 similar songs |
| `GET /api/sound/catalog` | signed in | – | `{"available", "instruments": [{id, label, songs}], "themesAvailable", "themes": [{id, label, songs}]}` – the 40 instruments of the AI with label in the page's language and the number of songs of the library that clearly contain them, the same for the nine offered themes (songs in which the AI hears the theme); `available` / `themesAvailable` = the AI has recognized instruments / themes at all (`ml.sound_catalog()`) |
| `GET /api/instruments` | signed in | – | the older name of `/api/sound/catalog`, same answer (it still has `available` and `instruments` as before) |
| `GET /api/stream` | signed in | `id`, `f=mp3` for browsers without Opus | audio from Navidrome (`stream`), otherwise `400` |

- **Song row** (`Library.describe()` + `rules._with_sound()`, also in `sample` of `/api/playlist`/`/api/preview` and
  `top` of `/api/artist`): `id`, `title`, `artist`, `artistId`, `album`, `year`, `cover`, `duration`, `genres`,
  `rating` and – if analyzed – `bpm`, `energy`, `moods`.
- `/api/song`: `synced` are the lines of synced lyrics `[[ms, text], …]` (from 3 lines on) from Navidrome's
  `getLyricsBySongId` – from the `.lrc` next to the file or embedded –, otherwise `null`; without a lyrics index,
  `lyrics` comes from there.
- `/api/song`: `playlists` are the active playlists visible to the account that aren't currently resting and that contain the
  song – for smart playlists in the pool of the rules, for mixes in the selection just written
  (`state/mixes.json`). `lyrics` comes from the lyrics index (`liedtext.text_of()`, without timestamps).
- `/api/song`, AI fields (`classify.song_details()`, each missing if unknown): `key` = key in Essentia's spelling
  (`"A minor"`, `"C# major"`), `camelot` = its code on the Camelot wheel (`"8A"`; A = minor, B = major, neighbours
  blend well), `keyStrength` = confidence 0–1; `bpmSource` = where `bpm` of the song row comes from: `"ai"` (the AI's
  tempo, its analysis windows agree) or `"measured"` (our own measurement); `instruments` = `[{id, label, strength}]`,
  the up to 5 strongest instruments (strength ≥ 0.1, strongest first; from about 0.2 an instrument is clearly there);
  `themes` = `[{id, label, strength}]`, the offered themes the AI hears in the song (from their threshold, strongest
  first).
- `/api/song/more` (“More like this”): pool of a radio starting from the song's band (Last.fm's similar bands and –
  with sound vectors – bands that sound alike), with one's own person (`_default_person()`: dislikes, kid-safe mode),
  without a minimum rating; ordered by `classify.rank_like()`: with sound vectors mainly by sound similarity to the
  song (songs without a vector after those that sound alike), plus arousal, mood and tempo, some randomness; at most
  3 songs by the band itself and 2 per other band, then shuffled. No playlist is created; “Keep as radio mix” in the
  interface creates one.
- `/api/stream`: fetches the audio via the admin account (`Navidrome.stream()`) and passes it through in chunks – the
  credentials stay on the server. The default is the original file (`format=raw`) with `Range` passed through
  (response `206` with `Content-Range`, seeking works); with `f=mp3` Navidrome transcodes to MP3 at 192 kbit/s (no seeking).
  Navidrome doesn't count this as a play – statistics, recap and taste stay untouched.
- Song IDs must match `^[A-Za-z0-9_-]{1,64}$` and be in the song list, otherwise `400 "This song no longer
  exists."`. **Kid-safe mode:** if one of the account's own people has it on, all three respond with `403` for songs with
  explicit lyrics or songs tagged “explicit” (`web._child_blocked()`); administrators are exempt.

## Images & covers

| Endpoint | Access | Parameters | Response |
|---|---|---|---|
| `GET /img/<id>` | signed in | `<id>` = cover ID from Navidrome (album, `ar-…` for artists, `pl-…`), `s` = size | image (`image/webp`, `image/jpeg` or `image/png`), `Cache-Control: max-age=604800` |
| `GET /live/<id>` | signed in | `<id>` must start with `pl-`, `s` = size, `v` = version | playlist image, `Cache-Control: max-age=86400` |
| `GET /cover` | own | `id` (playlist), `style` (default `mosaik`) | designed cover as `image/jpeg`, `Cache-Control: no-store` |
| `GET /api/cover/styles` | signed in | – | `{"<style>": "<label>"}` – without Pillow only `album` |
| `POST /api/cover/apply` | own | Body `{"id", "style"}` | `{"ok": true}` |
| `POST /api/cover/remove` | own | Body `{"id"}` | `{"ok": true}` |
| `POST /api/cover/upload` | own | Query `id`; body = raw image data (not JSON), at most 10 MiB | `{"ok": true}` |

- `/img/` fetches the image from Navidrome via the admin account (`getCoverArt`) and stores it in the cache under
  `state/cache/img/`; if the file there is older than 14 days, it is fetched again (if Navidrome is unreachable: the
  old image). `/live/` is for images that change: memory only (at most 200 entries),
  `v` is part of the key. Sizes are rounded to 64, 150, 300 or 600 (default 300). IDs must match
  `^[A-Za-z0-9_:.\-]{3,120}$`, otherwise `400 "invalid image ID"`. No image → `404` with an empty body.
  Both check only the sign-in, not whether the playlist or the album is visible to the account.
- `/cover` and `/api/cover/apply` render the image with `covers.render()`. `apply` uploads it via Navidrome's own API
  and records `cover = {style, sig, nid, at, rev}` in the playlist; `remove` deletes the image in Navidrome and
  the entry. `upload` detects the format from the first bytes (`covers.sniff()`: only JPEG, PNG, WebP; the
  `Content-Type` sent doesn't count) and stores `cover = {style: "eigenes", at, rev}`.
- Errors: unknown style → `400` (`/cover`: “Unknown cover style”, `/api/cover/apply`: “This style is not available
  here”; allowed are the styles from `covers.available_styles()`); playlist not in Navidrome yet → `400` “The
  playlist is not in Navidrome yet – apply first, then set the cover.”; no usable image → `400`.
  When covers are renewed automatically: [04 – Playlists](04-playlists.md).
