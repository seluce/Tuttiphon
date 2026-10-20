<!-- Detail page of a playlist: head with mosaic, sample, who's in it, rules, actions. -->
<script>
  import { untrack } from 'svelte'
  import Icon from '../components/Icon.svelte'
  import Empty from '../components/Empty.svelte'
  import Loading from '../components/Loading.svelte'
  import Avatar from '../components/Avatar.svelte'
  import TrackList from '../components/TrackList.svelte'
  import PlaylistHero from './playlist/PlaylistHero.svelte'
  import { S, findPl, canEdit, isAdmin, save } from '../lib/state.svelte.js'
  import { api } from '../lib/api.js'
  import { toast } from '../lib/overlay.svelte.js'
  import { fmt } from '../lib/format.js'
  import { t, tn, locale } from '../lib/i18n.svelte.js'
  import { openArtist } from '../lib/artist.js'
  import { player, playList, toggle } from '../lib/player.svelte.js'
  import { MIXEVERY, reroll } from './playlist/actions.js'

  let { id } = $props()

  const p = $derived(findPl(id))
  let d = $state.raw(null)
  let error = $state(null)
  let tracks = $state.raw([])

  let seq = 0
  async function load() {
    const mine = ++seq
    await save()   // save first, otherwise the server still shows the old state (e.g. after "Reshuffle")
    try {
      const r = await api(`/api/playlist?id=${encodeURIComponent(id)}`)
      if (mine !== seq) return
      d = r
      tracks = r.sample
      error = null
    } catch (e) {
      if (mine === seq) error = e.message
    }
  }
  // Reload when the playlist changes (edit, status, reshuffle, undo) or a run has finished
  const sig = $derived(p ? JSON.stringify(p) : '')
  $effect(() => {
    if (!sig) return
    void S.done
    untrack(load)
  })

  const status = $derived(p?.status || 'aktiv')
  const mix = $derived(p?.type === 'mix')
  const every = $derived(MIXEVERY[p?.mix?.every || 'day'])
  const own = $derived(d?.own !== false && canEdit(p))
  const max = $derived(Math.max(1, ...(d?.topArtists || []).map((a) => a[1])))
  // is the mix listened to? finished editions from the mix history (GET /api/playlist → usage)
  const usage = $derived.by(() => {
    const u = d?.usage
    if (!u) return null
    const pct = u.songs ? Math.round((100 * u.played) / u.songs) : 0
    const when = u.last ? new Date(`${u.last}T12:00`).toLocaleDateString(locale(), { day: 'numeric', month: 'short' }) : ''
    const vals = { heard: u.heard, pct }
    const main = !u.heard
      ? (u.played ? tn(u.periods, 'Only single songs played from the last edition ({pct} % of the songs).', 'Only single songs played from the last {n} editions ({pct} % of the songs).', vals)
        : tn(u.periods, 'Nothing played from the last edition.', 'Nothing played from the last {n} editions.'))
      : u.every === 'week' ? tn(u.periods, 'Listened to in the last week – {pct} % of its songs played.', 'Listened to in {heard} of the last {n} weeks – {pct} % of their songs played.', vals)
      : u.every === 'month' ? tn(u.periods, 'Listened to in the last month – {pct} % of its songs played.', 'Listened to in {heard} of the last {n} months – {pct} % of their songs played.', vals)
      : tn(u.periods, 'Listened to on the last day – {pct} % of its songs played.', 'Listened to on {heard} of the last {n} days – {pct} % of their songs played.', vals)
    return { main, last: u.heard ? t('Last edition listened to: {when}', { when }) : '', none: !u.played }
  })

  async function shuffle() {
    try {
      const r = await api('/api/preview', { body: { ...$state.snapshot(p), sampleSize: 25 } })
      tracks = r.sample
    } catch (e) {
      toast(e.message, { error: true })
    }
  }
  const enter = (fn) => (e) => { if (e.key === 'Enter') fn() }
  /** Is this list playing from its start right now? Then "Play" becomes "Pause" */
  const playing = $derived(player.playing && player.from === d?.name && player.queue[0]?.id === tracks[0]?.id)
