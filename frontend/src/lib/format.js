// Small helpers for numbers, texts and times – without state.
import { lang, locale, t, tword } from './i18n.svelte.js'

export const fmt = (n) => (n == null ? '–' : Number(n).toLocaleString(locale()))
export const stars = (n) => (n ? '★'.repeat(Math.round(n)) : '')
export const slug = (s) => s.toLowerCase().normalize('NFKD').replace(/[^\w]+/g, '-').replace(/^-|-$/g, '') || 'x'
export const uid = (base) => `${slug(base).slice(0, 40)}-${Math.random().toString(36).slice(2, 6)}`
/** Deep copy – also of $state objects (JSON removes the proxies). */
export const clone = (x) => JSON.parse(JSON.stringify(x))
export const today = () => new Date().toISOString().slice(0, 10)
export const debounce = (fn, ms) => { let timer; return (...a) => { clearTimeout(timer); timer = setTimeout(() => fn(...a), ms) } }
export const mmss = (s) => (s ? `${Math.floor(s / 60)}:${String(Math.round(s % 60)).padStart(2, '0')}` : '')
/** First letter in upper case ("piano" → "Piano") – for labels the server sends in lower case */
export const capitalize = (s) => (s ? s.charAt(0).toLocaleUpperCase(locale()) + s.slice(1) : s)
/** "3 songs" – both forms in English, each translated (plural(n, 'song', 'songs')). */
export const plural = (n, one, many) => `${fmt(n)} ${tword(n, one, many)}`   // i18n-ignore: checked where it is called

export function relTime(iso) {
  if (!iso) return '–'
  const min = Math.round((Date.now() - new Date(iso).getTime()) / 60000)
  if (min < 1) return t('just now')
  if (min < 60) return t('{n} min ago', { n: min })
  if (min < 48 * 60) return t('{n} h ago', { n: Math.round(min / 60) })
  return t('{n} days ago', { n: Math.round(min / 1440) })
}

export function greeting() {
  const hr = new Date().getHours()
  return hr < 5 ? t('Good night') : hr < 11 ? t('Good morning') : hr < 17 ? t('Hello') : hr < 22 ? t('Good evening') : t('Good night')
}

/** Fairly stable number from a text – for color gradients and person colors. */
export function hash(s) {
  let x = 0
  for (const c of String(s)) x = (x * 31 + c.charCodeAt(0)) | 0
  return Math.abs(x)
}

/** Color gradient for placeholder avatars (same name → same color). */
export function gradFor(name) {
  const a = hash(name) % 360, b = (a + 50) % 360
  return `linear-gradient(135deg, hsl(${a} 65% 52%), hsl(${b} 70% 42%))`
}

export const initials = (name) => (name || '?').replace(/[^\p{L}\p{N} ]/gu, '').split(/\s+/).filter(Boolean).slice(0, 2).map((w) => w[0]).join('').toUpperCase() || '♪'

/** A point in time the server wrote as "16.10.2026 03:12" (or "16.10.2026"): German as it is, other languages in
 *  their own format. */
export function serverDate(s) {
  if (!s || lang() === 'de') return s
  const m = /^(\d{1,2})\.(\d{1,2})\.(\d{4})(?:,?\s+(\d{1,2}):(\d{2}))?$/.exec(String(s).trim())
  if (!m) return s
  const d = new Date(+m[3], +m[2] - 1, +m[1], +(m[4] || 0), +(m[5] || 0))
  return m[4] ? d.toLocaleString(locale(), { dateStyle: 'medium', timeStyle: 'short' }) : d.toLocaleDateString(locale(), { dateStyle: 'medium' })
}
