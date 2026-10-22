# Changelog

A brief summary of what changes in each version. The newest version is on top; `npm run release` copies its
section into the release notes `README.txt`. If `docker-compose.yaml` has to be replaced during an update, it says so explicitly.
Changes that are not released yet are collected under “Unreleased” – the version number follows when they are
released.

## Unreleased

- **Translations checked:** corrections in all six new languages (e.g. Spanish “por sí solo” where it means “by
  itself”, Italian always “tu”, the colour theme with its own word), counts in the singular where there is one song
  or band, and recap titles in each language's own form (“octubre de 2026”).
- **Plugin card, more precise:** “Last answer with similar songs” says when and for whom – “probably for …” when
  Tuttiphon only guessed from the plays. A guess never brings a child profile's music and leaves 1-star songs in. The
  setup steps name “Sonic Analysis” for the smart queue too, and users see the help on radio by sound only once
  Navidrome really uses the plugin.
- **Who is listening, more reliably:** accounts without a person in Tuttiphon count as listening too, so their
  questions are never answered for someone else.
- **Covers set in Navidrome stay recognized** by the image Navidrome serves; if Navidrome creates such a playlist
  anew, Tuttiphon's cover comes back.
- **Notifications:** “new music” also arrives when the server speaks another language, and a translation that fails
  falls back to English instead of losing the message.
- **Small phones:** the assistant's buttons, the task bar, the mini player and messages stay above the navigation
  even when its labels take two lines; switches and segmented controls fit at 320 px; every switch has a name for
  screen readers. Statistics load faster (summaries kept per day).

- **Six more languages:** the interface and the server now also speak French, Dutch, Spanish, Italian, Portuguese
  and Polish – chosen per device under Settings → General (now a list), otherwise the browser's language. Counts
  follow the rules of each language (Polish “2 piosenki”, “5 piosenek”). The search understands moods, instruments
  and themes in these languages too (“musique calme”, “chitarra”, “kerstmuziek”). The translations were made with AI
  help – corrections are welcome on GitHub.
- **A new installation speaks the language of its first administrator:** the language of the server (notifications,
  playlist names in Navidrome) is taken from the browser at the first setup, and the setup assistant shows it in its
  first step to change.
- **Notifications in your own language:** every phone gets its notifications in the language of its Tuttiphon
  interface – also after you switch it; an ntfy topic in the language of the person's devices. Playlist names in them
  stay as in Navidrome.
- **The smart queue knows you on a shared account:** if the family person uses your Navidrome account too, the
  answers are now for you instead of for the family.
- **The bar of a running task can be put away:** ✕ or swipe it aside – it stays away until the run ends (a night
  analysis runs for hours); the spinning icon in the header stays.
- **Helping with translations:** `tools/translate.py` exports every text of a language as a simple table and puts
  corrections back after checking them – also for a new language.

## 1.6.0

The smart queue in Symfonium now plays for whoever is listening and moves on between bands; the help is half as long.

- **After updating:** nothing to do – the Navidrome plugin file stays the same as in 1.5.0.
- **The smart queue for whoever is listening.** Navidrome does not tell the plugin who asks – but Tuttiphon sees from
  the plays who is playing what. If the song asked about is playing on exactly one account (or only one account is
  playing), Instant Mix, song, artist and album radio and the smart queue in Symfonium answer for that person: without
  their dislikes, without what they heard in the last three hours or rated 1 star, songs they often skip further down.
  Otherwise the answer is for the family as before; kid-safe always stays as for the family. Settings → Navidrome
  shows for whom the last answer was.
- **The smart queue does not stay with one band:** Symfonium takes the most similar song every time – mostly of the
  same band, so it could play five of them in a row. After two songs of a band in a row, other bands now come first,
  and a band heard often in the last hour comes a little later.
- **Shorter help:** every help topic now says in a few short points what something does and where to find it –
  about half as long as before, without technical details; administrator topics point to the handbook for those. The
  questions & answers are shorter too and no longer repeat the topics.
- **Help for the family:** the help topic “Listening in Symfonium” explains the two Symfonium settings for the
  plugin – similar tracks for the radio mix and the smart queue by sonic analysis – as soon as the plugin is set up.
  The German texts now use Symfonium's German names for them.
- **Covers set by hand in Navidrome stay – also of the same image type.** Navidrome names a playlist's image after
  the playlist, so an image uploaded there by hand often kept the name of Tuttiphon's cover and was overwritten at the
  next renewal. Tuttiphon now keeps a checksum of every cover it uploads and compares it with the image in Navidrome
  before renewing. Works for covers uploaded from this version on.

## 1.5.0

Every play now reaches Tuttiphon as it happens through the Navidrome plugin, and the plugin answers by sound also for
songs the AI has not analysed yet.

- **After updating:** put the new `tuttiphon.ndp` into Navidrome's plugins folder (exactly this name, not unpacked)
  and restart Navidrome; allow the plugin **all users**; if you entered the agents line from 1.4.0, replace it with
  `tuttiphon,deezer,lastfm,listenbrainz`. Tuttiphon's own docker-compose stays as it is.
