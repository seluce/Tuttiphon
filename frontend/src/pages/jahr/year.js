// Year recap: which year it is about, its heading and what the hours of the day say.
import { t, locale } from '../../lib/i18n.svelte.js'
import { S } from '../../lib/state.svelte.js'

/** The year a recap is about: in January the one just ended, otherwise the current one (so far). */
export const recapYear = (now = new Date()) => (now.getMonth() === 0 ? now.getFullYear() - 1 : now.getFullYear())

/** December and January: the year recap gets a card on the start page. */
export const recapSeason = (now = new Date()) => now.getMonth() === 11 || now.getMonth() === 0

/** Heading of a year: "Your 2026" (the own person), "Our 2026" (the family), otherwise "Anna · 2026".
 *  mine: the first person ("My 2026") – for the picture someone shares. */
export function yearTitle(person, year, mine = false) {
  if (person?.family) return t('Our {year}', { year })
  if (person && person.id === S.me?.own) return mine ? t('My {year}', { year }) : t('Your {year}', { year })
  return `${person?.name || ''} · ${year}`
}

/** Part of the day with the most plays (hours: plays per hour 0–23) – null without any. */
export function partOfDay(hours) {
  const parts = [['morning', [5, 6, 7, 8, 9]], ['midday', [10, 11, 12, 13]], ['afternoon', [14, 15, 16, 17]],
    ['evening', [18, 19, 20, 21]], ['night', [22, 23, 0, 1, 2, 3, 4]]]
  const sums = parts.map(([k, hs]) => [k, hs.reduce((n, h) => n + (hours?.[h] || 0), 0)])
  const best = sums.reduce((a, b) => (b[1] > a[1] ? b : a))
  return best[1] ? best[0] : null
}

export const partText = (part) => ({
  morning: t('Mostly in the morning'),
  midday: t('Mostly around noon'),
  afternoon: t('Mostly in the afternoon'),
  evening: t('Mostly in the evening'),
  night: t('Mostly at night'),
})[part] || ''

/** Name of a weekday, 0 = Monday (1 January 2024 was a Monday). */
export const weekdayName = (i) => new Date(2024, 0, 1 + i, 12).toLocaleDateString(locale(), { weekday: 'long' })

/** Index of the largest value (null if all are 0). */
export function busiestIndex(list) {
  let best = null
  ;(list || []).forEach((n, i) => { if (n > 0 && (best === null || n > list[best])) best = i })
  return best
}
