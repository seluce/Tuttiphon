<!--
  Discover: ready-made suggestions, new music worlds, bands still missing, a table of all combinations.
  Administrators choose whose suggestions they see (All | <people>), starting with the family's.
-->
<script module>
  // Suggestions from the last visit – visible at once until the fresh ones arrive
  let cache = null
  // Person filter (administrators) – kept when coming back; null = the family's
  const remember = { filter: null }
</script>

<script>
  import { untrack } from 'svelte'
  import Icon from '../components/Icon.svelte'
  import Glyph from '../components/Glyph.svelte'
  import PageHead from '../components/PageHead.svelte'
  import Section from '../components/Section.svelte'
  import Empty from '../components/Empty.svelte'
  import Loading from '../components/Loading.svelte'
  import PersonAvatar from '../components/PersonAvatar.svelte'
  import SuggestionCard from './discover/SuggestionCard.svelte'
  import Missing from './discover/Missing.svelte'
  import Matrix from './discover/Matrix.svelte'
  import { S, isAdmin, ownPersons, defaultPerson, findPerson, save } from '../lib/state.svelte.js'
  import { api } from '../lib/api.js'
  import { hiddenCount, showHidden } from '../lib/discover.js'
  import { t, tn } from '../lib/i18n.svelte.js'

  const admin = isAdmin()
  let sg = $state.raw(cache)
  let error = $state(null)
  let matrixShown = $state(false)   // compute the table only when it is first unfolded

  let first = true
  function load() {
    const initial = first
    first = false
    api('/api/suggestions')
      .then((d) => { sg = cache = d; error = null })
      .catch((e) => { if (initial) error = e.message })
  }
  // Reload: on opening, after every finished run and after "Undo" (S.config is replaced then –
  // save first, then ask, otherwise the server still has the old state)
  $effect(() => {
    void S.config
    void S.done
    untrack(() => save().then(load))
  })

  /** Remove an accepted suggestion from the list. */
  function remove(s) {
    sg = cache = sg.filter((x) => x !== s)
  }

  const items = $derived((sg || []).filter((s) => !S.config.dismissed.includes(s.key)))
  const hidden = $derived(hiddenCount())
  /** Bring hidden ones back and have them computed again right away */
  function restore() {
    showHidden()
    save().then(load)
  }

  /* Person filter (administrators, as on "Playlists"): All | the family | the other people */
  const filterPersons = $derived(admin ? [findPerson(S.config.settings.defaultPerson), ...ownPersons().filter((p) => p.id !== S.config.settings.defaultPerson)].filter(Boolean) : [])
  let filter = $state(admin ? remember.filter || S.config.settings.defaultPerson || 'alle' : 'alle')   // i18n-ignore: filter id
  $effect(() => {
    if (filter !== 'alle' && !filterPersons.some((p) => p.id === filter)) filter = 'alle'   // person deleted in the meantime (i18n-ignore: filter id)
    remember.filter = filter
  })
  /** Whose suggestion: the playlist's person – the season's without one and a new music world (it comes with a mix
   *  for the family) count as the family's */
  const whose = (s) => s.person || (s.group === 'welten' || s.group === 'saison' ? defaultPerson() : s.group)

  /** Order: first the account's own person (not the shared one, even if it belongs to the same account),
   *  then the season, then the shared one and the rest */
  const groups = $derived.by(() => {
    const def = defaultPerson()
    const shared = S.config.settings.defaultPerson
    const me = (S.me?.user || '').toLowerCase()
    const personal = ownPersons().filter((p) => me && (p.user || '').toLowerCase() === me && p.id !== shared).map((p) => p.id)
    const rest = [def, ...ownPersons().map((p) => p.id)].filter((id) => !personal.includes(id))
    const order = [...new Set([...personal, 'saison', ...rest, 'welten'])]
    const shown = filter === 'alle' ? items : items.filter((s) => whose(s) === filter)   // i18n-ignore: filter id
    return order.map((g) => [g, shown.filter((s) => s.group === g)]).filter(([, l]) => l.length)
  })

  /* Collapse sections – the device remembers it */
  const FOLD_KEY = 'tuttiphon-discover-folded'
  let folded = $state(readFolded())
  function readFolded() {
    try { return JSON.parse(localStorage.getItem(FOLD_KEY) || '[]') } catch { return [] }
  }
  function toggle(g) {
    folded = folded.includes(g) ? folded.filter((x) => x !== g) : [...folded, g]
    try { localStorage.setItem(FOLD_KEY, JSON.stringify(folded)) } catch { /* private mode: only until reload */ }
  }
