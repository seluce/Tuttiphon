// Playlist editor: option lists and the editing sheet.
import { S } from './state.svelte.js'
import { fmt } from './format.js'
import { t, translated } from './i18n.svelte.js'
import { openSheet } from './overlay.svelte.js'
import { GROUP_LABEL } from './richtungen.js'
import EditorSheet, { editorFoot } from '../components/sheets/EditorSheet.svelte'

// Group names are stored data (field `group` of a vibe) – shown through GROUP_LABEL
const GROUPS = ['Genre', 'Thema', 'Jahreszeit', 'Zeitreise', 'Spezial']   // i18n-ignore: stored values
export const SORTS = translated(() => [['random', t('Random – new on every load')], ['neu', t('Newest first')], ['beliebt', t('Most popular first')], ['vergessen', t('Least recently played first')]])   // i18n-ignore: stored sort keys
export const AUSWAHL = translated(() => [['', t('Music world default')], ['0', t('all songs')], ['1', t('{stars} and up', { stars: '★' })], ['2', t('{stars} and up', { stars: '★★' })],
  ['3', t('{stars} and up', { stars: '★★★' })], ['4', t('{stars} and up', { stars: '★★★★' })], ['5', t('only {stars}', { stars: '★★★★★' })], ['hits', t('Only the hits')]])
export const FLAVORS = translated(() => [['ausgewogen', t('Balanced')], ['hits', t('Mostly hits')], ['entdecken', t('Mostly lesser-known')], ['geschmack', t('By taste')]])

/** Vibes as options (grouped), optionally with the number of matching songs. For <Select options={…}>. */
export function stilOptions(counts = null, includeAll = true) {
  const cfg = S.config
  const label = (s) => s.name + (counts && counts[s.id] != null ? ` · ${fmt(counts[s.id])}` : '')
  const groups = [...new Set([...GROUPS, ...cfg.stile.map((s) => s.group || 'Sonstiges')])]   // i18n-ignore: stored value
  return [
    ...(includeAll ? [['*', t('Everything – no restriction') + (counts?.['*'] != null ? ` · ${fmt(counts['*'])}` : '')]] : []),
    ...groups.map((g) => ({ group: GROUP_LABEL[g] ?? g, options: cfg.stile.filter((s) => (s.group || 'Sonstiges') === g).map((s) => [s.id, label(s)]) }))   // i18n-ignore: stored value
      .filter((g) => g.options.length),
  ]
}

/**
 * Editing sheet of a playlist (all settings with a live preview).
 * @param {object} p0 playlist (copied; only "Save" puts it into S.config)
 * @param {{ isNew?: boolean, onSaved?: (p: object) => void }} [opts]
 */
export function openEditor(p0, { isNew = false, onSaved = null } = {}) {
  openSheet({ title: isNew ? t('New playlist') : t('Edit playlist'), wide: true,
    component: EditorSheet, props: { p0, isNew, onSaved }, foot: editorFoot })
}
