# Tuttiphon – interface (Svelte 5 + Vite 8 + Tailwind 4)

`npm run build` builds `frontend/` into `web/`; the Python server (`app/web.py`) serves `web/`.
`web/` is generated and doesn't belong in Git. No dev server: build, then look at the test server.

## Structure

```
frontend/
  index.html, login.html     two entry points (app and sign-in)
  public/                    copied unchanged: favicon, manifest, sw.js, icons/
  src/
    main.js, App.svelte      frame: sidebar, header, router, overlays, tour
    login.js, Login.svelte   sign-in page
    app.css                  design system: colors, Tailwind tokens, recurring components
    shell/                   parts of the frame (navigation, search, account menu, apply bar)
    lib/                     logic without UI (state, API, router, overlays, helpers)
    components/              reusable components, components/sheets/ for side sheets
    pages/                   one file per page (larger pages with a subfolder, e.g. pages/settings/)
```

## State – `lib/state.svelte.js`

- `S.config` is deeply reactive. To change it, assign directly, then call `changed()` (saves after 450 ms).
  Call `snapshot()` first if the toast should offer “Undo”: `toast('…', { undo: true })`.
- **Proxy trap:** whatever you insert into `S.config` becomes a proxy there. Afterwards, keep working through `S.config`:
  `S.config.playlists.push(p); const neu = S.config.playlists.at(-1)`. And write `obj.genres ??= []` as its own
  statement, then pass `items={obj.genres}` (the value of a `??=` expression is the raw array).
- `S.status`, `S.library`, `S.pl`, `S.history`, `S.task` are only ever replaced as a whole.
- Instead of the old events: everything is reactive. Reload a page's own data after a run:
  `$effect(() => { S.done; untrack(load) })`. `S.saved` counts saves.
- Helpers: `findWelt/findStil/findPerson/findPl`, `plStatus(id)`, `artistId(name)`, `weltIds(p)`, `soundOf(p)`,
  `mixWording(p)`, `MOODS`, `passKey(user)`, `isAdmin()`, `ownPersons()`, `canEdit(p)`, `defaultPerson()`, `myPerson()`,
  `save()`, `undo()`, `reloadConfig()`, `mergeServerFields()`, `loadLibrary/loadStatus/loadPlaylists/loadHistory()`,
  `runTask(steps, extra)`, `applyNow()`, `pendingCount()`.

## Overlays – `lib/overlay.svelte.js`

Content as a snippet (defined in the template with `{#snippet name()}`, usable as a value in `<script>`) or as a component:

```js
openSheet({ title: t('Edit'), body: formSnippet, foot: buttonsSnippet, wide: true, onClose })
openSheet({ title: name, component: ArtistSheet, props: { name } })   // head: snippet instead of title
const v = await modal({ title, text, body | component+props, buttons: [{ label, value, primary, danger }] })
const ok = await confirmDialog(title, text, t('Delete'), true)
openSong(track)                       // lib/song.js – song window; playList(tracks, i, from) – lib/player.svelte.js
toast(t('Saved ✓'), { error, undo, action: { label, run } })   // error: stays until it is closed
closeSheet(); closeModal(value)
```

Errors of `api()` carry `status` and `offline` (Tuttiphon not reachable) – show `e.message` as an error toast instead of
swallowing it (`.catch(() => {})` only where nothing depends on it).

## Router – `lib/router.svelte.js`

`route.path`, `route.parts`, `route.query`, `params().get('person')`, `go('#/…')` (same route → page is rebuilt),
`replace('#/…')` (redirects: no new history entry), `rerender()`. Pages get their parts as props (e.g.
`Playlist { id }`, `Settings { tab }`, `Help { topic }`). An open sheet has a history entry of its own – the back button
closes it; `go()` and links from a sheet replace that entry.

## Components – `components/`

