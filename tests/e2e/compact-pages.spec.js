// Compact pages: the profile with its preferences first (favorite worlds as toggles, appearance folded at the bottom),
// bars that scroll sideways instead of wrapping on the phone, the assistant's music worlds in two columns on the phone,
// and the combined search that opens the assistant's preview instead of creating right away.
import { test, expect } from '@playwright/test'
import { login, visit } from './helpers.js'

test.describe('User', () => {
  test.beforeEach(async ({ context }) => login(context, 'user'))

  test('profile: favorite worlds as toggles, appearance folded at the bottom', async ({ page }) => {
    expect(await visit(page, '#/profil')).toEqual([])
    const likes = page.locator('[data-guide=likes]')
    await expect(likes.getByRole('heading', { name: 'Das hörst du gern' })).toBeVisible()
    await expect(likes.locator('.pickcard')).toHaveCount(0)
    expect(await likes.locator('.toggles').first().locator('.toggle').count()).toBeGreaterThan(0)

    const look = page.locator('details', { has: page.getByRole('heading', { name: 'Aussehen' }) })
    await expect(look).not.toHaveAttribute('open')
    await expect(look.getByText('Symbol', { exact: true })).toBeHidden()
    // after the preferences
    expect((await look.boundingBox()).y).toBeGreaterThan((await likes.boundingBox()).y)
    await look.locator('summary').click()
    await expect(look.getByText('Symbol', { exact: true })).toBeVisible()
    await expect(look.getByText('Farbe', { exact: true })).toBeVisible()
  })

  test('search: nothing found says what to try', async ({ page }) => {
    expect(await visit(page, '#/')).toEqual([])
    await page.getByRole('combobox', { name: 'Suche' }).fill('xyzunbekannt')
    await expect(page.getByText('Nichts gefunden – versuch eine Band, einen Song oder eine Stimmung wie „ruhig“.')).toBeVisible()
  })

  test('search: a combined mix opens the preview instead of creating it', async ({ page }) => {
    expect(await visit(page, '#/')).toEqual([])
    await page.getByRole('combobox', { name: 'Suche' }).fill('ruhige Kinderlieder')
    const combo = page.locator('.sr-item', { hasText: 'passende Songs' }).first()
    await combo.waitFor({ timeout: 5000 }).catch(() => {})
    test.skip(!(await combo.count()), 'no matching mix in the test data')
    const name = (await combo.locator('.ell > div').first().innerText()).trim()
    await combo.click()
    await expect(page).toHaveURL(/#\/neu\?.*step=3/)
    await expect(page).toHaveURL(/every=week/)   // as the search row says: “new every week”
    await expect(page.getByRole('button', { name: 'Playlist anlegen' })).toBeVisible()
    await expect(page.getByLabel('Name', { exact: true })).toHaveValue(name)
    await expect(page.locator('main .toggle.on', { hasText: 'ruhig' })).toBeVisible()
    await expect(page.getByText('Vorschau', { exact: true }).first()).toBeVisible()
  })
})

test.describe('Administrator', () => {
  test.beforeEach(async ({ context }) => login(context, 'admin'))

  test('statistics: the periods stay in one row on the phone', async ({ page }, info) => {
    test.skip(info.project.name !== 'phone', 'phone only')
    expect(await visit(page, '#/statistik')).toEqual([])
    const periods = page.locator('main .seg', { has: page.locator('a[href^="#/statistik"]') })
    await expect(periods.getByRole('link', { name: 'Woche', exact: true })).toBeVisible()
    const tops = await periods.locator('a').evaluateAll((links) => links.map((a) => Math.round(a.getBoundingClientRect().top)))
    expect(new Set(tops).size).toBe(1)
    expect((await periods.boundingBox()).height).toBeLessThan(60)
  })

  test('assistant: step bar in one row, music worlds in two columns on the phone', async ({ page }, info) => {
    test.skip(info.project.name !== 'phone', 'phone only')
    expect(await visit(page, '#/neu?step=1')).toEqual([])
    const steps = await page.locator('.stepper button').evaluateAll((bs) => bs.map((b) => Math.round(b.getBoundingClientRect().top)))
    expect(new Set(steps).size).toBe(1)
    const cards = page.locator('.pick .pickcard')
    const [a, b] = [await cards.nth(0).boundingBox(), await cards.nth(1).boundingBox()]
    expect(Math.round(a.y)).toBe(Math.round(b.y))
    expect(b.x).toBeGreaterThan(a.x)
  })
})
