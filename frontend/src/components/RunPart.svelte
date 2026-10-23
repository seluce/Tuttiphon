<!--
  What a running step is doing right now (task.progress from /api/task, app/progress.py): the part, a bar and how many
  of how many – with the time still to go and, in the night, by when it stops at the latest. Without a total (scan)
  the bar only moves.
-->
<script module>
  import { t, tn, locale } from '../lib/i18n.svelte.js'
  import { fmt } from '../lib/format.js'

  /** A duration in seconds, short and in the reader's language: "12 min", "1 h 20 min". */
  export function duration(seconds) {
    const unit = (n, u) => new Intl.NumberFormat(locale(), { style: 'unit', unit: u, unitDisplay: 'short' }).format(n)
    const m = Math.max(1, Math.round((seconds || 0) / 60))
    if (m < 60) return unit(m, 'minute')
    return m % 60 ? `${unit(Math.floor(m / 60), 'hour')} ${unit(m % 60, 'minute')}` : unit(m / 60, 'hour')
  }

  /** Name of a part (ids from app/progress.py) and what it counts. */
  export function partName(id) {
    return ({
      maintenance: t('Long-term maintenance'), flac: t('Converting music'), lyrics: t('Searching lyrics'),
      cover: t('Fetching covers'), lastfm: t('Fetching Last.fm knowledge'), audio: t('Sound analysis'),
      ml: t('AI sound analysis'), loudness: t('Measuring loudness'), classify: t('Classifying bands'),
      fingerprints: t('Audio fingerprints'), learn: t('Learning from mixes'), playlists: t('Writing playlists'),
      scan: t('Navidrome is reading everything in'), sync: t('Syncing with Navidrome'), lyricsindex: t('Indexing lyrics'),
      selfcheck: t('Self-check'), deezer: t('Looking up songs on Deezer'),
    })[id] || ''
  }

  function counted(id, done, total) {
    const d = { done: fmt(done) }
    if (total) {
      if (id === 'flac') return tn(total, '{done} of {n} file', '{done} of {n} files', d)
      if (id === 'cover') return tn(total, '{done} of {n} album', '{done} of {n} albums', d)
      if (id === 'lastfm') return tn(total, '{done} of {n} band', '{done} of {n} bands', d)
      if (id === 'playlists') return tn(total, '{done} of {n} playlist', '{done} of {n} playlists', d)
      return tn(total, '{done} of {n} song', '{done} of {n} songs', d)
    }
    if (id === 'scan' && done) return tn(done, '{n} file read', '{n} files read')
    return ''
  }
</script>

<script>
  let { p } = $props()
  const pct = $derived(p?.total ? Math.min(100, Math.floor((p.done / p.total) * 100)) : null)
  const count = $derived(p ? counted(p.part, p.done, p.total) : '')
  const until = $derived(p?.until ? new Date(p.until * 1000).toLocaleTimeString(locale(), { hour: '2-digit', minute: '2-digit' }) : '')
</script>

{#if p?.part}
  <div class="grid gap-1.5">
    <div class="flex justify-between gap-3 text-[.9rem]">
      <b class="ell">{partName(p.part)}</b>
      {#if pct !== null}<span class="tabular-nums font-[650]">{pct} %</span>{/if}
    </div>
    <div class="track" class:moving={pct === null} role="progressbar" aria-label={partName(p.part)}
      aria-valuemin="0" aria-valuemax="100" aria-valuenow={pct ?? undefined}><i style:width={pct === null ? null : `${pct}%`}></i></div>
    {#if count || p.left || until}
      <div class="muted small flex flex-wrap gap-x-3 gap-y-0.5">
        {#if count}<span class="tabular-nums">{count}</span>{/if}
        {#if p.left}<span>{t('about {time} left', { time: duration(p.left) })}</span>{/if}
        {#if until}<span>{t('until {time} at the latest', { time: until })}</span>{/if}
      </div>
    {/if}
  </div>
{/if}

<style>
  .track { position: relative; height: 8px; border-radius: 99px; background: var(--surface-2); overflow: hidden; }
  .track i { position: absolute; inset: 0 auto 0 0; border-radius: 99px; background: var(--grad); transition: width .6s var(--ease); }
  .track.moving i { width: 30%; animation: move 1.4s ease-in-out infinite; }
  @keyframes move { from { left: -30%; } to { left: 100%; } }
  @media (prefers-reduced-motion: reduce) { .track.moving i { animation: none; left: 0; width: 100%; opacity: .4; } }
</style>
