// What the AI sound analysis adds to the interface: key, tempo source, instruments and themes in the song window, bands
// that sound alike in the band window, instruments and themes in the search, the assistant and the sound editor, smooth
// transitions, audio fingerprints and “Same recording twice”. The test copy usually has no AI results (no Essentia on a PC), so
// the answers of the server are extended in the browser (page.route) – nothing is written.
import { test, expect } from '@playwright/test'
import { login, visit } from './helpers.js'

/** Extend the JSON answer of an endpoint (exact path, any query) with change(data). */
async function extend(page, path, change) {
  await page.route((url) => url.pathname === path, async (route) => {
    const res = await route.fetch()
    return route.fulfill({ response: res, json: change(await res.json()) })
  })
}
/** Answer an endpoint (exact path) in the browser with json() – the server is not asked. */
const answer = (page, path, json) => page.route((url) => url.pathname === path, (route) => route.fulfill({ json: json() }))
// answers still on their way when a test ends (e.g. the sound catalog) are dropped
test.afterEach(async ({ page }) => page.unrouteAll({ behavior: 'ignoreErrors' }))
const CATALOG = { available: true, instruments: [
  { id: 'piano', label: 'Klavier', songs: 120 }, { id: 'strings', label: 'Streicher', songs: 80 },
  { id: 'harp', label: 'Harfe', songs: 0 }],
themesAvailable: true, themes: [
  { id: 'film', label: 'Filmmusik', songs: 40 }, { id: 'epic', label: 'episch', songs: 25 },
  { id: 'space', label: 'Weltraum', songs: 0 }] }

test.describe('User', () => {
  test.beforeEach(async ({ context }) => login(context, 'user'))

  test('song window: key with Camelot code, tempo source, instruments, themes', async ({ page }) => {
    await extend(page, '/api/song', (d) => ({ ...d, bpm: 96, bpmSource: 'ai', key: 'A minor', camelot: '8A', keyStrength: 0.8,
      instruments: [{ id: 'piano', label: 'Klavier', strength: 0.6 }, { id: 'strings', label: 'Streicher', strength: 0.3 }],
      themes: [{ id: 'epic', label: 'episch', strength: 0.3 }] }))
    expect(await visit(page, '#/playlist/kinder-rock')).toEqual([])
    const row = page.locator('.play-row').first()
    const title = (await row.locator('.tt').innerText()).trim()
    await row.getByRole('button', { name: `Mehr zu ${title}` }).click()
    const sheet = page.locator('.sheet')
    await expect(sheet.getByText('a-Moll · 8A')).toBeVisible()
    await expect(sheet.getByText('96 BPM · KI')).toBeVisible()
    await expect(sheet.getByText('Instrumente:')).toBeVisible()
    await expect(sheet.getByText('Streicher')).toBeVisible()
    await expect(sheet.getByText('Themen:')).toBeVisible()
    await expect(sheet.getByText('episch', { exact: true })).toBeVisible()
  })

  test('song window: a weak key counts as uncertain, nothing without the AI', async ({ page }) => {
    let weak = true
    await extend(page, '/api/song', (d) => (weak
      ? { ...d, bpm: 120, bpmSource: 'measured', key: 'F# major', camelot: '2B', keyStrength: 0.3 }
      : { ...d, key: undefined, camelot: undefined, instruments: undefined, bpmSource: undefined }))
    expect(await visit(page, '#/playlist/kinder-rock')).toEqual([])
    const row = page.locator('.play-row').first()
    const title = (await row.locator('.tt').innerText()).trim()
    await row.getByRole('button', { name: `Mehr zu ${title}` }).click()
    const sheet = page.locator('.sheet')
    await expect(sheet.getByText('Fis-Dur · 2B · unsicher')).toBeVisible()
    await expect(sheet.getByText('120 BPM · gemessen')).toBeVisible()
    await page.keyboard.press('Escape')
    weak = false
    await row.getByRole('button', { name: `Mehr zu ${title}` }).click()
    await expect(sheet.locator('.lbl', { hasText: 'Liedtext' })).toBeVisible()   // the answer is there
    await expect(sheet.getByText('Instrumente:')).toHaveCount(0)
    await expect(sheet.getByText('Themen:')).toHaveCount(0)
    await expect(sheet.getByText(/-(Dur|Moll) · \d+[AB]/)).toHaveCount(0)
  })

  test('band window: bands that sound alike, without repeating the similar bands', async ({ page }) => {
    let similar = []
    await extend(page, '/api/artist', (d) => {
      similar = d.similar.map((s) => s.name)
      return { ...d, soundsLike: [{ name: 'Klangtest-Band', id: null, score: 0.7 }, ...d.similar.slice(0, 1).map((s) => ({ ...s, score: 0.6 }))] }
    })
    expect(await visit(page, '#/playlist/kinder-rock')).toEqual([])
    const row = page.locator('.play-row').first()
    const title = (await row.locator('.tt').innerText()).trim()
    await row.getByRole('button', { name: `Mehr zu ${title}` }).click()
    await page.locator('.sheet button.link').first().click()   // the band of the song
    const field = page.locator('.sheet .field', { has: page.locator('.lbl', { hasText: 'Klingt wie diese Bands' }) })
    await expect(field).toContainText('Klangtest-Band')
    if (similar.length) await expect(page.locator('.sheet .acard', { hasText: similar[0] })).toHaveCount(1)
  })
})

