// Phone usability: band names in rankings readable, swipe away notices at the bottom, bring back hidden suggestions,
// settings as a list of sections with a page per section.
import { test, expect } from '@playwright/test'
import { login, visit } from './helpers.js'

test.describe('Administrator', () => {
  test.beforeEach(async ({ context }) => login(context, 'admin'))

  test('band names in the statistics are readable on a phone', async ({ page }, info) => {
    test.skip(info.project.name !== 'phone', 'phone only')
    expect(await visit(page, '#/statistik')).toEqual([])
    const name = page.locator('.arow .ell').first()
    await expect(name).toBeVisible()
    expect((await name.boundingBox()).width).toBeGreaterThan(150)
  })

  test('swipe a notice away, bring hidden items back', async ({ page }) => {
    expect(await visit(page, '#/entdecken')).toEqual([])
    const before = await page.getByRole('button', { name: 'Nicht interessiert' }).count()
    test.skip(!before, 'no suggestions in the test data')
    await page.getByRole('button', { name: 'Nicht interessiert' }).first().click()
    const toast = page.getByRole('status').filter({ hasText: 'Ausgeblendet' })
    await expect(toast).toBeVisible()
    const box = await toast.boundingBox()
    const y = box.y + box.height / 2
    await page.mouse.move(box.x + 20, y)
    await page.mouse.down()
    await page.mouse.move(box.x + 120, y, { steps: 5 })
    await page.mouse.move(box.x + 220, y, { steps: 5 })
    await page.mouse.up()
    await expect(toast).toHaveCount(0)
    await page.getByRole('button', { name: 'Jetzt wieder zeigen' }).click()
    await expect(page.getByRole('button', { name: 'Jetzt wieder zeigen' })).toHaveCount(0)
  })
})

test.describe('Discover and music worlds', () => {
  test.beforeEach(async ({ context }) => login(context, 'admin'))

  test('sections can be collapsed and stay that way', async ({ page }) => {
    expect(await visit(page, '#/entdecken')).toEqual([])
    // the last section – the swipe test next door briefly hides the first one
    const head = page.locator('main section h2 button[aria-expanded]').last()
    test.skip(!(await head.count()), 'no suggestions in the test data')
    const name = (await head.innerText()).trim()
    await head.click()
    await expect(head).toHaveAttribute('aria-expanded', 'false')
    await page.reload()
    const again = page.locator('main section h2 button', { hasText: name.split('\n')[0] })
    await again.waitFor({ timeout: 30000 })   // the server recomputes the suggestions after the reload
    await expect(again).toHaveAttribute('aria-expanded', 'false')
    await again.click()
    await expect(again).toHaveAttribute('aria-expanded', 'true')
  })

  test('rebuild shows beforehand what changes', async ({ page }) => {
    expect(await visit(page, '#/welt/deutsch')).toEqual([])
    const btn = page.getByRole('button', { name: 'Neu zusammenstellen' })
    test.skip(!(await btn.count()), 'world is already automatic in the test data')
    await btn.click()
    const dialog = page.getByRole('dialog')
    await expect(dialog).toContainText('Bands')
    await expect(dialog).toContainText('→')
    await dialog.getByRole('button', { name: 'Abbrechen' }).click()
    await expect(page.getByRole('button', { name: 'Neu zusammenstellen' })).toBeVisible()
  })
})

