// Texts for the sections of the home page and the steps of "Update everything" –
// used by the home page and the settings.
import { go } from './router.svelte.js'
import { t, translated } from './i18n.svelte.js'

/** Sections of the home page: id → [title, description, icon] */
export const START_SECTIONS = translated(() => ({
  heute: [t('Today for all of you'), t('Your mixes of the day, large with cover'), 'sunrise'],
  todo: [t('To review'), t('Notes: missing passwords, new bands, old playlists …'), 'check-circle'],
  woche: [t('Played this week'), t('Most played bands of the last 7 days'), 'trending'],
  neu: [t('New in your library'), t('Recently added albums'), 'disc'],
  playlists: [t('All playlists'), t('All active playlists as a carousel'), 'playlists'],
  karten: [t('Deezer & library'), t('State of the ratings, file formats'), 'star'],
  verlauf: [t('History'), t('The latest runs'), 'clock'],
}))

/** Steps of a run: id → [icon, title, description] */
export const STEP_INFO = translated(() => ({
  flac: ['headphones', t('Convert music'), t('new FLAC files → Opus or AAC, archive originals as set')],
  lyrics: ['mic', t('Find & tidy up lyrics'), t('fetch missing lyrics with a time limit, delete duplicate .txt')],
  cover: ['image', t('Fetch missing covers'), t('save a cover as cover.jpg for albums without any picture – existing ones stay')],
  analyse: ['brain', t('Understand music'), t('analyze the sound with our own measurement and AI, fetch Last.fm knowledge, classify new bands – with a time limit')],
  playlists: ['playlists', t('Write playlists'), t('Smart playlists & mixes into the playlist folder')],
  scan: ['refresh', t('Navidrome scan & sync'), t('Navidrome reads everything in, names & owners are synced')],
  deezer: ['star', t('Deezer rating'), t('look up new songs on Deezer and set stars')],
}))

/** The settings now live on their own page – formerly a dialog. */
export const openEnvModal = () => go('#/einstellungen/navidrome')
