<!--
  Song sheet: cover, title, band, album – play, "More like this" (similar songs to listen to, kept as a radio mix on
  request), sound (tempo with its source, key with its Camelot code, the instruments and themes from the AI sound
  analysis, moods, genres), the playlists the song appears in, and the lyrics to read along. If the lyrics have timestamps,
  they follow along while playing: the current line is highlighted, tapping a line jumps there.
  Opened via lib/song.js → openSong(track).
-->
<script>
  import Icon from '../Icon.svelte'
  import Cover from '../Cover.svelte'
  import Field from '../Field.svelte'
  import TrackList from '../TrackList.svelte'
  import { MOODS } from '../../lib/state.svelte.js'
  import { closeSheet } from '../../lib/overlay.svelte.js'
  import { api } from '../../lib/api.js'
  import { openArtist, startRadio } from '../../lib/artist.js'
  import { mmss } from '../../lib/format.js'
  import { keyName } from '../../lib/sound.svelte.js'
  import { t } from '../../lib/i18n.svelte.js'
  import { player, isCurrent, playTrack, playAt, continueWith } from '../../lib/player.svelte.js'
  import { smooth } from '../../lib/motion.js'

  let { track } = $props()
  /** /api/song – until it arrives, the row from the list is used */
  let d = $state(null)
  let error = $state(null)
  let more = $state(null)
  let moreBusy = $state(false)
  let moreError = $state(null)
  let full = $state(false)

  $effect(() => {
    let alive = true
    api(`/api/song?id=${encodeURIComponent(track.id)}`)
      .then((r) => { if (alive) d = r })
      .catch((e) => { if (alive) error = e.message })
    return () => { alive = false }
  })

  const s = $derived(d || track)
  const on = $derived(isCurrent(track.id))
  const lines = $derived((d?.lyrics || '').split('\n'))

  /* Sound from the AI: where the tempo comes from, key with its Camelot code (weak estimates count as uncertain –
     mixes ignore them, like classify.py from ml.KEY_MIN) */
  const KEY_MIN = 0.5
  const tempo = $derived(!d?.bpm ? null
    : d.bpmSource === 'ai' ? { text: t('{bpm} BPM · AI', { bpm: d.bpm }), tip: t('Tempo recognized by the AI sound analysis') }
      : d.bpmSource === 'measured' ? { text: t('{bpm} BPM · measured', { bpm: d.bpm }), tip: t('Tempo measured by the sound analysis') }
        : { text: `${d.bpm} BPM`, tip: '' })
  const key = $derived(!d?.key ? null
    : !d.camelot ? keyName(d.key)
      : d.keyStrength != null && d.keyStrength < KEY_MIN ? t('{key} · {camelot} · uncertain', { key: keyName(d.key), camelot: d.camelot })
        : `${keyName(d.key)} · ${d.camelot}`)

  /* Lyrics that follow along: current line from the playback time, the box scrolls along */
  const synced = $derived(d?.synced || null)
  const cur = $derived.by(() => {
    if (!synced || !on) return -1
    const ms = player.time * 1000 + 250
    let k = -1
    for (let i = 0; i < synced.length && synced[i][0] <= ms; i++) k = i
    return k
  })
  const follow = (box) => {
    const k = cur
    const el = k >= 0 ? box.children[k] : null
    if (el) box.scrollTo({ top: el.offsetTop - box.clientHeight / 3, behavior: smooth() })
  }

  async function loadMore() {
    moreBusy = true
    moreError = null
    try {
      const r = await api(`/api/song/more?id=${encodeURIComponent(track.id)}`)
      more = r.songs
      if (more.length) continueWith(s, more, t('More like this · {title}', { title: s.title }))
    } catch (e) {
      moreError = e.message
    } finally {
      moreBusy = false
    }
  }
</script>