</script>

{#if !p}
  <Empty icon="playlists" title={t('This playlist doesn’t exist')}>
    <a class="btn" href="#/playlists">{t('Go to playlists')}</a>
  </Empty>
{:else}
  <div class="page">
    {#if error}
      <Empty icon="alert" title={t('Could not be loaded')} text={error}>
        <button class="btn" onclick={() => { error = null; d = null; load() }}><Icon name="refresh" size={16} />{t('Try again')}</button>
      </Empty>
    {:else if !d}
      <Loading text={t('Putting the playlist together …')} />
    {:else}
      <a href="#/playlists" class="link inline-flex gap-1.5 items-center mt-2.5 mb-3.5"><Icon name="left" size={16} />{isAdmin() ? t('All playlists') : t('My playlists')}</a>
      <PlaylistHero {p} {d} onreload={load} />

      <div class="g-2 section">
        <div class="card">
          <div class="card-head">
            <h2>{mix ? every.title : t('Sample')}</h2>
            <div class="btns">
              {#if tracks.length}
                <button class="btn sm primary" onclick={() => (playing ? toggle() : playList(tracks, 0, d.name))}>
                  <Icon name={playing ? 'pause' : 'play'} size={15} />{playing ? t('Pause') : t('Play')}
                </button>
              {/if}
              {#if mix && status === 'aktiv' && own}
                <button class="btn sm ghost" onclick={() => reroll(p)}><Icon name="dice" size={16} />{t('reshuffle')}</button>
              {:else if !mix}
                <button class="btn sm ghost" onclick={shuffle}><Icon name="shuffle" size={16} />{t('shuffle again')}</button>
              {/if}
            </div>
          </div>
          <p class="muted small -mt-1.5 mb-2.5">
            {mix
              ? every.about(fmt(d.count))
              : t('This is how a mix could look – Navidrome reshuffles on every request.')}
          </p>
          <TrackList {tracks} from={d.name} fold={10} />
        </div>

        <div class="grid gap-[18px] content-start">
          <div class="card">
            <div class="card-head"><h2>{t('Who’s in it?')}</h2></div>
            <div class="arows">
              {#each d.topArtists as [name, n, aid] (name)}
                <div class="arow" role="button" tabindex="0" onclick={() => openArtist(name)} onkeydown={enter(() => openArtist(name))}>
                  <Avatar {name} id={aid} size={40} />
                  <div class="ell"><b>{name}</b></div>
                  <div class="bar"><i style:width="{(n / max) * 100}%"></i></div>
                  <span class="n">{n}</span>
                </div>
              {/each}
            </div>
          </div>
          {#if usage}
            <div class="card">
              <div class="card-head"><h2>{t('Is it listened to?')}</h2></div>
              <p class="small" class:warn-t={usage.none}>{usage.main}</p>
              {#if usage.last}<p class="small muted mt-1">{usage.last}</p>{/if}
              <div class="hint">{t('Counts the songs of each finished edition that were played in its period – also from the album or elsewhere. An edition counts as listened to from 3 songs.')}</div>
            </div>
          {/if}
          <div class="card">
            <div class="card-head"><h2>{t('How it is made')}</h2></div>
            <ul class="rules">
              {#each d.summary as line, i (i)}<li>{line}</li>{/each}
            </ul>
            {#if d.nsp}
              <details class="small mt-3.5">
                <summary class="muted cursor-pointer">{mix ? t('Technical rule: selection pool') : t('Technical rule: .nsp')}</summary>
                <pre class="log h-auto max-h-[300px]">{JSON.stringify(d.nsp, null, 2)}</pre>
              </details>
            {/if}
          </div>
        </div>
      </div>
    {/if}
  </div>
{/if}