test.describe('Administrator', () => {
  test.beforeEach(async ({ context }) => login(context, 'admin'))

  test('search: an instrument opens the assistant with it as the own sound filter', async ({ page }) => {
    await extend(page, '/api/search', (d) => ({ ...d, instruments: [{ id: 'piano', label: 'Klavier', ids: ['piano'], count: 120 }] }))
    await answer(page, '/api/sound/catalog', () => CATALOG)
    expect(await visit(page, '#/')).toEqual([])
    await page.getByRole('combobox', { name: 'Suche' }).fill('Klavier')
    const item = page.locator('.sr-item', { hasText: '120 Songs · als Mix anlegen' })
    await expect(page.locator('.sr-group', { hasText: 'Instrumente' })).toBeVisible()
    await item.dispatchEvent('mousedown')
    await expect(page).toHaveURL(/instr=piano/)
    await expect(page.locator('.toggle', { hasText: 'Klavier' })).toHaveAttribute('aria-pressed', 'true')
    await expect(page.getByRole('button', { name: 'Playlist anlegen' })).toBeEnabled()   // “All × Everything” with an instrument
  })

  test('search: a theme opens the assistant with it as the own sound filter', async ({ page }) => {
    await extend(page, '/api/search', (d) => ({ ...d, themes: [{ id: 'film', label: 'Filmmusik', ids: ['film'], count: 40 }] }))
    await answer(page, '/api/sound/catalog', () => CATALOG)
    expect(await visit(page, '#/')).toEqual([])
    await page.getByRole('combobox', { name: 'Suche' }).fill('Filmmusik')
    await expect(page.locator('.sr-group', { hasText: 'Themen' })).toBeVisible()
    await page.locator('.sr-item', { hasText: '40 Songs · als Mix anlegen' }).dispatchEvent('mousedown')
    await expect(page).toHaveURL(/theme=film/)
    const field = page.locator('.field', { has: page.locator('.lbl', { hasText: 'Themen – eines davon reicht' }) })
    await expect(field.locator('.toggle', { hasText: 'Filmmusik' })).toHaveAttribute('aria-pressed', 'true')
    await expect(page.getByRole('button', { name: 'Playlist anlegen' })).toBeEnabled()   // “All × Everything” with a theme
  })

  test('search: a vibe that stands for a theme opens the assistant with the vibe', async ({ page }) => {
    await extend(page, '/api/search', (d) => ({ ...d, themes: [{ id: 'christmas', label: 'Weihnachten', ids: ['christmas'],
      count: 80, stil: 'weihnachten', stilName: 'Weihnachten' }] }))
    expect(await visit(page, '#/')).toEqual([])
    await page.getByRole('combobox', { name: 'Suche' }).fill('Weihnachten')
    await page.locator('.sr-item', { hasText: '80 Songs · als Mix anlegen' }).dispatchEvent('mousedown')
    await expect(page).toHaveURL(/stil=weihnachten/)
    await expect(page).not.toHaveURL(/theme=/)
  })

  test('assistant: unknown instruments and themes from the address are dropped', async ({ page }) => {
    await answer(page, '/api/sound/catalog', () => CATALOG)
    expect(await visit(page, '#/neu?type=mix&step=3&instr=xylophonx')).toEqual([])
    await expect(page.getByRole('button', { name: 'Playlist anlegen' })).toBeDisabled()
    expect(await visit(page, '#/neu?type=mix&step=3&theme=kinderx')).toEqual([])
    await expect(page.getByRole('button', { name: 'Playlist anlegen' })).toBeDisabled()
  })

  test('sound editor: instruments and themes by frequency, hidden without AI results', async ({ page }) => {
    let available = true
    await answer(page, '/api/sound/catalog', () => (available ? CATALOG
      : { available: false, instruments: CATALOG.instruments.map((x) => ({ ...x, songs: 0 })),
        themesAvailable: false, themes: CATALOG.themes.map((x) => ({ ...x, songs: 0 })) }))
    expect(await visit(page, '#/richtungen')).toEqual([])
    const card = page.locator('.scard', { hasText: 'nach Klang' }).first()
    test.skip(!(await card.count()), 'no sound vibe in the test data')
    await card.click()
    const sheet = page.locator('.sheet')
    const field = sheet.locator('.field', { has: page.locator('.lbl', { hasText: 'Instrumente – eines davon reicht' }) })
    await expect(field.locator('.toggle')).toHaveText(['Klavier120', 'Streicher80'])   // without songs: not offered
    const themes = sheet.locator('.field', { has: page.locator('.lbl', { hasText: 'Themen – eines davon reicht' }) })
    await expect(themes.locator('.toggle')).toHaveText(['Filmmusik40', 'episch25'])
    await page.keyboard.press('Escape')
    available = false
    await page.reload()
    await expect(page.locator('main')).not.toContainText('Tuttiphon startet')
    await page.locator('.scard', { hasText: 'nach Klang' }).first().click()
    await expect(sheet.locator('.lbl', { hasText: 'Stimmung – eine davon reicht' })).toBeVisible()
    await expect(sheet.locator('.lbl', { hasText: 'Instrumente' })).toHaveCount(0)
    await expect(sheet.locator('.lbl', { hasText: 'Themen' })).toHaveCount(0)
  })

  test('settings: smooth transitions and audio fingerprints', async ({ page }) => {
    expect(await visit(page, '#/einstellungen/playlists')).toEqual([])
    await expect(page.locator('.set-row', { hasText: 'Sanfte Übergänge in Mixen' }).locator('input[type=checkbox]')).toBeChecked()
    expect(await visit(page, '#/einstellungen/intel')).toEqual([])
    const card = page.locator('.card', { has: page.locator('h2', { hasText: 'Dieselbe Aufnahme doppelt' }) })
    await expect(card.locator('.set-row', { hasText: 'Audio-Fingerabdrücke erstellen' }).locator('input[type=checkbox]')).toBeChecked()
  })

  test('check library: the same recording twice with its copies', async ({ page }) => {
    const copy = (id, format, path) => ({ id, title: 'Lied', artist: 'Band', album: 'Album', albumId: null, format, bitRate: 900, duration: 200, path })
    await extend(page, '/api/pflege', (d) => ({ ...d, checks: [...d.checks.filter((c) => c.id !== 'aufnahme'), { id: 'aufnahme', title: 'Dieselbe Aufnahme doppelt',
      text: 'Derselbe Klang als mehrere Dateien.', count: 1, level: 'info', progress: { done: 3, total: 4 },
      items: [{ artist: 'Band', artistId: null, album: 'Album', albumId: null, title: 'Lied', detail: 'FLAC und OPUS · 2×',
        similarity: 0.95, copies: [copy('x1', 'FLAC', 'Band/Album/01 Lied.flac'), copy('x2', 'OPUS', 'Band/Album/01 Lied.opus')] }] }] }))
    expect(await visit(page, '#/einstellungen/bibliothek')).toEqual([])
    const check = page.locator('details.fold', { has: page.locator('summary', { hasText: 'Dieselbe Aufnahme doppelt' }) })
    await expect(check.locator('summary')).toContainText('Bisher 3 von 4 Songs verglichen')
    await check.locator('summary').click()
    await expect(check).toContainText('Band/Album/01 Lied.opus')
    await expect(check).toContainText('FLAC · 900 kbit/s · 3:20 · Album')
    await expect(check).toContainText('Die überzähligen Kopien entfernst du selbst')
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth)).toBe(true)
  })
})
