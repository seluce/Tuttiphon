// The year as a picture to share (1080 × 1920, the size of a status or story): heading, listening time, band of the
// year with its picture, top bands and songs, world and decade – drawn on a canvas in the interface language. The
// pictures come from Tuttiphon itself (/img/…), so the canvas stays readable.
import { t, tword } from '../../lib/i18n.svelte.js'
import { fmt, initials, gradFor } from '../../lib/format.js'

const W = 1080
const H = 1920
const PAD = 90

/** A picture from Tuttiphon – null if it does not come within 4 seconds. */
function picture(src) {
  return new Promise((done) => {
    const img = new Image()
    const timer = setTimeout(() => done(null), 4000)
    img.onload = () => { clearTimeout(timer); done(img) }
    img.onerror = () => { clearTimeout(timer); done(null) }
    img.src = src
  })
}

/** Text cut to a width with "…" */
function fit(ctx, text, width) {
  if (ctx.measureText(text).width <= width) return text
  let s = text
  while (s.length > 1 && ctx.measureText(s + '…').width > width) s = s.slice(0, -1)
  return s.trimEnd() + '…'
}

/** Largest font size (down to min) at which the text fits the width. */
function sized(ctx, text, weight, size, min, width, family) {
  for (; size > min; size -= 4) {
    ctx.font = `${weight} ${size}px ${family}`
    if (ctx.measureText(text).width <= width) return size
  }
  ctx.font = `${weight} ${min}px ${family}`
  return min
}

