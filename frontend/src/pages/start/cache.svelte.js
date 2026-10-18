// Data of the home pages (“Home” and “For you”) that should be back right away when returning –
// the page shows the last state and reloads in the background. Plus the switches that apply until the next reload.
import { api } from '../../lib/api.js'

class StartCache {
  /** /api/home: { songs, albums, artists, newAlbums } */
  home = $state.raw(null)
  /** /api/inbox: notices (“To review” or “Next steps”) */
  inbox = $state.raw(null)
  /** /api/suggestions: suggestions */
  sg = $state.raw(null)
  /** error text when loading failed and nothing is there yet: { home, inbox } */
  failed = $state.raw({})
  /** “To review”: all instead of the first five */
  todoAll = $state(false)
  /** “Update everything”: dry run / full scan */
  dryRun = $state(false)
  fullScan = $state(false)
}

export const cache = new StartCache()

const fetchInto = (key, path) => api(path)
  .then((d) => { cache[key] = d; cache.failed = { ...cache.failed, [key]: null } })
  .catch((e) => { cache.failed = { ...cache.failed, [key]: e.message } })

/** Numbers and new albums (/api/home) */
export const loadHome = () => fetchInto('home', '/api/home')
/** Notices (/api/inbox) */
export const loadInbox = () => fetchInto('inbox', '/api/inbox')
