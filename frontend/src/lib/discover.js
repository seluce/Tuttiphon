// Accept suggestions (Discover, start page, "For you").
import { S, snapshot, changed } from './state.svelte.js'
import { toast } from './overlay.svelte.js'
import { go } from './router.svelte.js'
import { uid, today, clone } from './format.js'
import { t } from './i18n.svelte.js'

/**
 * Create a suggestion from /api/suggestions as a playlist. The caller removes the suggestion from its list.
 * @returns {string} id of the new playlist
 */
export function accept(s) {
  snapshot()
  const id = uid(s.name)
  S.config.playlists.push({ ...clone(s.playlist), id, status: 'aktiv', created: today(), source: 'vorschlag' })
  changed()
  toast(S.config.settings.autoApply !== false ? t('“{name}” created – coming to Navidrome shortly', { name: s.name }) : t('“{name}” created', { name: s.name }),
    { undo: true, action: { label: t('View'), run: () => go(`#/playlist/${encodeURIComponent(id)}`) } })
  return id
}

/** How many suggestions are hidden? (deleted music worlds – "scene|…" – do not count) */
export const hiddenCount = () => (S.config.dismissed || []).filter((k) => !k.startsWith('scene|')).length

/** Show hidden suggestions again – deleted music worlds stay away. With "Undo". */
export function showHidden() {
  snapshot()
  S.config.dismissed = (S.config.dismissed || []).filter((k) => k.startsWith('scene|'))
  changed()
  toast(t('Hidden suggestions are back'), { undo: true })
}
