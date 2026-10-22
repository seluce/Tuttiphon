// Shared state: who is signed in, the configuration (people, music worlds, vibes, playlists),
// status, library, running tasks – plus saving with undo.
//
// S.config is deeply reactive: pages change the objects directly (p.name = '…', S.config.playlists.push(…))
// and then call changed() – that saves after a short pause. All views update by themselves.
// Careful: an object inserted into S.config becomes a proxy. Afterwards always keep working through S.config
// (e.g. `const p = S.config.playlists.at(-1)`), not through the original object.
//
// Everything else (status, library, pl …) is only replaced as a whole ($state.raw).

import { api } from './api.js'
import { debounce } from './format.js'
import { toast, closeSheet } from './overlay.svelte.js'
import { t, translated } from './i18n.svelte.js'

class Store {
  /** /api/me: { user, name, fullName, role: 'admin'|'user', own: [person ids], notfall (local administrator), … } */
  me = $state(null)
  /** /api/config (filtered by the server for users) */
  config = $state(null)
  status = $state.raw(null)
  /** /api/library + lookup tables artistIdx (name → id), artistCount, genreCount */
  library = $state.raw(null)
  /** /api/playlists: { playlists: [{ id, state, count, covers, navidrome, cover, name … }], handmade, orphans } */
  pl = $state.raw(null)
  history = $state.raw([])
  task = $state.raw(null)
  auto = $state.raw(null)
  running = $state(false)
  logLines = $state.raw([])
  installPrompt = $state.raw(null)
  /** Counts finished runs – pages that load their own data hang an $effect on it and reload. */
  done = $state(0)
  /** Counts successful saves. */
  saved = $state(0)
  /** Tuttiphon itself cannot be reached (network gone, server stopped) – unsaved changes wait for it. */
  offline = $state(false)
  /** The server runs a newer version than the one this page was loaded with (version text) – offer a reload. */
  newVersion = $state(null)
  dirty = false
  since = 0
}
export const S = new Store()

/* ------------------------------------------------------------------ Lookups */
export const findWelt = (id) => S.config.welten.find((w) => w.id === id)
export const findStil = (id) => S.config.stile.find((s) => s.id === id)
export const findPerson = (id) => S.config.personen.find((p) => p.id === id)
/** Separate music worlds that “All” leaves out for this person – on a child profile the children's music belongs to it
 *  (audio plays & audiobooks stay out), as in rules.child_worlds() on the server. */
export const outOfAll = (person) => S.config.welten.filter((w) => w.separate && !(person?.child && w.scene !== 'hoerspiel'))
export const findPl = (id) => S.config.playlists.find((p) => p.id === id)
/** Status of a playlist from /api/playlists (count, cover, state in Navidrome). */
export const plStatus = (id) => S.pl?.playlists.find((x) => x.id === id)
export const artistId = (name) => S.library?.artistIdx?.get(name)
/** Music worlds of a playlist as a list ("*" = all → empty). */
export const weltIds = (p) => (Array.isArray(p.welt) ? p.welt : p.welt && p.welt !== '*' ? [p.welt] : [])
/** Sound filter of a playlist (its own or its vibe's) – sound vibes exist only as mixes. */
export const soundOf = (p) => p?.sound || findStil(p?.stil)?.sound || null
/** How often a mix is put together anew – texts for the interface: [when, how often]. */
export const mixWording = (p) => ({
  day: [t('Today'), t('new every day')],
  week: [t('This week'), t('new every week')],
  month: [t('This month'), t('new every month')],
})[p?.mix?.every || 'day']
/** Moods from the sound analysis: the keys are stored, the values are display labels. */
export const MOODS = translated(() => ({
  ruhig: t('calm & gentle'),
  energie: t('energetic'),
  tanzbar: t('danceable'),
  froh: t('cheerful'),
  melancholisch: t('thoughtful'),
  schlaf: t('for falling asleep'),
  instrumental: t('no vocals'),
  akustisch: t('acoustic'),
}))
/** Key for the password of a Navidrome account in .env – like pass_key() on the server (Unicode-aware). */
export const passKey = (user) => (S.status?.env?.users || []).find((u) => u.name.toLowerCase() === String(user).toLowerCase())?.key
  || 'NAV_PASS_' + String(user).toUpperCase().replace(/[^\p{L}\p{N}_]/gu, '_')

