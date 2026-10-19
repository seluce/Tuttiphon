# 9 · Interface and tests

This chapter explains how the interface is built, how it talks to the server and how to test it.
The quick reference (components with props, classes, commands) is in
[`frontend/README.md`](../frontend/README.md); this chapter is about how things fit together and how they flow.

## Technology

| | |
|---|---|
| Framework | Svelte 5 with runes (`$state`, `$derived`, `$effect`, `$props`, snippets) – without SvelteKit |
| Build | Vite 8, two entry points: `frontend/index.html` (app) and `frontend/login.html` (sign-in) |
| Styling | Tailwind 4 with custom tokens in `frontend/src/app.css`, Inter font (`@fontsource-variable/inter`) |
| Icons | Lucide (`@lucide/svelte`), three custom drawings in `lib/icons.js` |
| Tests | Playwright against a test server with a copy of the data |

`npm run build` writes to `web/`. Files under `web/assets/` carry a content hash in their name; the server delivers
them with `Cache-Control: immutable`, and `index.html` and `login.html` with `no-cache` (`app/web.py`, `_static()`). So
after a build everything is fresh right away, without the browser holding on to anything old. `web/` is generated and
not in Git; `tuttiphon.sh` builds it when needed, the Docker image in a separate build stage ([Operations](08-operations.md)).

Without a build, the server answers `/` with 503 and the message “the interface has not been built yet”.

## Folders

```
frontend/
  index.html, login.html      entry points; a small script applies the theme (light/dark) before the first paint
  public/                     copied to web/ unchanged: favicon.svg, manifest.webmanifest, sw.js, icons/
  src/
    main.js · App.svelte      app startup and frame (sidebar, header, router, overlays, tour)
    login.js · Login.svelte   sign-in page
    app.css                   design system
    shell/                    parts of the frame: Nav, Search, UserMenu, TaskBar (apply bar), AdminOnly
    lib/                      logic without its own UI (see below)
    components/               reusable components; components/sheets/ for side sheets
    pages/                    one file per page; larger pages have a subfolder (pages/settings/, pages/start/ …)
```

### `lib/` at a glance

