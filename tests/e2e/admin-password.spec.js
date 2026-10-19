// Password of the local administrator: the setup form of the first start on the sign-in page and changing it under
// Settings → Users & permissions. The test copy has a password from its .env, so a first start and a password set in
// the browser are played in the browser (page.route) – POST /api/setup and /api/admin-password are answered there,
// nothing is written.
import { test, expect } from '@playwright/test'
import { login, visit } from './helpers.js'

test('first start: setup code and a new password', async ({ page }) => {
  await page.route('**/api/login', (route) => route.request().method() === 'GET'
    ? route.fulfill({ json: { setup: true, navidrome: false } }) : route.fallback())
  const sent = []
  await page.route('**/api/setup', (route) => {
    sent.push(route.request().postDataJSON())
    return sent.length === 1
      ? route.fulfill({ status: 401, json: { error: 'Der Einrichtungscode stimmt nicht.' } })
      : route.fulfill({ status: 200, json: { ok: true, user: '@notfall' } })
  })
  await page.goto('/login.html')
  await expect(page.getByText('Willkommen! Lege zuerst das Passwort')).toBeVisible()
  await expect(page.locator('#code')).toBeFocused()
  await expect(page.getByLabel('Benutzername')).toHaveCount(0)
  await expect(page.getByRole('button', { name: 'Lokaler Administrator' })).toHaveCount(0)

  await page.locator('#code').fill('abcd-efgh')
  await page.locator('#password').fill('ein-gutes-passwort')
  await page.locator('#password2').fill('ein-anderes-passwort')
  await page.getByRole('button', { name: 'Passwort festlegen und anmelden' }).click()
  await expect(page.getByRole('alert')).toContainText('stimmen nicht überein')
  expect(sent).toHaveLength(0)   // checked in the browser first

  await page.locator('#password2').fill('ein-gutes-passwort')
  await page.getByRole('button', { name: 'Passwort festlegen und anmelden' }).click()
  await expect(page.getByRole('alert')).toContainText('Einrichtungscode stimmt nicht')
  expect(sent[0]).toEqual({ code: 'abcd-efgh', password: 'ein-gutes-passwort' })

  await page.getByRole('button', { name: 'Passwort festlegen und anmelden' }).click()
  await expect.poll(() => sent.length).toBe(2)   // signed in – the page goes on to the app
})

test.describe('Administrator', () => {
  test.beforeEach(async ({ context }) => { await login(context, 'admin') })
  // the status is fetched again after saving – a request still under way when the test ends is no error
  test.afterEach(async ({ page }) => { await page.unrouteAll({ behavior: 'ignoreErrors' }) })

  test('the password from docker-compose can only be changed there', async ({ page }) => {
    await page.route((url) => url.pathname === '/api/status', async (route) => {
      const res = await route.fetch()
      const st = await res.json()
      return route.fulfill({ response: res, json: { ...st, env: { ...st.env, adminPassword: 'env' } } })
    })
    expect(await visit(page, '#/einstellungen/benutzer')).toEqual([])
    await expect(page.getByText('steht in docker-compose.yaml als TUTTIPHON_ADMIN_PASSWORD')).toBeVisible()
    await expect(page.getByRole('button', { name: 'Passwort ändern' })).toHaveCount(0)
  })

  test('a password set in the browser is changed with the current one', async ({ page }) => {
    await page.route((url) => url.pathname === '/api/status', async (route) => {
      const res = await route.fetch()
      const st = await res.json()
      return route.fulfill({ response: res, json: { ...st, env: { ...st.env, adminPassword: 'stored' } } })
    })
    const sent = []
    await page.route('**/api/admin-password', (route) => {
      sent.push(route.request().postDataJSON())
      return sent.length === 1
        ? route.fulfill({ status: 400, json: { error: 'Das bisherige Passwort stimmt nicht.' } })
        : route.fulfill({ json: { ok: true } })
    })
    expect(await visit(page, '#/einstellungen/benutzer')).toEqual([])
    const card = page.locator('.card', { hasText: 'Lokaler Administrator' })
    await card.getByLabel('Bisheriges Passwort').fill('falsch-falsch')
    await card.getByLabel('Neues Passwort').fill('ein-neues-passwort')
    await card.getByLabel('Passwort wiederholen').fill('ein-neues-passwort')
    await card.getByRole('button', { name: 'Passwort ändern' }).click()
    await expect(card.getByRole('status')).toContainText('bisherige Passwort stimmt nicht')
    await expect(page).toHaveURL(/einstellungen\/benutzer/)   // a wrong one does not lead to the sign-in
    await card.getByLabel('Bisheriges Passwort').fill('richtig-richtig')
    await card.getByRole('button', { name: 'Passwort ändern' }).click()
    await expect(page.getByText('Passwort geändert ✓')).toBeVisible()
    expect(sent[1]).toEqual({ current: 'richtig-richtig', password: 'ein-neues-passwort' })
  })
})
