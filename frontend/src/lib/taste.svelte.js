// Own taste (GET /api/taste?me=1), loaded once per session: share of each music world in one's own listening –
// so the music worlds page and the assistant show the worlds you listen to yourself first.
import { api } from './api.js'

export const T = $state({ me: null })
let asked = false

/** Load once (on error it stays null – then there is simply no sorting by listening). */
export function loadMyTaste() {
  if (asked) return
  asked = true
  api('/api/taste?me=1').then((t) => { T.me = t?.enough ? t : null }).catch(() => {})
}

/** Share of a music world in one's own listening (0–1) */
export const heardShare = (wid) => T.me?.welten?.find((w) => w.id === wid)?.share || 0

/** Music worlds sorted: liked (liked: Set) first, then by own listening, otherwise as saved */
export const byRelevance = (welten, liked = new Set()) =>
  [...welten].sort((a, b) => (liked.has(b.id) - liked.has(a.id)) || (heardShare(b.id) - heardShare(a.id)))
