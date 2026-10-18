// Setup assistant (#/einrichtung): the steps, nothing is saved before “Finish”, “Skip setup”, the redirect only while
// settings.setup.done is false (only for administrators), the entry under Settings → General. The data copy is
// migrated (done: true), so a new installation is played in the browser: GET /api/config and /api/status are
// extended, PUT /api/config, PUT /api/env and POST /api/task are answered there (page.route) – nothing is written.
import { test, expect } from '@playwright/test'
import { login, visit } from './helpers.js'

/** Extend the JSON answer of an endpoint (exact path, GET) with change(data). */
async function extend(page, path, change) {
  await page.route((url) => url.pathname === path, async (route) => {
    if (route.request().method() !== 'GET') return route.fallback()
    const res = await route.fetch()
    return route.fulfill({ response: res, json: change(await res.json()) })
  })
}
/** Answer writes in the browser and remember them. */
async function catchWrites(page) {
  const writes = []
  await page.route((url) => ['/api/config', '/api/env', '/api/task'].includes(url.pathname), (route) => {
    const r = route.request()
    if (r.method() === 'GET') return route.fallback()
    writes.push({ method: r.method(), path: new URL(r.url()).pathname, body: r.postDataJSON() })
    return route.fulfill({ json: r.method() === 'POST' ? { name: 'Test', steps: [], running: false, lines: [] } : { ok: true } })
  })
  return writes
}
/** A new installation: the assistant has not run, conversion is off (the template since configuration v10). */
const fresh = (cfg) => ({ ...cfg, settings: { ...cfg.settings, setup: { done: false }, opus: { ...cfg.settings.opus, enabled: false } } })
const connected = (st) => ({ ...st, navidrome: { ...st.navidrome, ok: true, version: '0.64.2 (test)' } })
const foot = (page) => page.locator('.wiz-foot')
test.afterEach(async ({ page }) => page.unrouteAll({ behavior: 'ignoreErrors' }))

