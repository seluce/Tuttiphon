// Listening in: tapping a song row starts the mini player, “…” opens the song sheet with “More like this” and
// lyrics; on a phone the preview shows only 10 songs at first.
import { test, expect } from '@playwright/test'
import { login, visit } from './helpers.js'

test.describe('User', () => {
  test.beforeEach(async ({ context }) => login(context, 'user'))

  test('song row plays, song sheet opens', async ({ page }) => {
    expect(await visit(page, '#/playlist/kinder-rock')).toEqual([])
    const row = page.locator('.play-row').first()
    const title = (await row.locator('.tt').innerText()).trim()
    await row.click()
    const mini = page.getByRole('region', { name: 'Wiedergabe' })
    await expect(mini).toContainText(title)
    await row.getByRole('button', { name: `Mehr zu ${title}` }).click()
    const sheet = page.locator('.sheet')
    await expect(sheet.getByRole('button', { name: 'Mehr davon' })).toBeVisible()
    await expect(sheet).toContainText('Liedtext')
    await page.keyboard.press('Escape')
    await mini.getByRole('button', { name: 'Wiedergabe beenden' }).click()
    await expect(mini).toHaveCount(0)
  })

  test('on a phone only 10 songs at first', async ({ page }, info) => {
    test.skip(info.project.name !== 'phone', 'phone only')
    expect(await visit(page, '#/playlist/kinder-rock')).toEqual([])
    await expect(page.locator('.play-row:visible')).toHaveCount(10)
    await page.getByRole('button', { name: /^Alle \d+ zeigen$/ }).click()
    await expect(page.locator('.play-row:visible')).toHaveCount(await page.locator('.play-row').count())
  })
})

test.describe('As an app on the phone', () => {
  test.beforeEach(async ({ context }) => login(context, 'user'))

  test('hint from the second visit on, stays gone once dismissed', async ({ page }, info) => {
    test.skip(info.project.name !== 'phone', 'phone only')
    await page.addInitScript(() => {
      if (!sessionStorage.getItem('erster')) { localStorage.setItem('tuttiphon-visits', '1'); sessionStorage.setItem('erster', '1') }
    })
    expect(await visit(page, '#/')).toEqual([])
    const hint = page.getByRole('note').filter({ hasText: 'Tuttiphon als App' })
    await expect(hint).toBeVisible()
    await hint.getByRole('button', { name: 'Verstanden' }).click()
    await expect(hint).toHaveCount(0)
    await page.reload()
    await expect(page.locator('main')).not.toContainText('Tuttiphon startet')
    await expect(hint).toHaveCount(0)
  })

  test('no hint on the first visit', async ({ page }) => {
    expect(await visit(page, '#/')).toEqual([])
    await expect(page.getByRole('note').filter({ hasText: 'Tuttiphon als App' })).toHaveCount(0)
  })
})
