// The bar of a running task at the bottom can be put away – with ✕ or swiped aside – until that run ends; the chip in
// the header stays. A running night analysis is played in the browser (GET /api/task answered there).
import { test, expect } from '@playwright/test'
import { login, visit } from './helpers.js'

const RUNNING = { running: true, name: 'Klanganalyse (nachts)', steps: ['analyse'], step: 'analyse', results: {}, finishedAt: null, lines: [] }

test.describe('Task bar', () => {
  test.beforeEach(async ({ context, page }) => {
    await login(context, 'admin')
    await page.route((url) => url.pathname === '/api/task', (route) =>
      route.request().method() === 'GET' ? route.fulfill({ json: RUNNING }) : route.fallback())
  })
  test.afterEach(async ({ page }) => page.unrouteAll({ behavior: 'ignoreErrors' }))

  test('closing the bar of a running task', async ({ page }) => {
    expect(await visit(page, '#/einstellungen/allgemein')).toEqual([])
    const bar = page.locator('.applybar', { hasText: 'Klanganalyse (nachts)' })
    await expect(bar).toBeVisible()
    await bar.getByRole('button', { name: 'Schließen' }).click()
    await expect(bar).toHaveCount(0)
    await expect(page.locator('header button .animate-spin, .topbar button .animate-spin').first()).toBeVisible()   // the chip stays
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
})
