// Help: “Show me” guides walk through the real interface, the (?) opens the explanation as a sheet,
// the search finds guides, topics and questions.
import { test, expect } from '@playwright/test'
import { login, visit } from './helpers.js'

const tip = (page) => page.getByRole('dialog').filter({ hasText: /\d+ \/ \d+/ })

test.describe('User', () => {
  test.beforeEach(async ({ context }) => login(context, 'user'))

  test('Show me walks through the assistant', async ({ page }) => {
    expect(await visit(page, '#/hilfe')).toEqual([])
    const card = page.locator('main .card', { has: page.getByRole('heading', { name: 'Eigene Playlist zusammenstellen' }) })
    await card.getByRole('button', { name: 'Zeig’s mir' }).click()
    await expect(page).toHaveURL(/#\/neu/)
    await expect(tip(page)).toContainText('1 / 3')
    await tip(page).getByRole('button', { name: 'Weiter' }).click()
    await expect(tip(page)).toContainText(/Für wen\?|Musik wählen/)   // with a family the user may choose for whom
    await tip(page).getByRole('button', { name: 'Weiter' }).click()
    await expect(tip(page)).toContainText('3 / 3')
    await tip(page).getByRole('button', { name: 'Zurück zur Hilfe' }).click()
    await expect(tip(page)).toHaveCount(0)
    await expect(page).toHaveURL(/#\/hilfe/)
  })

  test('Esc ends a guide', async ({ page }) => {
    await visit(page, '#/hilfe')
    await page.locator('main .card', { has: page.getByRole('heading', { name: 'Etwas nicht mehr hören' }) })
      .getByRole('button', { name: 'Zeig’s mir' }).click()
    await expect(tip(page)).toContainText('Mag nicht')
    await page.keyboard.press('Escape')
    await expect(tip(page)).toHaveCount(0)
  })

  test('the question mark opens the page explanation', async ({ page }) => {
    await visit(page, '#/playlists')
    await page.locator('h1').getByRole('link', { name: 'Hilfe' }).click()
    const sheet = page.locator('.sheet')
    await expect(sheet).toContainText('Deine Playlists')
    await expect(sheet.getByRole('button', { name: /Playlist ändern(?! oder)/ })).toBeVisible()
    await expect(page).toHaveURL(/#\/playlists/)
  })

  test('a guide started in the assistant starts it from scratch', async ({ page }) => {
    expect(await visit(page, '#/neu')).toEqual([])
    const cards = page.locator('.pick .pickcard')
    const choose = page.locator('.stepper button.on', { hasText: 'Für wen?' })   // with a family: who first
    if (await choose.count()) await cards.first().click()
    await cards.nth(1).click()   // a music world instead of “All”
    await expect(cards.first()).not.toHaveClass(/\bon\b/)
    await page.locator('h1').getByRole('link', { name: 'Hilfe' }).click()
    await page.locator('.sheet').getByRole('button', { name: /Eigene Playlist zusammenstellen/ }).click()
    await expect(tip(page)).toContainText('1 / 3')
    await expect(cards.first()).toHaveClass(/\bon\b/)   // from scratch: the first choice of the first step
  })

  test('child protection in the profile', async ({ page }) => {
    expect(await visit(page, '#/profil')).toEqual([])
    await expect(page.getByText('Songs mit derben Texten weglassen')).toBeVisible()
  })

  test('search in the help', async ({ page }) => {
    await visit(page, '#/hilfe')
    await page.getByLabel('Hilfe durchsuchen').fill('offline')
    await expect(page.getByRole('heading', { name: 'Mix fürs Handy' })).toBeVisible()
    await expect(page.getByRole('heading', { name: 'Musikwelt anlegen' })).toHaveCount(0)
    await page.getByLabel('Hilfe durchsuchen').fill('xyzunbekannt')
    await expect(page.getByText('Nichts gefunden')).toBeVisible()
  })
})

test.describe('Administrator', () => {
  test.beforeEach(async ({ context }) => login(context, 'admin'))

  test('guide switches between pages', async ({ page }) => {
    expect(await visit(page, '#/hilfe')).toEqual([])
    await page.locator('main .card', { has: page.getByRole('heading', { name: 'Familie einrichten' }) })
      .getByRole('button', { name: 'Zeig’s mir' }).click()
    await expect(page).toHaveURL(/#\/einstellungen\/navidrome/)
    await expect(tip(page)).toContainText('Konten & Passwörter')
    await tip(page).getByRole('button', { name: 'Weiter' }).click()
    await expect(page).toHaveURL(/#\/einstellungen\/benutzer/)
    await tip(page).getByRole('button', { name: 'Weiter' }).click()
    await expect(page).toHaveURL(/#\/personen/)
    await tip(page).getByRole('button', { name: 'Weiter' }).click()
    await expect(tip(page)).toContainText('Die Familie')   // with or without a family in the test data
    await expect(page).toHaveURL(/#\/personen/)
    await tip(page).getByRole('button', { name: 'Fertig' }).click()
    await expect(tip(page)).toHaveCount(0)
  })

  test('empty the trash – and undo', async ({ page }) => {
    await visit(page, '#/playlists')
    const fold = page.locator('details.fold', { hasText: 'Papierkorb ·' })
    await fold.locator('summary').click()
    await fold.getByRole('button', { name: 'Papierkorb leeren' }).click()
    await page.getByRole('dialog').getByRole('button', { name: 'Papierkorb leeren' }).click()
    await expect(page.getByText(/Playlists? endgültig gelöscht/)).toBeVisible()
    await expect(fold).toHaveCount(0)
    await page.getByRole('button', { name: 'Rückgängig' }).click()
    await expect(page.locator('details.fold', { hasText: 'Papierkorb ·' })).toHaveCount(1)
  })

  test('the question mark knows the history, the backup and the setup assistant', async ({ page }) => {
    for (const [hash, title] of [['#/verlauf', 'Die Startseite'], ['#/einstellungen/sicherung', 'Wiederherstellen'],
      ['#/einrichtung', 'Einrichtungsassistent']]) {
      await visit(page, hash)
      await page.locator('h1').getByRole('link', { name: 'Hilfe' }).click()
      await expect(page.locator('.sheet')).toContainText(title)
      await page.keyboard.press('Escape')
      await expect(page.locator('.sheet')).toHaveCount(0)   // closed before the next page opens its own
    }
  })

  test('“Jump right in” for notifications leads administrators to the settings', async ({ page }) => {
    await visit(page, '#/hilfe')
    await page.locator('main .card', { has: page.getByRole('heading', { name: 'Benachrichtigungen aufs Handy' }) })
      .getByRole('button', { name: 'Direkt loslegen' }).click()
    await expect(page).toHaveURL(/#\/einstellungen\/benachrichtigungen/)
  })

  test('jumping to a topic expands it', async ({ page }) => {
    await visit(page, '#/hilfe/mix')
    await expect(page.locator('#h-mix')).toHaveAttribute('open', '')
  })
})
