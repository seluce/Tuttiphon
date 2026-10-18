<!-- Playlist overview: grid per person, shared, paused, handmade (takeover) and trash. -->
<script module>
  // Filter and search are kept when coming back
  const remember = { filter: 'alle', query: '' }   // i18n-ignore: filter id
</script>

<script>
  import Icon from '../components/Icon.svelte'
  import Glyph from '../components/Glyph.svelte'
  import PageHead from '../components/PageHead.svelte'
  import Section from '../components/Section.svelte'
  import Empty from '../components/Empty.svelte'
  import Mosaic from '../components/Mosaic.svelte'
  import PersonAvatar from '../components/PersonAvatar.svelte'
  import PlaylistCard from '../components/PlaylistCard.svelte'
  import { S, isAdmin, ownPersons, canEdit, defaultPerson, plStatus, loadPlaylists } from '../lib/state.svelte.js'
  import { openTakeover } from '../lib/takeover.js'
  import { purgeAll } from './playlist/actions.js'
  import { plural } from '../lib/format.js'
  import { t } from '../lib/i18n.svelte.js'

  const admin = isAdmin()
  let filter = $state(remember.filter)
  let query = $state(remember.query)
  $effect(() => { remember.filter = filter; remember.query = query })

  const mineP = $derived(ownPersons())
  // Users: other people who share playlists with them (the server only sends what is shared)
  const others = $derived(admin ? [] : S.config.personen.filter((p) => !mineP.includes(p) && S.config.playlists.some((x) => x.person === p.id)))
  $effect(() => {
    if (filter !== 'alle' && filter !== 'geteilt' && !mineP.some((p) => p.id === filter)) filter = 'alle'   // person deleted in the meantime (i18n-ignore: filter id)
    if (filter === 'geteilt' && !others.length) filter = 'alle'   // i18n-ignore: filter id
  })

  const q = $derived(query.toLowerCase())
  const nameOf = (p) => (plStatus(p.id)?.name || p.name || p.id).toLowerCase()
  const personOf = (p) => p.person || defaultPerson()
  const pls = $derived(S.config.playlists.filter((p) =>
    (filter === 'alle' || filter === 'geteilt' || personOf(p) === filter) && (!q || nameOf(p).includes(q))))   // i18n-ignore: filter id
  const isActive = (p) => (p.status || 'aktiv') === 'aktiv'

  const ownGroups = $derived(filter === 'geteilt' ? [] : mineP
    .filter((person) => filter === 'alle' || filter === person.id)   // i18n-ignore: filter id
    .map((person) => ({ person, list: pls.filter((p) => personOf(p) === person.id && isActive(p)) }))
    .filter((g) => g.list.length || !q))
  const sharedGroups = $derived(filter === 'alle' || filter === 'geteilt'   // i18n-ignore: filter id
    ? others.map((person) => ({ person, list: pls.filter((p) => p.person === person.id && isActive(p)) })).filter((g) => g.list.length)
    : [])
  const paused = $derived(pls.filter((p) => p.status === 'pausiert' && canEdit(p)))
  const hand = $derived(filter === 'alle' ? (S.pl?.handmade || []).filter((x) => !q || x.name.toLowerCase().includes(q)) : [])   // i18n-ignore: filter id
  const trash = $derived(pls.filter((p) => p.status === 'papierkorb' && canEdit(p)))
  const nothing = $derived(!ownGroups.length && !sharedGroups.length && !paused.length && !hand.length && !trash.length)

  if (!S.pl) loadPlaylists().catch(() => {})
</script>

