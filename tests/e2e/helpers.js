// Shared test helpers: open a page signed in as admin or user and collect errors.
import { readFileSync } from 'node:fs'
import { expect } from '@playwright/test'
import { STATE } from './setup.js'

export const state = () => JSON.parse(readFileSync(STATE, 'utf8'))

/** Sign in as a role; the tour and the welcome assistant count as already seen. */
export async function login(context, role) {
  await context.addCookies([{ name: 'nt', value: state()[role], url: 'http://127.0.0.1:8790' }])
  await context.addInitScript((u) => {
    localStorage.setItem(`nt-tour:${u}`, '1')
    localStorage.setItem(`nt-welcome:${u}`, '1')
  }, state()[`${role}Account`] || '')
}

/** Open a page, wait until it has settled, and make sure there were no JavaScript or console errors. */
export async function visit(page, hash) {
  const errors = []
  page.on('pageerror', (e) => errors.push(e.message))
  page.on('console', (m) => { if (m.type() === 'error' && !/service ?worker|sw\.js|Failed to load resource/i.test(m.text())) errors.push(m.text()) })
  await page.goto('/' + hash)
  await expect(page.locator('main')).not.toContainText('Tuttiphon startet')
  await page.waitForLoadState('networkidle')
  await expect(page.locator('main')).not.toBeEmpty()
  return errors
}
