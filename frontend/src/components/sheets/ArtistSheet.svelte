<!--
  Artist sheet: picture, albums, bio – and everywhere the band appears (music worlds, vibes, people, playlists),
  similar bands (Last.fm) and bands that sound alike (AI sound vectors, without the ones already listed).
  Opened via lib/artist.js → openArtist(name).
-->
<script>
  import Icon from '../Icon.svelte'
  import Glyph from '../Glyph.svelte'
  import Avatar from '../Avatar.svelte'
  import Cover from '../Cover.svelte'
  import Field from '../Field.svelte'
  import TrackList from '../TrackList.svelte'
  import { S, findWelt, isAdmin, ownPersons, snapshot, changed, MOODS } from '../../lib/state.svelte.js'
  import { closeSheet, toast } from '../../lib/overlay.svelte.js'
  import { api } from '../../lib/api.js'
  import { openArtist, startRadio } from '../../lib/artist.js'
  import { fmt, plural } from '../../lib/format.js'
  import { t, tn } from '../../lib/i18n.svelte.js'

  let { name } = $props()
  const admin = isAdmin()
  /** /api/artist – the state of the music worlds (ws.state) and vibes (a.stile) is kept up to date here */
  let a = $state(null)
  let error = $state(null)
  let clamped = $state(true)
  // If another band was opened in the meantime, this sheet is gone – the answer is dropped
  $effect(() => {
    let alive = true
    api(`/api/artist?name=${encodeURIComponent(name)}`)
      .then((r) => { if (alive) a = r })
      .catch((e) => { if (alive) error = e.message })
    return () => { alive = false }
  })

  const TG = 'inline-flex align-[-3px] mr-1.5'   // icon before a name (music world, vibe)
  const IN = (ws) => ws.state === 'manuell' || ws.state === 'automatisch'
  const persons = $derived(ownPersons())
  const tags = $derived(a ? (a.tags || []).filter((tag) => !a.genres.some(([g]) => g.toLowerCase() === tag)).slice(0, 5) : [])
  // Tooltip per state of a band in a music world (the keys are stored states)
  const STATE_TIP = $derived({ manuell: t('included'), automatisch: t('automatically included'), herausgenommen: t('taken out') })
  const inWelten = $derived(a && !admin ? a.welten.filter(IN).map((ws) => findWelt(ws.id)).filter(Boolean) : [])
  const stile = $derived(S.config.stile.filter((s) => s.kind !== 'season' && ['Genre', 'Thema'].includes(s.group)))
  // bands that sound alike (AI) – those already under “Similar bands” are not repeated
  const soundsLike = $derived(a ? (a.soundsLike || []).filter((x) => !a.similar.some((y) => y.name === x.name)) : [])

  // Music worlds: click = add / take out
  function toggleWelt(ws, w) {
    snapshot()
    w.artists ??= []
    w.excludedArtists ??= []
    if (ws.state === 'manuell') { w.artists = w.artists.filter((x) => x !== a.name); ws.state = null }
    else if (ws.state === 'automatisch') { w.excludedArtists.push(a.name); ws.state = 'herausgenommen' }
    else if (ws.state === 'herausgenommen') { w.excludedArtists = w.excludedArtists.filter((x) => x !== a.name); ws.state = 'automatisch' }
    else { w.artists.push(a.name); ws.state = 'manuell' }
    changed()
    const v = { artist: a.name, world: w.name }
    toast(ws.state === 'manuell' ? t('{artist}: {world} – added', v)
      : ws.state === 'automatisch' ? t('{artist}: {world} – automatically included again', v)
        : ws.state === 'herausgenommen' ? t('{artist}: {world} – taken out', v)
          : t('{artist}: {world} – removed', v), { undo: true })
  }

  // Vibes (only for artists whose genres are missing or do not fit)
  function toggleStil(s) {
    snapshot()
    s.artists ??= []
    if (a.stile.includes(s.id)) { s.artists = s.artists.filter((x) => x !== a.name); a.stile = a.stile.filter((x) => x !== s.id) }
    else { s.artists.push(a.name); a.stile.push(s.id) }
    changed()
  }

  const likes = (p) => !!p.likes?.artists?.includes(a.name)
  const hates = (p) => !!p.dislikes?.artists?.includes(a.name)
  function setLike(p, kind) {
    const wasLike = likes(p), wasHate = hates(p)
    snapshot()
    p.likes ??= { welten: [], stile: [], artists: [] }
    p.dislikes ??= { artists: [], genres: [] }
    p.likes.artists = (p.likes.artists || []).filter((x) => x !== a.name)
    p.dislikes.artists = (p.dislikes.artists || []).filter((x) => x !== a.name)
    if (kind === 'like' && !wasLike) p.likes.artists.push(a.name)
    if (kind === 'hate' && !wasHate) p.dislikes.artists.push(a.name)
    changed()
  }

  const pct = (v) => `${Math.round((v || 0) * 100)} %`
