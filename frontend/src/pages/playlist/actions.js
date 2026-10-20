// Actions of the playlist page: change status, delete permanently, copy, keep this mix (smart playlists: save as a
// fixed playlist), reshuffle, cover.
// p is always the playlist from S.config (findPl) – changes to it redraw the page by themselves.
import { S, defaultPerson, findPerson, canEdit, changed, snapshot } from '../../lib/state.svelte.js'
import { openSheet, toast, confirmDialog } from '../../lib/overlay.svelte.js'
import { go } from '../../lib/router.svelte.js'
import { api } from '../../lib/api.js'
import { clone, uid, today } from '../../lib/format.js'
import { t, tn, locale, translated } from '../../lib/i18n.svelte.js'
import { plName } from '../../lib/playlist.js'
import { openEditor } from '../../lib/editor.js'
import CoverSheet from '../../components/sheets/CoverSheet.svelte'

/**
 * How often a mix is put together anew – texts of the playlist page. songs: template with {n} (shown in bold),
 * about(n): the sentence under the track list.
 */
export const MIXEVERY = translated(() => ({
  day: {
    eyebrow: t('Daily Mix · new every day'),
    title: t('Today in the mix'),
    songs: t('{n} songs today'),
    about: (n) => t('These exact {n} songs are in Navidrome today – tomorrow morning there is a new selection. Until then the list stays the same – good for offline in Symfonium.', { n }),
  },
  week: {
    eyebrow: t('Weekly Mix · new every week'),
    title: t('This week in the mix'),
    songs: t('{n} songs this week'),
    about: (n) => t('These exact {n} songs are in Navidrome this week – next Monday there is a new selection. Until then the list stays the same – good for offline in Symfonium.', { n }),
  },
  month: {
    eyebrow: t('Monthly Mix · new every month'),
    title: t('This month in the mix'),
    songs: t('{n} songs this month'),
    about: (n) => t('These exact {n} songs are in Navidrome this month – on the first of the month there is a new selection. Until then the list stays the same – good for offline in Symfonium.', { n }),
  },
}))

export function setStatus(p, status) {
  snapshot()
  const old = p.status || 'aktiv'
  p.status = status
  if (status === 'papierkorb') p.deletedAt = today()
  else delete p.deletedAt   // brought back from the trash
  changed()
  const auto = S.config.settings.autoApply !== false
  const msg = {
    pausiert: auto ? t('Paused – kept here, disappears from Navidrome shortly') : t('Paused – kept here'),
    papierkorb: t('Moved to the trash'),
    aktiv: auto ? t('Active again – coming to Navidrome shortly') : t('Active again'),
  }[status]
  toast(msg, { undo: true })
  if (old !== status && status === 'papierkorb') go('#/playlists')
}

export async function purge(p) {
  if (!await confirmDialog(t('Delete permanently?'), t('“{name}” is removed from the tool. Its rules are then gone.', { name: plName(p) }), t('Delete permanently'), true)) return
  snapshot()
  S.config.playlists = S.config.playlists.filter((x) => x.id !== p.id)
  changed()
  toast(t('Deleted'), { undo: true })
  go('#/playlists')
}

/** Empty the trash: remove all given playlists permanently – with "Undo" */
export async function purgeAll(list) {
  if (!list.length) return
  const n = list.length
  if (!await confirmDialog(t('Empty trash?'), tn(n, '{n} playlist is removed from the tool. Its rules are then gone.', '{n} playlists are removed from the tool. Their rules are then gone.'), t('Empty trash'), true)) return
  const ids = new Set(list.map((p) => p.id))
  snapshot()
  S.config.playlists = S.config.playlists.filter((x) => !ids.has(x.id))
  changed()
  toast(tn(n, '{n} playlist deleted permanently', '{n} playlists deleted permanently'), { undo: true })
}

export function duplicate(p, d) {
  const copy = clone(p)
  delete copy.file; delete copy.takeover; delete copy.deletedAt; delete copy.cover
  copy.id = uid(p.id)
  copy.name = t('{name} (copy)', { name: d.name })
  if (!canEdit(copy)) {   // copy of a shared playlist: then it belongs to oneself, name with one's own prefix
    copy.person = defaultPerson()
    copy.status = 'aktiv'
    if (p.name) copy.name = (findPerson(copy.person)?.prefix || '') + p.name
    else delete copy.name
  }
  openEditor(copy, { isNew: true, onSaved: (x) => go(`#/playlist/${encodeURIComponent(x.id)}`) })
}

export async function snapshotMix(p, d) {
  const n = Math.min(d.count, d.limit || 100)
  const label = `${d.name} – ${new Date().toLocaleDateString(locale(), { month: 'short', year: 'numeric' })}`
  const ok = p.type === 'mix'
    ? await confirmDialog(t('Keep this mix'), t('A selection of {n} songs is saved as the fixed playlist “{name}” in Navidrome. It won’t change after that – handy when you like a mix.', { n, name: label }), t('Save'))
    : await confirmDialog(t('Save as fixed playlist'), t('A selection of {n} songs is saved as the fixed playlist “{name}” in Navidrome. It won’t change after that.', { n, name: label }), t('Save'))
  if (!ok) return
  try {
    const r = await api('/api/snapshot', { body: { id: p.id } })
    toast(t('“{name}” saved with {n} songs ✓', { name: r.name, n: r.count }))
  } catch (e) { toast(e.message, { error: true }) }
}

/** Mix: a different selection now (new random value, goes to Navidrome with the next apply). */
export function reroll(p) {
  snapshot()
  p.mix ??= {}
  p.mix.salt = Math.random().toString(36).slice(2, 8)
  changed()
  toast(S.config.settings.autoApply !== false ? t('Reshuffled – coming to Navidrome shortly') : t('Reshuffled – bring it to Navidrome with “Apply”'), { undo: true })
}

/**
 * Choose a cover (designed, own picture or Navidrome default).
 * @param {object} p playlist  @param {object} d data from /api/playlist  @param {Function} [ondone] after a change
 */
export async function coverSheet(p, d, ondone) {
  if (!d.navidrome) {
    openSheet({ title: t('Cover'), component: CoverSheet, props: { p, d } })
    return
  }
  let styles = {}
  try { styles = await api(`/api/cover/styles?id=${encodeURIComponent(p.id)}`) } catch (e) { toast(e.message, { error: true }); return }
  openSheet({ title: t('Cover for “{name}”', { name: d.name }), component: CoverSheet, props: { p, d, styles, ondone } })
}
