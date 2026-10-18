// As an app on the phone: the browser's install prompt (Android/Chrome), otherwise the matching instructions.
// Used by the one-time hint on the home pages (components/InstallHint.svelte) and by
// Settings → General. Each device remembers by itself whether the hint was dismissed.
import { S } from './state.svelte.js'

const KEY = 'nt-install-hint'
const VISITS = 'nt-visits'

/** Is Tuttiphon currently running as an installed app? */
export const standalone = () => matchMedia('(display-mode: standalone)').matches || !!navigator.standalone
export const ios = () => /iphone|ipad|ipod/i.test(navigator.userAgent) || (navigator.platform === 'MacIntel' && navigator.maxTouchPoints > 1)
export const secure = () => window.isSecureContext

/** State of the hint: hidden = dismissed or installed */
export const hint = $state({ hidden: read(KEY) === 'done', visits: Number(read(VISITS) || 0) })

function read(key) {
  try { return localStorage.getItem(key) } catch { return null }
}
function write(key, value) {
  try { localStorage.setItem(key, value) } catch { /* private mode: then only until the next reload */ }
}

/** Before the app starts (main.js): keep the browser's install prompt – it may come before the app is ready */
export function listenInstall() {
  window.addEventListener('beforeinstallprompt', (e) => { e.preventDefault(); S.installPrompt = e })
  window.addEventListener('appinstalled', () => { S.installPrompt = null; dismissHint() })
}

/** On app start: count the visit */
export function initInstall() {
  hint.visits += 1
  write(VISITS, String(hint.visits))
}

/** Show the hint? Only on a phone or tablet, not as an app, from the second visit on, until it is dismissed. */
export const showHint = () => !hint.hidden && hint.visits >= 2 && !standalone() && matchMedia('(pointer: coarse)').matches

export function dismissHint() {
  hint.hidden = true
  write(KEY, 'done')
}

/** Show the browser's install prompt. -> true if it was installed */
export async function install() {
  const p = S.installPrompt
  if (!p) return false
  p.prompt()
  const choice = await p.userChoice
  S.installPrompt = null
  if (choice?.outcome === 'accepted') dismissHint()
  return choice?.outcome === 'accepted'
}