{#snippet personHead(person, title, sub)}
  <div class="flex gap-3 items-center">
    <PersonAvatar p={person} size={36} />
    <div><h2>{title}</h2><div class="muted tiny">{sub}</div></div>
  </div>
{/snippet}

<div class="page">
  <PageHead title={admin ? t('Playlists') : t('My playlists')} sub={admin
    ? t('Everything Tuttiphon looks after for you. Navidrome reshuffles smart playlists on every request – paused and deleted ones are kept here.')
    : t('Your playlists – Tuttiphon keeps them up to date, and you can listen to them in Symfonium. Further down: what others share with you.')}>
    {#snippet actions()}
      <div class="btns"><a class="btn primary" href="#/neu"><Icon name="plus" size={18} />{t('New playlist')}</a></div><!-- i18n-ignore: route -->
    {/snippet}
  </PageHead>

  <div class="btns justify-between mb-1.5">
    {#if mineP.length > 1 || others.length}
      <div class="seg">
        <button class:on={filter === 'alle'} onclick={() => (filter = 'alle')}>{t('All')}</button><!-- i18n-ignore: filter id -->
        {#if mineP.length > 1}
          {#each mineP as p (p.id)}
            <button class:on={filter === p.id} onclick={() => (filter = p.id)}><Glyph value={p.icon} size={15} />{p.name}</button>
          {/each}
        {/if}
        {#if others.length}
          <button class:on={filter === 'geteilt'} onclick={() => (filter = 'geteilt')}><Icon name="users" size={15} />{t('Shared')}</button>
        {/if}
      </div>
    {:else}
      <span></span>
    {/if}
    <!-- Phone: own full-width row, otherwise there would be hardly any room next to the selection -->
    <div class="search max-w-[300px] max-mobile:max-w-none max-mobile:basis-full max-mobile:order-first">
      <Icon name="search" size={18} />
      <input placeholder={t('Search playlists …')} bind:value={query} aria-label={t('Search playlists')} />
    </div>
  </div>

  {#each ownGroups as { person, list } (person.id)}
    <section class="section">
      <div class="section-head">
        {@render personHead(person, person.name,
          `${plural(list.length, 'playlist', 'playlists')} · ${person.public ? t('visible to everyone') : admin ? t('private for {user}', { user: person.user }) : t('only for you')}`)}
        <a href="#/person/{person.id}">{admin ? t('Preferences →') : t('Taste →')}</a>
      </div>
      {#if list.length}
        <div class="g-pl">{#each list as p (p.id)}<PlaylistCard {p} />{/each}</div>
      {:else}
        <div class="flex flex-wrap items-center gap-3 rounded-card border border-dashed border-line-2 px-4 py-3">
          <span class="muted small flex-1 min-w-[180px]">{t('No playlists for {name} yet.', { name: person.name })}</span>
          <div class="btns">
            <a class="btn primary sm" href="#/neu?person={person.id}"><Icon name="plus" size={15} />{t('New playlist')}</a><!-- i18n-ignore: route -->
            <a class="btn sm" href="#/entdecken">{t('Suggestions')}</a>
          </div>
        </div>
      {/if}
    </section>
  {/each}

  <!-- Users: shared by others – view only -->
  {#each sharedGroups as { person, list } (person.id)}
    <section class="section">
      <div class="section-head">
        {@render personHead(person, t('{name} shares', { name: person.name }),
          `${plural(list.length, 'playlist', 'playlists')} · ${t('to listen to in Symfonium, can be copied and adjusted')}`)}
      </div>
      <div class="g-pl">{#each list as p (p.id)}<PlaylistCard {p} />{/each}</div>
    </section>
  {/each}

  {#if paused.length}
    <Section title={t('Paused')} icon="pause">
      <p class="muted small -mt-1.5 mb-3.5">{t('Not in Navidrome, but kept here – one click brings them back.')}</p>
      <div class="g-pl">{#each paused as p (p.id)}<PlaylistCard {p} />{/each}</div>
    </Section>
  {/if}

  {#if hand.length}
    <Section title={t('Handmade – not in the tool yet')} icon="folder">
      <p class="muted small -mt-1.5 mb-3.5">{t('Your own .nsp files. The tool leaves them alone until you take them over – then they stay the same playlist in Navidrome.')}</p>
      <div class="g-pl">
        {#each hand as x (x.file)}
          <button class="pcard text-left" onclick={() => openTakeover(x.file)}>
            <div class="art"><Mosaic marks="folder" /></div>
            <div><div class="t">{x.name}</div><div class="s"><Icon name="plus" size={14} />{t('Take over …')}</div></div>
          </button>
        {/each}
      </div>
    </Section>
  {/if}

  {#if trash.length}
    <details class="fold section">
      <summary><Icon name="trash" size={18} />{t('Trash · {n}', { n: trash.length })}</summary>
      <div class="in">
        <div class="flex flex-wrap items-center justify-between gap-2">
          <p class="hint">{t('After 30 days in the trash, a playlist is deleted permanently on its own.')}</p>
          <button class="btn sm danger" onclick={() => purgeAll(trash)}><Icon name="trash" size={15} />{t('Empty trash')}</button>
        </div>
        <div class="g-pl">{#each trash as p (p.id)}<PlaylistCard {p} />{/each}</div>
      </div>
    </details>
  {/if}

  {#if nothing}
    {#if q}
      <Empty icon="search" title={t('Nothing found')} text={t('No playlist matches “{query}”.', { query })} />
    {:else}
      <Empty icon="playlists" title={t('No playlists yet')} text={t('Create the first one with the assistant or pick a suggestion.')}>
        <div class="btns">
          <a class="btn primary" href="#/neu"><Icon name="plus" size={16} />{t('New playlist')}</a><!-- i18n-ignore: route -->
          <a class="btn" href="#/entdecken">{t('Suggestions')}</a>
        </div>
      </Empty>
    {/if}
  {/if}
</div>