</script>

<div class="page">
  <PageHead title={t('Discover')} eyebrow={admin ? t('For all of you') : t('For you')} sub={admin
    ? t('Ready-made playlists from your library – matching your preferences and the season. One click creates them, ✕ hides a suggestion for six months.')
    : t('Ready-made playlists from your library – matching your taste and the season. “Create” adds them, ✕ hides a suggestion for six months.')} />

  {#if sg && !error && filterPersons.length > 1}
    <div class="seg mb-1.5">
      <button class:on={filter === 'alle'} onclick={() => (filter = 'alle')}>{t('All')}</button><!-- i18n-ignore: filter id -->
      {#each filterPersons as p (p.id)}
        <button class:on={filter === p.id} onclick={() => (filter = p.id)}><Glyph value={p.icon} size={15} />{p.name}</button>
      {/each}
    </div>
  {/if}

  {#if error}
    <Empty icon="alert" title={t('Suggestions could not be computed')} text={error} />
  {:else if !sg}
    <Loading text={t('Looking for matching playlists in your library …')} />
  {:else if groups.length}
    {#each groups as [g, list] (g)}
      {@const open = !folded.includes(g)}
      <section class="section">
        <div class="section-head">
          <div class="grid min-w-0">
            <h2 class="ih">
              <button type="button" class="fold-head" aria-expanded={open} title={open ? t('Collapse') : t('Expand')} onclick={() => toggle(g)}>
                {#if g === 'saison'}
                  <span class="hi"><Icon name="calendar" size={18} /></span>{t('Right for the season')}
                {:else if g === 'welten'}
                  <span class="hi"><Icon name="compass" size={18} /></span>{t('New music worlds discovered')}
                {:else}
                  {@const p = findPerson(g)}
                  <PersonAvatar {p} size={36} />{!admin && ownPersons().length === 1 ? t('For you') : t('For {name}', { name: p?.name || g })}
                {/if}
                {#if !open}<span class="pill text-[.78rem] font-semibold">{list.length}</span>{/if}
                <Icon name={open ? 'up' : 'down'} size={18} class="muted shrink-0" />
              </button>
            </h2>
            {#if g === 'welten' && open}<span class="muted small">{t('Scenes whose typical bands are already on your shelf')}</span>{/if}
          </div>
          {#if open && g !== 'saison' && g !== 'welten'}
            <a href="#/person/{g}">{admin ? t('Preferences →') : t('Change taste →')}</a>
          {/if}
        </div>
        {#if open}
          <div class={g === 'welten' ? 'g-welt' : 'g-cards'}>
            {#each list as s (s)}<SuggestionCard {s} onaccepted={() => remove(s)} />{/each}
          </div>
        {/if}
      </section>
    {/each}
  {:else}
    <Empty icon="check-circle" title={t('No new suggestions right now')} text={admin
      ? t('You already have everything that fits. New music or different preferences bring new ideas.')
      : t('You already have everything that fits. More favorite worlds or bands in your profile bring new ideas.')}>
      <div class="btns justify-center">
        {#if !admin}<a class="btn" href="#/profil">{t('My profile')}</a>{/if}
        {#if hidden}<button class="btn" onclick={restore}><Icon name="eye" size={16} />{t('Show {n} hidden again', { n: hidden })}</button>{/if}
      </div>
    </Empty>
  {/if}

  {#if hidden && groups.length}
    <div class="flex flex-wrap items-center gap-x-3 gap-y-1 mt-1">
      <span class="hint">{tn(hidden, '{n} hidden suggestion comes back by itself after six months.', '{n} hidden suggestions come back by themselves after six months.')}</span>
      <button class="link text-[.84rem]" onclick={restore}>{t('Show again now')}</button>
    </div>
  {/if}

  <Section icon="search" title={admin ? t('You might still be missing') : t('You might also like – not in your library yet')}>
    <Missing />
  </Section>

  <details class="fold section" ontoggle={(e) => { if (e.currentTarget.open) matrixShown = true }}>
    <summary>
      <Icon name="grid" size={18} />{t('All combinations as a table')}
      <span class="muted small font-medium">{t('· Music world × vibe with song counts')}</span>
    </summary>
    <div class="in">{#if matrixShown}<Matrix />{/if}</div>
  </details>
</div>

<style>
  .fold-head { display: flex; align-items: center; gap: 12px; min-width: 0; cursor: pointer; text-align: left; font: inherit; color: inherit; }
  .fold-head:hover { color: var(--accent); }
</style>
