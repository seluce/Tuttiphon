// Song sheet: info, listening in, lyrics, “More like this” and the playlists the song appears in.
import { openSheet } from './overlay.svelte.js'
import SongSheet from '../components/sheets/SongSheet.svelte'

/** Open the song sheet. track: row from a song list ({ id, title, artist, cover … }) – shown right away,
 *  the rest comes from /api/song. */
export function openSong(track) {
  if (!track?.id) return
  openSheet({ title: track.title || 'Song', component: SongSheet, props: { track } })
}
