// Browser tests (npm run test:e2e): the finished build (web/) against a test server with a COPY of the data
// (tests/e2e/setup.js → tools/testserver.sh). Run `npm run build` first. Chromium: /usr/bin/chromium or Playwright's own.
// locale de-DE on purpose: the tests check the German interface texts.
import { defineConfig, devices } from '@playwright/test'
import { existsSync } from 'node:fs'

const chromium = process.env.CHROME_PATH ?? (existsSync('/usr/bin/chromium') ? '/usr/bin/chromium' : undefined)

export default defineConfig({
  testDir: 'tests/e2e',
  globalSetup: './tests/e2e/setup.js',
  globalTeardown: './tests/e2e/teardown.js',
  workers: 4,
  retries: 0,
  forbidOnly: true,
  reporter: [['list']],
  timeout: 45_000,
  use: {
    baseURL: 'http://127.0.0.1:8790',
    locale: 'de-DE',
    timezoneId: 'Europe/Berlin',
    launchOptions: chromium ? { executablePath: chromium } : {},
    trace: 'retain-on-failure',
  },
  projects: [
    { name: 'desktop', use: { ...devices['Desktop Chrome'], viewport: { width: 1360, height: 900 } } },
    { name: 'phone', use: { ...devices['Pixel 7'] } },
  ],
})
