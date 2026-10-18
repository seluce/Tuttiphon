<!-- Vibes: what plays (genres, topics, seasons, decades, special) – plus assigning artists without genre tags. -->
<script>
  import Icon from '../components/Icon.svelte'
  import Glyph from '../components/Glyph.svelte'
  import Avatar from '../components/Avatar.svelte'
  import PageHead from '../components/PageHead.svelte'
  import Section from '../components/Section.svelte'
  import StilSheet from '../components/sheets/StilSheet.svelte'
  import { S, findStil, changed, snapshot, weltIds } from '../lib/state.svelte.js'
  import { openSheet, closeSheet, confirmDialog, toast } from '../lib/overlay.svelte.js'
  import { openArtist } from '../lib/artist.js'
  import { slug, plural } from '../lib/format.js'
  import { t, tn } from '../lib/i18n.svelte.js'
  import { GROUP_LABEL, GROUP_TEXT, stilGroups, summary } from '../lib/richtungen.js'

  const groups = $derived(stilGroups()
    .map((g) => ({ g, list: S.config.stile.filter((s) => (s.group || 'Sonstiges') === g) }))   // i18n-ignore: stored value
    .filter((x) => x.list.length))
  const used = (id) => S.config.playlists.filter((p) => p.stil === id && (p.status || 'aktiv') === 'aktiv').length
  const untagged = $derived(S.library?.untagged || [])
  /** Vibes that artists can be assigned to directly */
  const assignable = $derived(S.config.stile.filter((s) => s.kind !== 'season' && ['Genre', 'Thema'].includes(s.group)))   // i18n-ignore: stored values

  /** Vibe being edited in the side sheet (for the footer) */
  let editing = $state.raw(null)

  function openStil(s) {
    s.excludeElsewhere ??= { albums: [], titles: [], genres: [] }
    s.filters ??= {}
    for (const k of ['genres', 'artists', 'albums', 'titles']) s[k] ??= []
    editing = s
    openSheet({ title: s.name, wide: true, component: StilSheet, props: { s }, foot: stilFoot })
  }

  async function deleteStil(s) {
    const n = S.config.playlists.filter((p) => p.stil === s.id && p.status !== 'papierkorb').length
    if (!await confirmDialog(t('Delete “{name}”?', { name: s.name }), n ? tn(n, '{n} playlist uses this vibe – it moves to the trash.', '{n} playlists use this vibe – they move to the trash.') : t('No playlist uses this vibe.'), t('Delete'), true)) return
    snapshot()
    S.config.playlists.forEach((p) => {
      if (p.stil !== s.id) return
      p.status = 'papierkorb'
      p.stil = '*'
      if (!weltIds(p).length) p.welt = S.config.welten[0]?.id ?? '*'   // without any music world: all music
    })
    S.config.stile = S.config.stile.filter((x) => x !== s)
    changed()
    closeSheet()
    toast(t('“{name}” deleted', { name: s.name }), { undo: true })
  }

  function addStil() {
    const name = prompt(t('Name of the new vibe, e.g. “Acoustic covers”:'))
    if (!name) return
    let id = slug(name)
    while (findStil(id)) id += '-2'
    snapshot()
    S.config.stile.push({ id, name, icon: 'i:music', group: 'Thema', kind: 'normal', genres: [], artists: [], albums: [], titles: [],   // i18n-ignore: stored group
      excludeElsewhere: { albums: [], titles: [], genres: [] }, season: null, filters: {} })
    changed()
    openStil(S.config.stile.at(-1))
  }

  function assign(artist, e) {
    const s = findStil(e.currentTarget.value)
    e.currentTarget.value = ''
    if (!s) return
    snapshot()
    s.artists ??= []
    s.artists.push(artist)
    changed()
    toast(`${artist} → ${s.name}`, { undo: true })
  }
</script>

{#snippet stilFoot()}
  {#if editing}
    <button class="btn primary" onclick={closeSheet}>{t('Done')}</button>
    <a class="btn" href="#/neu?stil={editing.id}&step=1" onclick={closeSheet}>{t('Create a playlist with it')}</a><!-- i18n-ignore: route -->
    <button class="btn danger ml-auto" onclick={() => deleteStil(editing)}><Icon name="trash" size={16} />{t('Delete')}</button>
  {/if}
{/snippet}

<div class="page">
  <PageHead title={t('Vibes')} sub={t('A vibe says what plays. A song fits if any of its rules matches. Combined with a music world, it makes a playlist – e.g. Kids × Rock.')}>
    {#snippet actions()}
      <button class="btn primary" onclick={addStil}><Icon name="plus" size={18} />{t('New vibe')}</button>
    {/snippet}
  </PageHead>

  {#each groups as { g, list } (g)}
    <Section title={GROUP_LABEL[g] ?? g}>
      {#if GROUP_TEXT[g]}<p class="muted small -mt-1.5 mb-3.5">{GROUP_TEXT[g]}</p>{/if}
      <div class="grid grid-cols-[repeat(auto-fill,minmax(240px,1fr))] gap-3">
        {#each list as s (s.id)}
          {@const n = used(s.id)}
          <button class="scard grid-cols-[52px_minmax(0,1fr)] text-left cursor-pointer text-inherit" onclick={() => openStil(s)}>
            <div class="size-[52px] rounded-[14px] grid place-items-center bg-surface-2 text-accent"><Glyph value={s.icon || 'music'} size={24} /></div>
            <div class="min-w-0">
              <div class="t">{s.name}</div>
              <div class="w">{summary(s)}</div>
              {#if n}<div class="tiny muted mt-1">{plural(n, 'playlist', 'playlists')}</div>{/if}
            </div>
          </button>
        {/each}
      </div>
    </Section>
  {/each}

  {#if untagged.length}
    <Section title={t('Bands without genre tags')}>
      <p class="muted small -mt-1.5 mb-3.5">{t('These bands don’t show up in genre vibes otherwise. Assign them directly – e.g. herrH → Rock & Punk.')}</p>
      <div class="agrid">
        {#each untagged as x (x.artist)}
          {@const mine = S.config.stile.filter((s) => (s.artists || []).includes(x.artist))}
          <div class="acard">
            <button type="button" class="cursor-pointer" title={x.artist} aria-label={t('View {name}', { name: x.artist })} onclick={() => openArtist(x.artist)}>
              <Avatar name={x.artist} id={x.id} size={72} />
            </button>
            <div class="nm">{x.artist}</div>
            <div class="sub">{mine.length ? mine.map((s) => s.name).join(', ') : plural(x.songs, 'song', 'songs')}</div>
            <select class="text-[.8rem] px-2 py-[5px] w-full" aria-label={t('Vibe for {name}', { name: x.artist })} onchange={(e) => assign(x.artist, e)}>
              <option value="">{mine.length ? t('+ more …') : t('+ vibe …')}</option>
              {#each assignable.filter((s) => !mine.includes(s)) as s (s.id)}<option value={s.id}>{s.name}</option>{/each}
            </select>
          </div>
        {/each}
      </div>
    </Section>
  {/if}
</div>
