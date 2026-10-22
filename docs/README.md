# Tuttiphon – technical handbook

Tuttiphon maintains smart playlists and mixes for Navidrome, enriches the library (Opus, lyrics, Deezer stars,
sound analysis with local AI) and gives every family member their own view. This handbook describes **how**
this works – for everyone who develops or runs Tuttiphon. What the family sees in the app is explained by the help in the
interface. For users and admins there are two short guides: [Features](features.md) (what Tuttiphon does, privacy, why
these models) and [Installation and configuration](installation.md).

The handbook describes the current state of the code. Whoever changes something updates the affected chapter in the same go.

## Chapters

| | Chapter | What it covers |
|---|---|---|
| 1 | [Architecture](01-architecture.md) | Navidrome, Tuttiphon and Symfonium; process and threads; modules; folders; command line |
| 2 | [Data model](02-data-model.md) | `config.json` with all fields, migration, `.env`, `state/`, `logs/`, `backup/` |
| 3 | [API](03-api.md) | all HTTP endpoints with permissions, parameters and responses |
| 4 | [Playlists](04-playlists.md) | music world × vibe × person, rules, writing and syncing, takeover, mixes and how they learn from listening, suggestions, combined search, covers |
| 5 | [Maintenance](05-maintenance.md) | runs and steps, short pause while applying, “Update everything”, Opus, lyrics, Deezer, scan with self-check, daily refresh, night analysis, folder watch |
| 6 | [Intelligence](06-intelligence.md) | sound analysis, AI sound analysis (Essentia), moods, Last.fm, classification of new bands, taste per account, statistics and recap |
| 7 | [Security](07-security.md) | sign-in and lockout, roles, sessions, local administrator and setup mode, network lock, reverse proxy, what the server filters |
| 8 | [Operations](08-operations.md) | PC and Docker, publishing the image, memory and CPU, storage locations, updates, versions and going back, the Navidrome plugin, backup, multiple instances, troubleshooting, server log |
| 9 | [Interface](09-interface.md) | Svelte structure, state and saving, windows, “For you”, search, music world, tour and welcome, design, tests, extending |

**Where to start, by question**
- *Where do I begin?* → [Architecture](01-architecture.md), then [Data model](02-data-model.md).
- *Why does a playlist (not) contain this song?* → [Playlists](04-playlists.md), section Rules.
- *A run failed.* → [Operations](08-operations.md), troubleshooting, and [Maintenance](05-maintenance.md).
- *New endpoint or new page?* → [Security](07-security.md) and [Interface](09-interface.md), section Extending.

## Terms

| Term | In code | Meaning |
|---|---|---|
| Music world | `welt` | Who plays: a group of bands (and genres), e.g. Kinder or Mittelalter; can be linked to a scene |
| Scene | `scene` | catalog of typical bands of a music genre (`app/scenes.json`); linked music worlds take in these bands automatically |
| Vibe | `stil` | What is played: genre, topic, season, decade or special filter; sound vibes select by the sound analysis |
| Person | `person` | Who the playlist is for: one person per Navidrome account – the owner of its playlists (private there), with likes and dislikes |
| Family | `family: true` | optional person with a Navidrome account of its own that Tuttiphon creates: its playlists are for everyone, “What everyone likes” exists only there; nobody signs in to Tuttiphon with its account, shared devices use it in Symfonium. Who may change its playlists: `settings.familyEdit` |
| Smart playlist | `.nsp` | rule file; Navidrome selects anew from all matching songs on every request |
| Mix | `type: "mix"`, `.m3u` | fixed selection that Tuttiphon puts together anew daily, weekly or monthly |
| Radio | `radio.seed` | mix of a band and similar bands |
| Run | `task` | one execution of steps in the background, with a log and an entry in the history |
| Step | `flac`, `lyrics`, `analyse`, `playlists`, `scan`, `deezer` | one part of a run |
| Update everything | `settings.pipeline` | the run with all configured steps |
| Auto-apply | `settings.autoApply` | changed playlists go into Navidrome on their own after a short wait |
| Short pause | `TaskRunner.pause_for()` | applying playlists briefly pauses a running Opus, lyrics, analysis or Deezer run; afterwards it continues as “… (continued)” |
| Takeover | `takeover` | a hand-made `.nsp` is maintained by Tuttiphon and stays the same playlist |
| Daily refresh | `settings.dailyAt`, `dailyMode` | daily run at the set time (default: write playlists and scan – this is when the mixes change); in addition, the play counters are saved once a day for the recap |
| Night analysis | `settings.analysis.night` | nightly `analyse` run (default 01:00–05:00) that analyzes pending songs without a time limit – first the sound analysis, then the AI |
| AI sound analysis | `app/ml.py`, `settings.analysis.ml` | pre-trained models (Essentia) pick out mood, vocals, acoustic/electronic and music style; refines the sound analysis |
| Mixes learn | `settings.mixLearn`, `app/feedback.py` | what gets skipped comes up less often in mixes, songs rated 1 star by hand not at all anymore |
| Self-check | `app/selfcheck.py` | after every scan: does Navidrome show as many songs per playlist as Tuttiphon expects? Deviations → “To review” |
| Instance | `<playlist folder>/.tuttiphon/` | a running Tuttiphon – on the PC or in the Docker container; registration and run lock live in the shared playlist folder |
| Administrator / user | `role: admin \| user` | role in Tuttiphon; users only see their own person's and the family's items |
| Local administrator | `@notfall`, `app/localadmin.py` | Tuttiphon's own administrator account, also when Navidrome is not running: its password is set in the browser at the first start with a setup code from the server log (only a hash in `state/admin_password.json`) – or as `TUTTIPHON_ADMIN_PASSWORD` |
| Setup mode | `Handler.network`, `POST /api/setup` | a server on the network without an administrator password: sign-in required, the password is set with the one-time setup code from the server log and `setup-code.txt` |
