<!--
  Settings → Lyrics: lyrics search and kid-safe mode – status of the index and the songs detected as explicit:
  grouped by band (most first, collapsed), with search by band, song or word, filter blocked/allowed, the words
  found per song and “allow all” per band (with undo).
-->
<script>
  import Icon from '../../components/Icon.svelte'
  import Avatar from '../../components/Avatar.svelte'
  import Card from './Card.svelte'
  import Row from './Row.svelte'
  import Seg from '../../components/Seg.svelte'
  import { S, changed, snapshot } from '../../lib/state.svelte.js'
  import { api } from '../../lib/api.js'
  import { toast } from '../../lib/overlay.svelte.js'
  import { openArtist } from '../../lib/artist.js'
  import { fmt, plural } from '../../lib/format.js'
  import { t, tn } from '../../lib/i18n.svelte.js'

  /** The allowed songs – always fresh from S.config, because “Undo” replaces S.config as a whole */
  function allowList() {
    S.config.settings.kinderschutz ??= { allow: [] }
    S.config.settings.kinderschutz.allow ??= []
    return S.config.settings.kinderschutz.allow
  }

  /** null = loading, false = error */
  let data = $state.raw(null)
  const load = () => api('/api/kinderschutz').then((d) => { data = d }).catch(() => { data = false })
  load()

  const allowSet = $derived(new Set(S.config.settings.kinderschutz?.allow || []))
  const allowed = (id) => allowSet.has(id)
  function toggle(id) {
    const list = allowList()
    if (allowed(id)) list.splice(list.indexOf(id), 1)
    else list.push(id)
    changed()
  }

  /* search, filter, groups per band */
  let q = $state('')
  let filter = $state('alle')   // i18n-ignore: filter id
  let opened = $state([])
  let limit = $state(15)
  const groups = $derived.by(() => {
    if (!data) return []
    const term = q.trim().toLowerCase()
    const by = new Map()
    for (const s of data.songs) {
      const ok = allowSet.has(s.id)
      if ((filter === 'erlaubt' && !ok) || (filter === 'gesperrt' && ok)) continue
      if (term && ![s.artist, s.title, s.album, ...s.words.map((w) => w[0])].some((x) => (x || '').toLowerCase().includes(term))) continue
      if (!by.has(s.artist)) by.set(s.artist, { artist: s.artist, artistId: s.artistId, songs: [] })
      by.get(s.artist).songs.push(s)
    }
    return [...by.values()].map((g) => {
      const words = new Map()
      for (const s of g.songs) for (const [w, k] of s.words) words.set(w, (words.get(w) || 0) + k)
      return { ...g, allowed: g.songs.filter((s) => allowSet.has(s.id)).length,
        words: [...words].sort((a, b) => b[1] - a[1]).slice(0, 3).map(([w]) => w) }
    }).sort((a, b) => b.songs.length - a.songs.length || (a.artist || '').localeCompare(b.artist || ''))
  })
  const counts = $derived(data ? { songs: data.songs.length, bands: new Set(data.songs.map((s) => s.artist)).size,
    allowed: data.songs.filter((s) => allowSet.has(s.id)).length } : null)
  const shown = $derived(groups.reduce((n, g) => n + g.songs.length, 0))
  const narrowed = $derived(!!q.trim() || filter !== 'alle')   // i18n-ignore: filter id
  /** A search with few matches has everything expanded, otherwise only what you expand yourself */
  const isOpen = (g) => (!!q.trim() && shown <= 40) !== opened.includes(g.artist)
  const flip = (g) => { opened = opened.includes(g.artist) ? opened.filter((x) => x !== g.artist) : [...opened, g.artist] }

  /** Allow all shown songs of a band – or, if all are allowed, block them again */
  function setBand(g) {
    const allOk = g.allowed === g.songs.length
    snapshot()
    const ids = new Set(g.songs.map((s) => s.id))
    const list = allowList()
    if (allOk) S.config.settings.kinderschutz.allow = list.filter((id) => !ids.has(id))
    else for (const id of ids) if (!allowSet.has(id)) list.push(id)
    changed()
    const songs = plural(g.songs.length, 'song', 'songs')
    toast(allOk ? t('{band}: {songs} blocked again', { band: g.artist, songs }) : t('{band}: {songs} allowed', { band: g.artist, songs }), { undo: true })
  }
  async function reindex() {
    try {
      await api('/api/liedtexte/update', { body: {} })
    } catch (e) {
      toast(e.message, { error: true })
      return
    }
    toast(t('Lyrics are being read in the background'))
    setTimeout(load, 4000)
  }
</script>