| File | Contents |
|---|---|
| `api.js` | `api(path, { method, body })` – JSON, header `X-Tuttiphon`, 401 → sign-in page, errors as `Error` with the server's text |
| `state.svelte.js` | shared state `S`, saving/undo, loading, runs (see below) |
| `overlay.svelte.js` | side sheet, dialog, toast (`openSheet`, `modal`, `confirmDialog`, `toast`) |
| `router.svelte.js` | hash router: `route`, `go()`, `rerender()`, `params()`, `syncRoute()` |
| `icons.js` | icon names → Lucide; motifs for music worlds/vibes/people; old emojis → icon |
| `playlist.js` | `plName()`, `plEmoji()`, `plDescribe()`, states `STATE` |
| `format.js` | numbers, times, `uid()`, `slug()`, gradients for placeholders |
| `theme.js` | theme light/dark/system (`localStorage` `tuttiphon-theme`) |
| `editor.js` | option lists and `openEditor()` (edit sheet of a playlist) |
| `artist.js` | `openArtist()` (band window), `startRadio()` |
| `player.svelte.js` | listening: state `player` (list, current track, time), `playList()`, `playTrack()`, `continueWith()`, `toggle()`, `next()`, `prev()`, `seek()`, `stop()` – see [Listening](#listening-and-the-song-window) |
| `song.js` | `openSong(track)` – song window |
| `sound.svelte.js` | results of the AI sound analysis: `keyName()` (key in the page's language), the catalog of instruments and themes `loadCatalog()`/`soundCatalog()`/`instrumentLabel()`/`themeLabel()` (`GET /api/sound/catalog`, loaded once per language), `narrowsLibrary(sound)` (instruments or themes allow “All × Everything”) |
| `discover.js` | `accept()` – create a suggestion as a playlist |
| `takeover.js` | `openTakeover()` – take over a handmade playlist |
| `welten.js`, `richtungen.js` | `addWelt()`; summary, groups and season helpers for vibes |
| `account.js` | `logout()`, `passwordModal()` |
| `history.js` | summary of a run, `openLog()` |
| `settings-info.js` | texts for home page sections and run steps |
| `tour.svelte.js` | tour and guides (state, tour steps per role, `startTour()`, `startGuide(id)`, `endTour()` – “seen” only for the tour, in the browser and on the server) |
| `guides.js` | “Show me” guides: `GUIDES` with three short steps, search words, role, condition `show(admin)` and `steps(ctx)`; `guidesFor(admin)`, `guideById()`, `guideSteps()` |

## Languages

The interface speaks English and German. English is in the code and goes through `t()` from `lib/i18n.svelte.js`;
German comes from dictionaries `{ 'English text': 'deutscher Text' }` in `src/locales/de/*.js` (one file per area). The
language: the choice on this device (Settings → General → Language), otherwise the browser's, otherwise English. The
German dictionary is a separate file in the build and is only loaded for German (`await import()` in
`i18n.svelte.js`). `api()` sends the language along as `X-Lang` (`lang()`).

**Switching without a reload.** The language is reactive state (`$state.raw`): `t()` and `tn()` in a template or a
`$derived` follow a switch at once; `lang()` and `locale()` are functions for the same reason. Texts outside the
template are `$derived` in components and `translated(() => …)` at module level (a Proxy that is rebuilt per
language). `setLanguage()` returns whether the language changed; Settings → General then calls `reloadTexts()`
(`lib/state.svelte.js`), which fetches status, playlists and (administrators, if loaded) the history again with the
new `X-Lang`. Pages fetch their own data in the new language the next time they load. `tools/i18n-check.mjs` reports a
`t()` that runs only once – at module level or while a component is set up – as `static`. Rules, fixed terms and
check tools (`tools/i18n-check.mjs`, `tools/compile-check.mjs`):
[`frontend/README.md`, “Texts and languages”](../frontend/README.md#texts-and-languages).

## Pages and routes

The router reads `location.hash`; `App.svelte` picks the page and rebuilds it for every new route
(`{#key}` over path, query and `route.key`). When the page changes, an open side sheet closes and the page scrolls to
the top; `go()` to the current route only rebuilds and keeps the position. Help and settings are the exception
(`SAME_PAGE`): the part after `#/hilfe/` or `#/einstellungen/` only picks the target on the same page – the page stays
and scrolls by itself.

**Loaded when opened.** Only the pages opened most often (`Start`, `Home`, `Playlists`, `Playlist`) are part of the app
file; all others are files of their own (`PAGES` in `App.svelte`, drawn through `components/Lazy.svelte`). Shortly after
the start they are loaded in the background (`preload()`, for users without the admin pages), so opening them later
needs no server. If a file cannot be loaded – usually Tuttiphon was updated while the page was open and the old files
are gone – `main.js` reloads the page once (`vite:preloadError`, at most once a minute, never for the background
loading); otherwise `Lazy` shows “This page could not be loaded” with “Reload”. A newer server version is also noticed
directly: `loadStatus()` compares the `version` of `/api/status` with the one at the start (every 30 s and whenever the
page becomes visible again) and `App.svelte` then offers “Reload” (`S.newVersion`).

**Back button.** Redirects replace the address instead of adding a history entry (`replace()` in
`lib/router.svelte.js`): unknown addresses → `#/`, the welcome and setup assistants at the start, users on
`#/person/neu` → `#/willkommen` – so “back” never leads into a redirect again. An open side sheet has a history entry
of its own (same address, `history.state.ntSheet`): the back button – on Android, in the browser – closes the sheet
instead of leaving the page. Closing it otherwise removes the entry again; going somewhere from the sheet (`go()` or a
link) replaces it, so “back” afterwards leads to the page before. The steps of the assistants have no history entries
(“back” leaves the assistant).

| Route | Page | Who |
|---|---|---|
| `#/` | `Start.svelte` (administrator) or `Home.svelte` (“For you”) | everyone |
| `#/willkommen` | `Welcome.svelte` – assistant for new users | everyone |
| `#/einrichtung` | `Setup.svelte` – setup assistant, see [Setup assistant](#setup-assistant) | administrator |
| `#/playlists`, `#/playlist/<id>` | overview, detail page | everyone (users: their own + shared) |
| `#/neu?person=…&welt=…&stil=…&type=…&step=…` (from the search also `mood=…`, `instr=…`, `theme=…`, `name=…`, `every=day\|week\|month`) | `Wizard.svelte` – see [Assistant](#assistant-new-playlist) | everyone |
| `#/entdecken` | suggestions, missing bands, music world × vibe table | everyone |
| `#/welten`, `#/welt/<id>` | music worlds (users: view, “Like”) | everyone |
| `#/richtungen` | vibes | administrator |
| `#/personen`, `#/person/<id>`, `#/person/neu` | people, profile, assistant for a new person | profile: own; rest: administrator |
| `#/profil` | users with a profile → `#/person/<id>`; administrator → people | everyone |
| `#/statistik/<gesamt\|woche\|monat\|jahr>` | statistics and recap | everyone (own accounts) |
| `#/einstellungen`, `#/einstellungen/<section>` | `Settings.svelte` – fifteen sections in five groups (`allgemein`, `konto` · `benutzer`, `start`, `benachrichtigungen` · `navidrome`, `speicher` · `playlists`, `deezer`, `lyrics`, `opus`, `intel`, `bibliothek` · `ablaeufe`, `sicherung`); without a section the list on the phone, the first section on the computer – see [Settings](#settings) | everyone (users only `allgemein` and `konto`) |
| `#/verlauf` | history of all runs | administrator |
| `#/hilfe/<topic>` | help (one version per role), expands the topic and jumps to it | everyone |

Admin pages show users a friendly notice (`shell/AdminOnly.svelte`). That is only a convenience – the actual
boundary is drawn by the server, which doesn't send admin data to users in the first place
([Security](07-security.md)).

## App startup

`App.svelte`, function `init()`:

1. Apply the theme (`theme.js`).
2. Load `/api/me` and `/api/config`. If that fails, the page shows the error with “Try again” – “Server unreachable”
   when Tuttiphon cannot be reached at all; then it also tries again by itself every 10 s.
3. Users are sent to `#/willkommen` (`needsWelcome()`) if they don't have a profile yet – or have a profile
   without favorite worlds, without favorite bands and without their own playlists and haven't finished the assistant
   yet (`S.me.welcomeSeen` from the server or `localStorage` `tuttiphon-welcome:<account>`). Not if the route is already
   `#/willkommen` or `#/hilfe…`; never for administrators.
   Administrators go to `#/einrichtung` (`needsSetup()`) while `settings.setup.done` is `false` – a new
   installation that nobody has set up yet. Only once per browser session (`sessionStorage` `tuttiphon-setup`), not from
   `#/hilfe…`; never for users.
4. Load status and library; pages that can show little without the library (music world, assistant, person,
   vibes) wait for it.
5. Show the page, then load the playlist status, start polling for runs, refetch the status every 30 s. In a hidden
   tab both pause; when the page becomes visible again they continue at once (and a pending change is saved when it
   gets hidden).
6. Register the service worker (only over https or localhost), load the other pages in the background. The
   “Install as app” prompt (`S.installPrompt`) is kept from the very beginning (`listenInstall()` in `main.js`) – the
   browser may offer it before the app has started.
7. After 1.5 s start the tour – only for administrators and users with a profile, not on
   `#/willkommen` and `#/einrichtung` (the setup assistant starts it when it is done), and only if the account hasn't finished it yet (`S.me.tourSeen` from the server, otherwise
   `localStorage` `tuttiphon-tour:<account>`); see [Tour and welcome](#tour-and-welcome).

## State and saving

`lib/state.svelte.js` holds one state `S` for the whole app.

| Field | Source | Kind |
|---|---|---|
| `S.me` | `/api/me` | who is signed in, role, own people |
| `S.config` | `/api/config` | **deeply reactive** – pages change objects directly |
| `S.status`, `S.library`, `S.pl`, `S.history` | `/api/status`, `/api/library`, `/api/playlists`, `/api/history` | only ever replaced as a whole |
| `S.task`, `S.auto`, `S.running`, `S.logLines` | `/api/task` | current run, auto-apply, live log |
| `S.done`, `S.saved` | counters | go up after every finished run or every save |
| `S.offline`, `S.newVersion` | requests, `/api/status` | Tuttiphon cannot be reached (unsaved changes wait); the server runs a newer version (offer “Reload”) |

**Saving.** A page changes e.g. `p.name = 'Neu'` and calls `changed()`. After 450 ms without another change, `save()`
sends the whole configuration via `PUT /api/config` – saves run one after another, never two at once.
Afterwards the playlist status and the library are refetched after a short delay. If the server rejects it, a toast
appears, an open side sheet closes (it would keep editing objects that are no longer in `S.config`) and the
configuration is reloaded (the last change is then discarded). If Tuttiphon cannot be reached (no answer at all, or a
reverse proxy answers 502–504 – `api()` marks such errors with `offline`), the change stays: `S.offline` shows a notice
at the top of the page, the status is asked again every 5 s, and as soon as the server answers the change is saved.
`api()` errors carry `status`; without an error text from the server they say “The server reported an error (status)”.
A 401 leads to the sign-in page with the address within the app (`/login.html#/…`), and after signing in back there.
The sign-in page (`Login.svelte`) asks `GET /api/login` first. In setup mode (`{"setup": true}`: a new installation on
the network without an administrator password, [Security](07-security.md#setup-mode)) it shows only the setup form:
“Setup code” (`XXXX-XXXX`, with a hint that it is in the container log and in `setup-code.txt`), “New administrator
password” and “Repeat password”, button “Set password and sign in” (`POST /api/setup`); it checks beforehand that the
code isn't empty, the password has at least 8 characters and both are the same; there is no switch to the normal
sign-in. As long as Navidrome is not connected (`{"navidrome": false}`), it opens straight as the local administrator
with a hint and without the switch to the normal sign-in. In both cases the setup assistant takes over after signing
in.

**Undo.** Before a change `snapshot()`, afterwards `toast('…', { undo: true })`. The button restores the previous state,
closes open overlays (which would otherwise keep working on old objects) and saves. The toast disappears by
itself (with a button after 6.5 s, otherwise after 2.6 s); errors stay until they are closed (×) and are announced
right away by screen readers (`role="alert"`). Swiped aside – with a finger on the phone, with the mouse on the
computer, from 60 px – it goes immediately (`ToastHost.svelte`); buttons in it stay tappable.

**Ranked lists** (`.arow` in `app.css`: band, bar, number – “Who’s in it?”, statistics, assistant): on the phone the
bar sits below the name so that the name stays readable; picture and number span both lines.

**Proxy trap.** Whatever you insert into `S.config` becomes a reactive proxy there; the original object is then no
longer reactive. So after `S.config.playlists.push(p)` continue with `S.config.playlists.at(-1)`. Likewise write
`obj.genres ??= []` as its own statement and pass `obj.genres` afterwards – the value of the expression
`obj.genres ??= []` is the raw array.

**What the server changes itself** (`file`, `takeover`, `cover` of a playlist; bands that the step “Understand
music” assigns to a music world on its own): after a run, `mergeServerFields()` merges this into the existing
objects without replacing `S.config` – open edit sheets keep their references, and the next save
doesn't overwrite the server's assignments.

**A page's own data** (e.g. `/api/playlist`, `/api/home`, `/api/stats`) is loaded by the page itself and reloaded after
a run: `$effect(() => { S.done; untrack(load) })`.

## Runs and auto-apply in the interface

`pollTask()` polls `/api/task?since=<n>` – every second while a run is in progress or an auto-apply is pending,
otherwise every 4 s. New log lines go to `S.logLines` (at most 5,000). When a run ends, the app first takes over the
server's changes (`mergeServerFields()`), then saves its own pending changes, reloads status, library, playlists
and (administrator) the history, and increments `S.done`.

`shell/TaskBar.svelte` shows a small indicator at the top of the header while something is running, and a floating bar
at the bottom (notice bar). Users only see apply runs (all steps are `playlists` or `scan`, `isApplyRun()`),
no analysis or maintenance runs. The bar shows the first thing that applies:

| State | Bar |
|---|---|
| a (visible) run is in progress | “<name> …”, for administrators with “Progress” (jumps to the live log on the home page) |
| `S.auto.waiting` and playlists not yet applied | “Changes follow after the running task” |
| `S.auto.due` set | “Changes reach Navidrome in N s” with “Now” (`applyNow()`) |
| auto-apply off, playlists pending | “N change(s) not yet in Navidrome” with “Apply” |

`applyNow()` first saves open changes and then calls `POST /api/apply/now` – if an analysis or similar is running,
the server pauses it briefly for this ([Maintenance](05-maintenance.md#short-pause-for-an-apply-pause_for)). On the
computer the bar is a pill centered above the content; on the phone (up to 900 px) it spans the full width (12 px margin),
sits above the bottom navigation, the text wraps to at most two lines, and in the playlist assistant
(`.wiz-foot`) it is hidden. What happens on the server is described in [Playlists](04-playlists.md) and
[Maintenance](05-maintenance.md).

## Overlays

`lib/overlay.svelte.js` manages one side sheet, one dialog and one toast; they are drawn by
`SheetHost`, `ModalHost` and `ToastHost` in `App.svelte`. The content is either a snippet (defined in the calling
component with `{#snippet}` and used as a value in the script) or a component with props:

```js
openSheet({ title: name, component: ArtistSheet, props: { name } })
const ok = await confirmDialog(t('Delete playlist?'), t('It disappears from Navidrome.'), t('Delete'), true)
const picked = await modal({ title: t('Take over “{name}”', { name }), component: TakeoverChoice, props: { info, choice },
  buttons: [{ label: t('Cancel'), value: 'cancel' }, { label: t('Apply'), value: 'ok', primary: true }] })
```

While a side sheet is open, the page behind it does not scroll (`html.sheet-open`), Tab stays inside the sheet, the
sidebar and the page are `inert`, and the back button closes the sheet ([Pages and routes](#pages-and-routes)).
The dialog uses `<dialog>` with `showModal()`: Enter triggers the default button, Esc closes it. Dangerous buttons are
never the default. Values from a dialog are kept in `$state` of the content component or in an object passed in – not
in the DOM.

## Attachments

Whatever has to touch an element directly is a Svelte 5 attachment (`{@attach fn}`, no `use:` actions): the function
gets the element when it is mounted, runs again when state it reads changes, and a function it returns cleans up.

| Where | Attachment | Does |
|---|---|---|
| `components/SheetHost.svelte` | `focusPanel` | a new side sheet gets the focus itself – not its first field, otherwise the keyboard pops up on the phone |
| `components/ModalHost.svelte` | `show` | opens the `<dialog>` with `showModal()` |
| `pages/start/LiveLog.svelte` | `follow` | the live log scrolls to the end whenever lines arrive (it reads `lines`) – unless it was scrolled up to read |
| `components/sheets/SongSheet.svelte` | `follow` | synced lyrics: keeps the current line in the upper third of the box while the song plays |
| `pages/welten/WeltEdit.svelte` | `focusSearch` | “Add band” puts the cursor into the band search |
| `components/Seg.svelte` | `showChosen(value)` (exported) | a row that scrolls sideways brings the chosen option (`.on`) into view – only sideways, the page never moves. Used by every `Seg`, the step bars of the assistants (`Wizard`, `NewPerson`, `Setup`) and the person and period rows of the statistics |

## Pages for everyone: For you, Discover, search, music world, profile

### “For you” and the home page

Both home pages start with a **compact header** (`.hero.grad.compact` from `app.css`: less padding,
smaller heading, even smaller on the phone) – the space belongs to the mixes and suggestions. The administrators'
home page (`pages/Start.svelte`, header `pages/start/StartHero.svelte` with “Update everything”) orders its
sections by `settings.start.sections` ([Data model](02-data-model.md#home-page)).

“For you” (`pages/Home.svelte`, users) has a fixed order:

| Section | Contents |
|---|---|
| Header | date, greeting with first name, number of own playlists and mixes, songs in the library; “New playlist”, “Discover”. Without own playlists, a sentence about what will appear here |
| Next steps | only if there are any: entries from `GET /api/inbox` (profile, preferences – only as long as Tuttiphon doesn't already know the taste from listening, `taste.profile()` with `enough` –, first playlist, password); “later” adds them to `ignored`. Without an own playlist, “Your first playlist” is left out – “Let’s go” covers that |
| Let’s go | only without an own playlist, instead of “Your mixes” and “Your own playlists”: a sentence about mixes and up to three mix suggestions to tap – no buttons of its own, “New playlist” and “Discover” are in the header |
| Your mixes | as soon as there are own playlists: the own mixes (`TodayRow`); without a mix, a row with mix suggestions and “Create your own mix” |
| Discovered for you | up to 6 suggestions for own people (`GET /api/suggestions`, without hidden and shared ones) as `pages/home/IdeaCard.svelte`; without suggestions the section is left out |
| Your week | recap of the week for the own person (`GET /api/rueckblick`). Left out without an own person and without a password as long as “Next steps” shows “Turn on statistics & stars”; otherwise “Turn on stats” there |
| Your own playlists | own active playlists – only if there are any |
| Shared by the family | active playlists of other people – only if there are any |
| New in your library | new albums (`GET /api/home`); albums by favorite bands from the last 45 days first, with the “Favorite band” badge (`AlbumCard`, field `fav`) – the same on the administrators' home page |
| How it works | tip cards, only as long as there is no own playlist |

The mix suggestions in “Let’s go” and “Your mixes” (`mixIdeas`, up to three) leave out the ones “Discovered for you”
already shows as a card – no suggestion appears twice. Links to whole lists read “See all →” (“Discovered for you” →
`#/entdecken`, “Your own playlists” → `#/playlists`).

**The administrators' home page** (`Start.svelte`): “Today for you” shows the mixes (`TodayRow`); without a mix, one
card with a sentence about mixes and a single row of up to three mix suggestions as chips plus “Create a mix”
(`#/neu?type=mix`) – more suggestions are under Discover. “See all →” leads to the playlists (“Today for you”,
“Family playlists”) and to the history; “Full recap →” to the week. “To review” (`TodoList`) lists the notes from
`GET /api/inbox` with their actions; “Assign music world …” (`do: "artist"`) opens the band window, where the world is
chosen, and asks for the list again once the window closes. The card **Deezer rating** (`pages/start/DeezerCard.svelte`,
section `karten` next to `LibraryCard`) shows rated / not found / waiting and offers “Rate new songs”, “Retry songs
not found” and “Check everything again” (or “Continue full check · done/total”). It has no switch for stars given by
hand – that is under [Settings → Deezer stars](#settings--deezer-stars). “Rate new songs” is left out while “To review” is on the page
and already offers “Rate now” for the new songs (note `deezer-…`).

### Discover

`pages/Discover.svelte` (`#/entdecken`): ready-made suggestions per person, new music worlds, “You might also like –
not in your library yet” (administrators: “You might still be missing”, `discover/Missing.svelte`) and, folded, the
table of all music world × vibe combinations (`discover/Matrix.svelte`, computed only when first unfolded).

**Person filter** (administrators, as soon as there is more than one person): a row All | the default person | the
other people. It starts on the default person (`settings.defaultPerson`) and is kept when coming back to the page
(until the app is reloaded); suggestions for the season and new music worlds count as the default person's.

**Order and collapsing.** The suggestions for the signed-in account's own person come first – not the shared
person, even if it is linked to the same account –, then “Right for the season”, then the shared person,
the others and “New music worlds discovered”. Each area collapses and expands via its heading, showing the
number of suggestions when collapsed; the device remembers this (`localStorage` `tuttiphon-discover-folded`).

**Hidden suggestions.** ✕ (“Not interested”, at the top right of every card – on a new music world on its picture)
hides a suggestion for half a year. Below the suggestions it says
how many are hidden, with “Show again now”; if nothing is left, the empty page offers “Show N hidden
again” (`lib/discover.js`: `hiddenCount()`, `showHidden()` – deleted music worlds stay hidden).

Suggestion cards (`IdeaCard`, in Discover `pages/discover/SuggestionCard.svelte`) show the suggestions' `because`
field as a small label with a sparkle icon, e.g. “Played often”, “From listening” or “Played often: Band A, Band B”
([Playlists](04-playlists.md#suggestions)).

### Search

`shell/Search.svelte` in the header (the `/` key jumps into it, arrow keys, Enter, Esc). The interface searches
bands, playlists, music worlds and own people itself; from 2 characters on it additionally asks `GET /api/search`
250 ms after the last keystroke. Groups in this order:

| Group | Source | Tap |
|---|---|---|
| Create as mix | `combos` ([combined search](04-playlists.md#combined-search)), subtitle “Mix · N matching songs, new every week” | `openCombo()`: the assistant's last step with the preview (`#/neu?type=mix&step=3&name=<title>` plus `person`, `welt`, `stil`, `mood`, `instr`, `theme`) – nothing is created until “Create playlist”; users without an own person go to `#/willkommen` first |
| Bands | `S.library.artists`, up to 6 | band window |
| Playlists | `S.config.playlists` without the trash, up to 5 | playlist page |
| Music worlds | up to 4 | music world page |
| People | own people, up to 3 | profile |
| Mood | `moods` – also the listening vibes “In the background” / “For listening closely” for words such as „Hintergrundmusik“ or „zum Zuhören“ | assistant with the matching sound vibe as a mix (`#/neu?stil=…&type=mix&step=1`), without a vibe `#/neu` |
| Instruments | `instruments` (AI, from 3 characters): label with a capital first letter, “N songs · create as mix”, piano icon | `openCombo()` with the instrument as the playlist's own sound filter (`instr=<ids>`, name = the label) – a mix of the whole library |
| Themes | `themes` (AI, from 3 characters; none when a music world's name contains the input): label with a capital first letter – or the name of the vibe that stands for the theme (`stilName`, „Weihnachten“) –, “N songs · create as mix”, an icon per theme (Christmas tree, record, crown, moon, heart, flower, microphone, palm, rocket) | with `stil`: the assistant with that vibe as a mix (`#/neu?stil=…&type=mix&step=1`), otherwise `openCombo()` with the theme as the playlist's own sound filter (`theme=<ids>`) – a mix of the whole library |
| Sounds like | `styles` (AI music styles) | band window of the first band |
| Songs | `songs` | song window |
| In the lyrics | `lyrics`: title, band and the matching line in quotation marks | song window |

Without a hit the list says “Nothing found – try a band, a song or a mood like “calm”.”

### Listening and the song window

Songs can be played wherever they appear as a list: the sample or a mix's selection on the
playlist page, the preview in the assistant, “Popular songs” in the band window and “More like this” in the song
window. The component for this is `components/TrackList.svelte` (`tracks`, `from` = name of the list, `fold`, `compact`):

- **Tapping** a row plays the song and then the rest of the list; the current one is highlighted (title in
  accent color, wave icon instead of the number, on the phone on the cover). The band name opens the band window,
  “…” the song window.
- `fold`: on the phone only this many rows at first, then “Show all N” (playlist page: 10). `compact`: only cover,
  title/band, length – for the window and the assistant.
- On the playlist page, “Play” in the header of the sample plays the whole list; while it plays, it becomes “Pause”.

`components/MiniPlayer.svelte` (in `App.svelte`) appears as soon as something plays: on the computer as a bar at the
bottom next to the sidebar (title, previous, pause/resume, next, position for seeking, close), on the phone as a card
above the navigation (without “Previous song” and times, the position as a thin line). Tapping the title or cover
opens the song window. It sets `--player` to its height (`--player-h`: 72 px, 64 px on the phone) so that the apply bar,
toasts, the end of the page and the assistant's footer stay above it. `lib/player.svelte.js` plays `/api/stream` with a
single `Audio` element – as the original file, in browsers without Opus (`canPlayType`) as MP3 – and reports title,
band and cover to the Media Session (lock screen and headphone buttons on the phone).

The **song window** (`components/sheets/SongSheet.svelte`, `openSong(track)`) shows the row from the list right away
and loads the rest from `GET /api/song`: cover, title, band (opens the band window), album, year, length; “Play”
or “Pause”; “More like this” (`GET /api/song/more`) – similar songs play after this one (`continueWith()`), the list
is shown in the window, “Keep as radio mix” creates a radio of the band (`startRadio()`); tempo with its source (`bpmSource`: “96 BPM · AI” or
“· measured”, the tooltip says more), key with its Camelot code (`keyName()`: “A minor · 8A”, German “a-Moll · 8A”; with
a `keyStrength` below 0.5 – mixes ignore such keys – “· uncertain”), moods, genres and, in a line of their own,
“Instruments: …” and “Themes: …” with the labels from the server – each only if the song has it;
“Appears in” with links to the playlists; the lyrics, shortened from 15 lines on with “show the whole text”. If they
have timestamps (`synced`), they follow along while this song plays: the current line is bold, sung lines are gray,
the box scrolls along; tapping a line jumps there (`playAt()` – if the song isn't playing yet, it starts at
that point). Songs that
kid-safe mode hides don't open ([API](03-api.md#songs--listening-in)).

The **band window** (`components/sheets/ArtistSheet.svelte`, `openArtist(name)`) shows, after “Similar bands in your
library” (Last.fm), “Sounds like these bands”: `soundsLike` from `GET /api/artist` (AI sound vectors) as round pictures
that open that band's window – without the bands already listed above; missing without sound vectors.

### Music world for users

`pages/Welt.svelte` shows administrators `pages/welten/WeltEdit.svelte`, everyone else
`pages/welten/WeltView.svelte`. There:

- **“Daily Mix”** in the header: creates a mix of this world for the own person (`defaultPerson()` = first own
  person) – `{welt, stil: "*", type: "mix", mix: {size: 50, perArtist: 3, every: "day"}, source: "welt"}`, with
  “Undo” – and opens it. If this person already has a mix from this world (no radio, not in the
  trash), the button is called “Your mix” and opens that one. If `findPerson(defaultPerson())` finds no person,
  this button and “Like” lead to the welcome assistant.
- **“Your favorites here”**: only if `forMe` from `GET /api/welt` contains bands – the world's share of your own
  listening (“N% of what you listen to …”, at least 1%) and up to 8 most-played bands of the world; tapping opens the
  band window. After that come all bands of the world.

### Music worlds sorted by listening

`lib/taste.svelte.js` loads `GET /api/taste?me=1` once per session. The music worlds page and the “New
playlist” assistant show the worlds in this order (`byRelevance()`): favorite worlds of the own people, then by
share of own listening, otherwise as saved; the welcome assistant by listening. For users, worlds from 5% carry
“you listen to it often”; for administrators, worlds created by Tuttiphon carry “created by Tuttiphon”. Deleting or
unlinking a world with a scene adds `scene|<id>` to `dismissed` (`forgetScene()` in `WeltEdit`). Under
Settings → Intelligence, “Create music worlds automatically” switches `settings.welten.auto`.

**Rebuild** (`WeltEdit`, only for worlds with a scene that were changed by hand or are named differently than in the
catalog): `GET /api/welt/neu` delivers the preview – bands before and after, what drops out and what is added, playlists
without their own name that will be named differently afterwards. Once confirmed, the interface empties `artists`,
`excludedArtists`, `albums` and `genres`, sets `autoScene` and takes over the scene's name and icon – with “Undo”.
Filters (excluded titles and albums, stars, minimum length, own world) stay, as does the ID, so that playlists and
favorite worlds stay attached. Bands that became free are checked for a new world by the warm-up right after saving
(`web._sync_welten()` also watches the bands of each world).

### Profile

`pages/personen/Profile.svelte` (`#/person/<id>`, for users also `#/profil`), from top to bottom:

1. **Header**: picture, name, Navidrome account, visibility, for the own profile “Statistics on” or “Turn on
   statistics” (→ Settings → My account), for others “Password stored” or “Password missing – enter it”; “New
   playlist” and “Suggestions”.
2. **From your listening** (`TasteCard`, only with a Navidrome account – see below).
3. **What you like to hear** (in the administrator's view of a person: “Preferences”): favorite music worlds as compact toggles like the vibes
   (`LikedWelten` with `compact`), favorite vibes (`StilToggles`), favorite bands (`ArtistChips`).
4. **Dislikes**: bands and “Genre contains”.
5. **Kid-safe mode** and **To your phone** side by side (see below).
6. **Profile** (prefix for playlist names, who may see the playlists; administrators: Navidrome user, visibility,
   “Make default”, “Delete person”) next to the folded **Appearance** (name, icon, color – rarely changed).
7. The person's playlists.

### Profile: “From your listening”

`components/TasteCard.svelte` is in the profile (`pages/personen/Profile.svelte`) of every person with a Navidrome
account and loads `GET /api/taste?person=…` (prop `me`: `?me=1`). With enough listening: music worlds with bars and
share – per world “+ Remember” (as a favorite world; afterwards “✓ Favorite world”) –, the most-played bands as chips
(“+” adds one as a favorite band, tapping the name opens the band window), moods and styles. “Add all” next to the
heading (on the phone below the text) adds worlds from 8% and the five most-played bands to `likes`; it is only shown
while something of that is still missing. For the own person addressed as “you” (“From your listening”), for others
“From <name>’s listening”. With a [sound taste](06-intelligence.md#sound-taste-appsoundtastepy) (`sound: true`) the
explanation below the heading ends with “Also learns from the sound of what you play.” (others: “… of what <name>
plays.”). With too little listening a hint; without a stored password a hint as well (own profile:
“Turn on →” to Settings → My account); without an account nothing.

### Profile: kid-safe mode and “To your phone”

Under “Dislikes” there are two cards: **Kid-safe mode** turns on `person.clean` (“Leave out songs with explicit
lyrics”), **To your phone** – only if `settings.notify.enabled` – shows `components/PushDevice.svelte` in your own profile
(turn this device on and off, “Send test”) and below it, collapsed, “Or via the ntfy app”: your own
ntfy topic `person.push` with “Send test” (`POST /api/notify/test` with `person`). Another person's profile shows
only the ntfy topic, because everyone registers their devices themselves. Both always set the value
(`false` or `""`) instead of deleting the field – `merge_user_changes()` only takes over fields that are sent along.

### Playlist page and playlist cards

The header of the playlist page (`pages/playlist/PlaylistHero.svelte`, actions in `pages/playlist/actions.js`) shows
picture, kind and person, the state as a pill (`StatePill`), the numbers (bands for every kind of playlist) and the
actions by status and rights – so that they don't wrap into several rows on the phone, only the most frequent ones
are buttons:

| Playlist | Buttons | In the “…” sheet |
|---|---|---|
| own, active | “Edit”, for mixes (not recaps) “Reshuffle” | Cover, Pause playlist, “Keep this mix” (mix) or “Save as fixed playlist” (smart playlist) – both `snapshotMix()` → `POST /api/snapshot` ([Playlists](04-playlists.md#keep-this-mix-snapshot)) –, Duplicate, Open in Navidrome, Move to trash |
| own, paused | “Reactivate”, “Edit”, trash icon | – |
| in the trash | “Restore”, “Delete permanently” | – |
| someone else's, shared | “Copy for me”, “Open in Navidrome” | – |

Playlist cards (`PlaylistCard`) show a **state dot** (`StateDot`) only for administrators and only for states other
than `aktuell` (“in Navidrome”) – new, changed, scan, error …; users see none (a dot with a tooltip says nothing on a
phone).

### Assistant: “New playlist”

`pages/Wizard.svelte` (`#/neu`): for whom (only with more than one own person) → music world → vibe → finishing
touches with the preview (`pages/wizard/StepFinish.svelte`); “Create playlist” saves it with `source: "assistent"` and
opens the playlist page. URL parameters: `person`, `welt` (comma-separated), `stil`, `type=mix`, `step`; from the
search also `mood=<key>,…` (only keys of `MOODS`: sets `sound: {moods}` and makes it a mix – 40 songs, 3 per band,
weekly; with a sound vibe as `stil` the playlist's own filter starts from a copy of the vibe's, because it replaces
it), `instr=<id>,…` (instruments of the AI: sets `sound.instruments` and makes it a mix; ids the catalog of
`GET /api/sound/catalog` doesn't know are dropped as soon as it is loaded; an instrument alone is enough – “All ×
Everything” is then allowed), `theme=<id>,…` (themes of the AI, the same way: `sound.themes`) and `name=…` (suggested name, at most 120 characters). Values that no longer exist are dropped; `step=3`
without a music world or vibe starts at the music world. On the phone the music worlds are compact cards in two
columns (small picture with the icon, name and song count below it), and the step bar scrolls sideways
(`showChosen`). The type field (`components/TypeField.svelte`) turns a playlist that picks by sound into a mix; its
note tells a sound vibe apart from the playlist's own sound filter, e.g. a mood from the search.
The last step shows the mood toggles and the instrument or theme picker (`components/SoundPicker.svelte`, `kind`
`instruments` or `themes`) only when the draft came with a mood, instrument or theme from the search; the edit sheet
shows the picker for a playlist whose own sound filter has instruments or themes.

**Sound editor** (`components/SoundEditor.svelte`, in the vibe sheet under “Sound”): moods, instruments, themes,
energy, tempo, danceability (any / very danceable / not for dancing) and – once the AI has analyzed songs (`available`
of the sound catalog) or the filter already has them – “Easy to listen to” (`approachable`: low 0–0.45, high 0.6–1) and
“For close listening” (`engaging`: low 0–0.6, high 0.75–1), the ranges of the bundled vibes “In the background” and
“For listening closely”. The picker (`SoundPicker`) shows the instruments – or, as “Themes – one of them is enough”, the themes – of
`GET /api/sound/catalog` that occur in songs, most songs first, with the count, the first 12 and “Show all N”; a song
fits if at least one of the chosen ones is clearly in it. Without AI results (`available` / `themesAvailable` false or
no songs) it is hidden, unless some are already chosen. The vibes page names them in the short description
(`richtungen.js` `summary()`: “by sound: calm & gentle · piano · epic”, “by sound: easy to listen to · for the
background · relaxed”).

### Listening-based playlist types in the editor

`EditorSheet` recognizes `fav`, `review` and `together` (`special`) and then allows “All × Everything” (also with
`mix.flavor: "geschmack"` and with an own sound filter that requires instruments or themes, `sound.instruments`,
`sound.themes`): for `review` only period and song count, for `fav` only “How long does something count as
new?” instead of music world and vibe, for `together` instead of the type the choice of whose taste counts (own people
and people visible to everyone, at least two). `MixFields` has “Length” (by song count or 20 minutes to 1½ hours,
`mix.minutes`); “Blend” additionally offers “By taste”. On the playlist page, recap playlists have no “Reshuffle”,
and the header says “Recap · changes on the first of the month”. Suggestion cards state the minutes for a fixed length.

### Tidying up and seasons

“To review” (home page, `TodoList`) knows the actions `pause` and `pauseAll` (with “Undo”); users see
the same hints for their own playlists under “Next steps” as a link. Resting seasonal playlists show “resting until its
season” (`STATE.ruht`) and, in the header of the playlist page, from when they will be back in Symfonium (`back`).
Settings → Playlists: “Seasonal playlists only in season” (`seasonRest`); in the edit sheet for seasonal vibes “All year
in Symfonium, not just in season” (`yearRound`). Settings → Check library: card “Missing covers” with a switch and
“Fetch now” (steps `cover` + `scan`).

### Statistics

`pages/Stats.svelte` (`#/statistik/<gesamt|woche|monat|jahr>`): with more than one own person a row of people at the
top (lock icon if the password is missing), then the period row Overall · This week · 30 days · Year <year> – on the
phone with short labels (Overall · Week · 30 days · <year>). Both rows scroll sideways when they don't fit
(`showChosen`). In the bars of the overview and the recap, the music worlds get a wider name column (`Bars` with
`wide`: up to 46 %, long names wrap to two lines instead of being cut off). The recap (week, 30 days, year;
`pages/stats/Rueckblick.svelte`) has “Keep as playlist” below the numbers → `POST /api/rueckblick/keep`.

### Settings

`pages/Settings.svelte` holds fifteen sections in five groups – administrators see all of them, users only General
and My account (one group, so without a heading):

| Group | Sections (`#/einstellungen/<id>`) |
|---|---|
| Account | General (`allgemein`), My account (`konto`) |
| Family | Users & permissions (`benutzer`), Home page (`start`), Notifications (`benachrichtigungen`) |
| Connection | Navidrome (`navidrome`), Storage locations (`speicher`) |
| Music | Playlists (`playlists`), Deezer stars (`deezer`), Lyrics (`lyrics`), Conversion (`opus`), Intelligence (`intel`), Check library (`bibliothek`) |
| Operation | Automation (`ablaeufe`), Backup (`sicherung`) |

Every entry has an icon and a short description (Conversion: “FLAC → Opus” or “FLAC → AAC”, after the codec).

- **Computer:** the list on the left with the group headings, sticky; if it is taller than the window it scrolls by
  itself and keeps the active section in view. The section is on the right; `#/einstellungen` without a section shows
  the first one.
- **Phone** (up to 900 px): `#/einstellungen` shows only the grouped list (each group a card with rows and ›); every
  section opens as its own page at the top, with “‹ Settings” back to the list, which is back at the position it was
  left.
- A section is rebuilt when “Undo” replaces the whole configuration (`{#key S.config}`).

### Settings → My account

`pages/settings/Konto.svelte`:

- **Signed in**: picture, name, “Navidrome account “<user>” · <role>” and “Sign out” with the logout icon; below it a
  hint that the password is changed in Navidrome. For the local administrator the role line reads “Local administrator
  with all rights” and the hint says that its password is changed under Settings → Users & permissions – or, with
  `env.adminPassword` `"env"`, that it is set in `docker-compose.yaml` (`TUTTIPHON_ADMIN_PASSWORD`).
  With sign-in turned off, a card “Sign-in” explains instead that it turns on once the local administrator has a
  password, with a link to Settings → Users & permissions.
- **Statistics & stars**: without a stored password, a password field and “Turn on” (`POST /api/me/password`, verified
  with Navidrome); with one, “Turned on” and “Turn off” – after the question “Forget password?” the same call with
  `password: null`. For the local administrator only the hint that it has no Navidrome account of its own.
- **Your profiles** (not for the local administrator): the own people, or “Create profile” (`#/willkommen`).
- **Introduction**: “Start tour” and “show again” for hidden suggestions and tips.

### Settings → Users & permissions

`pages/settings/Benutzer.svelte`: the card “Who may do what?” with the roles of the accounts (`PUT /api/accounts`)
and the card “Local administrator” – with sign-in on, how to sign in as local administrator; without, that sign-in
starts once it has a password. Below it `pages/settings/AdminPassword.svelte`, by `env.adminPassword`:

| Source | Shows |
|---|---|
| `"env"` | only a note that the password is set in `docker-compose.yaml` as `TUTTIPHON_ADMIN_PASSWORD` and can only be changed there |
| `"stored"` | “Current password”, “New password”, “Repeat password”, button “Change password”; a hint that only a fingerprint is kept and how to reset a forgotten one (delete `admin_password.json`, then the setup code) |
| `""` (none yet, e.g. the PC without sign-in) | “Password of the local administrator”, “Repeat password”, button “Set password”; the hint that everyone then signs in |

The form checks beforehand (current password entered, at least 8 characters, both the same), then sends
`POST /api/admin-password`. After a change a toast “Password changed ✓” appears and the status is reloaded; after
setting the first password the page reloads – sign-in is on from then on, and the answer has already signed this
browser in as local administrator.

### Settings → Deezer stars

Whether stars given by hand are overwritten is set only here: permanently with “Overwrite stars given by hand” (card
“Who gets stars?”, `deezer.overwriteManual`) or – while that is off – once with the switch “also overwrite stars given
by hand” below “Check everything again” (card “In the full run”), which sends `overwrite_manual: true` with
`deezer_mode: "full"` for this one run. The home page's Deezer card has no such switch.

### Settings → Playlists and Intelligence

- **Playlists**, card “Mixes that learn”: besides “Learn from listening” (`mixLearn`) the switch “Smooth transitions in
  mixes” (`smoothTransitions`, default on).
- **Intelligence**, stage 2 “AI” of the card “Sound analysis” (only while the AI is available): below the progress the
  songs analyzed with the current AI version – key, tempo, instruments, how easy to listen to (`ml.current`) of all songs, the songs with a sound vector (`ml.vectors`), the
  most common instruments (`ml.instruments`) and themes (`ml.themes`) and – as long as not all analyzed songs have the current version – the
  note that the AI listens to the library once more over the next nights. Card “Same recording twice”: without
  `fpcalc` “fpcalc is not installed …”, otherwise the progress of the fingerprints (`songs` of `total`), what is open,
  not readable and the last run, after a comparison the groups found (“N recordings are there more than once”, extra
  files, when compared) with a button to Check library; the switch “Make audio fingerprints”
  (`analysis.fingerprints`, independent of the AI).

### Settings: Lyrics, Check library, Notifications

- **Lyrics** additionally shows the card “Lyrics search & kid-safe mode” (`pages/settings/Kinderschutz.svelte`): number
  of lyrics read in with “Read in now”, for whom kid-safe mode is on, and the songs detected as explicit
  grouped by band: bands with the most songs first, collapsed, 15 at first, then 30 more at a time; per band the
  most frequent words and “allow all” (with undo), expanded per song the words found with their count and
  “allow” → `settings.kinderschutz.allow`. Above that, a search by band, song, album or word (with up to 40
  hits everything is expanded) and the filter All/Blocked/Allowed; the count line then shows the hits. The page always
  reads the allowed songs fresh from `S.config` – “Undo” replaces `S.config` as a whole.
- **Check library** (`pages/settings/Bibliothek.svelte`): per check from `GET /api/pflege` an expandable row
  with explanation and number (“all good” at 0), containing up to 60 entries; tapping the band opens the band window.
  Long names are cut off (the list has a `minmax(0,1fr)` column) instead of widening the page. “Same recording twice”
  (`aufnahme`, fingerprint icon): while not all songs have a fingerprint (`progress`) the row says “So far N of M songs
  compared …” and shows “none so far” instead of “all good”; below each group its copies – title (opens the song
  window to listen in), format, bit rate, length, album and the path in the music folder – and at the end a hint to
  remove the extra copies by hand. Before the first comparison (fingerprints available and on) a note says when the
  check appears.
- **Notifications** (`pages/settings/Benachrichtigungen.svelte`): on/off and “This device” (`PushDevice`);
  a separate card “Via ntfy” with server, own topic and “Send test”, Tuttiphon's address, who has their own
  topic, a note on `NTFY_TOKEN`; a third card with one switch per event.

### Setup assistant

`pages/Setup.svelte` (`#/einrichtung`, administrators only) asks on the first start of a new installation what
Tuttiphon should do. Seven steps with the stepper and the footer (`.wiz-foot`) of the other assistants; every step is
one card (`pages/settings/Card.svelte`) with a short explanation and the rows of the settings (`Row`, `Switch`,
`Seg`); options with an explanation are cards with a radio button (`pages/setup/Choice.svelte`, class `.choice`).

| Step | Contents | Settings |
|---|---|---|
| Navidrome (`setup/StepNavidrome.svelte`) | status (“Connected – Navidrome 0.64.2” or the error with “Check again”); the form of Settings → Navidrome (`pages/settings/Connection.svelte`, shared with the settings page) – folded as “Change connection” when connected, a note instead when address, account and password all come from `docker-compose.yaml`. Without a connection “Next” and the later steps stay locked; the text says why and points to “Skip setup” | `.env` via `PUT /api/env` (saved right away) |
| Conversion (`setup/StepConvert.svelte`) | Off / Opus (“smallest files, ideal for Android”, with `bitrate`) / AAC (“for iPhone, iPad and Mac”, with `aacBitrate`); when on: what is converted (the lossless files in the music folder – the first run everything, then new ones) and the check of equal length, files waiting (`GET /api/opus/info`), the original: to the archive (with path and state of the archive folder from `S.status.paths.archive`: reachable, read-only, missing), keep, delete (asks first and shows a warning) | `opus.enabled`, `codec`, `original` |
| Lyrics (`setup/StepLyrics.svelte`) | search on/off; with search: also plain text, LRCLIB and NetEase (at least one stays on), replace plain text later; delete duplicate `.txt` | `lyrics.fetch`, `savePlain`, `providers`, `upgradePlain`, `cleanup` |
| Understand music (`setup/StepMusic.svelte`) | sound analysis on/off; AI only when `GET /api/intel` reports it as available, otherwise one note – the server's reason (`ml.reason`, e.g. Essentia or the models missing) or “not installed here – part of the Docker image”; the depth tiles with their time estimate (`pages/settings/Depth.svelte` with its own `onchange`); audio fingerprints (with a note without `fpcalc`); night analysis with its time window (start ≠ end; the nightly Deezer refresh and the weekly cover search run in it too) | `analysis.enabled`, `ml`, `depth`, `fingerprints`, `night` |
| Deezer stars (`setup/StepDeezer.svelte`) | why (top tracks in Symfonium, “Only the hits”), on/off, whose accounts (`S.status.env.users`), stars given by hand: keep (default) or overwrite (with a warning) | step `deezer` in `pipeline`, `deezer.users`, `deezer.overwriteManual`; only when the switch was changed also `deezer.refresh` and `watch.deezer` |
| Automation (`setup/StepAutomation.svelte`) | daily refresh off / playlists / everything with its time, folder watch with its interval | `dailyMode`, `dailyAt`, `watch.enabled`, `watch.interval` |
| Summary (`setup/StepSummary.svelte`) | one row per step with “Change”, the switch “Start the first run now” (only with a connection; lists the steps that will run) | – |

Every step starts with the current values – on a new installation the defaults. The steps change only a **draft**
(`pages/setup/draft.js`: `draftFrom()` copies the settings when the page opens, `applyDraft()` writes them back);
`S.config` changes only with **“Finish”**: `applyDraft()`, `settings.setup = {done: true, at: "YYYY-MM-DD"}`, save,
`loadStatus()` (the home page's “Update everything” uses the new steps). With “Start the first run now” “Finish”
also calls `runTask()` with the steps of `pipeline` – the same as “Update everything”; nothing else starts a run.
**“Skip setup”** (next to the title, asks first) only sets `settings.setup` and points to Settings. Both lead to
`#/`, where the tour follows if the account hasn't seen it yet. If the server rejects the save, the assistant stays
open (the error comes from `save()`).

During the assistant there is no tour; the (?) next to the title opens the help topic “Setup assistant”, and the
notice “Navidrome cannot be reached” above the page is left out – the first step says it itself. On the phone the
apply bar is hidden like in the other assistants (`.wiz-foot`). Settings → General has the card “Setup assistant”
with “Run the setup assistant again” (administrators only), which opens `#/einrichtung` with the current values.

### Settings → General: “About Tuttiphon”

The card shows everyone the version (`S.status.version` from `GET /api/status`). Administrators also see whether
Tuttiphon runs in the container or on the computer, other active instances, whether sign-in is turned on, and under
“What’s new?” (collapsed) the last five sections from `GET /api/changelog` (sub-points indented, `levels`) ([Operations](08-operations.md#updates)).
Above it, administrators find the card “Setup assistant” ([Setup assistant](#setup-assistant)).

## Design

- **Colors** are CSS variables in `app.css` (`--bg`, `--surface`, `--accent` …), dark by default, light via
  `data-theme="light"` or the system setting. `@theme inline` turns them into Tailwind classes (`bg-surface`,
  `text-muted`, `border-line` …) that change with the theme. The status colors `--ok`, `--warn`, `--err` are darker in
  the light theme and `--accent-text` is the accent as text on `--accent-soft` (`.pill.acc`) – text and pills stay at a
  contrast of at least 4.5:1 in both themes.
- **Less motion**: with the system setting “reduce motion” there are no animations, transitions or smooth scrolling
  (`app.css`; JavaScript scrolls with `smooth()` from `lib/motion.js`).
- **Installed app on the iPhone** (`viewport-fit=cover`, status bar over the page): the top bar, the sidebar, the side
  sheets, toasts, the bottom navigation, the apply bar and the assistant's footer keep clear of the status bar, the
  notch and the home indicator (`env(safe-area-inset-*)`).
- **Accessibility**: the navigation marks the current page (`aria-current`), the search is a combobox with a list
  of options, `Field` names its content as a group, the song rows are a play button with the band and “…” as buttons
  of their own above it, the × and + in chips have a touch area of 32 px and a name with the value.
- **Components** that appear on many pages are classes in `@layer components` (`btn`, `card`, `pill`, `pcard`,
  `trk`, `kpi`, page header `hero` with `grad` and `compact` …). Page-specific styling is written as Tailwind classes in the component; pseudo-elements, counters and animations go in
  a `<style>` block of the component.
- **Phone** is everything up to 900 px (`max-mobile:`): no sidebar, navigation at the bottom (four entries + “More”),
  side sheets from the bottom, the apply notice bar across the full width. Segmented controls (`Seg`, `.seg`) and step
  bars (`.stepper`) that don't fit scroll sideways instead of wrapping; `showChosen` keeps the chosen option in view
  ([Attachments](#attachments)).
- **Icons** via `<Icon name>`; music worlds, vibes and people store their icon as `"i:name"` in
  `config.json` – `<Glyph value>` shows it (older emojis are translated). If a name is missing, it is added as a Lucide import
  in `lib/icons.js`; new motifs also go into `MOTIFS`.

## App, tour, help

- **As an app**: `manifest.webmanifest` and icons in `public/`. `sw.js` always loads fresh from the server first and only
  falls back to the last loaded interface without a network; `/api`, `/img`, `/live`, `/cover` never go through the cache.
  When the app page refers to other files than last time (a new version), the files of older versions are removed from
  the cache (`/__build` in the cache remembers the list).
  `lib/install.svelte.js` remembers the browser's install prompt (`beforeinstallprompt`, only over https or
  localhost) and counts every opening (`localStorage` `tuttiphon-visits`). **Hint** `components/InstallHint.svelte` below the
  header of “For you” and the home page: only on a phone or tablet (`pointer: coarse`), not as an installed app
  (`display-mode: standalone`), from the second opening on, until it is dismissed or Tuttiphon is installed (`tuttiphon-install-hint`,
  per device). With a prompt “Install” and “Not now”, otherwise the instructions for iPhone (Share → “Add to
  Home Screen”) or Android (menu ⋮ → “Add to Home screen”) and “Got it”. The same is always available
  under Settings → General → “Install as app”.
- **Notifications via the app**: `lib/push.js` – `supported()` (secure address, service worker, `PushManager`,
  `Notification`), `state()` asks `POST /api/push/status` with this device's push address, `enable()` gets the
  permission, subscribes with the push service using the key from `GET /api/push/key` (again if the key has
  changed) and sends the subscription together with `location.origin` to `POST /api/push/subscribe`; `disable()` unsubscribes.
  `components/PushDevice.svelte` shows from this: not possible (with a reason: https missing, on iPhone first add it to the
  Home Screen, the browser can't do it, something is missing on the server), blocked, on (“Send test”, “Turn off”) or
  “Turn on for this device”. `sw.js` shows incoming messages (`push`: title, text, icon, `tag`) and
  on tap (`notificationclick`) opens the page sent along – in an open Tuttiphon window, otherwise in a new one.
- **Tour**: `lib/tour.svelte.js` + `components/Tour.svelte`. The steps point to fixed anchors in the frame
  (`data-tour="nav|bottomnav|more|new|search"`) – anyone rebuilding the navigation or search must keep these anchors. When it
  appears: [Tour and welcome](#tour-and-welcome).
- **“Show me” guides**: `lib/guides.js`, shown by the same `Tour.svelte`. Instead of screenshots they lead
  through the real interface – on the phone as on the PC. A step can switch the page first (`go`), waits for its
  target (`sel`; up to 8 s while a `<Loading>` with `data-loading` is visible, otherwise 1.5 s), scrolls it into view
  between the header and the bottom bar (fixed targets not) and places the hint to the right of it, below,
  above or, on the phone, at the bottom edge. `reset: true` rebuilds the step's page even when it is already open (the
  assistant then starts from scratch instead of in a half-filled draft). `optional: true` skips a step without a
  target; a required target that doesn't appear shows the hint centered. A tap on the highlighted target ends the guide and triggers the target.
  Guides don't count as a seen tour. The targets carry `data-guide="…"` (`taste`, `likes`, `dislikes`,
  `sichtbar`, `pl-actions`, `anlegen`, `vorschlag`, `update`, `welt-neu`, `person-neu`, in the settings via
  `<Card guide>`: `rechte`, `passwoerter`, `schritte`, `watch`, `statistik`, `einfuehrung`, `notify`, `kinderschutz-liste`;
  in the profile `kinderschutz`, `push`) or existing classes
  (`.stepper`, `.pick`, `.wiz-foot`, `.g-pl .pcard`, `.g-welt .wcard`). Anyone rebuilding these places keeps the anchors.
- **Help**: `pages/Help.svelte` with the contents in `pages/help/` (one version each for administrators and users):
  search, “What would you like to do?” (`GuideCard` per guide: three short steps, “Show me”, “Jump right in” – `href`,
  or `href(admin)` when it depends on the role), Getting started, expandable topics (`Topic`, with the matching guides
  as buttons), Questions & answers, Terms. The search reads the text of the topics from the page after rendering
  (`data-topic`); all words must occur. Interface buttons appear in the text as `<Ui icon>` – so you recognize them on
  every device; there are no screenshots anymore. Topics name their guides in `guides`.
- **(?) next to the page title** (`components/HelpLink.svelte`, mapping route → topic is there): opens the topic as a
  sheet (`pages/help/HelpSheet.svelte`) with the matching guides at the top; without a matching topic for the role – or
  if the help file cannot be loaded, e.g. after an update – it leads to the help.

### Tour and welcome

Both appear only once per account – on all devices and under every address. This is remembered twice: in the browser
(`localStorage` `tuttiphon-tour:<account>` or `tuttiphon-welcome:<account>`) and on the server (`POST /api/seen`, `state/seen.json`;
`/api/me` delivers `tourSeen`/`welcomeSeen`). If the call fails, it only counts on this device.

| | Tour | Welcome assistant |
|---|---|---|
| Code | `lib/tour.svelte.js`, `components/Tour.svelte` | `pages/Welcome.svelte` (`#/willkommen`), tip cards in `pages/welcome/TipCards.svelte` |
| for whom | administrators (`ADMIN_STEPS`) and users with a profile (`USER_STEPS`) | users without a profile, or with a profile without preferences and own playlists (`needsWelcome()` in `App.svelte`) |
| starts | 1.5 s after the app starts, not on `#/willkommen` (`startTour()`) | when the app starts, via redirect, not from `#/hilfe…` |
| skipped if | `S.me.tourSeen` or `tuttiphon-tour:<account>` | `S.me.welcomeSeen` or `tuttiphon-welcome:<account>` – without a profile it comes anyway |
| finished by | the end or “Skip” (`endTour()` → `{what: "tour"}`) | “Create N playlists” or “Continue without playlists” in the Playlists step (`finish()`) or – only with an existing profile – “Later – look around first” on the first page; both call `remember()` → `{what: "welcome"}` |
| again | Settings → My account (`startTour(true)`, jumps to `#/` first) | via `#/willkommen` (e.g. “Create profile” in the profile and under Settings → My account, as long as there is no profile) |

The assistant leads through Hello, Profile, Music worlds, Favorite bands, Dislikes, Playlists, Done. The profile (person
with their own account) is only created with “Save profile & show suggestions” at the end of the Dislikes step; until then
it only collects locally. Right when it opens, it asks `GET /api/taste?me=1`; if there is enough listening, the music
worlds from 8% of what was played and the five most-played bands are preselected (only if nothing is chosen there yet),
and in the Favorite bands step the up to 12 most-played bands come first. In the Playlists step it shows suggestions from
`GET /api/suggestions?person=…`; the first three non-shared ones are preselected.

## Testing

| Tool | Purpose |
|---|---|
| `npm run test:py` | Python tests for `app/` (`tests/python/`, `unittest` from the standard library): rules and local evaluation, mixes, configuration and `.env`, sign-in and permissions, backup, run lock and instances, lyrics/folder watch, conversion to Opus and AAC with real files generated in the test, mix learning, self-check, AI sound analysis (without Essentia, with a simulated analysis process). They run in a fresh temp folder (`tests/python/env.py`, import it before any `app.*`), without network and without the NAS; tests marked with `@unittest.expectedFailure` describe known deviations |
| `npm run build` | must complete without warnings (Svelte reports, among other things, accessibility issues and misused runes) |
| `tools/testserver.sh <port> <folder> [--auth] [--web <build>]` | test server with a **copy** of `data/`, auto-apply and folder watch off, no schedules. `--auth` turns on sign-in (adds a random `TUTTIPHON_ADMIN_PASSWORD` to the copy's `.env` if that line is missing – it only checks this name) and prints session cookies for the local administrator and a user account (`--user <account>`) |
| `node tools/screens.mjs --base … --out … [--cookie tuttiphon=…] [--mobile \| --mobile-small] [--light] [--text] [--fresh] [--lang en] '#/…'` | screenshots and console errors per page (`--mobile-small`: a small phone, 360 × 740 – narrow layouts break there first). Without `--fresh` the script sets the browser markers `tuttiphon-tour:<account>`/`tuttiphon-welcome:<account>` so that tour and welcome don't get in the way; with `--fresh` it leaves them out – but both only appear if the account is also not listed in `state/seen.json` of the data copy |
| `npm run test:e2e` | Playwright: every page as administrator and as a user, computer and phone (Pixel 7), without JavaScript or console errors; sign-in page; redirect without a session (`pages.spec.js`); help: guides with page changes, Esc, the sheet behind the (?), search, jumping to a topic (`help.spec.js`); what the AI sound analysis adds – key, tempo source, instruments and themes in the song window, bands that sound alike, instruments and themes in the search, the assistant and the sound editor, a vibe that stands for a theme, smooth transitions, fingerprints and “Same recording twice” – with the server's answers extended in the browser (`page.route`), because the test copy usually has no AI results (`ai-sound.spec.js`); the setup assistant – redirect of a new installation only for administrators and once per session, all steps without saving before “Finish”, “Skip setup”, locked without a connection, the entry under Settings → General – with a new installation played in the browser and every write answered there (`setup-assistant.spec.js`) |

The browser tests start their own test server on port 8790 (`tests/e2e/setup.js`), warm it up (library,
playlists, “To review”, suggestions – otherwise the first pages would all wait for the NAS at the same time) and delete the
data copy at the end (`teardown.js`). They never trigger anything that writes to Navidrome or the NAS.

Test servers get their own folder for instance registration and the run lock via `TUTTIPHON_SHARED_DIR` – otherwise
they would register as another Tuttiphon instance in the real playlist folder (`.tuttiphon/`). In a
Git worktree without `data/`, `tools/testserver.sh` copies the data of the main folder.

**When testing by hand** the same applies: saving in the test copy is harmless, but don't start runs and don't
trigger credentials, accounts, covers or takeovers – that would go to the real Navidrome or the real music.

## Extending

**New page**
1. Create `pages/Name.svelte` (props for route parts), with `<div class="page">` and `<PageHead>` at the top.
2. Add a loader to `PAGES` and the route to the `switch` in `App.svelte` (`lazy('name', props)`); admin pages with
   `admin ? lazy('name') : { C: AdminOnly }` and their name in `ADMIN_PAGES`.
3. Navigation in `shell/Nav.svelte` (both lists, possibly the “More” menu), help topic in `HelpLink.svelte`.
4. Add the route to `tests/e2e/pages.spec.js`.

**New setting**
1. Default value in `app/default_config.json` and – if existing configurations need it – a migration in
   `app/config.py` ([Data model](02-data-model.md)).
2. Input in the matching section under `pages/settings/` with `Row`, `Toggle`, `NumInput` …; change, then `changed()`.

**New endpoint**: create it in the server and secure it ([Security](07-security.md), [API](03-api.md)),
call it in the interface via `api()`.
