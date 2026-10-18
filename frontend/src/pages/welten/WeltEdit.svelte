<!--
  Edit a music world (administrators): header with name/icon, bands, suggestions, taken-out bands,
  playlists, scene & settings, fine-tuning. w: world from S.config · d: response of /api/welt ·
  loads: counts reloads (afterwards “Add band” is a button again).
-->
<script>
  import { untrack } from 'svelte'
  import Icon from '../../components/Icon.svelte'
  import Avatar from '../../components/Avatar.svelte'
  import Collage from '../../components/Collage.svelte'
  import Section from '../../components/Section.svelte'
  import Field from '../../components/Field.svelte'
  import Select from '../../components/Select.svelte'
  import Switch from '../../components/Switch.svelte'
  import ChipEditor from '../../components/ChipEditor.svelte'
  import ArtistPicker from '../../components/ArtistPicker.svelte'
  import GlyphButton from '../../components/GlyphButton.svelte'
  import PlaylistCard from '../../components/PlaylistCard.svelte'
  import { S, changed, snapshot, weltIds } from '../../lib/state.svelte.js'
  import { confirmDialog, modal, toast } from '../../lib/overlay.svelte.js'
  import { api } from '../../lib/api.js'
  import { go } from '../../lib/router.svelte.js'
  import { openArtist } from '../../lib/artist.js'
  import { fmt, plural } from '../../lib/format.js'
  import { t, tn } from '../../lib/i18n.svelte.js'
  import { genreSuggestions } from '../../lib/richtungen.js'
  import { narrowsLibrary } from '../../lib/sound.svelte.js'

  let { w, d, loads } = $props()

  // create missing lists (separate statements – see the proxy trap in frontend/README.md)
  untrack(() => {
    w.artists ??= []
    w.excludedArtists ??= []
    w.albums ??= []
    w.genres ??= []
    w.excludeTitles ??= []
    w.excludeAlbums ??= []
  })

  const RATINGS = $derived([['0', t('any')], ['1', '★'], ['2', '★★'], ['3', '★★★'], ['4', '★★★★'], ['5', '★★★★★']])

  /** Change with an undo point; msg → notice with “Undo” */
  function mutate(fn, msg = null) {
    snapshot()
    fn()
    changed()
    if (msg) toast(msg, { undo: true })
  }

  /* “Rebuild”: only for worlds with a scene that were changed by hand or are named differently than in the catalog */
  const RESET_KEYS = ['artists', 'excludedArtists', 'albums', 'genres']
  const resettable = $derived(!!d.scene && (RESET_KEYS.some((k) => w[k]?.length) || w.name !== d.scene.name || w.icon !== d.scene.icon))
  let preview = $state.raw(null)
  const names = (list) => (list.length > 10 ? t('{names} and {n} more', { names: list.slice(0, 10).join(', '), n: list.length - 10 }) : list.join(', '))

  async function rebuild() {
    try {
      preview = await api(`/api/welt/neu?id=${encodeURIComponent(w.id)}`)   // i18n-ignore: API route
    } catch (e) {
      toast(e.message, { error: true })
      return
    }
    const ok = await modal({ title: t('Rebuild “{name}”?', { name: w.name }), body: rebuildBody,
      buttons: [{ label: t('Cancel'), value: false }, { label: t('Rebuild'), value: true, primary: true }] })
    if (!ok) return
    const p = preview
    mutate(() => {
      for (const k of RESET_KEYS) w[k] = []
      w.autoScene = true
      w.name = p.name
      w.icon = p.icon
    }, t('“{name}” rebuilt', { name: p.name }))
  }

  const sugg = $derived(d.similar.filter((x) => !w.excludedArtists.includes(x.artist)))
  const linkedElsewhere = $derived(new Set(S.config.welten.filter((x) => x !== w).map((x) => x.scene)))
  const sceneOptions = $derived([['', t('— none —')], ...(S.library?.scenes || []).map((s) =>
    [s.id, linkedElsewhere.has(s.id)
      ? t('{name} · {n} in your library – already taken', { name: s.name, n: s.present.length })
      : t('{name} · {n} in your library', { name: s.name, n: s.present.length })])])
  const playlists = $derived(d.playlists.map((p) => S.config.playlists.find((x) => x.id === p.id) || p))

  // “Add band”: the card turns into an artist search (with the cursor in it) – until the data is reloaded
  let adding = $state(false)
  $effect(() => {
    loads
    untrack(() => (adding = false))
  })
  function startAdding() {
    adding = true
  }
  const focusSearch = (box) => { box.querySelector('input')?.focus() }

  function removeBand(m) {
    mutate(() => {
      if (m.auto) w.excludedArtists.push(m.name)
      else w.artists = w.artists.filter((x) => x !== m.name)
    }, t('{name} taken out', { name: m.name }))
  }
  function addBand(a) {
    mutate(() => {
      w.excludedArtists = w.excludedArtists.filter((x) => x !== a)
      w.artists.push(a)
    }, t('{name} added', { name: a }))
  }
  /** Keyboard for the band cards (they contain their own remove button) */
  const keyOpen = (e, name) => {
    if (e.target === e.currentTarget && (e.key === 'Enter' || e.key === ' ')) { e.preventDefault(); openArtist(name) }
  }

  /** Do not create a catalog world again on its own once it was deleted or unlinked */
  function forgetScene(scene) {
    if (!scene) return
    S.config.dismissed ??= []
    if (!S.config.dismissed.includes(`scene|${scene}`)) S.config.dismissed.push(`scene|${scene}`)
  }

  async function deleteWelt() {
    const n = d.playlists.filter((p) => p.status === 'aktiv').length
    if (!await confirmDialog(t('Delete “{name}”?', { name: w.name }), n ? tn(n, '{n} playlist uses this music world – it moves to the trash.', '{n} playlists use this music world – they move to the trash.') : t('No playlist uses this music world.'), t('Delete'), true)) return
    snapshot()
    S.config.playlists.forEach((p) => {
      if (!weltIds(p).includes(w.id)) return
      const rest = weltIds(p).filter((x) => x !== w.id)
      p.welt = rest.length ? (rest.length === 1 ? rest[0] : rest) : '*'
      if (rest.length) return   // other worlds remain – so does the playlist
      p.status = 'papierkorb'
      if ((p.stil || '*') === '*' && !p.fav && !p.review && !p.together && !p.radio && !narrowsLibrary(p.sound)) p.stil = S.config.stile[0].id
    })
    const name = w.name
    forgetScene(w.scene)
    S.config.welten = S.config.welten.filter((x) => x !== w)
    changed()
    toast(t('“{name}” deleted', { name }), { undo: true })
    go('#/welten')
  }
