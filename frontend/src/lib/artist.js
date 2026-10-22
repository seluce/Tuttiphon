// Artists: sheet with picture, info, albums, similar bands – and "radio" (a mix of similar bands).
import { S, defaultOwner, snapshot, changed } from './state.svelte.js'
import { openSheet, closeSheet, toast } from './overlay.svelte.js'
import { go } from './router.svelte.js'
import { uid, today } from './format.js'
import { t } from './i18n.svelte.js'
import ArtistSheet from '../components/sheets/ArtistSheet.svelte'

/** Open the artist sheet (picture, albums, bio – and everywhere the band appears). */
export function openArtist(name) {
  openSheet({ title: name, component: ArtistSheet, props: { name } })
}

/** Create a "similar to …" radio as a mix (new every week) – or open the existing one. For your own person
 *  (administrators without one: the family's); without a person of your own, the welcome comes first. */
export function startRadio(name, person = defaultOwner()?.id) {
  const have = S.config.playlists.find((p) => p.person === person && p.radio?.seed?.length === 1 && p.radio.seed[0] === name && (p.status || 'aktiv') !== 'papierkorb')
  closeSheet()
  if (!person) { go('#/willkommen'); return }
  if (have) { go(`#/playlist/${encodeURIComponent(have.id)}`); return }
  snapshot()
  const id = uid(`radio-${name}`)
  S.config.playlists.push({ id, person, welt: '*', stil: '*', type: 'mix', radio: { seed: [name] },
    mix: { size: 50, perArtist: 3, every: 'week' }, status: 'aktiv', created: today(), source: 'radio' })
  changed()
  toast(t('Radio · {name} created – {name} and similar bands, new every week', { name }), { undo: true })
  go(`#/playlist/${encodeURIComponent(id)}`)
}
