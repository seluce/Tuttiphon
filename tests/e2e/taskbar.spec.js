// The bar of a running task at the bottom can be put away – with ✕ or swiped aside – until that run ends; the chip in
// the header stays. "Progress" shows how far the run is. A running night analysis is played in the browser
// (GET /api/task answered there).
import { test, expect } from '@playwright/test'
import { login, visit } from './helpers.js'

const RUNNING = { running: true, name: 'Klanganalyse (nachts)', steps: ['analyse'], step: 'analyse', results: {}, finishedAt: null, lines: [] }
let started = 1   // the run's start time – another one is another run
let extra = {}    // more of the status (progress) for one test

test.describe('Task bar', () => {
  test.beforeEach(async ({ context, page }) => {
    started = 1
    extra = {}
    await login(context, 'admin')
    await page.route((url) => url.pathname === '/api/task', (route) =>
      route.request().method() === 'GET' ? route.fulfill({ json: { ...RUNNING, ...extra, startedAt: started } }) : route.fallback())
  })
  test.afterEach(async ({ page }) => page.unrouteAll({ behavior: 'ignoreErrors' }))

  test('closing the bar of a running task', async ({ page }) => {
    expect(await visit(page, '#/einstellungen/allgemein')).toEqual([])
    const bar = page.locator('.applybar', { hasText: 'Klanganalyse (nachts)' })
    await expect(bar).toBeVisible()
    await bar.getByRole('button', { name: 'Schließen' }).click()
    await expect(bar).toHaveCount(0)
    await expect(page.locator('[data-task-chip]')).toBeVisible()   // the chip stays …
    await expect(page.locator('[data-task-chip]')).toBeFocused()   // … and takes the keyboard focus
    started = 2   // the next run (e.g. the daily refresh) – the app never saw a moment without a run
    await expect(bar).toBeVisible({ timeout: 15000 })
  })

  test('swiping it aside', async ({ page }) => {
    expect(await visit(page, '#/einstellungen/allgemein')).toEqual([])
    const bar = page.locator('.applybar', { hasText: 'Klanganalyse (nachts)' })
    await expect(bar).toBeVisible()
    const box = await bar.locator('span').first().boundingBox()
    await page.mouse.move(box.x + 5, box.y + box.height / 2)
    await page.mouse.down()
    await page.mouse.move(box.x + 80, box.y + box.height / 2, { steps: 4 })
    await page.mouse.move(box.x + 200, box.y + box.height / 2, { steps: 4 })
    await page.mouse.up()
    await expect(bar).toHaveCount(0)
  })

  test('progress at a glance', async ({ page }) => {
    extra = { pos: 0, durations: [null], elapsed: 600,
      progress: { part: 'audio', done: 1234, total: 5000, elapsed: 600, left: 1800, until: null } }
    expect(await visit(page, '#/einstellungen/allgemein')).toEqual([])
    const bar = page.locator('.applybar', { hasText: 'Klanganalyse · 24 %' })
    await expect(bar).toBeVisible()
    await bar.getByRole('button', { name: 'Fortschritt' }).click()
    const sheet = page.getByRole('dialog', { name: 'Klanganalyse (nachts)' })
    await expect(sheet).toContainText('Schritt 1 von 1')
    await expect(sheet).toContainText('1.234 von 5.000 Songs')
    await expect(sheet).toContainText('noch etwa 30 Min.')
  })
})
