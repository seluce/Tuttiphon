// Home pages, playlist page and Discover: no action twice, the "…" menu of a playlist, the person filter on
// Discover, ✕ in the corner of a suggestion, state dots only where they say something.
import { readFileSync } from 'node:fs'
import { join } from 'node:path'
import { test, expect } from '@playwright/test'
import { login, visit, state } from './helpers.js'

const config = () => JSON.parse(readFileSync(join(state().work, 'data', 'config.json'), 'utf8'))

test.describe('Administrator', () => {
  test.beforeEach(async ({ context }) => login(context, 'admin'))

  test('playlist page: “Edit” as a button, the other actions in the “…” menu', async ({ page }) => {
    expect(await visit(page, `#/playlist/${state().playlist}`)).toEqual([])
    const actions = page.locator('[data-guide=pl-actions]')
    await expect(actions.getByRole('button', { name: 'Bearbeiten' })).toBeVisible()
    await expect(actions.getByRole('button', { name: 'Pausieren' })).toHaveCount(0)
    await actions.getByRole('button', { name: 'Mehr', exact: true }).click()
    const sheet = page.getByRole('dialog')
    await expect(sheet.getByRole('button', { name: 'Pausieren' })).toBeVisible()
    // a mix is kept, a smart playlist is saved as a fixed playlist – the same function
    await expect(sheet.getByRole('button', { name: /^(Mischung behalten|Als feste Playlist speichern)$/ })).toBeVisible()
    await expect(sheet.getByRole('button', { name: 'In den Papierkorb' })).toBeVisible()
    await page.keyboard.press('Escape')
    await expect(sheet).toHaveCount(0)
  })

  test('Discover: person filter starts with the family (without one: the first person), ✕ in the corner of the card', async ({ page }) => {
    expect(await visit(page, '#/entdecken')).toEqual([])
    const seg = page.locator('main .seg')
    test.skip(!(await seg.count()), 'no suggestions or only one person in the test data')
    const cfg = config()
    // the local administrator has no person of their own: the family first – the test data may have none
    const first = cfg.personen.find((p) => p.family) ?? cfg.personen[0]
    await expect(seg.getByRole('button', { name: first.name, exact: true })).toHaveClass(/\bon\b/)
    const before = await page.locator('main section h2 button[aria-expanded]').count()
    await seg.getByRole('button', { name: 'Alle', exact: true }).click()
    expect(await page.locator('main section h2 button[aria-expanded]').count()).toBeGreaterThanOrEqual(before)
    const card = page.locator('.scard', { has: page.getByRole('button', { name: 'Anlegen' }) }).first()
    test.skip(!(await card.count()), 'no playlist suggestion in the test data')
    const x = await card.getByRole('button', { name: 'Nicht interessiert' }).boundingBox()
    const create = await card.getByRole('button', { name: 'Anlegen' }).boundingBox()
    expect(x.y + x.height).toBeLessThanOrEqual(create.y)   // above the buttons, not in an extra row below them
  })

  test('home page: Deezer card without a second “rate” button and without the switch for stars given by hand', async ({ page }) => {
    expect(await visit(page, '#/')).toEqual([])
    const card = page.locator('.card', { has: page.getByRole('heading', { name: 'Deezer-Bewertung' }) })
    test.skip(!(await card.count()), 'the cards are switched off on the home page')
    await expect(card.getByText('auch von Hand vergebene Sterne überschreiben')).toHaveCount(0)
    if (await page.locator('.todo').getByRole('button', { name: 'Jetzt bewerten' }).count()) {
      await expect(card.getByRole('button', { name: 'Neue bewerten' })).toHaveCount(0)
    }
  })

  test('“To review”: a new band opens its window', async ({ page }) => {
    expect(await visit(page, '#/')).toEqual([])
    const assign = { name: /^Musikwelt zuordnen/ }
    const item = page.locator('.todo-item', { has: page.getByRole('button', assign) }).first()
    test.skip(!(await item.count()), 'no new band in the test data')
    const band = (await item.locator('b').first().innerText()).replace(/^Neu: /, '').trim()
    await item.getByRole('button', assign).click()
    const sheet = page.getByRole('dialog')
    await expect(sheet.getByRole('heading', { name: band }).first()).toBeVisible()
    await page.keyboard.press('Escape')
    await expect(sheet).toHaveCount(0)
  })

  test('state dots only for playlists that are not up to date in Navidrome', async ({ page }) => {
    expect(await visit(page, '#/playlists')).toEqual([])
    for (const dot of await page.locator('.pcard .dot-state').all()) {
      expect(await dot.getAttribute('title')).not.toBe('in Navidrome')
    }
  })
})

test.describe('User', () => {
  test.beforeEach(async ({ context }) => login(context, 'user'))

  test('no state dots on the playlist cards', async ({ page }) => {
    expect(await visit(page, '#/playlists')).toEqual([])
    await expect(page.locator('.pcard').first()).toBeVisible()
    await expect(page.locator('.dot-state')).toHaveCount(0)
  })

  test('For you: “Let’s go” repeats neither the buttons of the greeting nor the suggestion cards', async ({ page }) => {
    expect(await visit(page, '#/')).toEqual([])
    const go = page.locator('section', { has: page.getByRole('heading', { name: 'Los geht’s' }) })
    test.skip(!(await go.count()), 'the test account already has playlists')
    await expect(go.getByRole('link')).toHaveCount(0)
    const cards = page.locator('section', { has: page.getByRole('heading', { name: 'Für dich entdeckt' }) }).locator('.scard .t')
    await expect(cards.first()).toBeVisible()
    const shown = (await cards.allInnerTexts()).map((x) => x.trim())
    for (const chip of await go.getByRole('button').allInnerTexts()) expect(shown).not.toContain(chip.trim())
  })
})
