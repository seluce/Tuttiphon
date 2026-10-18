// Results of the AI sound analysis in the interface: keys in the page's language and the catalog of instruments and
// themes (GET /api/sound/catalog – labels in the page's language, songs per entry).
import { api } from './api.js'
import { t, lang, translated } from './i18n.svelte.js'

/** Key in Essentia's spelling (as GET /api/song sends it) → its name in the page's language */
const KEY_NAMES = translated(() => ({
  'C major': t('C major'), 'C minor': t('C minor'),
  'C# major': t('C♯ major'), 'C# minor': t('C♯ minor'),
  'D major': t('D major'), 'D minor': t('D minor'),
  'Eb major': t('E♭ major'), 'Eb minor': t('E♭ minor'),
  'E major': t('E major'), 'E minor': t('E minor'),
  'F major': t('F major'), 'F minor': t('F minor'),
  'F# major': t('F♯ major'), 'F# minor': t('F♯ minor'),
  'G major': t('G major'), 'G minor': t('G minor'),
  'Ab major': t('A♭ major'), 'Ab minor': t('A♭ minor'),
  'A major': t('A major'), 'A minor': t('A minor'),
  'Bb major': t('B♭ major'), 'Bb minor': t('B♭ minor'),
  'B major': t('B major'), 'B minor': t('B minor'),
}))
// other spellings of the same pitch (the server's Camelot table accepts them too)
const SAME_PITCH = { Db: 'C#', 'D#': 'Eb', Gb: 'F#', 'G#': 'Ab', 'A#': 'Bb' }

/** "A minor" → "A minor" / "a-Moll", "C# major" → "C♯ major" / "Cis-Dur"; unknown spellings stay as they are. */
export function keyName(key) {
  const [note = '', scale = ''] = String(key || '').split(' ')
  return KEY_NAMES[`${SAME_PITCH[note] || note} ${scale}`] ?? key
}

/* ------------------------------------------------------------------ sound catalog */
// GET /api/sound/catalog: instruments and themes of the AI – labels in the page's language, songs per entry.
// items: instruments [{id, label, songs}], themes: the same for the themes (null until loaded); at: language of the
// labels; available / themesAvailable: the AI has recognized instruments / themes at all
const catalog = $state({ items: null, themes: null, available: false, themesAvailable: false, at: null })
let pending = null

/** Load the catalog once per language (again after a switch); resolves to the catalog. */
export function loadCatalog() {
  const l = lang()
  if (catalog.items && catalog.at === l) return Promise.resolve(catalog)
  if (pending?.l === l) return pending.p
  const p = api('/api/sound/catalog').then((r) => {
    catalog.items = r.instruments || []
    catalog.themes = r.themes || []
    catalog.available = !!r.available
    catalog.themesAvailable = !!r.themesAvailable
    catalog.at = l
    return catalog
  }).finally(() => { if (pending?.p === p) pending = null })
  pending = { l, p }
  return p
}

/** The catalog (reactive): items (instruments), themes, available, themesAvailable */
export const soundCatalog = () => catalog

/** Label of an instrument id in the page's language – loads the catalog if needed, the id until it is there. */
export function instrumentLabel(id) {
  if (catalog.at !== lang()) loadCatalog().catch(() => {})
  return catalog.items?.find((x) => x.id === id)?.label ?? id
}

/** Label of a theme id in the page's language – like instrumentLabel(). */
export function themeLabel(id) {
  if (catalog.at !== lang()) loadCatalog().catch(() => {})
  return catalog.themes?.find((x) => x.id === id)?.label ?? id
}

/** Does a sound filter narrow the whole library enough for “All × Everything”? With instruments or themes of the AI
 *  (“calm piano music”, “film music” from the search) – the server allows it the same way (config.validate_config). */
export const narrowsLibrary = (snd) => !!(snd?.instruments?.length || snd?.themes?.length)
