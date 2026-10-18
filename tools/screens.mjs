// Open pages in headless Chromium: screenshots + errors from the console.
//
//   node tools/screens.mjs --base http://127.0.0.1:8792 --out <dir> [--cookie nt=…] [--mobile] [--light] [--text] '#/' '#/playlists' …
//
//   --cookie  session (see tools/testserver.sh --auth)   --mobile  phone (Pixel 7)   --light  light theme
//   --mobile-small  small phone (360 × 740) – narrow layouts break here first
//   --text    also print the visible text of the page (shortened)
//   --fresh   tour and welcome assistant as on the very first visit (otherwise they count as seen)
//   --lang en|de  interface language (otherwise the browser's: German)
// Exit code 1 if a page had console errors or JavaScript errors.
import { chromium, devices } from '@playwright/test'
import { existsSync, mkdirSync } from 'node:fs'

const args = process.argv.slice(2)
const opt = (name) => { const i = args.indexOf(name); if (i < 0) return null; const v = args[i + 1]; args.splice(i, 2); return v }
const flag = (name) => { const i = args.indexOf(name); if (i < 0) return false; args.splice(i, 1); return true }
const base = opt('--base') || 'http://127.0.0.1:8791'
const out = opt('--out') || 'screens'
const cookie = opt('--cookie')
const small = flag('--mobile-small')
const mobile = flag('--mobile') || small
const light = flag('--light')
const text = flag('--text')
const fresh = flag('--fresh')
const lang = opt('--lang')
const routes = args.length ? args : ['#/']
mkdirSync(out, { recursive: true })

const browser = await chromium.launch({ executablePath: existsSync('/usr/bin/chromium') ? '/usr/bin/chromium' : undefined })
const context = await browser.newContext({
  ...(mobile ? devices['Pixel 7'] : { viewport: { width: 1360, height: 900 } }),
  ...(small ? { viewport: { width: 360, height: 740 }, screen: { width: 360, height: 740 } } : {}),
  locale: lang === 'en' ? 'en-US' : 'de-DE', timezoneId: 'Europe/Berlin', colorScheme: light ? 'light' : 'dark',
})
let account = ''
if (cookie) {
  const [name, ...rest] = cookie.split('=')
  await context.addCookies([{ name, value: rest.join('='), url: base }])
  // the signed-in account: the tour and the welcome assistant remember "seen" per account
  const me = await fetch(`${base}/api/me`, { headers: { Cookie: cookie, 'X-Tuttiphon': '1' } }).then((r) => r.json()).catch(() => ({}))
  account = (me.user || '').toLowerCase()
}
// Do not start the tour and the welcome assistant automatically
if (!fresh) {
  await context.addInitScript((u) => {
    try {
      localStorage.setItem('nt-tour', '1')
      if (u) { localStorage.setItem(`nt-tour:${u}`, '1'); localStorage.setItem(`nt-welcome:${u}`, '1') }
    } catch {}
  }, account)
}

let bad = 0
for (const route of routes) {
  const page = await context.newPage()
  const errors = []
  page.on('console', (m) => { if (m.type() === 'error' && !/service ?worker|sw\.js/i.test(m.text())) errors.push(m.text()) })
  page.on('pageerror', (e) => errors.push('JS: ' + e.message))
  await page.goto(base + '/' + route.replace(/^\//, ''), { waitUntil: 'networkidle' }).catch((e) => errors.push('goto: ' + e.message))
  await page.waitForTimeout(800)
  const file = `${out}/${(route.replace(/^#\/?/, '') || 'start').replace(/[^\w-]+/g, '_')}${small ? '-mobil360' : mobile ? '-mobil' : ''}${light ? '-hell' : ''}.png`
  await page.screenshot({ path: file, fullPage: true })
  console.log(`${errors.length ? '✗' : '✓'} ${route} → ${file}`)
  for (const e of errors) console.log('    ' + e)
  if (text) console.log((await page.locator('main').innerText().catch(() => '')).slice(0, 1500).replace(/\n{2,}/g, '\n'))
  bad += errors.length ? 1 : 0
  await page.close()
}
await browser.close()
process.exit(bad ? 1 : 0)
