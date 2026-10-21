// Switching the interface language happens in place: no reload, the texts on the page and in the navigation follow,
// the choice is kept for the next visit.
import { test, expect } from '@playwright/test'
import { login, visit } from './helpers.js'

test.describe('Language', () => {
  test.beforeEach(async ({ context }) => login(context, 'admin'))

  test('switching the language changes the texts without reloading', async ({ page }) => {
    expect(await visit(page, '#/einstellungen/allgemein')).toEqual([])
    await expect(page.getByText('Aussehen', { exact: true })).toBeVisible()
    await page.evaluate(() => { window.stillTheSamePage = true })

    await page.getByRole('combobox', { name: 'Sprache', exact: true }).selectOption('en')
    await expect(page.getByText('Appearance', { exact: true })).toBeVisible()
    await expect(page.getByText('Aussehen', { exact: true })).toHaveCount(0)
    await expect(page.locator('nav').first()).toContainText('Settings')
    expect(await page.evaluate(() => window.stillTheSamePage)).toBe(true)
    expect(await page.evaluate(() => [document.documentElement.lang, localStorage.getItem('tuttiphon-lang')])).toEqual(['en', 'en'])

    await page.reload()
    await expect(page.getByText('Appearance', { exact: true })).toBeVisible()   // kept for the next visit

    await page.getByRole('combobox', { name: 'Language', exact: true }).selectOption('fr')   // one of the other languages
    await expect(page.getByText('Apparence', { exact: true })).toBeVisible()
    expect(await page.evaluate(() => document.documentElement.lang)).toBe('fr')

    await page.getByRole('combobox', { name: 'Langue', exact: true }).selectOption('de')
    await expect(page.getByText('Aussehen', { exact: true })).toBeVisible()
    await expect(page.locator('nav').first()).toContainText('Einstellungen')
  })
})