<div class="grid gap-[22px]">
  <div class="grid grid-cols-[auto_minmax(0,1fr)] gap-4 items-center">
    <Cover id={s.cover} size={112} class="rounded-[14px]" />
    <div class="grid gap-1 min-w-0">
      <h2 class="text-[1.3rem] leading-tight">{s.title}</h2>
      <button type="button" class="link text-left w-fit" onclick={() => openArtist(s.artist)}>{s.artist}</button>
      <div class="muted small">{[s.album, s.year, mmss(s.duration)].filter(Boolean).join(' · ')}</div>
    </div>
  </div>

  {#if error}
    <div class="note">{error}</div>
  {:else}
    <div class="btns">
      <button class="btn primary" onclick={() => playTrack(s)}>
        <Icon name={on && player.playing ? 'pause' : 'play'} size={18} />{on && player.playing ? t('Pause') : t('Play')}
      </button>
      <button class="btn" onclick={loadMore} disabled={moreBusy}>
        <Icon name={moreBusy ? 'loader' : 'sparkles'} size={17} class={moreBusy ? 'animate-spin' : ''} />{t('More like this')}
      </button>
    </div>
  {/if}

  {#if moreError}<div class="note">{moreError}</div>{/if}
  {#if more}
    <Field label={t('More like this')}>
      {#if more.length}
        <TrackList tracks={more} from={t('More like this · {title}', { title: s.title })} compact />
        <div class="flex flex-wrap items-center justify-between gap-2 mt-1">
          <span class="hint">{t('Similar songs from your library – they play after this one.')}</span>
          <button class="btn sm" onclick={() => startRadio(s.artist)}><Icon name="radio" size={15} />{t('Keep as radio mix')}</button>
        </div>
      {:else}
        <div class="hint">{t('Your library has nothing similar to this song.')}</div>
      {/if}
    </Field>
  {/if}

  {#if d && (d.bpm || d.key || d.moods?.length || d.genres?.length || d.instruments?.length || d.themes?.length)}
    <div class="grid gap-2">
      {#if tempo || key || d.moods?.length || d.genres?.length}
        <div class="btns">
          {#if tempo}<span class="pill" title={tempo.tip || undefined}>{tempo.text}</span>{/if}
          {#if key}<span class="pill" title={t('Key and its code on the Camelot wheel – neighboring codes blend well in a mix')}>{key}</span>{/if}
          {#each d.moods || [] as m}<span class="pill acc">{MOODS[m] || m}</span>{/each}
          {#each d.genres || [] as g}<span class="pill">{g}</span>{/each}
        </div>
      {/if}
      {#if d.instruments?.length}
        <div class="btns">
          <span class="muted small">{t('Instruments:')}</span>
          {#each d.instruments as x (x.id)}<span class="pill">{x.label}</span>{/each}
        </div>
      {/if}
      {#if d.themes?.length}
        <div class="btns">
          <span class="muted small">{t('Themes:')}</span>
          {#each d.themes as x (x.id)}<span class="pill">{x.label}</span>{/each}
        </div>
      {/if}
    </div>
  {/if}

  {#if d?.playlists?.length}
    <Field label={t('Appears in')}>
      <div class="grid gap-1.5">
        {#each d.playlists as p (p.id)}
          <a class="member-row no-underline" href="#/playlist/{encodeURIComponent(p.id)}" onclick={() => closeSheet()}>
            <Icon name={p.mix ? 'shuffle' : 'playlists'} size={18} /><span class="flex-1">{p.name}</span>
          </a>
        {/each}
      </div>
    </Field>
  {/if}

  {#if d}
    <Field label={t('Song lyrics')}>
      {#if synced}
        <div class="lyrics live" {@attach follow}>
          {#each synced as [ms, line], i (i)}
            <button type="button" class="ln" class:now={i === cur} class:past={i < cur} onclick={() => playAt(s, ms / 1000)}>{line || '♪'}</button>
          {/each}
        </div>
        {#if !on}<div class="hint">{t('The lyrics follow along while playing. Tap a line to jump there.')}</div>{/if}
      {:else if d.lyrics}
        <div class="lyrics" class:clamped={!full && lines.length > 14}>
          {#each lines as l, i (i)}<p>{l}</p>{/each}
        </div>
        {#if lines.length > 14}
          <button class="link w-fit" onclick={() => (full = !full)}>{full ? t('less') : t('show the whole text')}</button>
        {/if}
      {:else}
        <div class="hint">{t('There are no lyrics for this song.')}</div>
      {/if}
    </Field>
  {/if}
</div>

<style>
  .lyrics { display: grid; gap: 4px; font-size: .95rem; line-height: 1.5; color: var(--text-2); }
  .lyrics.clamped { max-height: 21em; overflow: hidden; mask-image: linear-gradient(180deg, #000 70%, transparent); }
  .lyrics.live { position: relative; max-height: 20em; overflow-y: auto; gap: 2px; padding: 4px 0;
    mask-image: linear-gradient(180deg, transparent, #000 8%, #000 88%, transparent); }
  .ln { display: block; text-align: left; padding: 3px 0; color: var(--text-2); cursor: pointer;
    transition: color .25s, transform .25s; transform-origin: left center; }
  .ln.past { color: var(--muted); }
  .ln.now { color: var(--text); font-weight: 750; transform: scale(1.03); }
  .ln:hover { color: var(--accent); }
</style>