- **Sound answers also for songs the AI has not analysed yet:** Instant Mix, the smart queue and sound paths take the
  mean sound of the song's album or band – before, such a song got only the radio with the same similarity for every
  song, and a path between such songs stayed empty. Paths mix bands (only a few songs per band), similar bands come
  only from what may play, an artist who only takes part in a song leads to their own songs, and the same recording
  (“(Remastered)”) comes only once.
- **Navidrome plugin, sturdier:** while Tuttiphon is not reachable (update, restart), Navidrome rests the plugin for
  two minutes and asks its other sources; plays are handed on later. Wrong keys from elsewhere no longer shut the
  plugin out – the right key always passes.
- **Skips, judged more carefully:** a cross-fade, going back to the previous song, the first song after a long pause
  and a short track played to its end no longer count as skipped; with several devices on one account every player
  is judged on its own.
- **Privacy:** live plays are kept only for accounts with a person in Tuttiphon that are not blocked, readable only
  by Tuttiphon, and removed after 120 days also for accounts that stopped playing. The plugin's answers leave out
  explicit songs as soon as a profile has kid-safe mode (before only with a child profile).
- **Navidrome plugin card:** “Copy” also works over http, the agents lines can be selected, the status refreshes
  itself, and while no play arrives a hint says what to check. The plugin file now carries the licenses of the parts
  compiled into it.
- **Plays live from Navidrome.** The Tuttiphon plugin now also passes every play on as it happens (as Navidrome's
  scrobbler): the listening clock gets exact times, also when a song is played twice a day; the mixes learn from real
  skips – a song left within 30 seconds – for every song, not only guessed from the mix history; and accounts without
  a stored password get their plays into the recap. In Navidrome, allow the plugin **all users** (plugin settings →
  Users) and update the plugin file. Settings → Navidrome shows the last play received.
- **Navidrome plugin address:** the card now recommends Tuttiphon's address in the home network – an https address
  through a reverse proxy may turn the plugin's requests away. Errors in Navidrome's log now say what Tuttiphon
  answered.
- **The image no longer depends on one server for the AI models:** each model file gets three attempts with pauses,
  and if essentia.upf.edu does not answer (as during the 1.3.0 build), the rest comes from an unchanged copy in the
  repository's pre-release `ai-models-v1` – with the same checksums. The copy is made once with the workflow “AI
  models copy”.
- **Navidrome plugin, setting it up:** the plugin downloaded in Settings → Navidrome keeps its name `tuttiphon.ndp`
  (phones saved it as `tuttiphon.ndp.zip` – rename such a file, do not unpack it). The card, the help and the handbook
  show the agents line for `navidrome.toml` as well (`Agents = "tuttiphon,deezer,lastfm,listenbrainz"`) and put
  Tuttiphon in front of Navidrome's own defaults – the line given in 1.4.0 left out ListenBrainz.

## 1.4.0

Navidrome and its apps now find similar songs by sound – with a plugin that asks Tuttiphon.

- **Instant Mix by sound – the Tuttiphon plugin for Navidrome.** Navidrome asks Tuttiphon for similar songs and
  artists: Instant Mix in Navidrome, “similar songs”, song and artist radio and related artists in Symfonium and other
  apps then follow the sound of your own files from the AI sound analysis – also for bands that Last.fm hardly knows.
  Apps with OpenSubsonic's `sonicSimilarity` also get sound paths from one song to another. Set up under Settings →
  Navidrome → “Navidrome plugin”: create a key, download the plugin, put it into Navidrome's plugins folder, add
  `ND_AGENTS=tuttiphon,lastfm,deezer` to Navidrome's settings, enter address and key in Navidrome. Needs Navidrome
  0.64 or later. Navidrome does not say who is listening – the songs come from the whole library as for the family,
  without explicit songs as soon as there is a child profile.
- No changes to Tuttiphon's `docker-compose.yaml` needed (only Navidrome's, see above).

## 1.3.0

A family library played by parents and children – each with their own taste – and covers that make the
formats easy to spot.

- **Children’s music no longer shapes a parent’s taste.** In the profile, “Not part of your taste” takes music worlds
  out of a person’s taste – e.g. the children’s music that plays on a parent’s account. Discoveries, album of the week,
  own sound, favorite bands and “Good morning” then follow the person’s own music; the family person on the same
  account keeps it, and the playlists of the music world stay as they are. “To review” points it out when a separate
  world such as children’s music makes up a big part of what an account plays.
- **Child profiles.** If a child has a Navidrome account of their own, the administrator marks the profile as a
  child profile (in the kid-safe card). Then children’s music belongs to the child’s whole library – discoveries, album
  of the week, own sound and good morning include it, audio plays stay out of the mixes –, and kid-safe mode is always
  on. When an account plays mostly children’s music, “To review” asks the administrator “Is … a child?” with one click
  to set it – and such an account is never told to keep its music out.
- **“New for you this week”** – on Mondays a short notification to each person with “Discovered for you” or “Album of
  the week”: how many never played songs are waiting and which album it is – on a phone shared by several people once.
  It can be turned off under Settings → Notifications.
- **Covers for the formats.** Discovered, album of the week, good morning, own sound, new from favorite bands, what
  everyone likes, rediscover and your month get a cover of their own by themselves – the same look every week, with
  the album itself on the album of the week – so they are easy to spot in Symfonium. An image set in Navidrome itself
  stays; after “Navidrome default” the format cover does not come back. A format whose designed cover was removed
  before this version gets the format cover once more on the first run – “Navidrome default” takes it away for good.
