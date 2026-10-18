// First-visit tour and "Show me" guides: highlight areas of the real interface one after another.
// Shown by components/Tour.svelte (App.svelte). startTour(): the tour – on the first visit by itself, otherwise via
// Settings → My account (startTour(true)). startGuide(id): a guide from lib/guides.js.
import { S, isAdmin } from './state.svelte.js'
import { api } from './api.js'
import { go } from './router.svelte.js'
import { closeSheet } from './overlay.svelte.js'
import { guideById, guideSteps } from './guides.js'
import { t, translated } from './i18n.svelte.js'

// sel: targets in this order – the first visible one is highlighted (sidebar on the PC, bottom bar on the phone).
// Without a visible target the hint is centered.
const ADMIN_STEPS = translated(() => [
  { title: t('Welcome to Tuttiphon'), text: t('In one minute I’ll show you where everything is. You can skip at any time – the tour can be restarted under Settings → My account.') },
  { sel: ['[data-tour=nav] a[href="#/"]', '[data-tour=bottomnav] a[href="#/"]'], title: t('Home'), text: t('Your mixes of the day, what there is to review – and “Update everything”: convert music, fetch lyrics and covers, analyze the sound, write playlists, scan Navidrome, set stars. One click.') },
  { sel: ['[data-tour=new]', '[data-tour=more]'], title: t('New playlist'), text: t('The assistant asks: For whom? Which music world? Which vibe? – and shows right away what comes out. Either as a smart playlist or as a mix that puts itself together anew daily, weekly or monthly. On the phone under “More”.') },
  { sel: ['[data-tour=nav] a[href="#/playlists"]', '[data-tour=bottomnav] a[href="#/playlists"]'], title: t('Playlists'), text: t('All playlists Tuttiphon looks after for you. Tapping opens preview, “Who’s in it?”, cover and editing.') },
  { sel: ['[data-tour=nav] a[href="#/entdecken"]', '[data-tour=bottomnav] a[href="#/entdecken"]'], title: t('Discover'), text: t('Ready-made suggestions matching your preferences and the season – one click creates them.') },
  { sel: ['[data-tour=nav] a[href="#/welten"]', '[data-tour=bottomnav] a[href="#/welten"]'], title: t('Music worlds'), text: t('Who plays what: kids’ rock, medieval, … Tuttiphon recognizes typical bands by itself.') },
  { sel: ['[data-tour=nav] a[href="#/personen"]', '[data-tour=more]'], title: t('People'), text: t('Who the playlists are for: Navidrome account, favorite worlds, dislikes. On the phone under “More”.') },
  { sel: ['[data-tour=nav] a[href="#/statistik"]', '[data-tour=more]'], title: t('Statistics & recap'), text: t('Most played bands, “Played this week” and your yearly recap. On the phone under “More”.') },
  { sel: ['[data-tour=nav] a[href="#/einstellungen"]', '[data-tour=more]'], title: t('Settings'), text: t('Everything can be adjusted: home page, Navidrome server, users & rights, Deezer stars, lyrics, Opus conversion and what “Update everything” does.') },
  { sel: ['[data-tour=search]'], title: t('Search'), text: t('Bands, songs, playlists, music worlds and moods – on the PC also with the / key.') },
  { sel: ['[data-tour=nav] a[href="#/hilfe"]', '[data-tour=more]'], title: t('Help'), text: t('Guides that show you everything right on the page, and answers to common questions. The question mark next to every page title explains exactly that page.'), last: true },
])
// Users: only what they see themselves – in simple words
const USER_STEPS = translated(() => [
  { title: t('Great to have you here!'), text: t('In one minute I’ll show you where to find things. You can skip at any time and start the tour again later under Settings → My account.') },
  { sel: ['[data-tour=nav] a[href="#/"]', '[data-tour=bottomnav] a[href="#/"]'], title: t('For you'), text: t('Your home page: your mixes, new ideas for playlists and what you listened to this week.') },
  { sel: ['[data-tour=new]', '[data-tour=more]'], title: t('New playlist'), text: t('An assistant asks step by step: Which music? Which mood? Normal playlist or mix? You see right away which songs would be in it. On the phone under “More”.') },
  { sel: ['[data-tour=nav] a[href="#/playlists"]', '[data-tour=bottomnav] a[href="#/playlists"]'], title: t('My playlists'), text: t('All your playlists – and those others share with you. Tap: listen in, change the cover or adjust.') },
  { sel: ['[data-tour=nav] a[href="#/entdecken"]', '[data-tour=bottomnav] a[href="#/entdecken"]'], title: t('Discover'), text: t('Ready-made suggestions matching your taste and the season. “Create” adds them, ✕ hides them.') },
  { sel: ['[data-tour=nav] a[href="#/welten"]', '[data-tour=bottomnav] a[href="#/welten"]'], title: t('Music worlds'), text: t('Your music sorted by kind, for example children’s songs or medieval. Here you see which bands belong to it and can make a playlist from it.') },
  { sel: ['[data-tour=nav] a[href="#/statistik"]', '[data-tour=more]'], title: t('My statistics'), text: t('What you listen to most – with a recap of this week, the last 30 days and the year. On the phone under “More”.') },
  { sel: ['[data-tour=nav] a[href="#/profil"]', '[data-tour=more]'], title: t('My profile'), text: t('What Tuttiphon has recognized from your listening, your favorites and dislikes. Your suggestions come from that.') },
  { sel: ['[data-tour=search]'], title: t('Search'), text: t('Find bands, songs, playlists and moods – “calm children’s songs” turns right into a mix. On the PC also with the / key.') },
  { sel: ['[data-tour=nav] a[href="#/hilfe"]', '[data-tour=more]'], title: t('Help'), text: t('Guides that show you everything right on the page, and answers to common questions. The question mark next to every page title explains exactly that page.'), last: true },
])