| Component | Props |
|---|---|
| `Icon` | `name` (see `lib/icons.js`), `size`, `class` |
| `Glyph` | `value` ("i:teddy", icon name or emoji), `size` – icon of a music world/vibe/person |
| `GlyphButton` / `GlyphPicker` | `bind:value`, `onpick` |
| `Avatar` | `name`, `id` (otherwise from the library), `size` – artist image |
| `Cover` | `id`, `size` – album cover |
| `Mosaic` | `covers`, `marks` (icons), `size` |
| `Collage` | `artists`, `icon`, `title`, `sub` |
| `Stack` | `artists`, `n`, `size` |
| `PersonAvatar` | `p`, `size` |
| `PlaylistArt` / `PlaylistCard` | `p`, `st`, `size` / `p` |
| `StateDot` / `StatePill` | `state` |
| `Field` | `label`, content |
| `Switch` | `bind:checked` or `checked`, `onchange(v)`, `label`, `hidelabel` (label only for screen readers), `disabled` |
| `Seg` | `options` [[value, text]], `bind:value`/`value`, `onchange(v)` |
| `Select` | `options` (also groups `{group, options}`), `value`, `onchange(v)`, further attributes |
| `ChipEditor` | `items` (reactive array), `onchange`, `placeholder`, `suggestions` |
| `ArtistPicker` / `ArtistChips` | `onpick`, `exclude` / `items`, `onchange` |
| `SoundEditor` | `obj` (gets `obj.sound`: moods, instruments, themes, energy/tempo/danceability), `onchange` |
| `SoundPicker` | `kind` (`instruments` or `themes`), `value` (ids), `onchange(ids)` – instruments or themes of the AI (`lib/sound.svelte.js`), hidden without AI results |
| `Carousel` | `wide`, content |
| `Section` | `title`, `icon`, `action` (snippet), content |
| `TrackList` | `tracks` (song rows with `id`), `from`, `fold` (on the phone only this many at first), `compact` – tapping plays, “…” opens the song window |
| `MiniPlayer` | – (once in `App.svelte`; state in `lib/player.svelte.js`) |
| `PushDevice` | – turn notifications via the app on/off/test them for this device (`lib/push.js`) |
| `Empty` | `icon`, `title`, `text`, content (buttons) |
| `PageHead` | `title`, `sub`, `eyebrow`, `help`, `actions` (snippet), content |
| `Loading` | `text` |

## Design

- Recurring elements are classes in `app.css`: `btn` (+ `primary`, `ghost`, `white`, `danger`, `sm`, `lg`, `icon`),
  `card`, `pill` (+ `ok`, `warn`, `err`, `acc`), `chip`, `toggle`, `seg`, `switch`, `field`/`lbl`, `frow`, `hint`, `note`,
  `empty`, `page`, `page-head`, `section`, `hero…`, `g-pl`/`g-cards`/`g-welt`/`g-2`/`g-3`, `pcard`, `wcard`, `scard`,
  `agrid`/`acard`, `trk`, `arow`, `kpi`, `sbar`, `hbar`, `todo-item`, `step`, `hist-row`, `log`, `stepper`, `pickcard`,
  `wiz-foot`, `today-card`, `fold`, `choice`, `member-row`, `hi`, `progress`, `muted`/`small`/`tiny`/`ell`.
- Everything page-specific as Tailwind classes. Colors via the tokens: `bg-surface`, `bg-surface-2`, `text-muted`,
  `text-text-2`, `border-line`, `text-accent`, `bg-accent-soft`, `text-ok/warn/err`; radii `rounded-small/card/big/huge`.
  Phone view: `max-mobile:…` (up to 900 px). Whatever gets cumbersome with classes (pseudo-elements, counters,
  animations) goes into a `<style>` block of the component.
- Tailwind's Preflight is active: lists have no bullets (`list-disc pl-5`), images and SVGs are `block`.

## Texts and languages

The interface speaks English, German, French, Dutch, Spanish, Italian, Portuguese and Polish (`LANGUAGES` in
`lib/i18n.svelte.js`). **English is the source language:** every text in the code is English and goes through `t()`.
The other languages come from dictionaries `{ 'English text': 'translation' }` in `locales/<lang>/*.js` – the same
file names in every language (one per area, merged by `locales/<lang>/index.js`). The language: the choice saved on
this device (Settings → General → Language), otherwise the browser language, otherwise English. Every dictionary is
its own file in the build and is only loaded for its language; numbers and dates follow `LOCALES` (pt: pt-PT).

