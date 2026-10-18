// History of runs: summary and log.
import { api } from './api.js'
import { modal, toast } from './overlay.svelte.js'
import { t, tn, translated } from './i18n.svelte.js'
import { fmt } from './format.js'
import LogView from '../pages/history/LogView.svelte'

export const STEP_LABEL = translated(() => ({ flac: t('Convert'), lyrics: t('Lyrics'), analyse: t('Understand music'), playlists: t('Playlists'), scan: t('Scan'), deezer: 'Deezer' }))

/** One sentence on what a run did. */
export function summaryText(e) {
  const s = e.summary || {}, out = []
  if (s.flac?.converted) out.push(t('{n} converted', { n: fmt(s.flac.converted) }))
  const ly = s.lyrics || {}
  const found = (ly.synced || 0) + (ly.plain || 0)
  if (found) out.push(t('{n} lyrics found', { n: fmt(found) }))
  if (ly.deleted) out.push(t('{n} lyrics tidied up', { n: fmt(ly.deleted) }))
  if (s.playlists && (s.playlists.written || s.playlists.removed)) {
    out.push(s.playlists.removed
      ? tn(s.playlists.written, '{n} playlist written, {removed} removed', '{n} playlists written, {removed} removed', { removed: fmt(s.playlists.removed) })
      : tn(s.playlists.written, '{n} playlist written', '{n} playlists written'))
  }
  if (s.scan?.changed) out.push(t('{n} adjusted in Navidrome', { n: fmt(s.scan.changed) }))
  if (s.scan?.deleted) out.push(t('{n} removed from Navidrome', { n: fmt(s.scan.deleted) }))
  const an = s.analyse || {}
  if (an.audio?.analysed) out.push(tn(an.audio.analysed, '{n} song analyzed', '{n} songs analyzed'))
  if (an.assigned) out.push(tn(an.assigned, '{n} band classified', '{n} bands classified'))
  if (s.deezer) out.push(s.deezer.mode === 'recalc' ? t('Stars recalculated: {n} changed', { n: fmt(s.deezer.set) })
    : tn(s.deezer.set, 'Deezer: {found} found, {n} star set', 'Deezer: {found} found, {n} stars set', { found: fmt(s.deezer.found) }))
  // nothing to count: say how it ended if a step failed or left notes (results: step → "ok" / "warnung" / "fehler" …)
  const results = Object.values(e.results || {})
  if (!out.length && e.log && results.includes('fehler')) out.push(t('Failed – tap to see the log'))
  else if (!out.length && e.log && results.includes('warnung')) out.push(t('With notes – tap to see the log'))
  if (e.dryRun) out.push(t('Dry run'))
  return out.join(' · ') || t('no changes')
}

/** Show the log of a run in a dialog. */
export async function openLog(e) {
  if (!e.log) { toast(e.skipped ? t('Skipped: {reason}', { reason: e.skipped }) : t('There is no log for this run.')); return }
  try {
    const res = await api(`/api/log?file=${encodeURIComponent(e.log)}`)
    modal({ title: t('Log: {name}', { name: e.name }), component: LogView, props: { text: res.text }, buttons: [{ label: t('Close'), value: 'ok' }] })
  } catch (err) {
    toast(err.message, { error: true })
  }
}
