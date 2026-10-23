// Every page opens without errors – as administrator and as user, on desktop and on phone.
import { test, expect } from '@playwright/test'
import { login, visit, state } from './helpers.js'

const SETTINGS = ['allgemein', 'konto', 'benutzer', 'start', 'navidrome', 'speicher', 'playlists', 'deezer', 'lyrics', 'opus', 'intel', 'ablaeufe', 'sicherung', 'bibliothek', 'benachrichtigungen']

// Placeholders <playlist>, <welt>, <person> are replaced in the test with IDs from the data copy
const adminRoutes = ['#/', '#/playlists', '#/playlist/<playlist>', '#/neu', '#/entdecken', '#/welten', '#/welt/<welt>', '#/richtungen',
  '#/personen', '#/person/<person>', '#/statistik', '#/statistik/jahr', '#/jahr', '#/verlauf', '#/hilfe', ...SETTINGS.map((t) => `#/einstellungen/${t}`)]
const fill = (route) => route.replace(/<(\w+)>/, (_, k) => state()[k])
const userRoutes = ['#/', '#/playlists', '#/neu', '#/entdecken', '#/welten', '#/statistik', '#/jahr', '#/profil', '#/hilfe',
  '#/einstellungen/allgemein', '#/einstellungen/konto']

test.describe('Administrator', () => {
  test.beforeEach(async ({ context }) => login(context, 'admin'))
  for (const route of adminRoutes) {
    test(route, async ({ page }) => {
      expect(await visit(page, fill(route)), route).toEqual([])
    })
  }
  test('the year story closes with Escape', async ({ page }) => {
    expect(await visit(page, '#/jahr')).toEqual([])
    await expect(page.getByRole('dialog')).toBeVisible()
    await page.keyboard.press('Escape')
    await expect(page).not.toHaveURL(/#\/jahr/)
  })
})

test.describe('User', () => {
  test.beforeEach(async ({ context }) => login(context, 'user'))
  for (const route of userRoutes) {
    test(route, async ({ page }) => {
      expect(await visit(page, route), route).toEqual([])
    })
  }
  test('admin pages show a notice instead of content', async ({ page }) => {
    await visit(page, '#/richtungen')
    await expect(page.getByText('Das verwaltet der Administrator')).toBeVisible()
  })
  test('settings show only General and My account', async ({ page }) => {
    await visit(page, '#/einstellungen/navidrome')
    await expect(page.locator('main')).not.toContainText('Benutzer & Rechte')
  })
})

test('sign-in page', async ({ page }) => {
  await page.goto('/login.html')
  await expect(page.getByRole('heading', { name: 'Tuttiphon' })).toBeVisible()
  await expect(page.getByRole('button', { name: 'Anmelden' })).toBeVisible()
  await page.getByRole('button', { name: 'Lokaler Administrator' }).click()
  await expect(page.getByText('Administrator-Passwort', { exact: true })).toBeVisible()
  await page.getByText('Passwort vergessen?').click()   // how to reset it, right on the sign-in page
  await expect(page.getByText('admin_password.json')).toBeVisible()
})

test('sign-in page of a new installation: only the local administrator', async ({ page }) => {
  // not connected to Navidrome yet (played in the browser – the test copy is connected)
  await page.route('**/api/login', (route) => route.request().method() === 'GET'
    ? route.fulfill({ json: { navidrome: false } }) : route.continue())
  await page.goto('/login.html')
  await expect(page.getByText('Noch nicht eingerichtet')).toBeVisible()
  await expect(page.getByText('Administrator-Passwort', { exact: true })).toBeVisible()
  await expect(page.getByLabel('Benutzername')).toHaveCount(0)
  await expect(page.getByRole('button', { name: 'Zurück zur normalen Anmeldung' })).toHaveCount(0)
  await expect(page.locator('#password')).toBeFocused()
})

test('without a session it goes to sign-in', async ({ page }) => {
  await page.goto('/')
  await expect(page).toHaveURL(/login\.html/)
})