**Counts:** `tn(n, '{n} song', '{n} songs')`, `plural()` and `tword()` pick the form by the plural rules of the
language (`Intl.PluralRules`): the English singular text for the category “one” (French: 0 and 1), otherwise the plural
text – whose entry may hold several forms. Polish does: `'{n} songs': { few: '{n} piosenki', many: '{n} piosenek' }`.
The server does the same (`i18n.category()`, `_n()`/`_sn()`, entries as JSON objects).

**Keeping the languages complete:** a new or changed English text gets its entry in every language. German is
checked strictly (missing = error); for the other languages `npm run test:i18n` lists `missing` texts as a warning
(they show in English) and checks every entry like the German one – placeholders, the same markup as the English
text, valid plural forms. Address: German, Spanish, Italian, Dutch informal (du, tú, tu, je), French “vous”, Portuguese
(European) the polite third person, Polish the imperative.

**Switching happens without a reload.** The language is reactive state (`$state.raw` in `i18n.svelte.js`): every
`t()` that runs inside a template expression or a `$derived` follows a switch at once; `lang()` and `locale()` are
functions for the same reason. After a switch, `reloadTexts()` (`lib/state.svelte.js`) fetches again what the server
words in the language of the request (status, playlists, the library with the names of the scene catalog, the history
if it was loaded); pages fetch their own data in the new language the next time they open – the start page its mix
ideas too. `api()` sends the language as `X-Lang` (read with `untrack`, so an `$effect` calling `api()` does not run
again on a switch); a plain `fetch()` adds `'X-Lang': lang()` itself.

```js
import { t, tn, locale, translated } from '../lib/i18n.svelte.js'
import { fmt, plural } from '../lib/format.js'

t('Save')                                               // a text
t('Files to convert: {n}', { n: fmt(count) })           // with values: whole sentence, {name} placeholders
plural(n, 'song', 'songs')                              // "3 songs" / "3 Songs" – counting words
tn(n, '{n} song left', '{n} songs left')                // a sentence with a count
new Date(x).toLocaleDateString(locale(), { … })          // dates and numbers: locale(), never 'de-DE'

const LABEL = $derived({ a: t('A') })                   // in a component: texts outside the template as $derived
export const STEPS = translated(() => [{ title: t('…') }])   // at module level: built again for each language
```

- Only literal texts in `t()`, `tn()` and `plural()` – `tools/i18n-check.mjs` reads them from the code.
- A text must be translated where it is used, not once: in the template, in `$derived(…)`, in a function, or at
  module level inside `translated(() => …)` (a Proxy that behaves like the object/array and is rebuilt per language;
  read-only – copy it with `[...X]`/`{...X}` before storing it in `$state`). `tools/i18n-check.mjs` reports a `t()`
  at module level or in a component's setup as `static` – also inside functions that run right away there:
  `(() => t('…'))()`, callbacks of `.map`/`.filter`/`.find`/`.reduce`/`.forEach` …, `Array.from(x, fn)`. Allowed:
  `$state(t('…'))` with a single `t()` as the direct argument, as a starting value someone edits (e.g. the name of a
  new playlist) – not `$state({ a: t('…') })`. Store data in `$state` (e.g. `null`) and translate where it is shown
  (`{name ?? t('automatic')}`). A deliberate exception needs `// i18n-ignore static` on the line; a plain
  `i18n-ignore` skips only the german, bare, shadow and dynamic checks.
- Whole sentences with placeholders, never sentences glued together from translated pieces (word order differs).
  `{@html t('… <b>…</b> …')}` only for fixed texts without values from data.
- Data stays as it is: values stored in the configuration or sent to the server (ids, mood keys, group names
  such as “Genre”/“Thema” in `stile`), routes, CSS classes, icon names, storage keys. Translate only what is shown,
  e.g. `const GROUP_LABEL = { Thema: t('Topic') }` and `{GROUP_LABEL[g] ?? g}`.
- Texts from the server (error messages, step titles) and from the user (names of music worlds, people, playlists)
  are shown as they are – not through `t()`.
- Names, units and formats look the same in every language (Navidrome, Symfonium, Opus, kbit/s …).
- Describe what a function does. No references to old scripts and, for users, no file paths. Two audiences:
  administrators (everything, may be technical) and users (simple, addressed as “you”; German: Du-Form).
