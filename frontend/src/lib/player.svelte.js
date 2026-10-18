// Listening in the browser: plays songs from a list one after another (preview, band, search, "More like this").
// The sound comes from Navidrome via /api/stream – as the original file, as MP3 in browsers without Opus.
// Shown by components/MiniPlayer.svelte; on the phone also on the lock screen (Media Session).
// A track needs { id, title, artist, cover?, album?, duration? } – just as the server delivers it in song lists.
/** queue: list, i: current track, time/dur in seconds, error: the track cannot be played (the text comes from
 *  MiniPlayer, in the current language), from: name of the list ("Preview · …") */
export const player = $state({ queue: [], i: -1, playing: false, loading: false, time: 0, dur: 0, error: false, from: '' })

let audio = null
let mp3 = null

function el() {
  if (audio) return audio
  audio = new Audio()
  audio.preload = 'auto'
  mp3 = !audio.canPlayType('audio/ogg; codecs="opus"')
  audio.addEventListener('play', () => { player.playing = true; player.error = false })
  audio.addEventListener('pause', () => (player.playing = false))
  audio.addEventListener('timeupdate', () => (player.time = audio.currentTime))
  audio.addEventListener('durationchange', () => {
    player.dur = Number.isFinite(audio.duration) ? audio.duration : current()?.duration || 0
  })
  audio.addEventListener('waiting', () => (player.loading = true))
  audio.addEventListener('playing', () => (player.loading = false))
  audio.addEventListener('canplay', () => (player.loading = false))
  audio.addEventListener('ended', () => next(true))
  audio.addEventListener('error', () => {
    if (!audio.getAttribute('src')) return
    player.loading = false
    player.playing = false
    player.error = true
  })
  if ('mediaSession' in navigator) {
    const ms = navigator.mediaSession
    ms.setActionHandler('play', () => audio.play())
    ms.setActionHandler('pause', () => audio.pause())
    ms.setActionHandler('nexttrack', () => next())
    ms.setActionHandler('previoustrack', () => prev())
  }
  return audio
}

export const current = () => player.queue[player.i] || null
export const isCurrent = (id) => !!id && current()?.id === id

function load(startAt = 0) {
  const tr = current()
  const a = el()
  if (!tr) return
  player.time = 0
  player.dur = tr.duration || 0
  player.error = false
  player.loading = true
  a.src = `/api/stream?id=${encodeURIComponent(tr.id)}${mp3 ? '&f=mp3' : ''}`
  if (startAt) a.addEventListener('loadedmetadata', () => { a.currentTime = startAt }, { once: true })
  a.play().catch(() => { player.loading = false })
  if ('mediaSession' in navigator && 'MediaMetadata' in window) {
    navigator.mediaSession.metadata = new MediaMetadata({
      title: tr.title || '', artist: tr.artist || '', album: tr.album || '',
      artwork: tr.cover ? [{ src: `/img/${encodeURIComponent(tr.cover)}?s=300`, sizes: '300x300' }] : [],
    })
  }
}

/** Play a list from track `start`. If exactly this track is already playing, only pause/resume. */
export function playList(list, start = 0, from = '') {
  const tracks = (list || []).filter((tr) => tr?.id)
  const tr = (list || [])[start]
  if (!tr?.id) return
  if (isCurrent(tr.id)) { toggle(); return }
  player.queue = tracks
  player.i = Math.max(0, tracks.indexOf(tr))
  player.from = from
  load()
}

/** Play a single track – with `list`, playback continues there afterwards. */
export function playTrack(tr, list = null, from = '') {
  if (list) playList(list, list.indexOf(tr), from)
  else playList([tr], 0, from)
}

/** Jump to a position in a song (lyrics line) – if it is not playing yet, play from there. */
export function playAt(tr, seconds) {
  if (isCurrent(tr.id)) {
    seek(seconds)
    if (!player.playing) toggle()
    return
  }
  player.queue = [tr]
  player.i = 0
  player.from = ''
  load(seconds)
}

export function toggle() {
  const a = el()
  if (!current()) return
  if (player.error) { load(); return }
  if (a.paused) a.play().catch(() => {})
  else a.pause()
}

export function next(auto = false) {
  if (player.i < player.queue.length - 1) { player.i++; load() }
  else if (auto) { player.playing = false; player.time = 0; el().currentTime = 0; el().pause() }
}

export function prev() {
  const a = el()
  if (a.currentTime > 3 || player.i === 0) { a.currentTime = 0; return }
  player.i--
  load()
}

export function seek(seconds) {
  const a = el()
  if (Number.isFinite(seconds)) a.currentTime = Math.max(0, Math.min(seconds, player.dur || seconds))
}

/** Close the player: sound off, list empty */
export function stop() {
  const a = el()
  a.pause()
  a.removeAttribute('src')
  a.load()
  Object.assign(player, { queue: [], i: -1, playing: false, loading: false, time: 0, dur: 0, error: false, from: '' })
  if ('mediaSession' in navigator) navigator.mediaSession.metadata = null
}

/** Continue with this list after the playing song (if it is not playing, the list starts with `first`). */
export function continueWith(first, list, from = '') {
  const rest = (list || []).filter((tr) => tr?.id && tr.id !== first.id)
  if (isCurrent(first.id)) {
    player.queue = [current(), ...rest]
    player.i = 0
    player.from = from
    if (!player.playing) toggle()
  } else {
    playList([first, ...rest], 0, from)
  }
}