- No changes to `docker-compose.yaml` needed.

## 1.2.0

New ways to find music in your own library – most songs in a family library have never been played.

- **“Discovered for you”** – like Spotify’s Discover Weekly, inside your own library: every Monday 30 songs the
  account has never played, picked by its taste, at most two per band and one per album.
- **“Album of the week”** – every Monday one whole album the account has never played, by a favorite band or in its
  sound, in album order; no singles, EPs or compilations. It stays the same all week.
- **“Good morning” from your listening.** Tuttiphon now knows when each account listens (from the plays it already
  sees in Navidrome, so it works right away) and suggests “Good morning” only to those who really listen in the
  morning: as long as their usual morning round, starting calm and getting livelier, and sounding like what they play
  in the morning. The card says why (“for the usual listening on weekdays around 6:45”).
- **Fewer, better suggestions first.** Per person, “Discover” now starts with a small core set of formats with a fixed
  rhythm (discovered, album of the week, own sound, new from favorite bands, rediscover, your month, good morning and
  the Daily Mixes of the two most played worlds); all other ideas are behind “more ideas”. Music worlds and your own
  playlists work as before.
- **Is a mix listened to?** The page of a mix now shows how much of its last editions was played (“Listened to in 3 of
  the last 8 weeks – 18 % of their songs played”). A mix of which not a single song played for at least 12 days appears
  under “To review” with “Pause” – sooner than the 90 days that apply to all playlists.
- The new formats need a stored Navidrome password for the account (its plays). Without one the suggestions stay as
  before; “Good night” and “Car ride” are unchanged. No changes to `docker-compose.yaml` needed.

## 1.1.0

- **No password in docker-compose.yaml any more.** At the first start Tuttiphon opens straight to its setup: you set
  the password of the local administrator in the browser, with a one-time setup code. The code makes sure that nobody
  else who reaches the page first can claim it. Only a hash of the password is kept.
- The setup page says where the code is: in the container log on the line “Setup code:” (written there again whenever
  the page is opened) and in `config/setup-code.txt`.
- The password can be changed under Settings → Users & permissions (with the current one). Forgotten: delete
  `config/state/admin_password.json` – Tuttiphon then asks again with a new code. The sign-in page and the help
  explain both.
- `TUTTIPHON_ADMIN_PASSWORD` stays as an option: if it is set, it applies as before and can only be changed there.
  **Existing installations need no change.** To switch, remove the line, recreate the container and enter the setup
  code from the log. The interface can no longer write it into `config/.env`.

## 1.0.2

- The container log (`docker logs`) is always English, whatever the server language. The run logs in the interface
  keep the server language.
- A new installation opens the sign-in page straight as the local administrator: until Navidrome is connected, a
  Navidrome account cannot sign in anyway. After signing in, the setup assistant connects it.
- Phone: the labels in the bar at the bottom stay on one line and centered under their icon. For users the entry
  “My playlists” is now called “Playlists”, like for administrators.

## 1.0.1

The names from the time when Tuttiphon was called NaviTool no longer count. **Check before updating:**

- The administrator password is only read as `TUTTIPHON_ADMIN_PASSWORD`. `NAVITOOL_PASSWORD` and `TUTTIPHON_PASSWORD`
  no longer count – with only one of them, the container does not start. Rename any other `NAVITOOL_…` variable to
  `TUTTIPHON_…` as well, in `docker-compose.yaml` and in `config/.env`.
- Everyone signs in once more (the session cookie has a new name); each browser also forgets its theme and language
  choice once.
- Backups named `navitool-sicherung-….zip` are no longer listed or cleaned up – keep them elsewhere or delete them.
- The hidden folder `.navitool/` in the playlist folder is no longer used (Tuttiphon uses `.tuttiphon/`) and can be
  deleted after the update. Playlists still marked "NaviTool" count as hand-made.
- Gone as well: reading the credentials and logs of an earlier Deezer rating script from `deezer-bewertung/` in the
  Navidrome folder, and rebuilding runs from before the history existed from their logs.

## 1.0.0

- First public version on GitHub. The ready-made image is `ghcr.io/seluce/tuttiphon` – installation with
  `docker-compose.yaml` as described in the README. Everything before was a beta (0.x); there are no changes to the
  program compared with 0.17.1.