test.describe('Conversion', () => {
  test.beforeEach(async ({ context }) => login(context, 'admin'))

  test('target format AAC has its own quality levels, the section shows the format', async ({ page }, info) => {
    const phone = info.project.name === 'phone'
    // the list of sections shows the format – on the phone the list is a page of its own: there and back
    const listShows = async (text) => {
      if (phone) await page.locator('main a[href="#/einstellungen"]').click()
      await expect(page.locator('nav.set-nav')).toContainText(text)
      if (phone) await page.locator('nav.set-nav a[href="#/einstellungen/opus"]').click()
    }
    expect(await visit(page, '#/einstellungen/opus')).toEqual([])
    const target = page.getByRole('group').filter({ has: page.getByRole('button', { name: 'AAC', exact: true }) })
    await target.getByRole('button', { name: 'AAC', exact: true }).click()
    await expect(page.getByRole('button', { name: '224', exact: true })).toHaveAttribute('aria-pressed', 'true')
    await listShows('FLAC → AAC')
    await target.getByRole('button', { name: 'Opus', exact: true }).click()
    await expect(page.getByRole('button', { name: '160', exact: true })).toHaveAttribute('aria-pressed', 'true')
    await listShows('FLAC → Opus')
  })
})

test.describe('Settings', () => {
  test.beforeEach(async ({ context }) => login(context, 'admin'))

  test('sections in groups; on the phone a list, each section a page of its own', async ({ page }, info) => {
    expect(await visit(page, '#/einstellungen')).toEqual([])
    const nav = page.locator('nav.set-nav')
    for (const group of ['Konto', 'Familie', 'Verbindung', 'Musik', 'Betrieb']) await expect(nav.getByText(group, { exact: true })).toBeVisible()
    if (info.project.name !== 'phone') {
      await expect(nav.locator('a.on')).toContainText('Allgemein')   // computer: list and the first section
      return
    }
    await nav.locator('a[href="#/einstellungen/deezer"]').click()
    await expect(page).toHaveURL(/#\/einstellungen\/deezer/)
    await expect(page.getByRole('heading', { level: 1, name: 'Deezer-Sterne' })).toBeVisible()
    await expect(page.locator('nav.set-nav')).toHaveCount(0)
    await page.locator('main a[href="#/einstellungen"]').click()
    await expect(page.locator('nav.set-nav a[href="#/einstellungen/deezer"]')).toBeVisible()
  })
})

test.describe('Child protection list', () => {
  test.beforeEach(async ({ context }) => login(context, 'admin'))

  // Mocked list (the test data has no lyrics index): many bands, one with three songs
  const songs = [
    ...['Alpha', 'Beta', 'Gamma'].map((t, i) => ({ id: `e2e-k${i}`, title: t, artist: 'Testband Derb', album: 'Laut',
      artistId: null, allowed: false, words: [['mist', 2 - (i % 2)]] })),
    ...Array.from({ length: 40 }, (_, i) => ({ id: `e2e-x${i}`, title: `Lied ${i}`, artist: `Band ${String(i).padStart(2, '0')}`,
      album: 'Album', artistId: null, allowed: false, words: [['kacke', 1]] })),
  ]
  const fake = (page) => page.route('**/api/kinderschutz', (r) =>
    r.fulfill({ json: { index: { songs: 1000, running: false }, persons: ['Kinder'], songs } }))

  test('grouped by band, searchable, allow a whole band at once', async ({ page }) => {
    await fake(page)
    expect(await visit(page, '#/einstellungen/lyrics')).toEqual([])
    await expect(page.getByText('43 Songs von 41 Bands')).toBeVisible()
    // the band with the most songs is on top, collapsed; more bands only on request
    const head = page.getByRole('button', { name: /Testband Derb.*3 Songs/ })
    await expect(head).toHaveAttribute('aria-expanded', 'false')
    await expect(page.getByText('Weitere 26 Bands zeigen')).toBeVisible()
    await head.click()
    await expect(page.getByText('Gamma')).toBeVisible()
    await expect(page.getByText('„mist“ ×2').first()).toBeVisible()
    await head.click()
    // searching for a word finds only the matching songs
    await page.getByLabel('Derbe Songs durchsuchen').fill('mist')
    await expect(page.getByText('3 von 43 Songs · 1 Band')).toBeVisible()
    await expect(page.getByText('Gamma')).toBeVisible()
    await expect(page.getByText('Lied 3', { exact: true })).toHaveCount(0)
    await page.getByLabel('Derbe Songs durchsuchen').fill('')
    // allow all songs of the band – and undo
    const row = page.locator('main div.flex', { has: head })
    await row.getByRole('button', { name: 'alle erlauben' }).click()
    await expect(row.getByRole('button', { name: 'alle erlaubt' })).toBeVisible()
    await expect(page.getByText('3 erlaubt', { exact: false }).first()).toBeVisible()
    await page.getByRole('status').getByRole('button', { name: 'Rückgängig' }).click()
    await expect(row.getByRole('button', { name: 'alle erlauben' })).toBeVisible()
  })
})

test.describe('Notifications on the phone', () => {
  // Notifications are off in the test data – switch them on for display only (nothing is saved)
  const notifyOn = (page) => page.route('**/api/config', async (r) => {
    if (r.request().method() !== 'GET') return r.continue()
    const res = await r.fetch()
    const cfg = await res.json()
    cfg.settings.notify = { ...cfg.settings.notify, enabled: true }
    await r.fulfill({ response: res, json: cfg })
  })

  test('administrator: settings show “This device” and ntfy separately', async ({ page, context }) => {
    await login(context, 'admin')
    expect(await visit(page, '#/einstellungen/benachrichtigungen')).toEqual([])
    await expect(page.getByText('Dieses Gerät', { exact: true })).toBeVisible()
    await expect(page.getByRole('button', { name: 'Auf diesem Gerät einschalten' })).toBeVisible()
    await expect(page.getByRole('heading', { name: 'Über ntfy' })).toBeVisible()
  })

  test('user: switch on in the profile, ntfy only as an alternative', async ({ page, context }) => {
    await login(context, 'user')
    await notifyOn(page)
    expect(await visit(page, '#/profil')).toEqual([])
    await expect(page.getByRole('heading', { name: 'Aufs Handy' })).toBeVisible()
    await expect(page.getByRole('button', { name: 'Auf diesem Gerät einschalten' })).toBeVisible()
    await expect(page.getByText('Oder über die ntfy-App')).toBeVisible()
  })
})

test.describe('Back button and updates', () => {
  test.beforeEach(async ({ context }) => login(context, 'user'))

  test('the back button closes a sheet; going on from a sheet does not add a step', async ({ page }, info) => {
    test.skip(info.project.name !== 'phone', 'phone only (“More” sheet)')
    expect(await visit(page, '#/playlists')).toEqual([])
    const more = page.locator('.bottomnav').getByRole('button', { name: 'Mehr' })
    await more.click()
    await expect(page.getByRole('dialog')).toBeVisible()
    await page.goBack()
    await expect(page.getByRole('dialog')).toHaveCount(0)
    await expect(page).toHaveURL(/#\/playlists$/)
    await more.click()
    await page.getByRole('dialog').getByRole('link', { name: 'Hilfe & Anleitung' }).click()
    await expect(page).toHaveURL(/#\/hilfe$/)
    await page.goBack()
    await expect(page).toHaveURL(/#\/playlists$/)
  })

  test('an unknown address leads home without a step back into it', async ({ page }) => {
    expect(await visit(page, '#/playlists')).toEqual([])
    await page.evaluate(() => { location.hash = '#/gibt-es-nicht' })
    await expect(page).toHaveURL(/#\/$/)
    await page.goBack()
    await expect(page).toHaveURL(/#\/playlists$/)
  })

  test('a page whose file is gone (update in between) offers a reload', async ({ page }) => {
    // the file of the help page cannot be loaded – as after an update while the app was open
    await page.route(/\/assets\/Help-[^/]*\.js$/, (r) => r.fulfill({ status: 404, contentType: 'text/plain', body: '' }))
    await visit(page, '#/hilfe')
    await expect(page.getByText('Diese Seite konnte nicht geladen werden')).toBeVisible({ timeout: 15000 })
    await expect(page.getByRole('button', { name: 'Neu laden' })).toBeVisible()
  })
})