- English: natural and short, sentence case, American spelling (color, favorite). Fixed terms:

  | German | English |
  |---|---|
  | Musikwelt | music world |
  | Richtung | vibe |
  | Stil (KI-Stil) | style |
  | Stimmung | mood |
  | Person / Personen | person / people |
  | Übernehmen (in Navidrome) | apply |
  | Hinzufügen (what was recognized → preferences; not „übernehmen“) | add |
  | Lauf, Schritt | run, step |
  | Verlauf | history |
  | Probelauf | dry run |
  | Zu prüfen | to review |
  | Entdecken / Für dich | Discover / For you |
  | Kinderschutz | kid-safe mode |
  | Mag nicht (not „No-Go“) | dislikes |
  | Lieblingswelt, Lieblingsband | favorite world, favorite band |
  | Band / Bands (not „Künstler“) | band / bands (artists of the library) |
  | Rückblick / Dein Monat | recap / your month |
  | Lokaler Administrator | local administrator |
  | Umwandlung | conversion |
  | Sterne / Favoriten | stars / favorites |
  | Bibliothek (not „Sammlung“) | library (not “collection”) |
  | Sicherung | backup |
  | Ordner-Überwachung | folder watch |
  | Abgleich (Symfonium with the server – not „Sync“) | sync |
  | Vorsilbe (in front of playlist names – not „Präfix“) | prefix |
  | Lieblingsrichtungen | favorite vibes |
  | Kein Zugang (role) | No access |
  | Kopie anlegen (playlist menu) | Duplicate |
  | Einrichtungsassistent | setup assistant |
  | Sprache des Servers | language of the server |
  | Klanganalyse / KI-Klanganalyse | sound analysis / AI sound analysis |
  | Eingängig / anspruchsvoll (AI value `approachable` in sound filters) | easy to listen to / demanding |
  | Zum genauen Zuhören / für nebenbei (AI value `engaging`) | for close listening / for the background |
  | Im Hintergrund, Zum Zuhören (bundled sound vibes) | In the background, For listening closely |
  | Thema / Themen der KI (Weihnachten, Filmmusik … in sound filters and the search; the vibe group „Thema“ stays “Topic”) | theme / themes (not “Theme” alone – that is the color theme, „Design“) |
  | Einordnung | classification |
  | Saison-Playlist | seasonal playlist |
  | Mix, Daily Mix / Weekly Mix / Monthly Mix (only real mixes) | mix, Daily Mix / Weekly Mix / Monthly Mix |
  | Querbeet (smart playlist of a whole world: „Die 90er · Querbeet“, „Niklas’ Querbeet“) | All Sorts (“The 90s · All Sorts”, “Lukas’s All Sorts”) |
  | Die Hits (in playlist names) | The Hits |
  | Musik verstehen (the analysis step, also in the history) | Understand music |
  | Passwort hinterlegt / Passwort fehlt | password stored / password missing |
  | Alle ansehen → (link to the whole list) | See all → |
  | Familie | family |
  | Administrator:in / Benutzer:in | administrator / user |

**Help texts** (`pages/help/`): a topic opens with one sentence, then at most about seven points of one or two short
sentences each – what something does and where it is (a link to the page). No technical details (models, percentages,
file sizes, internal limits) and nothing the page already says in its own hints; administrator topics point to the
handbook on GitHub for details. Buttons and terms exactly as the interface names them (`<Ui>` chips, “Dislikes”/„Mag
nicht“). Questions & answers do not repeat a topic.

Checks: `node tools/i18n-check.mjs` (all files: missing and conflicting German entries, German entries whose `{name}`
placeholders differ from the English text, `t()`/`tn()` values that lack a placeholder, German or bare text left in the
code, unused entries) and `node tools/compile-check.mjs <files>` (compiles single files without a full build). The
server's counterpart is `python3 tools/i18n_check.py` with the same placeholder checks.

## Testing

```bash
npm run build
tools/testserver.sh 8791 <workdir>                  # copy of the data, auto-apply off
tools/testserver.sh 8792 <workdir> --auth           # with sign-in, prints cookies for admin and user (--user <account>)
node tools/screens.mjs --base http://127.0.0.1:8792 --out <folder> --cookie tuttiphon=… [--mobile] [--light] '#/' '#/playlists'
```