</script>

{#snippet kv(value, label)}
  <div class="grid"><b class="text-[1.25rem]">{value}</b><span class="text-[.78rem] text-muted">{label}</span></div>
{/snippet}

<div class="grid gap-[22px]">
  {#if error}
    <div class="empty">{error}</div>
  {:else if !a}
    <div class="grid justify-items-center gap-3 text-center pt-1.5">
      <Avatar {name} size={150} />
      <h1>{name}</h1>
      <div class="muted">{t('loading …')}</div>
    </div>
  {:else}
    <div class="grid justify-items-center gap-3 text-center pt-1.5">
      <Avatar name={a.name} id={a.id} size={150} />
      <h1>{a.name}</h1>
      <div class="muted">
        {plural(a.songs, 'song', 'songs')} · {plural(a.albums.length, 'album', 'albums')}{a.rating ? ` · Ø ${'★'.repeat(Math.round(a.rating)) || '–'}` : ''}{a.plays ? ` · ${t('{n}× played', { n: fmt(a.plays) })}` : ''}
      </div>
      <div class="btns justify-center">
        {#each a.genres as [g]}<span class="pill">{g}</span>{/each}
        {#each tags as tag}<span class="pill" title={t('Tag from Last.fm')}>{tag}</span>{/each}
        {#each a.scenes as s}<span class="pill acc">{s}</span>{/each}
      </div>
      <div class="btns justify-center mt-1.5">
        <button class="btn primary sm" onclick={() => startRadio(a.name)}><Icon name="radio" size={16} />{t('Start radio')}</button>
      </div>
    </div>

    {#if a.top?.length}
      <Field label={t('Popular songs')}>
        <TrackList tracks={a.top} from={a.name} compact />
      </Field>
    {/if}

    {#if a.bio}
      <div>
        <p class="text-text-2 text-[.9rem] leading-[1.6]" class:line-clamp-4={clamped}>{a.bio}</p>
        <button class="link" onclick={() => (clamped = !clamped)}>{clamped ? t('read more') : t('less')}</button>
      </div>
    {/if}

    {#if a.albums.length}
      <Field label={t('Albums')}>
        <div class="grid grid-flow-col auto-cols-[120px] gap-3 overflow-x-auto pb-1.5">
          {#each a.albums as al, i (i)}
            <div class="grid gap-1.5 text-[.8rem]">
              <Cover id={al.cover} size={120} class="rounded-[10px]" />
              <b class="ell">{al.name}</b>
              <span class="muted tiny">{al.year || ''} · {plural(al.mine, 'song', 'songs')}</span>
            </div>
          {/each}
        </div>
      </Field>
    {/if}

    <!-- users only see where the band is included -->
    {#if inWelten.length}
      <Field label={t('Belongs to')}>
        <div class="toggles">
          {#each inWelten as w (w.id)}
            <a class="toggle" href="#/welt/{w.id}" onclick={() => closeSheet()}><Glyph value={w.icon} size={15} class={TG} />{w.name}</a>
          {/each}
        </div>
      </Field>
    {/if}

    {#if admin}
      <Field label={t('In which music worlds?')}>
        <div class="toggles">
          {#each a.welten as ws (ws.id)}
            {@const w = findWelt(ws.id)}
            {#if w}
              <button class="toggle" class:on={IN(ws)} onclick={() => toggleWelt(ws, w)}
                title={STATE_TIP[ws.state] || t('not included')}>
                <Glyph value={w.icon} size={15} class={TG} />{w.name}
                {#if ws.state === 'automatisch'}<span class="n">{t('auto')}</span>{/if}
                {#if ws.state === 'herausgenommen'}<span class="n">{t('out')}</span>{/if}
              </button>
            {/if}
          {/each}
        </div>
        <div class="hint">{t('Tapping adds or takes out the band. “auto” = recognized automatically via the scene.')}</div>
      </Field>

      <details class="fold">
        <summary>
          {t('Assign vibes')}
          <span class="muted small font-medium">{a.stile.length ? t('· {n} assigned', { n: a.stile.length }) : t('· only needed without matching genre tags')}</span>
        </summary>
        <div class="in">
          <div class="toggles">
            {#each stile as s (s.id)}
              <button class="toggle" class:on={a.stile.includes(s.id)} onclick={() => toggleStil(s)}><Glyph value={s.icon} size={15} class={TG} />{s.name}</button>
            {/each}
          </div>
        </div>
      </details>
    {/if}

    <!-- people (users: only their own) -->
    <Field label={admin ? t('People') : persons.length === 1 ? t('Do you like the band?') : t('Your profiles')}>
      <div class="grid gap-2">
        {#each persons as p (p.id)}
          <div class="member-row">
            <span class="hi"><Glyph value={p.icon || 'user'} size={18} /></span>
            <b class="flex-1">{p.name}</b>
            <button class="toggle" class:on={likes(p)} onclick={() => setLike(p, 'like')}><Icon name="heart" size={15} />{t('Favorite')}</button>
            <button class="toggle no" class:on={hates(p)} onclick={() => setLike(p, 'hate')}><Icon name="ban" size={15} />{t('never')}</button>
          </div>
        {/each}
      </div>
      {#if !admin}<div class="hint">{t('“Favorite”: shows up more often in your mixes. “never”: never gets into your playlists.')}</div>{/if}
    </Field>

    {#if a.sound}
      <Field label={t('Sound')}>
        <div class="grid gap-2.5 p-3.5 rounded-card bg-surface-2">
          <div class="grid grid-cols-[repeat(auto-fit,minmax(90px,1fr))] gap-2.5">
            {#if a.sound.bpm}{@render kv(`≈ ${Math.round(a.sound.bpm)}`, 'BPM')}{/if}
            {@render kv(pct(a.sound.energy), t('Energy'))}
            {@render kv(pct(a.sound.dance), t('Danceability'))}
            {@render kv(pct(a.sound.valence), t('Mood'))}
          </div>
          {#if a.sound.moods.length}
            <div class="btns">{#each a.sound.moods as m}<span class="pill acc">{MOODS[m] || m}</span>{/each}</div>
          {/if}
          {#if a.sound.styles?.length}
            <div class="small"><span class="muted">{t('Sounds like:')}</span> {a.sound.styles.join(' · ')}</div>
          {/if}
          <div class="hint">{tn(a.sound.songs, 'from the sound analysis of {n} song', 'from the sound analysis of {n} songs')}</div>
        </div>
      </Field>
    {/if}

    {#if a.playlists.length}
      <Field label={admin ? t('In your playlists') : t('In these playlists')}>
        <div class="grid gap-1.5">
          {#each a.playlists as p (p.id)}
            <a class="member-row no-underline" href="#/playlist/{encodeURIComponent(p.id)}" onclick={() => closeSheet()}>
              <Icon name="playlists" size={18} /><span class="flex-1">{p.name}</span><span class="muted small">{plural(p.songs, 'song', 'songs')}</span>
            </a>
          {/each}
        </div>
      </Field>
    {/if}

    {#if a.similar.length}
      <Field label={t('Similar bands in your library')}>
        <div class="agrid">
          {#each a.similar as s (s.name)}
            <button class="acard" onclick={() => openArtist(s.name)}><Avatar name={s.name} id={s.id} size={72} /><div class="nm">{s.name}</div></button>
          {/each}
        </div>
      </Field>
    {/if}

    {#if soundsLike.length}
      <Field label={t('Sounds like these bands')}>
        <div class="agrid">
          {#each soundsLike as s (s.name)}
            <button class="acard" onclick={() => openArtist(s.name)}><Avatar name={s.name} id={s.id} size={72} /><div class="nm">{s.name}</div></button>
          {/each}
        </div>
        <div class="hint">{t('By the sound of the songs – recognized by the AI sound analysis.')}</div>
      </Field>
    {/if}

    {#if a.missing?.length}
      <Field label={t('Similar bands you are still missing')}>
        <div class="toggles">
          {#each a.missing as [m]}
            <a class="toggle" href="https://www.last.fm/music/{encodeURIComponent(m)}" target="_blank" rel="noopener">{m}<Icon name="external" size={13} /></a>
          {/each}
        </div>
        <div class="hint">{admin ? t('According to Last.fm – to listen in or for Lidarr.') : t('According to Last.fm – tap to listen in.')}</div>
      </Field>
    {/if}

    {#if !a.lastfm && admin}
      <div class="note">{t('With a Last.fm key under Settings → Intelligence you get tags here, more accurate similar bands and bands you are still missing.')}</div>
    {/if}
  {/if}
</div>