</script>

{#snippet rebuildBody()}
  {#if preview}
    <div class="grid gap-2.5 text-[.92rem] leading-[1.5]">
      <p class="muted">{t('The bands then come only from the scene, and so do the name and icon: “{name}”. Excluded titles, stars and the other fine-tuning stay.', { name: preview.name })}</p>
      <p><b>{t('{before} → {after} bands', { before: fmt(preview.before), after: fmt(preview.after) })}</b></p>
      {#if preview.dropped.length}
        <p><b>{t('No longer included:')}</b> {t('{names}. They can get a music world of their own.', { names: names(preview.dropped) })}</p>
      {/if}
      {#if preview.added.length}<p><b>{t('Newly included:')}</b> {names(preview.added)}</p>{/if}
      {#if preview.renamed.length}
        <p class="warn-t">{tn(preview.renamed.length, 'One playlist will then have a different name, also in Symfonium: {list}', '{n} playlists will then have different names, also in Symfonium: {list}',
          { list: preview.renamed.slice(0, 3).map(([a, b]) => t('“{from}” → “{to}”', { from: a, to: b })).join(', ') + (preview.renamed.length > 3 ? ' …' : '') })}</p>
      {/if}
    </div>
  {/if}
{/snippet}

<a href="#/welten" class="link inline-flex gap-1.5 items-center mt-2.5 mb-3.5"><Icon name="left" size={16} />{t('All music worlds')}</a>

<div class="hero">
  <div class="hero-bg" style:background-image={d.artists[0]?.[2] ? `url(/img/ar-${d.artists[0][2]}?s=300)` : undefined}></div>
  <div class="hero-row items-center">
    <div class="w-[180px]"><Collage artists={d.artists} /></div>
    <div class="hero-text">
      <div class="eyebrow">{t('Music world')}</div>
      <div class="flex gap-2.5 items-center flex-wrap">
        <GlyphButton value={w.icon} size={30} onpick={(v) => mutate(() => (w.icon = v))} />
        <input class="input text-[1.6rem] font-extrabold bg-transparent border-transparent px-2 py-1 -ml-2 max-w-full" value={w.name} aria-label={t('Name')}
          onchange={(e) => { const v = e.currentTarget.value.trim(); mutate(() => (w.name = v || w.name)); e.currentTarget.value = w.name }} />
      </div>
      <div class="hero-meta">
        <span><b>{fmt(d.memberList.length)}</b> {d.memberList.length === 1 ? t('band') : t('bands')}</span>
        <span><b>{fmt(d.songs)}</b> {d.songs === 1 ? t('song') : t('songs')}</span>
        {#if d.scene && w.autoScene && !w.auto}<span class="pill acc"><Icon name="sparkles" size={13} />{t('Scene: {name}', { name: d.scene.name })}</span>{/if}
        {#if w.separate}<span class="pill">{t('separate world')}</span>{/if}
        {#if w.auto}<span class="pill acc"><Icon name="sparkles" size={13} />{t('created by Tuttiphon')}</span>{/if}
      </div>
      <div class="btns mt-2">
        <a class="btn white" href="#/neu?welt={w.id}&step=2"><Icon name="plus" size={17} />{t('Playlist from this world')}</a><!-- i18n-ignore: route -->
        {#if resettable}
          <button class="btn" title={t('Take bands, name and icon entirely from the scene again')} onclick={rebuild}><Icon name="wand" size={17} />{t('Rebuild')}</button>
        {/if}
        <button class="btn icon danger" title={t('Delete music world')} aria-label={t('Delete music world')} onclick={deleteWelt}><Icon name="trash" size={18} /></button>
      </div>
    </div>
  </div>
</div>

<Section title={t('Bands · {n}', { n: d.memberList.length })}>
  <p class="muted small -mt-1.5 mb-3.5">{d.scene && w.autoScene
    ? t('“auto” = found on its own, matching {scene}. × takes a band out.', { scene: d.scene.name })
    : t('× removes a band. Tip: with a scene further down, typical bands are added automatically.')}</p>
  <div class="agrid">
    {#each d.memberList as m (m.name)}
      <div class="acard" role="button" tabindex="0" onclick={() => openArtist(m.name)} onkeydown={(e) => keyOpen(e, m.name)}>
        <Avatar name={m.name} id={m.id} size={84} />
        {#if m.auto}<span class="pill acc tag">{t('auto')}</span>{/if}
        <div class="nm">{m.name}</div>
        <div class="sub">{plural(m.songs, 'song', 'songs')}</div>
        <button class="btn icon sm rm" title={m.auto ? t('Take out of this world') : t('Remove')} aria-label={m.auto ? t('Take out of this world') : t('Remove')}
          onclick={(e) => { e.stopPropagation(); removeBand(m) }}><Icon name="x" size={15} /></button>
      </div>
    {/each}
    {#if adding}
      <div class="col-span-2 self-center" {@attach focusSearch}>
        <ArtistPicker placeholder={t('Search for a band …')} exclude={() => d.memberList.map((m) => m.name)} onpick={addBand} />
      </div>
    {:else}
      <button class="acard add" onclick={startAdding}>
        <div class="av size-[84px]"><Icon name="plus" size={30} /></div>
        <div class="nm">{t('Add band')}</div>
      </button>
    {/if}
  </div>
</Section>

{#if sugg.length}
  <Section title={t('Might fit too')}>
    <p class="muted small -mt-1.5 mb-3.5">{t('Similar genres – not in any music world yet. Tap one to add it.')}</p>
    <div class="agrid">
      {#each sugg as x (x.artist)}
        <button class="acard ghost" title={t('{pct}% similar', { pct: Math.round(x.score * 100) })} onclick={() => mutate(() => w.artists.push(x.artist), t('{name} added', { name: x.artist }))}>
          <Avatar name={x.artist} id={x.id} size={72} />
          <div class="nm">{x.artist}</div>
          <div class="sub">{x.genres.slice(0, 2).join(', ')}</div>
          <span class="pill acc"><Icon name="plus" size={12} />{t('add')}</span>
        </button>
      {/each}
    </div>
  </Section>
{/if}

{#if d.excluded.length}
  <Section title={t('Taken out')}>
    <div class="btns">
      {#each d.excluded as x (x.name)}
        <span class="chip has-av"><Avatar name={x.name} id={x.id} size={24} />{x.name}<button class="x" title={t('add back')} aria-label={t('add back')}
          onclick={() => mutate(() => (w.excludedArtists = w.excludedArtists.filter((y) => y !== x.name)), t('{name} back in', { name: x.name }))}>↺</button></span>
      {/each}
    </div>
  </Section>
{/if}

{#if d.playlists.length}
  <Section title={t('Playlists with this world')}>
    <div class="g-pl">{#each playlists as p (p.id)}<PlaylistCard {p} />{/each}</div>
  </Section>
{/if}

<div class="g-2 section">
  <div class="card">
    <div class="card-head"><h2><span class="hi"><Icon name="sparkles" size={18} /></span>{t('Scene')}</h2></div>
    <p class="muted small mb-3">{d.scene ? d.scene.description : t('With a scene, the world knows the typical bands and adds them automatically.')}</p>
    <div class="frow">
      <label class="f">{t('Scene')}
        <Select options={sceneOptions} value={w.scene || ''} onchange={(v) => mutate(() => { if (w.scene !== v) forgetScene(w.scene); w.scene = v || null; w.autoScene = !!v })} />
      </label>
    </div>
    {#if w.scene}
      <div class="mt-3"><Switch checked={!!w.autoScene} onchange={(v) => mutate(() => (w.autoScene = v))} label={t('add matching bands automatically')} /></div>
      <div class="hint mt-1.5">{t('The scene’s typical bands and bands that match by genres, Last.fm, AI music style, language and decade – new ones too.')}</div>
    {/if}
  </div>
  <div class="card">
    <div class="card-head"><h2><span class="hi"><Icon name="settings" size={18} /></span>{t('Settings')}</h2></div>
    <div class="frow">
      <label class="f">{t('Minimum rating')}
        <Select options={RATINGS} value={w.minRating ?? 0} onchange={(v) => mutate(() => (w.minRating = Number(v)))} />
      </label>
      <label class="f">{t('Minimum length in seconds')}
        <input class="input" type="number" min="0" step="5" value={w.minDuration ?? ''} placeholder={String(S.config.settings.minDuration ?? '')}
          onchange={(e) => { const v = e.currentTarget.value; mutate(() => (w.minDuration = v === '' ? null : Number(v))) }} />
      </label>
    </div>
    <div class="mt-3.5"><Switch checked={!!w.separate} onchange={(v) => mutate(() => (w.separate = v))} label={t('Separate world – don’t mix into “All” playlists')} /></div>
  </div>
</div>

<details class="fold section">
  <summary><Icon name="sliders" size={18} />{t('Advanced: album series, genres, exclusions')}</summary>
  <div class="in">
    <Field label={t('Albums whose name contains this – e.g. compilation series like “Unter meinem Bett”')}><ChipEditor items={w.albums} /></Field>
    <Field label={t('Genre contains – all songs with this genre belong to it')}><ChipEditor items={w.genres} suggestions={genreSuggestions()} placeholder={t('e.g. {example}', { example: 'Children' })} /></Field>
    <Field label={t('Exclude titles that contain this')}><ChipEditor items={w.excludeTitles} /></Field>
    <Field label={t('Exclude albums that contain this')}><ChipEditor items={w.excludeAlbums} /></Field>
  </div>
</details>