/* ------------------------------------------------------------------ Who is signed in? */
export const isAdmin = () => !S.me || S.me.role === 'admin'
/** A run that only applies changes to Navidrome (writing playlists + scan) – told by its steps, its name is translated. */
export const isApplyRun = (task) => !!task?.steps?.length && task.steps.every((s) => s === 'playlists' || s === 'scan')
/** Your own person – one person per Navidrome account (the local administrator and accounts without one: null). */
export const myPerson = () => S.config?.personen.find((p) => (S.me?.own || [])[0] === p.id) || null
/** The family – an entry with a Navidrome account of its own (or null). */
export const familyPerson = () => S.config?.personen.find((p) => p.family) || null
/** Is this person (object or id) the family? */
export const isFamily = (p) => !!(typeof p === 'string' ? findPerson(p) : p)?.family
/** May you create, change and delete the family's playlists? (settings.familyEdit) */
const familyEditable = () => isAdmin() || (S.config?.settings.familyEdit || 'all') === 'all'
/** May you edit this playlist? Administrators all; users their own and – unless only administrators may – the family's. */
export const canEdit = (p) => isAdmin() || (S.me?.own || []).includes(p?.person) || (isFamily(p?.person) && familyEditable())
/** People you may create playlists for: administrators everyone; users their own person and the family (if allowed). */
export const creatablePersons = () => (isAdmin() ? S.config.personen
  : [myPerson(), familyEditable() ? familyPerson() : null].filter(Boolean))
/** The owner of a new playlist when none is chosen: your own person, otherwise the family, otherwise the first one. */
export const defaultOwner = () => myPerson() || (isAdmin() ? familyPerson() || S.config.personen[0] || null : null)

/* ------------------------------------------------------------------ Saving (with undo) */
let saveTimer
let savePromise = Promise.resolve()
let undoSnapshot = null

/** Remember the state before changing something – toast(…, { undo: true }) can restore it. */
export function snapshot() {
  undoSnapshot = $state.snapshot(S.config)
}
/** Call after every change to S.config: saves after a short pause. */
export function changed() {
  S.dirty = true
  clearTimeout(saveTimer)
  saveTimer = setTimeout(save, 450)
}
/** Save right away (waits for saves in progress). */
export function save() {
  clearTimeout(saveTimer)
  if (!S.dirty) return savePromise
  S.dirty = false
  // save one after another (never two PUTs at once that could overtake each other)
  savePromise = savePromise
    .then(() => api('/api/config', { method: 'PUT', body: $state.snapshot(S.config) }))
    .then(() => { reachable(); S.saved++; refreshSoon(); libraryLater() })
    .catch(async (e) => {
      if (e.offline) {
        // Tuttiphon cannot be reached: keep the change and save it as soon as the server is back
        S.dirty = true
        if (!waitingToast) toast(t('Tuttiphon can’t be reached right now – your change will be saved when it’s back.'))
        waitingToast = true   // once per outage
        unreachable()
        return
      }
      // The server rejected the change -> otherwise all further saves fail with the same error
      toast(t('Saving failed: {error} – the last change was discarded.', { error: e.message }), { error: true })
      closeSheet()   // an open sheet would otherwise keep working on objects that are no longer in S.config
      try { S.config = await api('/api/config') } catch { /* server gone */ }
    })
  return savePromise
}

/* ------------------------------------------------------------------ Connection to Tuttiphon */
let retryTimer
let waitingToast = false
/** A request failed because Tuttiphon cannot be reached: ask again regularly until it answers. */
function unreachable() {
  S.offline = true
  clearTimeout(retryTimer)
  retryTimer = setTimeout(() => { loadStatus() }, 5000)
}
/** Tuttiphon answered: save changes that were waiting for it. */
function reachable() {
  clearTimeout(retryTimer)
  if (!S.offline) return
  S.offline = false
  waitingToast = false
  if (S.dirty) save()
}
export async function undo() {
  if (!undoSnapshot) return
  closeSheet()   // open sheets would otherwise keep working on the old objects
  S.config = undoSnapshot
  undoSnapshot = null
  changed()
  await save()
  toast(t('Undone'))
}
const refreshSoon = debounce(async () => {
  try { S.pl = await api('/api/playlists') } catch { /* does not matter */ }
}, 900)
const libraryLater = debounce(() => loadLibrary().catch(() => {}), 1500)

export async function reloadConfig() {
  await save()
  S.config = await api('/api/config')
}
/** Copy what the server changes by itself (file name, takeover, cover, classified bands) into the existing objects –
 *  without replacing S.config (open edit sheets hold references to it). */
export function mergeServerFields(server) {
  const byId = new Map(server.playlists.map((p) => [p.id, p]))
  for (const p of S.config.playlists) {
    const sp = byId.get(p.id)
    if (!sp) continue
    for (const k of ['file', 'takeover', 'cover']) {
      if (k in sp) p[k] = sp[k]
      else delete p[k]
    }
  }
  // Bands the server assigned to a music world by itself during classification (step "Understand music") –
  // otherwise the next save from the interface would overwrite them again
  const worlds = new Map((server.welten || []).map((w) => [w.id, w]))
  for (const w of S.config.welten) {
    const sw = worlds.get(w.id)
    if (!sw) continue
    const have = new Set(w.artists || [])
    const out = new Set(w.excludedArtists || [])
    const added = (sw.artists || []).filter((a) => !have.has(a) && !out.has(a))
    if (!added.length) continue
    w.artists ??= []
    w.artists.push(...added)
  }
}