/** Round picture of a band – its image or, without one, its initials on its colors. */
async function bandPicture(ctx, name, id, x, y, r, family) {
  const img = id ? await picture(`/img/ar-${id}?s=300`) : null
  ctx.save()
  ctx.beginPath()
  ctx.arc(x + r, y + r, r, 0, Math.PI * 2)
  ctx.clip()
  if (img) ctx.drawImage(img, x, y, r * 2, r * 2)
  else {
    const [a, b] = (gradFor(name).match(/#[0-9a-f]{3,8}|hsl\([^)]*\)|rgba?\([^)]*\)/gi) || ['#8b5cf6', '#ec4899'])
    const g = ctx.createLinearGradient(x, y, x + r * 2, y + r * 2)
    g.addColorStop(0, a)
    g.addColorStop(1, b || a)
    ctx.fillStyle = g
    ctx.fillRect(x, y, r * 2, r * 2)
    ctx.fillStyle = '#fff'
    ctx.font = `800 ${Math.round(r * 0.7)}px ${family}`
    ctx.textAlign = 'center'
    ctx.textBaseline = 'middle'
    ctx.fillText(initials(name), x + r, y + r)
  }
  ctx.restore()
  ctx.beginPath()
  ctx.arc(x + r, y + r, r, 0, Math.PI * 2)
  ctx.strokeStyle = 'rgba(255, 255, 255, .55)'
  ctx.lineWidth = 6
  ctx.stroke()
}

/**
 * The picture as a PNG blob. d: the year recap (/api/rueckblick?kind=jahr), title: its heading in the first person
 * ("My 2026"), extra: { world, decade } – lines for the foot (or empty).
 */
export async function yearPicture(d, title, extra = {}) {
  try { await document.fonts?.ready } catch { /* the default font is fine too */ }
  const family = getComputedStyle(document.body).fontFamily || 'sans-serif'
  const canvas = document.createElement('canvas')
  canvas.width = W
  canvas.height = H
  const ctx = canvas.getContext('2d')

  // background: Tuttiphon's colors, two soft lights
  const bg = ctx.createLinearGradient(0, 0, W, H)
  bg.addColorStop(0, '#7c3aed')
  bg.addColorStop(0.55, '#c026d3')
  bg.addColorStop(1, '#db2777')
  ctx.fillStyle = bg
  ctx.fillRect(0, 0, W, H)
  for (const [x, y, r, a] of [[W * 0.9, 260, 520, 0.22], [W * 0.05, H * 0.72, 640, 0.16]]) {
    const glow = ctx.createRadialGradient(x, y, 0, x, y, r)
    glow.addColorStop(0, `rgba(255, 255, 255, ${a})`)
    glow.addColorStop(1, 'rgba(255, 255, 255, 0)')
    ctx.fillStyle = glow
    ctx.fillRect(0, 0, W, H)
  }

  const width = W - PAD * 2
  ctx.textBaseline = 'alphabetic'
  ctx.textAlign = 'left'
  ctx.fillStyle = 'rgba(255, 255, 255, .78)'
  ctx.font = `800 34px ${family}`
  ctx.fillText('TUTTIPHON', PAD, 150)

  ctx.fillStyle = '#fff'
  sized(ctx, title, 850, 128, 72, width, family)
  ctx.fillText(title, PAD, 290)

  // listening time
  const hours = Math.round(d.totals.hours)
  const [before, after = ''] = tword(hours, '{n} hour of music', '{n} hours of music').split('{n}')
  ctx.font = `850 210px ${family}`
  const num = fmt(hours)
  ctx.fillText(num, PAD, 530)
  const numW = ctx.measureText(num).width
  ctx.font = `700 46px ${family}`
  ctx.fillText(fit(ctx, (before + after).trim(), width - numW - 30), PAD + numW + 28, 530)
  ctx.fillStyle = 'rgba(255, 255, 255, .85)'
  ctx.font = `600 40px ${family}`
  ctx.fillText(fit(ctx, `${tword(d.totals.plays, '{n} play', '{n} plays').replace('{n}', fmt(d.totals.plays))} · ${
    tword(d.totals.artists, '{n} band', '{n} bands').replace('{n}', fmt(d.totals.artists))}`, width), PAD, 600)

  // band of the year
  const top = d.topArtists[0]
  let y = 690
  if (top) {
    ctx.fillStyle = 'rgba(255, 255, 255, .78)'
    ctx.font = `800 34px ${family}`
    ctx.fillText(t('Band of the year').toUpperCase(), PAD, y)
    await bandPicture(ctx, top.name, top.id, PAD, y + 36, 110, family)
    ctx.textAlign = 'left'
    ctx.textBaseline = 'alphabetic'
    ctx.fillStyle = '#fff'
    sized(ctx, top.name, 850, 76, 44, width - 270, family)
    ctx.fillText(fit(ctx, top.name, width - 270), PAD + 260, y + 150)
    ctx.fillStyle = 'rgba(255, 255, 255, .85)'
    ctx.font = `600 38px ${family}`
    ctx.fillText(fit(ctx, t('{plays} plays from {songs} songs', { plays: fmt(top.plays), songs: fmt(top.songs) }), width - 270), PAD + 260, y + 205)
    y += 300
  }

  // top bands and songs
  const list = (label, rows) => {
    if (!rows.length) return
    ctx.fillStyle = 'rgba(255, 255, 255, .78)'
    ctx.font = `800 34px ${family}`
    ctx.fillText(label.toUpperCase(), PAD, y)
    y += 62
    rows.forEach((text, i) => {
      ctx.fillStyle = 'rgba(255, 255, 255, .6)'
      ctx.font = `800 42px ${family}`
      ctx.fillText(String(i + 1), PAD, y)
      ctx.fillStyle = '#fff'
      ctx.font = `700 42px ${family}`
      ctx.fillText(fit(ctx, text, width - 70), PAD + 70, y)
      y += 58
    })
    y += 30
  }
  list(t('Most played bands'), d.topArtists.slice(0, 5).map((a) => a.name))
  list(t('Most played songs'), d.topSongs.slice(0, 5).map((s) => `${s.title} – ${s.artist}`))

  // foot: world and decade, one line each
  ctx.fillStyle = 'rgba(255, 255, 255, .85)'
  ctx.font = `650 36px ${family}`
  ;[extra.world, extra.decade].filter(Boolean).forEach((line, k) => ctx.fillText(fit(ctx, line, width), PAD, Math.max(y + 40, H - 130) + k * 52))

  return new Promise((done, fail) => canvas.toBlob((b) => (b ? done(b) : fail(new Error(t('The picture could not be made.')))), 'image/png'))
}

/** Share the picture (phone: the share menu) or, where the browser cannot share files, save it. -> 'shared' | 'saved' | null */
export async function sharePicture(blob, name, title) {
  const file = new File([blob], name, { type: 'image/png' })
  if (navigator.canShare?.({ files: [file] })) {
    try {
      await navigator.share({ files: [file], title })
      return 'shared'
    } catch (e) {
      if (e?.name === 'AbortError') return null   // closed the share menu
    }
  }
  const url = URL.createObjectURL(blob)
  const a = Object.assign(document.createElement('a'), { href: url, download: name })
  document.body.append(a)
  a.click()
  a.remove()
  setTimeout(() => URL.revokeObjectURL(url), 10000)
  return 'saved'
}