<Card title={t('Lyrics search & kid-safe mode')} icon="shield-check" guide="kinderschutz-liste">
  <p class="muted small">{t('Tuttiphon reads in all lyrics. This lets the search find songs by a line from the lyrics, and kid-safe mode detects explicit lyrics. You turn on kid-safe mode per person in their profile.')}</p>
  {#if data === null}
    <div class="skel h-[60px]"></div>
  {:else if data === false}
    <p class="err-t small">{t('The status could not be loaded.')}</p>
  {:else}
    <Row label={t('Lyrics read in')} hint={data.index.running ? t('Being read in right now …') : t('New ones are added on their own with every scan.')}>
      <div class="flex gap-3 items-center">
        <b>{data.index.songs == null ? '–' : fmt(data.index.songs)}</b>
        <button class="btn sm" disabled={data.index.running} onclick={reindex}><Icon name="refresh" size={15} />{t('Read in now')}</button>
      </div>
    </Row>
    <Row label={t('Kid-safe mode on for')} hint={t('Turn it on in the profile of the person concerned.')}>
      <span class="small">{data.persons.length ? data.persons.join(', ') : t('no one')}</span>
    </Row>
    <Row label={t('Detected as explicit')} hint={t('What you allow stays in, even with kid-safe mode.')} full>
      {#if !data.songs.length}
        <p class="muted small">{t('No songs with explicit lyrics detected.')}</p>
      {:else}
        <div class="grid grid-cols-1 gap-3">
          <div class="flex flex-wrap gap-2 items-center">
            <div class="search flex-1 min-w-[min(200px,100%)]">
              <Icon name="search" size={16} />
              <input placeholder={t('Search band, song or word …')} bind:value={q} aria-label={t('Search explicit songs')} oninput={() => { limit = 15; opened = [] }} />
            </div>
            <Seg options={[['alle', t('All')], ['gesperrt', t('Blocked')], ['erlaubt', t('Allowed')]]} bind:value={filter} /><!-- i18n-ignore: filter ids -->
          </div>
          <div class="tiny muted">
            {#if narrowed}{t('{shown} of {songs} · {bands}', { shown: fmt(shown), songs: plural(counts.songs, 'song', 'songs'), bands: plural(groups.length, 'band', 'bands') })}
            {:else}{t('{songs} by {bands} · {allowed} allowed', { songs: plural(counts.songs, 'song', 'songs'), bands: plural(counts.bands, 'band', 'bands'), allowed: fmt(counts.allowed) })}{/if}
          </div>
          {#if !groups.length}
            <p class="muted small">{t('Nothing found.')}</p>
          {/if}
          {#each groups.slice(0, limit) as g (g.artist)}
            {@const open = isOpen(g)}
            {@const allOk = g.allowed === g.songs.length}
            <div class="grid grid-cols-1 gap-1">
              <div class="flex gap-3 items-center">
                <button type="button" class="contents cursor-pointer" title={g.artist} aria-label={g.artist} onclick={() => openArtist(g.artist)}><Avatar name={g.artist} id={g.artistId} size={32} /></button>
                <button type="button" class="flex-1 min-w-0 text-left cursor-pointer flex items-center gap-2" aria-expanded={open} onclick={() => flip(g)}>
                  <span class="min-w-0 flex-1">
                    <span class="ell block font-semibold">{g.artist}</span>
                    <span class="tiny muted ell block">{plural(g.songs.length, 'song', 'songs')}{g.allowed ? t(' · {n} allowed', { n: fmt(g.allowed) }) : ''}{g.words.length ? ` · ${g.words.join(', ')}` : ''}</span>
                  </span>
                  <Icon name={open ? 'up' : 'down'} size={16} class="muted shrink-0" />
                </button>
                <button class="btn sm" class:primary={allOk} onclick={() => setBand(g)}>{#if allOk}<Icon name="check" size={14} />{t('all allowed')}{:else}{t('allow all')}{/if}</button>
              </div>
              {#if open}
                <div class="grid grid-cols-1 gap-0.5 pl-[44px] max-mobile:pl-3">
                  {#each g.songs as s (s.id)}
                    <div class="flex gap-3 items-center py-0.5">
                      <div class="flex-1 min-w-0">
                        <div class="ell">{s.title}</div>
                        <div class="tiny muted ell">{s.album}{#each s.words as [w, k] (w)}{' · '}{t('“{word}”', { word: w })}{k > 1 ? ` ×${k}` : ''}{/each}</div>
                      </div>
                      <button class="btn sm" class:primary={allowed(s.id)} onclick={() => toggle(s.id)}>
                        {#if allowed(s.id)}<Icon name="check" size={14} />{t('allowed')}{:else}{t('allow')}{/if}
                      </button>
                    </div>
                  {/each}
                </div>
              {/if}
            </div>
          {/each}
          {#if groups.length > limit}
            <button class="btn sm ghost justify-self-start" onclick={() => (limit += 30)}>{tn(Math.min(30, groups.length - limit), 'Show {n} more band', 'Show {n} more bands')}</button>
          {/if}
        </div>
      {/if}
    </Row>
  {/if}
</Card>
