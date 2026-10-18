import '@fontsource-variable/inter'
import './app.css'
import { mount } from 'svelte'
import App from './App.svelte'
import { listenInstall } from './lib/install.svelte.js'
import { preloading } from './components/Lazy.svelte'

// The browser offers installing as an app early – possibly before the app has started (listen right away)
listenInstall()

// A file of the app could not be loaded (a page opened for the first time, the German texts …): usually Tuttiphon was
// updated while this page was open and the old files are gone. A reload brings the new version – at most once a
// minute, so a file that is really missing does not reload forever (the page then shows the error itself).
// Not for pages loaded in the background (App.svelte): that would reload in the middle of whatever you are doing.
window.addEventListener('vite:preloadError', () => {
  if (preloading()) return
  let last = 0
  try { last = Number(sessionStorage.getItem('nt-reloaded') || 0) } catch { /* private mode */ }
  if (Date.now() - last < 60000) return
  try { sessionStorage.setItem('nt-reloaded', String(Date.now())) } catch { /* private mode */ }
  location.reload()
})

export default mount(App, { target: document.getElementById('app') })