/**
 * Running tour or guide: steps, current step i, direction dir (+1/−1, for skipping missing targets),
 * guide (id of the guide, null for the tour) and back (route when the guide was started).
 */
export const tour = $state({ active: false, steps: [], i: 0, dir: 1, guide: null, title: '', back: '', skipped: [] })

/** Browser key: tour already seen? Per account – several people can sign in on the same device. */
export const tourKey = () => (S.me?.user ? `tuttiphon-tour:${S.me.user.toLowerCase()}` : 'tuttiphon-tour')

/**
 * Start the tour – without force only if it was never shown on this device.
 * force (Settings → My account): always, going to the home page first.
 */
export function startTour(force = false) {
  if (!force && S.me?.tourSeen) return   // remembered on the server – applies to all devices and addresses
  try {
    if (!force && localStorage.getItem(tourKey())) return
  } catch { /* private mode: just show it */ }
  if (tour.active) return
  if (force) go('#/')
  Object.assign(tour, { steps: [...(isAdmin() ? ADMIN_STEPS : USER_STEPS)], i: 0, dir: 1, guide: null, title: '', back: '', skipped: [], active: true })   // a copy: a running tour keeps its texts
}

/** "Show me": start a guide from lib/guides.js – does not count as a seen tour. */
export function startGuide(id) {
  const g = guideById(id)
  if (!g) return
  closeSheet()
  Object.assign(tour, { steps: guideSteps(g), i: 0, dir: 1, guide: id, title: g.title, back: location.hash || '#/', skipped: [], active: true })
}

/** End (also skip). The tour is remembered as seen – in the browser and on the server (per account). */
export function endTour() {
  if (!tour.active) return
  tour.active = false
  if (tour.guide) {
    tour.guide = null
    return
  }
  try { localStorage.setItem(tourKey(), 'done') } catch { /* does not matter */ }
  if (S.me) S.me.tourSeen = true
  api('/api/seen', { body: { what: 'tour' } }).catch(() => { /* then only in the browser */ })
}

export function nextStep() {
  tour.dir = 1
  if (tour.i >= tour.steps.length - 1) endTour()
  else tour.i++
}

export function prevStep() {
  tour.dir = -1
  if (tour.i > 0) tour.i--
}

/** Skip a step without a target (optional: true) – in the direction last moved */
export function skipStep() {
  if (!tour.skipped.includes(tour.i)) tour.skipped.push(tour.i)
  if (tour.dir < 0 && tour.i > 0) tour.i--
  else nextStep()
}
