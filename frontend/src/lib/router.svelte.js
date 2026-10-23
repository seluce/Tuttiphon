// Hash router: #/path/part?query. App.svelte picks the page from route.parts.
//
//   #/                       Home (administrator) or “For you” (user)
//   #/playlists  #/playlist/<id>  #/neu?person=…  #/entdecken  #/welten  #/welt/<id>
//   #/richtungen  #/personen  #/person/<id>  #/profil  #/willkommen  #/einrichtung (setup assistant, administrators)
//   #/statistik/<kind>  #/jahr/<person>/<year>  #/einstellungen/<tab>  #/verlauf  #/hilfe/<topic>

function decoded(part) {
  try { return decodeURIComponent(part) } catch { return part }
}

function read() {
  const raw = location.hash.replace(/^#/, '') || '/'
  const i = raw.indexOf('?')
  const path = i < 0 ? raw : raw.slice(0, i)
  const query = i < 0 ? '' : raw.slice(i + 1)
  return { path, query, parts: path.split('/').filter(Boolean).map(decoded) }
}

export const route = $state({ ...read(), key: 0 })
let before = null   // path of the address before the current one in this tab (null: the first one)

/** Re-read the address – needed when location.hash was set and the page has to be right immediately
 *  (the hashchange event only comes later). */
export function syncRoute() {
  const now = read()
  if (now.path !== route.path || now.query !== route.query) before = route.path
  Object.assign(route, now)
}

/** Path of the address before this one (null if the tab started here) – a full-screen page closes back to it. */
export const previous = () => before

addEventListener('hashchange', syncRoute)

// An open sheet has a history entry of its own (lib/overlay.svelte.js) so the back button closes it. Going somewhere
// from it replaces that entry instead of adding one after it – otherwise "back" would lead to the old page twice.
export const transient = () => !!history.state?.ntSheet

let leaving = null   // while the entry of a closed sheet is being removed (history.back() is asynchronous)
/** Remove the current sheet entry again (the sheet was closed without the back button). */
export function dropTransient() {
  if (!transient() || leaving) return
  leaving = new Promise((done) => {
    const end = () => { removeEventListener('popstate', end); clearTimeout(timer); leaving = null; done() }
    const timer = setTimeout(end, 600)   // in case no popstate comes
    addEventListener('popstate', end)
  })
  history.back()
}
/** Is a closed sheet's entry being removed right now? (Its popstate is not a "back" of the user.) */
export const isLeaving = () => !!leaving
/** Run fn once the page's own entry is the current one again (right away if nothing is being removed). */
export const afterLeaving = (fn) => (leaving ? leaving.then(fn) : fn())

/** Go to an address – if already there, the page is rebuilt. */
export function go(hash) {
  if (leaving) { leaving.then(() => go(hash)); return }   // first back to the page's own entry, then on from there
  if (location.hash === hash || (hash === '#/' && !location.hash)) route.key++
  else if (transient()) replace(hash)
  else location.hash = hash
}

/** Go to an address without a new history entry (redirects: "back" must not lead to the redirect again). */
export function replace(hash) {
  history.replaceState(null, '', hash)
  syncRoute()
}

// Links (<a href="#/…">) clicked while a sheet's entry is the current one: replace it as well
addEventListener('click', (e) => {
  if (!transient() || e.defaultPrevented || e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return
  const a = e.target.closest?.('a[href^="#"]')
  if (!a || (a.target && a.target !== '_self')) return
  e.preventDefault()
  go(a.getAttribute('href'))
})

/** Rebuild the current page (load fresh data). */
export function rerender() {
  route.key++
}

/** Query parameters of the current address (#/neu?person=mia → params().get('person')). */
export const params = () => new URLSearchParams(route.query)
