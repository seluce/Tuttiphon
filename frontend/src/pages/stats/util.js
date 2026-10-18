// Helpers for the statistics pages.
import { fmt } from '../../lib/format.js'
import { t, locale, translated } from '../../lib/i18n.svelte.js'

/** Large numbers in short: 20,611 → "20.6k" */
export const compact = (n) => (n >= 10000 ? t('{n}k', { n: (n / 1000).toLocaleString(locale(), { maximumFractionDigits: 1 }) }) : fmt(n))

export const MONTHS = translated(() => [t('Jan'), t('Feb'), t('Mar'), t('Apr'), t('May'), t('Jun'), t('Jul'), t('Aug'), t('Sep'), t('Oct'), t('Nov'), t('Dec')])

/** Date of a day ("2026-10-12") readable – at noon, so no time zone shifts the day. */
export const dayLabel = (key, opts) => new Date(key + 'T12:00').toLocaleDateString(locale(), opts)