test.describe('Administrator', () => {
  test.beforeEach(async ({ context }) => login(context, 'admin'))

  test('new installation: led to the assistant, walks through all steps, saves only with “Finish”', async ({ page }) => {
    const writes = await catchWrites(page)
    await extend(page, '/api/config', fresh)
    await extend(page, '/api/status', connected)
    expect(await visit(page, '#/')).toEqual([])
    await expect(page).toHaveURL(/#\/einrichtung$/)
    await expect(page.getByRole('heading', { name: 'Tuttiphon einrichten' })).toBeVisible()
    await expect(page.getByText('Verbunden – Navidrome 0.64.2')).toBeVisible()

    await foot(page).getByRole('button', { name: 'Weiter' }).click()
    await expect(page.getByRole('heading', { name: 'Verlustfreie Dateien umwandeln?' })).toBeVisible()
    await expect(page.getByRole('radio', { name: /^Aus/ })).toBeChecked()   // off until someone chooses it
    await page.locator('label.choice', { hasText: 'Opus' }).click()
    await expect(page.getByText('Und das Original?')).toBeVisible()
    await page.locator('label.choice', { hasText: 'Löschen' }).click()   // asks first – cancelled, archive stays
    await page.locator('dialog').getByRole('button', { name: 'Abbrechen' }).click()
    await expect(page.getByRole('radio', { name: /^Ins Archiv verschieben/ })).toBeChecked()

    for (const heading of ['Lyrics', 'Musik verstehen', 'Sterne von Deezer', 'Was soll von selbst laufen?', 'Alles bereit?']) {
      await foot(page).getByRole('button', { name: 'Weiter' }).click()
      await expect(page.getByRole('heading', { name: heading })).toBeVisible()
    }
    await expect(page.locator('.member-row', { hasText: 'Umwandlung' })).toContainText('Opus · ')
    expect(writes).toEqual([])   // nothing saved so far

    await foot(page).getByRole('button', { name: 'Fertig' }).click()
    await expect(page).toHaveURL(/#\/$/)
    const saved = writes.filter((w) => w.path === '/api/config')
    expect(saved.length).toBeGreaterThan(0)
    const st = saved.at(-1).body.settings
    expect(st.setup.done).toBe(true)
    expect(st.setup.at).toMatch(/^\d{4}-\d{2}-\d{2}$/)
    expect([st.opus.enabled, st.opus.codec, st.opus.original]).toEqual([true, 'opus', 'archive'])
    expect(writes.some((w) => w.path === '/api/task')).toBe(false)   // no run without “Start the first run now”
  })

  test('“Skip setup” only marks it as done', async ({ page }) => {
    const writes = await catchWrites(page)
    await extend(page, '/api/config', fresh)
    expect(await visit(page, '#/einrichtung')).toEqual([])
    await page.getByRole('button', { name: 'Einrichtung überspringen' }).click()
    await page.locator('dialog').getByRole('button', { name: 'Überspringen' }).click()
    await expect(page).toHaveURL(/#\/$/)
    const st = writes.filter((w) => w.path === '/api/config').at(-1).body.settings
    expect(st.setup.done).toBe(true)
    expect(st.opus.enabled).toBe(false)   // the rest stays as it was
  })

  test('without a connection the assistant does not go on', async ({ page }) => {
    await catchWrites(page)
    await extend(page, '/api/status', (st) => ({ ...st, navidrome: { ok: false, error: 'Testfehler' } }))
    expect(await visit(page, '#/einrichtung')).toEqual([])
    await expect(page.getByText('Tuttiphon erreicht Navidrome noch nicht: Testfehler')).toBeVisible()
    await expect(page.getByRole('button', { name: 'Verbindung testen' })).toBeVisible()
    await expect(foot(page).getByRole('button', { name: 'Weiter' })).toBeDisabled()
    await expect(page.locator('main')).not.toContainText('Navidrome ist nicht erreichbar')   // no second notice above
  })

  test('the redirect comes once per session, and not when it is done', async ({ page }) => {
    await catchWrites(page)
    expect(await visit(page, '#/playlists')).toEqual([])   // data copy: done – stays where it is
    await expect(page).toHaveURL(/#\/playlists$/)
    await extend(page, '/api/config', fresh)
    await page.reload()
    await expect(page).toHaveURL(/#\/einrichtung$/)
    await page.evaluate(() => { location.hash = '#/playlists' })
    await page.reload()   // looked around first: not sent back in the same session
    await expect(page.locator('main')).not.toContainText('Tuttiphon startet')
    await expect(page).toHaveURL(/#\/playlists$/)
  })

  test('Settings → General opens it again', async ({ page }) => {
    await catchWrites(page)
    expect(await visit(page, '#/einstellungen/allgemein')).toEqual([])
    await page.locator('.card', { hasText: 'Einrichtungsassistent erneut starten' }).getByRole('link', { name: 'Starten' }).click()
    await expect(page).toHaveURL(/#\/einrichtung$/)
    await expect(page.getByRole('heading', { name: 'Tuttiphon einrichten' })).toBeVisible()
  })
})

test.describe('User', () => {
  test.beforeEach(async ({ context }) => login(context, 'user'))

  test('never led to the assistant, which is for administrators only', async ({ page }) => {
    await catchWrites(page)
    await extend(page, '/api/config', (cfg) => ({ ...cfg, settings: { ...cfg.settings, setup: { done: false } } }))
    expect(await visit(page, '#/')).toEqual([])
    await expect(page).not.toHaveURL(/einrichtung/)
    await visit(page, '#/einrichtung')
    await expect(page.getByText('Das verwaltet der Administrator')).toBeVisible()
    await visit(page, '#/einstellungen/allgemein')
    await expect(page.locator('main')).not.toContainText('Einrichtungsassistent')
  })
})
