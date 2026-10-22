// Playlist helpers: name, symbols, description, state, owners.
import { S, findWelt, findStil, findPerson, myPerson, isFamily, weltIds } from './state.svelte.js'
import { t, translated } from './i18n.svelte.js'

/** Symbols of a playlist (music worlds + vibe) – as a list for <Mosaic marks>. */
export function plEmoji(p) {
  if (p.rules) return ['text']
  const w = weltIds(p).map((id) => findWelt(id)?.icon).filter(Boolean)
  const s = p.stil && p.stil !== '*' ? findStil(p.stil)?.icon : p.hits ? 'star' : null
  return [...(w.length ? w : ['globe']), s].filter(Boolean)
}

// Words of generated names: they are part of the name in Navidrome, so they follow the server language
// (Settings → General), not the language of the interface – the server sends its templates (GET /api/status → names,
// as rules.base_name() uses them). "Mix" only for real mixes; a whole music world without a vibe is "All Sorts".
const NAMES_EN = { all: '{world} · All Sorts', hits: '{world} · The Hits', everything: 'Everything' }
const MIX_LABEL = { day: 'Daily Mix', week: 'Weekly Mix', month: 'Monthly Mix' }

/**
 * Display name – own name, otherwise the name the server gave it, otherwise built from music world × vibe × person
 * like the server does (for a playlist the server does not know yet).
 */
export function plName(p) {
  const st = S.pl?.playlists.find((x) => x.id === p.id)
  if (st?.name && !p.name) return st.name
  if (p.name) return p.name
  if (p.rules) return p.originalName || t('Playlist')
  const words = S.status?.names || NAMES_EN
  const person = findPerson(p.person)
  const w = weltIds(p).map((id) => findWelt(id)?.name).filter(Boolean).join(' + ')
  const s = p.stil && p.stil !== '*' ? findStil(p.stil)?.name : null
  const base = p.type === 'mix' ? `${MIX_LABEL[p.mix?.every] || MIX_LABEL.day} · ${[w, s].filter(Boolean).join(' · ') || words.everything}`
    : !s ? (p.hits ? words.hits : words.all).replace('{world}', w) : !w ? s + (p.hits ? ' (Hits)' : '')
      : S.config.settings.namePattern.replace('{welt}', w).replace('{stil}', s + (p.hits ? ' (Hits)' : ''))
  return (person?.prefix || '') + base
}

/** People in the order the pages show them: yours, the family, then the others (as in the configuration). */
export function ownerOrder(list) {
  const me = myPerson()
  const rank = (x) => (x.id === me?.id ? 0 : x.family ? 1 : 2)
  return [...list].sort((a, b) => rank(a) - rank(b))
}

/**
 * “What everyone likes” exists only for the family, with the other people as members (at least two). Otherwise it
 * goes – and an “All × Everything” left without it becomes a mix by the own taste, as the server does. Changes x.
 */
export function fixTogether(x) {
  if (!x.together) return x
  if (isFamily(x.person)) {
    x.together = x.together.filter((id) => findPerson(id) && !isFamily(id))
    if (x.together.length >= 2) return x
  }
  delete x.together
  if (!weltIds(x).length && (x.stil || '*') === '*' && !x.radio && !x.fav && !x.review) {
    x.type = 'mix'
    x.mix = { ...x.mix, flavor: 'geschmack' }
  }
  return x
}

export function plDescribe(p) {
  if (p.rules) return t('own rules')
  const w = weltIds(p).map((id) => findWelt(id)?.name).filter(Boolean).join(' + ') || t('All')
  const s = p.stil && p.stil !== '*' ? findStil(p.stil)?.name : t('Everything')
  return `${w} × ${s}`
}

/** State of a playlist (keys: states from the server) → [text, color] (ok | new | warn | off). */
export const STATE = translated(() => ({
  aktuell: [t('in Navidrome'), 'ok'], neu: [t('new'), 'new'],
  'geändert': [t('changed'), 'warn'],   // i18n-ignore: state key from the server
  scan: [t('waiting for scan'), 'warn'],
  entfernen: [t('being removed'), 'warn'], pausiert: [t('paused'), 'off'], papierkorb: [t('Trash'), 'off'], fehler: [t('Error'), 'warn'],
  ruht: [t('resting until its season'), 'off'],
}))
