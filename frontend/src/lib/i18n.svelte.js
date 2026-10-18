// Languages of the interface. English is the source language: every text in the code is English and goes through t().
// Other languages are dictionaries English text → translation (locales/<lang>/*.js); a missing entry shows the English
// text. The language: the saved choice on this device, otherwise the browser language, otherwise English.
// It can change while the page runs (Settings → General): the language is reactive state, so every text a template
// shows through t() follows at once – no reload. Texts computed outside the template therefore have to follow too:
// in a component with $derived, at module level with translated() (rules: frontend/README.md, “Texts and languages”).
// A dictionary is loaded only for its language (own file; the first one by top-level await before anything renders).
const DICTS = { de: () => import('../locales/de/index.js') }
export const LANGUAGES = [
  { key: 'en', name: 'English' },
  { key: 'de', name: 'Deutsch' },
]
const STORE = 'tuttiphon-lang'

/** The saved choice on this device: 'auto' (follow the browser) or a language key. */
export function choice() {
  try {
    const v = localStorage.getItem(STORE)
    return v && (v === 'auto' || LANGUAGES.some((l) => l.key === v)) ? v : 'auto'
  } catch {
    return 'auto'
  }
}

/** 'auto' → the first browser language we have, otherwise English. */
function resolve(c) {
  if (c !== 'auto') return c
  const wanted = typeof navigator === 'undefined' ? [] : navigator.languages?.length ? navigator.languages : [navigator.language]
  for (const raw of wanted) {
    const code = String(raw || '').toLowerCase().split('-')[0]
    if (LANGUAGES.some((l) => l.key === code)) return code
  }
  return 'en'
}

// English follows the browser's region for numbers and dates (e.g. en-GB)
const localeOf = (l) => (l === 'de' ? 'de-DE'
  : typeof navigator !== 'undefined' && /^en-/i.test(navigator.language || '') ? navigator.language : 'en-US')
const dictOf = async (l) => (DICTS[l] ? (await DICTS[l]()).default : {})

const first = resolve(choice())
const firstDict = await dictOf(first)
// replaced as a whole on a change (raw: the dictionary itself is never proxied)
let cur = $state.raw({ lang: first, locale: localeOf(first), dict: firstDict })
if (typeof document !== 'undefined') document.documentElement.lang = first

/** Current language ('en' or 'de') – reactive. */
export const lang = () => cur.lang

/** Current locale for numbers and dates – reactive. */
export const locale = () => cur.locale

let latest = 0   // only the newest call may switch – an older one may still be loading its dictionary

/**
 * Save a new choice ('auto' or a language key) and switch to it right away. -> true if the language changed.
 * Throws if the dictionary cannot be loaded – the saved choice and the language then stay as they were.
 */
export async function setLanguage(value) {
  const call = ++latest
  const next = resolve(value)
  let dict = cur.dict
  if (next !== cur.lang) {
    try {
      dict = await dictOf(next)
    } catch (e) {
      if (call === latest) throw e
      return false   // a newer choice came in meanwhile – this one no longer counts
    }
  }
  if (call !== latest) return false
  try {
    localStorage.setItem(STORE, value)
  } catch { /* private mode: applies to this page only */ }
  if (next === cur.lang) return false
  cur = { lang: next, locale: localeOf(next), dict }
  document.documentElement.lang = next
  return true
}

const fill = (s, params) => (params ? s.replace(/\{(\w+)\}/g, (m, k) => (k in params ? params[k] : m)) : s)

/** Translate an English text; {name} placeholders are filled from params. */
export function t(text, params) {
  return fill(cur.dict[text] ?? text, params)
}

/** Singular or plural form by count (both English, each translated); {n} is the formatted count. */
export function tn(n, one, other, params) {
  return t(n === 1 ? one : other, { n: Number(n ?? 0).toLocaleString(cur.locale), ...params })   // i18n-ignore: checked where tn() is called
}

/**
 * A module-level object or array with texts, e.g. `export const LABEL = translated(() => ({ a: t('A') }))`.
 * Used exactly like the value itself (LABEL.a, LIST.map …); it is built again when the language changes, and
 * templates reading it follow the change.
 * Read-only: copy it with [...X] / {...X} before storing it in $state or passing it to structuredClone().
 */
export function translated(build) {
  let at = cur
  let value = build()
  const now = () => {
    if (at !== cur) {   // reading cur makes templates and $derived depend on the language
      at = cur
      value = build()
    }
    return value
  }
  return new Proxy(Array.isArray(value) ? [] : {}, {
    get: (_, key) => Reflect.get(now(), key),
    set: (_, key, v) => Reflect.set(now(), key, v),
    has: (_, key) => Reflect.has(now(), key),
    deleteProperty: (_, key) => Reflect.deleteProperty(now(), key),
    ownKeys: () => Reflect.ownKeys(now()),
    getOwnPropertyDescriptor: (_, key) => {
      const d = Reflect.getOwnPropertyDescriptor(now(), key)
      return d && key !== 'length' ? { ...d, configurable: true } : d
    },
  })
}