- Credits: the Deezer star ratings build on [dztnr](https://github.com/scatolo/dztnr) by scatolo, a fork of
  [sptnr](https://github.com/krestaino/sptnr) by Kevin Restaino (MIT) – named in the README and in
  THIRD-PARTY-NOTICES.md.

## 0.17.1

Fixes from a comprehensive audit (security, files, configuration, performance, interface, texts, release).

- **Your music is safer when converting:**
  - The new file is decoded completely and compared with the length the original declares. A damaged or cut-off
    original (an unfinished copy or download) therefore stays where it is, and so does its original.
  - A missing or read-only archive folder converts nothing, instead of leaving every song twice in the library. The
    archive folder itself is never created, and an archive inside the music folder is refused.
  - ALAC → AAC can no longer lose a song. An interrupted move to an archive on another disk is finished in the next
    run, and a different file of the same name in the archive is kept.
  - Tags of WAV and AIFF files reach AAC files, Opus files get their own front cover, and cover.jpg is only written
    for folders with a single album. Two originals with the same name (Song.flac and Song.wav) are left alone with a
    note.
- **Lyrics, loudness and backups:**
  - Tidying up lyrics keeps a .txt next to an empty or "instrumental" .lrc.
  - Loudness leaves hard-linked files (e.g. downloads still being shared) alone and keeps owner, permissions and the
    ID3 version.
  - Backups never contain earlier backups.
- **One family account can no longer break things for everyone:**
  - Values such as endless numbers or text where a number belongs are refused when saving, and a broken playlist is
    skipped instead of stopping all others.
  - Each account can create at most 200 playlists and 20 profiles.
  - Kid-safe mode also applies to new profiles of the same account, and the search hides songs tagged as explicit.
  - A user's test notification only goes to their own topic.
- **Sign-in and server:**
  - The sign-in lock also counts attempts that are still being checked.
  - Security headers on every answer, no technical details in error messages, data files only readable by Tuttiphon.
  - "My account" shows when the stored Navidrome password no longer works and lets you enter the new one.
- **Damaged files are set aside instead of being emptied:** Deezer ranks, recap, mix learning, the lyrics index
  (rebuilt right away, kid-safe playlists are rewritten) and the push key. A damaged config.json stops the start with
  a clear message instead of failing everywhere.
- **Much faster with large libraries:**
  - With 25,000 songs the playlists page opens in 6.5 s instead of 48 s the first time, and in 2.5 s instead of 16 s
    after the song list was reloaded – with exactly the same results. Statistics and suggestions are faster too.
  - Less memory in normal operation.
  - The folder watch analyzes only the new music, so new songs reach their playlists without waiting for the backlog.
  - The AI no longer waits forever if loading its models hangs, and a briefly unreadable file no longer costs a song
    its sound and AI values.
- **Interface:**
  - The app loads faster: rarely used pages load when first opened.
  - After an update an open app reloads or offers "Reload" instead of showing an empty page.
  - If Tuttiphon can't be reached, changes are kept and saved as soon as it is back.
  - The back button closes an open window.
  - Playlist cards and help topics fit on small phones; on the iPhone the app keeps clear of the status bar.
  - Readable status colors in the light theme, better keyboard and screen-reader support, "reduce motion" is
    respected.
  - Errors stay visible until closed, and failed actions say why.
  - A mix created from the search renews weekly, as the search says.
- **Help and texts:**
  - New help topics "Setup assistant", "Backup" and "Language & theme". The notifications topic describes push
    through the app first.
  - After a password change the help says how to turn statistics & stars back on.
  - Many corrections. German singular forms ("1 Song"), consistent terms, and "Unser Oktober" for family recaps.
  - Playlist names from suggestions follow the server language. "What's new?" shows nested items separately.
- **Installing and building:**
  - The compose file is now called `docker-compose.yaml` (the GitHub workflows `.yaml` too). The release folder ships
    the template as `docker-compose.example.yaml`, so it can never take the place of your own compose file by mistake
    – an existing `docker-compose.yml` keeps working unchanged.
  - New files no longer get the owner `1000:10` by default: on new installations they belong to the user Tuttiphon
    runs as (`user:`). Existing installations keep their earlier setting.
  - The README now says to create the config, backups and archive folders first and give them to the `user:` account.
    Otherwise the container keeps restarting.
  - The published image always contains the AI models. `latest` only moves for the newest release.
  - Building it yourself now uses the complete interface sources, so the build on the NAS matches the official one.
  - Licenses of all bundled parts are listed in THIRD-PARTY-NOTICES.md.
  - The README names the licensor of the AI models.
  - New section on going back to an older version.
  - The README is short now (features, quick start, links); details moved to docs/features.md and
    docs/installation.md.

## 0.17.0

- New **setup assistant** for new installations: after the first sign-in an administrator is asked step by step what
  Tuttiphon should do – connection to Navidrome, converting lossless files (Opus, AAC or off, and what happens to the
  originals), lyrics, understanding the music, Deezer stars, what runs by itself – each with a short explanation and
  a sensible default; a first run only starts if you ask for it. It can be skipped and opened again under
  Settings → General. New installations no longer convert anything until someone turns it on; existing
  installations don't see the assistant and keep all their settings, conversion included.
- The taste per account also learns from the sound: from the AI's sound vectors of what an account plays, favorites
  and rates highly, Tuttiphon finds a few typical sounds (a family account gets one for the children's songs and one
  for the adults' music instead of a meaningless average); songs skipped often and rated 1–2 stars count against.
  Mixes weight with it, “Your sound” most, and suggestions that sound like what the person plays move up. The card
  “From your listening” then says “Also learns from the sound of what you play.”
- The AI sound analysis recognizes two more things per song: how easy it is to listen to (mainstream or demanding)
  and how much it asks for close listening (or is background music). Two new sound vibes use them: **“In the
  background”** and **“For listening closely”** – existing installations get them with the update (in the server’s
  language), a vibe someone deleted stays deleted. The sound editor has “Easy to listen to” and “For close listening”
  (and “not for dancing” for danceability), and the search understands “Hintergrundmusik”, “easy listening”, “zum
  Zuhören” and the like.
- The AI's **themes** are usable: Christmas, film music, epic, dark, love songs, romantic, ballads, summer and space –
  the sound editor has “Themes – one of them is enough”, the song window shows a song's themes, and the search finds
  them (“Filmmusik”, “episch”, “düster”, “dark” …) with a mix to create, also combined (“düstere Mittelalter”). A music
  world or vibe of the same name comes first: “Kinder” stays the music world, “Weihnachten” the vibe “Christmas”, whose
  keywords are far more precise. No new analysis needed – every song the AI already knows has its themes.
- New README for GitHub: what Tuttiphon does, screenshots, installation, configuration and why these AI models
  (and not bigger ones) – so it runs on a small NAS. `docker-compose.yml` is now short; the options are explained
  in the README.
- After the update the AI analyzes the library once more – one pass that also covers the re-analysis 0.16.0 brought
  (key, tempo, instruments, sound vector): new music first, the rest night after night; until then the two new
  vibes only find the songs already done. The image brings two more small models (about 1 MB).

## 0.16.0

- New version numbers: everything so far is a beta (0.x) – 1.0.0 will be the first public version on GitHub.
  The earlier versions 1.0.0 … 2.1.1 are now 0.1.0 … 0.15.1.
- Ready for GitHub: license AGPL-3.0-or-later, a README for new users, a ready-made image
  `ghcr.io/seluce/tuttiphon` (built automatically for every release) and automatic checks for every change.
- `docker-compose.yml` is now a template for new installations: the ready-made image instead of building it yourself,
  example paths `/music`, `/archive`, `/backup`. Existing installations keep their docker-compose.yml – nothing needs
  to be replaced.
- The README and the handbook describe the installation for any NAS; the separate guide for one NAS model is gone.
- Building it yourself: the release for moving an installation is now `npm run release:with-data` (formerly
  `release:umzug`); its folder is called `first-install/`.
- Help → Docker names the paths of the template and links to the README on GitHub; Settings → General → About
  Tuttiphon links to the source code.
- The emergency access is now the **local administrator** – Tuttiphon’s own account with all rights, which works
  without Navidrome. Its password is `TUTTIPHON_ADMIN_PASSWORD`; `TUTTIPHON_PASSWORD` and `NAVITOOL_PASSWORD` keep
  working, so existing docker-compose.yml files need no change. The template’s placeholder is `change-me`.
- Changing the language under Settings → General happens right away, without reloading the page.
- “Music import” in the settings is now called “Conversion”; on the home page a single step starts with
  “Run separately”.
- Settings → Users & permissions fits on the phone: the role choice moves below the name.
- No more false “Tuttiphon is running twice” after an update that changes the container’s host name: every
  installation now recognizes its own earlier announcements.
- Simpler to use:
  - Settings on the phone: a list in five groups (Account, Family, Connection, Music, Operation), each section opens
    as its own page; on the computer the side list has the same groups.
  - Clear terms: smart playlists of a whole world are called “… · Querbeet”/“All Sorts” – “Mix” only for playlists
    that renew themselves. German uses Band, Bibliothek, Mag nicht and Daily Mix throughout; adding favorites is
    “hinzufügen”, no longer “übernehmen”.
  - Less twice: the playlist page shows Edit (and Reshuffle) – the rest is in the “…” menu; Discover has a person
    filter for administrators; duplicate buttons on the home pages are gone.
  - The search opens a mix as a preview first instead of creating it right away; “To review” offers “Assign music
    world …” for new bands and opens the band window.
  - Profile: “What you like to hear” as compact choices, name/icon/color at the bottom, “+ Remember” for detected
    favorite worlds.
  - Phone: choice bars scroll sideways instead of breaking into two lines; step 1 of the assistant shows two worlds
    per row; status dots only for administrators.
- Fixes from a usability check:
  - Sound vibes describe themselves (“by sound: cheerful · getting livelier”) instead of “still empty”, and the
    group “Sound” has a label.
  - Delivered vibes added by an update get their name in the server language (e.g. “Guten Morgen”).
  - A failed run says so in the history instead of “no changes”.
  - The × to take a band out of a music world is visible on touch screens.
  - Playlists in the trash no longer say “for everyone”.
  - “You might still be missing” no longer suggests bands that are already in the library.
  - Smaller wording and layout fixes on the phone (profile, taste card, settings icons, assistant).
- Check library finds the **same recording twice** by its sound – also across formats, folders and albums, e.g. a
  FLAC file left next to its converted Opus file or a song on the album and on a best-of. Live and studio versions,
  re-recordings, karaoke and instrumental versions stay apart. Audio fingerprints (Chromaprint `fpcalc`, new in the
  Docker image) are made during “Understand music” and at night, new songs first; they can be turned off
  (Settings → Intelligence, default on). Without `fpcalc` (e.g. on the PC) the check stays off. The fingerprints
  (about 3 KB per song) are not part of the backup – they renew themselves.
- The AI sound analysis understands more (it analyzes the library once more, new songs first, the rest night after
  night – until then everything keeps working with the earlier results):
  - **Sound similarity:** a compact sound vector per song tells which songs and bands
    sound alike. The artist window gets “sounds like” bands from the library, “More like this” and the band radio
    rank by sound, and classifying new bands also compares their sound with that of each music world.
  - **Smooth transitions:** mixes are ordered so that one song leads into the next – similar sound, close tempo,
    a compatible key (Camelot wheel) and similar energy, still never the same band twice in a row
    (Settings → Playlists, default on; not in mixes for falling asleep or waking up).
  - **Instruments:** the strongest of 40 instruments per song (piano, guitars, strings, violin, synthesizer …).
    Sound vibes can require instruments, and the search knows instrument words: “Klavier”, “Gitarre”, “Streicher”,
    “piano”, “strings” – e.g. “ruhige Klaviermusik”.
  - **Key and tempo:** the AI recognizes the key and a more reliable tempo; the tempo replaces the old estimate
    (which was off for about a third of the songs) in sound vibes, “for falling asleep” and mixes. The song window
    can show key and tempo.
  - In the interface: the song window shows the key with its Camelot code, where the tempo comes from and the
    instruments; the search lists instruments and opens a mix of them as a preview; the sound editor of a vibe has an
    instrument picker; Settings → Playlists has the switch “Smooth transitions in mixes”, Settings → Intelligence shows
    the progress of the new analysis and of the audio fingerprints (with their own switch); Check library lists the
    copies of each recording with format, length and path – and expanded checks no longer widen the page.
- Language switch: a quick double switch can no longer mix up languages; the sign-in page, the app manifest and
  error messages follow the interface language.
- Security check before publishing:
  - On the network, Tuttiphon stays locked if the administrator password goes missing while it runs.
  - Saving an empty value no longer deletes an administrator password stored under an old name.
  - Placeholders count in any spelling.
  - Sign-in only from the interface. Failed attempts lock per account and address, so a stranger can no longer lock
    an account for everyone.
  - Behind a reverse proxy, `TUTTIPHON_TRUSTED_PROXIES` names the proxy: the lock then counts each person’s own
    address, and the session cookie is only sent via https.
  - Links in the shared playlist folder are no longer followed.
  - Backups fail loudly when settings or credentials cannot be read.
  - A fresh checkout without a data/ folder creates one instead of writing into the project folder.
  - The image runs as a normal user by default and contains the license.

## 0.15.1

- The handbook, README, change log and release notes are now in English (the release notes file is
  `README.txt`). The interface still speaks German for German browsers.
- Search understands English mood words too: “calm”, “sleep”, “dance”, “good mood”, “without vocals” …
- The mood “ohne Gesang” is called “no vocals” in English everywhere (German unchanged).
- New bands are classified right away only if they reach the stricter of 0.75 and the configured threshold.

## 0.15.0

- Tuttiphon speaks English and German. The interface follows the browser’s language; it can be switched per
  device under Settings → General → Language. With a German browser, everything stays German, word for word as before.
- New alongside it: “Language of the server” (administrators only) for logs, notifications and the names
  Tuttiphon assigns by itself. Existing installations are set to German, new ones start in English.
- The scene catalog and the bundled vibes come in English and German; the vibes now also find
  English songs (“Dance”, “Sleep”, “Spring” …). Applies to new installations – existing vibes stay as they are.
- The help pages only load when opened, so the app starts a little faster.
- Small fixes: with a count of 1 it now says “1 song”, “1 playlist” instead of “1 songs”; under “Via ntfy” a space
  was missing.

## 0.14.0

- NaviTool is now called **Tuttiphon** – tutti, all together, like the whole family. The name changes in the interface, in the app icon
  on the phone, in notifications and in the playlist descriptions.
- Nothing needs to be adjusted: the existing docker-compose.yml with NAVITOOL_PASSWORD remains valid, as do sign-in,
  playlists, old backups and the shared folder in the playlist folder. At the next sync, Tuttiphon
  changes the description of every playlist in Navidrome to the new name once.
- On the iPhone, an icon already placed on the home screen keeps its old name until it is added again.

## 0.13.0

- Music import: optionally AAC instead of Opus (Settings → Music import → Target format). iPhone, iPad and Mac
  play AAC everywhere; the default is 224 kbit/s, selectable from 128 to 320. Tags are carried over completely, including MusicBrainz IDs,
  ISRC and multiple artists, the way Navidrome reads them, plus the cover. The switch applies to new conversions –
  existing Opus files stay as they are. Opus remains the default.

## 0.12.0

- Notifications via the app: instead of ntfy, messages now come straight from Tuttiphon to the phone, without an
  extra app. Turn on each device once – administrators under Settings → Notifications, everyone else
  in their profile under “To your phone”. Requires Tuttiphon’s https address, and on the iPhone, Tuttiphon on the home screen.
  ntfy still works for anyone who uses it.
- Kid-safe mode list (Settings → Lyrics): grouped by band, bands with the most songs first and collapsed,
  with search by band, song or word and the filter Blocked/Allowed. Each song shows which words were found;
  “allow all” unblocks an entire band at once, with Undo.

## 0.11.0

- More accurate Deezer stars: a match only counts if band and title fit – previously about one song in twenty
  got another song’s rank, for example Pentatonix “Bored” got that of “Bohemian Rhapsody”. If the search finds nothing,
  Tuttiphon looks up the song precisely by its MusicBrainz ID and ISRC – this finds about two thirds of the songs
  previously not found. Stars that came from a wrongly matched song disappear again; your own stay.
- Top tracks per band: if many songs of a band share the highest star count, the most popular ones get one more
  star – so Symfonium sorts the top tracks correctly.
- Every night Tuttiphon rechecks 1,500 songs with Deezer, starting with those rated by the old search. After about two
  weeks everything has been checked once; after that the stars stay up to date.
- Synced lyrics: in the song window the lyrics scroll along during playback; tapping a line jumps there.
- Even out loudness (Settings → FLAC → Opus, opt-in): Tuttiphon measures the loudness of every song at night
  and writes ReplayGain values into the files without re-encoding them. Turn on ReplayGain in Symfonium, and
  all songs play equally loud.

## 0.10.0

- Music worlds: “Rebuild” rebuilds a world with a scene entirely from that scene, with its name and
  icon – beforehand Tuttiphon shows which bands drop out and whether playlists get different names. Bands that become free
  immediately get a world of their own if there are enough of them. Playlists and favorite worlds stay attached.
- Discover: your own suggestions are on top, then those for the season, then the family’s. Each section can be
  collapsed; the device remembers it.

## 0.9.3

- “What do you like to listen to?” only asks as long as Tuttiphon doesn’t already know the taste from listening.

## 0.9.2

- Statistics on the phone: for the most played bands, the bar sits below the name – the names are fully readable. The same
  in “Who’s in it?” and in the assistant.
- Notices at the bottom, such as “15 playlists deleted”, can be swiped away to the side.
- Discover: a hidden suggestion comes back after half a year if it still fits then. At the bottom of the
  page, all hidden ones can be brought back right away – so Discover never runs empty. Deleted music worlds stay
  gone, even when restoring under My account.

## 0.9.1

- On the phone, the second time it is opened, Tuttiphon suggests once to put it on the home screen as an app – with a
  button where the browser offers this, otherwise with short instructions. Once dismissed, the hint does not come back.

## 0.9.0

- Listening in the browser: tapping a song plays it – in a playlist’s sample, in the assistant’s
  preview, among a band’s popular songs. A small player at the bottom shows what is playing; on the phone also on the
  lock screen. Listening in does not count for statistics and recap.
- Song window: “…” on a song or a hit in the search shows the album, the sound, which playlists the song appears in and
  the lyrics to read along. “More like this” then plays similar songs from your collection, “Keep as radio mix”
  turns them into a playlist.
- Shorter pages: without playlists of your own, “For you” shows a “Let’s go” card instead of several empty sections, the
  sample on the phone shows only 10 songs at first, people without playlists appear as a single line, “You might also like” shows
  only 6 bands at first.
- Kid-safe mode also applies to listening in: explicit songs can’t be played.

## 0.8.0

- Less memory: the song list takes about a third of what it used to, every additional account with open
  statistics about 15 instead of 70 MB. In operation Tuttiphon thus needs about 110 instead of 170 MB.
- The song list is refreshed in the background every 15 minutes – no page waits for it anymore.
- Folder watch only reads folders in which something has changed: with 22,000 songs a check takes
  fractions of a second instead of half a minute.
- Playlists in the trash are permanently deleted on their own after 30 days.
- Once a week Tuttiphon cleans up: data stored for songs that have been gone for 30 days – e.g. after
  conversion to Opus – is forgotten; very old skip marks of the mixes are dropped; once a month the
  lyrics index is compacted. If the music folder is unreachable at the moment, nothing is forgotten.

## 0.7.0

- Missing covers: for albums without any picture, Tuttiphon fetches a cover from the Cover Art Archive or from Deezer and places it as
  cover.jpg next to the music – during “Update everything” and once a week at night. Existing pictures stay; new
  albums get two days for Lidarr.
- Seasonal playlists such as Christmas appear in Symfonium only during their season and then come back on their own.
- “To review” reports playlists nobody has listened to for three months – with “Pause” – and duplicate playlists.
- New mixes for the daily routine: Good morning, which starts calm and gets livelier, and Car ride with an hour of
  music for the whole family.
- Your own covers stay: when a seasonal playlist comes back or a playlist is brought back from pause or trash,
  Tuttiphon uploads your own image again.
- Kid-safe mode now also applies to favorite songs and star playlists, in the family mix for everyone involved – including
  anyone who has since been set to private – and in the monthly recap. The recap also leaves out dislikes and songs rated 1 star.
- More reliable: the lyrics index no longer forgets anything during short NAS outages. Newly created music worlds are
  no longer lost when saving. Covers are only placed in folders with exactly one album. Notifications that didn’t
  arrive are retried; errors are reported at most once a day. Plays count for the
  correct day even if the daily refresh runs after 6 a.m.
- Faster and leaner in continuous operation: the playlist overview calculates each mix only once and paused ones not at all;
  Deezer figures, recap and backup list are cached; the lyrics index and new music worlds run
  at most every 6 hours after pure playlist runs. Backups leave out the lyrics index; it rebuilds itself.
- docker-compose.yml limits the container logs to 30 MB. Applying the new file is optional – if you do, first enter
  the password and paths from your previous file.

## 0.6.0

- Music worlds form on their own: Tuttiphon recognizes from genres, Last.fm tags, AI music style, language and decade
  which worlds the collection yields – such as The 80s, The 90s, Eurodance, German rap, Pop & charts, Schlager &
  party or audio dramas – and creates them as soon as there are enough bands or someone listens to them a lot.
- New bands, e.g. from Lidarr, join their world on their own – also existing worlds with a scene.
- A new installation starts without predefined music worlds and gets them from its own collection.
- The music worlds page and the assistants show the worlds you listen to first, with “you listen to it often”.
- New worlds are collected under “To review”. Deleted ones don’t come back; this can be turned off under
  Settings → Intelligence.
- The lyrics search also recognizes the language of every song. On the first start, the lyrics are read in
  once more for this.

## 0.5.1

- Playlists: “Empty trash” deletes all playlists in the trash at once – with confirmation and “Undo”.

## 0.5.0

- New from your favorite bands: whatever is added by the bands someone likes or listens to most lands as a
  playlist under Discover. On the home page, such albums carry the badge “Favorite band”.
- What everyone likes: a mix for the family in which everyone’s taste counts equally – good for car rides.
- Good night: a mix with a fixed length, about 30 minutes, that gets calmer and calmer and fades out without vocals where possible.
  The length in minutes can be set for any mix.
- Your month: the most played songs of the last month as a playlist that switches on the first of the month – there is always
  just one. Plus Your year. In the statistics, every recap can be kept as a fixed playlist.
- Lyrics search: one line from the song is enough; the search shows the song with the matching line.
- Kid-safe mode: per person, songs with explicit lyrics can be left out of all playlists and mixes. The detected
  songs are listed under Settings → Lyrics and can be allowed individually.
- Check library: duplicates, albums without a cover or with gaps, very short files, songs without a genre and low-quality
  MP3s at a glance.
- Notifications to the phone via ntfy: to the administrator for errors, new music and newly classified bands,
  to each person with their own topic for news from their favorite bands and the monthly recap.
- Help: new guides for kid-safe mode and notifications, topics and questions about everything new.

## 0.4.0

- New hands-on help: under “What would you like to do?” there are guides such as “Mix for your phone”, “Make suggestions
  better” or “Stop hearing something”. “Show me” leads step by step through the real interface – on the phone
  just as on the PC. The screenshots have been dropped.
- The ? next to each page title opens the page’s explanation as a window, with the matching guide at the top.
- The help can be searched. Topics expand and collapse; buttons appear in the text just as in the interface.
- New help topic “Search & moods”.

## 0.3.0

- Taste from listening: Tuttiphon recognizes from plays in Symfonium, favorites and stars given by the listeners themselves
  which music worlds and bands someone likes. Stars from the Deezer rating don’t count here.
- Suggestions come from this even without entered preferences, marked “Played often”: mixes of the
  favorite worlds, radios of the most played bands, rediscovery and new music worlds that fit what has been played.
- New mix “Your sound”: every day, songs from the entire library that sound like your own taste – by
  sound, AI music style and bands.
- All personal mixes prefer songs that sound like the person’s taste.
- Profile: card “From your listening” with music worlds, bands and moods, each can be applied with one tap.
- Welcome assistant: favorite worlds and bands are preselected from what has been played.
- Search also finds songs, AI music styles and moods – a mood directly creates a matching mix.
- Combined search: inputs like “calm children’s songs” or “Christmas kids” immediately suggest the matching mix.
- Music world page: “Your favorites here” and “Daily mix” with one tap.
- New bands, e.g. from Lidarr, are added to their music world automatically when the match is certain; “To review” shows what
  was classified, with “Undo”.
- “For you” and home page: compact header, mixes and suggestions first, explanations only for new accounts.
- Changes to playlists no longer wait for a long analysis: analysis, lyrics, Opus and Deezer pause briefly,
  then continue on their own.
- Welcome assistant and tour appear only once per account, on all devices.
- Phone: notice bar at the bottom across the full width, search field in “My playlists” on its own line.
- Sign-in: password managers such as Bitwarden fill in username and password correctly.
- Log in the container: startup with version, storage locations and Navidrome, plus every run with its result, sign-ins,
  backups and errors – each with a timestamp.
- Version number and this changelog under Settings → General.
- Texts in the interface only explain the function.

## 0.2.0

- Sign-in: the cursor no longer jumps into the password field while typing the name.
- Tour: anyone who finishes or skips it won’t see it again on any device.
- Help and settings no longer jump to the top first when switching.
- “Progress” leads to the live log. During a run, no countdown keeps counting down endlessly anymore.
- A new music world opens without an error message.
- Settings → Intelligence: sound analysis and AI are in one card with two levels.
- Docker: the image sets the read permissions itself. docker-compose.yml rebuilds on every create – for this, add
  `pull_policy: build` under `image:` once.

## 0.1.0

- First version as a Docker container on a NAS.
- New interface, sign-in with the Navidrome account and a separate view for each family account.
- Mixes learn from skipped songs and stars given by hand.
- Self-check after every scan, AI sound analysis with night analysis, daily backup, an archive folder for the converted originals.