/* ------------------------------------------------------------------ Loading data */
export async function loadLibrary(refresh = false) {
  const lib = await api('/api/library' + (refresh ? '?refresh=1' : ''))
  lib.artistIdx = new Map(lib.artists.map(([a, , id]) => [a, id]))
  lib.artistCount = new Map(lib.artists.map(([a, n]) => [a, n]))
  lib.genreCount = new Map(lib.genres)
  S.library = lib
}
let pageVersion = null   // version of the server when this page was loaded
export async function loadStatus() {
  try {
    const st = await api('/api/status')
    reachable()
    pageVersion ??= st.version
    if (st.version && st.version !== pageVersion) S.newVersion = st.version
    S.status = st
  } catch (e) {
    if (e.offline) unreachable()   // Tuttiphon itself is gone – that says nothing about Navidrome
    else S.status = { navidrome: { ok: false, error: e.message } }
  }
}
export async function loadPlaylists() {
  S.pl = await api('/api/playlists')
  return S.pl
}
export async function loadHistory() {
  try { S.history = await api('/api/history') } catch { /* administrators only */ }
}
/** After switching the language: fetch again what the server words in the language of the request (status,
 *  playlists, the library with the names of the scene catalog, the history if it was loaded). */
export async function reloadTexts() {
  await Promise.all([loadStatus(), loadPlaylists().catch(() => {}), loadLibrary().catch(() => {}),
    isAdmin() && S.history?.length ? loadHistory() : null])
}

/* ------------------------------------------------------------------ Tasks (runs) */
export async function runTask(steps, extra = {}) {
  await save()
  try {
    S.task = await api('/api/task', { body: { steps, ...extra } })
    S.running = true
    pollTask()
    return true
  } catch (e) {
    toast(e.message, { error: true })
    return false
  }
}
/** Apply changed playlists to Navidrome right away (instead of waiting for auto-apply). */
export async function applyNow() {
  await save()
  try {
    S.task = await api('/api/apply/now', { body: {} })
    S.running = true
    pollTask()
  } catch (e) {
    toast(e.message, { error: true })
  }
}
let pollHandle
let pollGen = 0
export async function pollTask() {
  clearTimeout(pollHandle)
  const gen = ++pollGen   // a new call (e.g. after "Apply") replaces a poll still in progress
  try {
    const st = await api(`/api/task?since=${S.since}`)
    reachable()
    if (st.lines.length) {
      S.since = st.lines[st.lines.length - 1].n
      S.logLines = [...S.logLines, ...st.lines].slice(-5000)
    }
    const was = S.running
    S.task = st
    S.auto = st.auto
    S.running = st.running
    if (was && !st.running) {
      if (isAdmin()) toast(t('{name} – done ✓', { name: st.name }))
      else if (isApplyRun(st)) toast(t('Your changes are now in Navidrome ✓ – Symfonium shows them after the next sync'))
      // first take over what the server changed (e.g. classified bands), then save open changes –
      // otherwise the older state of the interface would overwrite the server's assignments
      mergeServerFields(await api('/api/config'))
      await save()
      await Promise.allSettled([loadStatus(), loadLibrary(true), loadPlaylists(), isAdmin() ? loadHistory() : null])
      S.done++
    }
  } catch (e) {
    if (e.offline) unreachable()   // otherwise: briefly gone, the next poll tries again
  }
  // in a hidden tab: pause – it continues as soon as the page is visible again
  if (gen === pollGen && !document.hidden) pollHandle = setTimeout(pollTask, S.running || S.auto?.due != null ? 1000 : 4000)
}
let polling = false
export function startPolling() {
  polling = true
  pollTask()
}
if (typeof document !== 'undefined') {
  document.addEventListener('visibilitychange', () => {
    if (document.hidden) {
      if (S.dirty) save()   // the page may be closed next – do not wait for the pause after the last change
      return
    }
    if (!polling) return
    pollTask()
    loadStatus()   // also notices a new version of the server
  })
}

/** Playlists that are not (like this) in Navidrome yet – for the number at "Playlists" and the apply bar. */
export const pendingCount = () => (S.pl?.playlists || []).filter((p) => ['neu', 'geändert', 'scan', 'entfernen'].includes(p.state)   // i18n-ignore: playlist states from the server
  && (isAdmin() || canEdit(findPl(p.id)))).length + (isAdmin() ? S.pl?.orphans?.length || 0 : 0)   // users: only their own
