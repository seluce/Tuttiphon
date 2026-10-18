// Vibes: groups, short description, season date format – and genre suggestions for input fields.
import { S, MOODS } from './state.svelte.js'
import { plural } from './format.js'
import { t, tn, locale, translated } from './i18n.svelte.js'
import { instrumentLabel, themeLabel } from './sound.svelte.js'

// Group names are data: stored in the configuration (field `group` of a vibe) and compared – they stay German.
export const GROUPS = ['Genre', 'Thema', 'Jahreszeit', 'Zeitreise', 'Spezial', 'Klang']   // i18n-ignore: stored values
/** Shown name of a group (stored name → text); unknown groups are shown as they are: GROUP_LABEL[g] ?? g */
export const GROUP_LABEL = translated(() => ({
  Genre: t('Genre'),
  Thema: t('Topic'),
  Jahreszeit: t('Season'),
  Zeitreise: t('Time travel'),
  Spezial: t('Special'),
  Klang: t('Sound'),
  Sonstiges: t('Other'),   // i18n-ignore: stored value (vibes without a group)
}))
export const GROUP_TEXT = translated(() => ({
  Genre: t('By the genre tags of the songs – e.g. Rock, Hip-Hop, Folk.'),
  Thema: t('By keywords in the album or song title – e.g. dancing, sleeping.'),
  Jahreszeit: t('Seasonal content – hidden from other playlists outside its season.'),
  Zeitreise: t('By release year.'),
  Spezial: t('By rating, favorites, new additions or listening habits.'),
  Klang: t('By the sound analysis – tempo, energy, mood.'),
}))

/** All groups: the fixed ones first, then those from the data (no group → „Sonstiges“). */
export const stilGroups = () => [...new Set([...GROUPS, ...S.config.stile.map((s) => s.group || 'Sonstiges')])]   // i18n-ignore: stored value

/** Middle of a stored range [lo, hi] – 0…1 (tempo: BPM). */
const mid = (r) => (r[0] + r[1]) / 2

/** The sound filter of a vibe in words ("cheerful · piano · epic · getting livelier") – moods, instruments and themes
 *  (AI), ranges (also how easy to listen to and how much for close listening, from the AI), course. */
function soundWords(s) {
  const snd = s.sound || {}, out = (snd.moods || []).map((m) => MOODS[m] ?? m)
  for (const x of snd.instruments || []) out.push(instrumentLabel(x))
  for (const x of snd.themes || []) out.push(themeLabel(x))
  if (snd.approachable) out.push(mid(snd.approachable) >= 0.5 ? t('easy to listen to') : t('demanding'))
  if (snd.engaging) out.push(mid(snd.engaging) >= 0.5 ? t('for close listening') : t('for the background'))
  if (snd.energy) out.push(mid(snd.energy) < 0.4 ? t('low energy') : mid(snd.energy) > 0.6 ? t('high energy') : t('medium energy'))
  if (snd.bpm) out.push(mid(snd.bpm) < 95 ? t('slow') : mid(snd.bpm) > 125 ? t('fast') : t('medium tempo'))
  if (snd.dance) out.push(mid(snd.dance) >= 0.5 ? MOODS.tanzbar : t('not for dancing'))
  if (snd.valence && mid(snd.valence) > 0.6) out.push(MOODS.froh)
  if (snd.valence && mid(snd.valence) < 0.4) out.push(MOODS.melancholisch)
  if (snd.arousal && mid(snd.arousal) > 0.6) out.push(t('lively'))
  if (snd.arousal && mid(snd.arousal) < 0.4) out.push(t('relaxed'))
  if (s.arc === 'rise') out.push(t('getting livelier'))   // mixer.py: starts calm, then livelier
  return [...new Set(out)]
}

/** "06-01" (how the server stores seasons) → day and month in the format of the language ("01.06." / "06/01") */
const dayMonth = (md) => new Date(2000, +md.slice(0, 2) - 1, +md.slice(3)).toLocaleDateString(locale(), { day: '2-digit', month: '2-digit' })

/** Short description of a vibe ("5 genres · 1 band"). */
export function summary(s) {
  if (s.kind === 'season') return t('automatically collects the current season')
  const f = s.filters || {}, parts = []
  if (s.genres?.length) parts.push(plural(s.genres.length, 'genre', 'genres'))
  if (s.albums?.length || s.titles?.length) parts.push(plural((s.albums?.length || 0) + (s.titles?.length || 0), 'keyword', 'keywords'))
  if (s.artists?.length) parts.push(plural(s.artists.length, 'band', 'bands'))
  if (f.years) parts.push(`${f.years[0]}–${f.years[1]}`)
  if (f.minRating) parts.push(t('{stars} and up', { stars: '★'.repeat(f.minRating) }))
  if (f.loved) parts.push(t('favorites'))
  if (f.addedDays) parts.push(tn(f.addedDays, 'new in the last {n} day', 'new in the last {n} days'))
  if (f.notPlayedDays) parts.push(tn(f.notPlayedDays, 'not played for {n} day', 'not played for {n} days'))
  if (s.season) parts.push(`${dayMonth(s.season[0])} – ${dayMonth(s.season[1])}`)
  if (s.sound || s.arc) {
    const words = soundWords(s)
    parts.push(words.length ? t('by sound: {list}', { list: words.join(' · ') }) : t('by sound'))
  }
  return parts.join(' · ') || t('still empty')
}

/** "25.11." / "25.11" / "11-25" → "11-25" (how the server stores seasons); invalid → null */
export function normMD(v) {
  let m = /^(\d{1,2})\.(\d{1,2})\.?$/.exec(v || ''), mm, dd
  if (m) { dd = +m[1]; mm = +m[2] } else if ((m = /^(\d{1,2})-(\d{1,2})$/.exec(v || ''))) { mm = +m[1]; dd = +m[2] } else return null
  if (mm < 1 || mm > 12 || dd < 1 || dd > 31) return null
  return `${String(mm).padStart(2, '0')}-${String(dd).padStart(2, '0')}`
}
/** "11-25" → "25.11." */
export const showMD = (md) => (md ? `${md.slice(3)}.${md.slice(0, 2)}.` : '')

/** Genres of the library as suggestions for <ChipEditor suggestions>. */
export const genreSuggestions = () => (S.library?.genres || []).map(([g, n]) => [g, plural(n, 'song', 'songs')])
