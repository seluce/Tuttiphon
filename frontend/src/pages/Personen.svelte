<!--
  People: overview – the family first (or a card to set it up: FamilySetup.svelte in a sheet), then one person per
  Navidrome account: account, password, what they like. Profiles the update to one person per account merged into
  someone else (settings.mergedPersons) are listed on top with “Add person”.
-->
<script>
  import Icon from '../components/Icon.svelte'
  import PageHead from '../components/PageHead.svelte'
  import PersonAvatar from '../components/PersonAvatar.svelte'
  import FamilySetup from './personen/FamilySetup.svelte'
  import { S, findWelt, findPerson, familyPerson, changed } from '../lib/state.svelte.js'
  import { openSheet, confirmDialog } from '../lib/overlay.svelte.js'
  import { go } from '../lib/router.svelte.js'
  import { pwOk, setDraft } from './personen/shared.js'
  import { t, tn } from '../lib/i18n.svelte.js'
  import { plural } from '../lib/format.js'

  const countOf = (p) => S.config.playlists.filter((x) => x.person === p.id && (x.status || 'aktiv') === 'aktiv').length
  const weltenOf = (p) => (p.likes?.welten || []).map((id) => findWelt(id)).filter(Boolean)
  const family = $derived(familyPerson())
  const people = $derived(S.config.personen.filter((p) => !p.family))
  // left over from the update to one person per account: the old shared person (look, playlists) and merged profiles
  const setup = $derived(S.config.settings.familySetup || null)
  const former = $derived((setup?.playlists || []).filter((id) => S.config.playlists.some((x) => x.id === id && x.status !== 'papierkorb')).length)
  const merged = $derived((S.config.settings.mergedPersons || []).filter((x) => x?.name))

  const setUp = () => openSheet({ title: t('Set up the family'), component: FamilySetup })
  /** No family after all: the former family playlists stay with the person they belong to now – only for that account
   *  (until now they stayed for everyone, rules.for_everyone). */
  async function noFamily() {
    if (!await confirmDialog(t('Continue without a family?'), t('The former family playlists then stay with the person they belong to now – only that account sees them.'), t('Without a family'))) return
    delete S.config.settings.familySetup
    changed()
  }
  function addMerged(x) {
    setDraft($state.snapshot(x))
    go('#/person/neu')   // i18n-ignore: route
  }
  function hideMerged(x) {
    const rest = S.config.settings.mergedPersons.filter((y) => y !== x)
    if (rest.length) S.config.settings.mergedPersons = rest
    else delete S.config.settings.mergedPersons
    changed()
  }
</script>

{#snippet card(p)}
  {@const n = countOf(p)}
  {@const welten = weltenOf(p)}
  <a class="card no-underline grid gap-3.5 transition-[border-color] duration-200" href="#/person/{p.id}">
    <div class="flex gap-3.5 items-center">
      <PersonAvatar {p} size={64} />
      <div class="min-w-0">
        <h2>{p.name}</h2>
        <div class="muted small">Navidrome: {p.user}{#if p.family}{' · '}{t('for everyone')}{/if}</div>
      </div>
      {#if p.family}<span class="pill acc ml-auto"><Icon name="home" size={12} />{t('Family')}</span>{/if}
    </div>
    <div class="btns">
      <span class="pill">{plural(n, 'playlist', 'playlists')}</span>
      {#if pwOk(p.user)}
        <span class="pill ok"><Icon name="check" size={12} />{t('Password stored')}</span>
      {:else}
        <span class="pill warn"><Icon name="lock" size={12} />{t('Password missing')}</span>
      {/if}
    </div>
    {#if welten.length}
      <div class="small muted">{t('likes {list}', { list: welten.map((w) => w.name).join(' · ') })}</div>
    {:else}
      <div class="small warn-t">{t('No preferences yet – tap to set them')}</div>
    {/if}
  </a>
{/snippet}

<div class="page">
  <PageHead title={t('People')} sub={t('Every person has a Navidrome account of their own – their playlists end up there, and its stars & favorites count. The family’s playlists are for everyone.')}>
    {#snippet actions()}
      <a class="btn primary" data-guide="person-neu" href="#/person/neu"><Icon name="plus" size={18} />{t('Add person')}</a><!-- i18n-ignore: route -->
    {/snippet}
  </PageHead>

  {#if merged.length}
    <div class="grid gap-2.5 mb-[18px]">
      {#each merged as x, i (i)}
        <div class="note flex flex-wrap gap-2.5 items-center border border-accent/40">
          <Icon name="user" size={18} class="shrink-0 text-accent" />
          <span class="flex-1 min-w-[12rem]">{t('{name} needs a Navidrome account of their own. Until then, their playlists are with {into} – create the account in Navidrome, then add {name} here.',
            { name: x.name, into: findPerson(x.into)?.name || x.into || '?' })}</span>
          <button class="btn sm primary" onclick={() => addMerged(x)}><Icon name="plus" size={15} />{t('Add person')}</button>
          <button class="btn sm ghost" title={t('Don’t show again')} onclick={() => hideMerged(x)}>{t('hide')}</button>
        </div>
      {/each}
    </div>
  {/if}

  <div class="grid gap-[18px] grid-cols-[repeat(auto-fill,minmax(280px,1fr))]">
    {#if family}
      <div class="grid" data-guide="familie">{@render card(family)}</div>
    {:else}
      <div class="card grid gap-3.5 content-start border-dashed" data-guide="familie">
        <div class="flex gap-3.5 items-center">
          <PersonAvatar p={{ id: 'familie', icon: setup?.icon || 'i:home', color: setup?.color }} size={64} />
          <h2>{t('Family')}</h2>
        </div>
        <p class="muted small">{t('Tuttiphon creates a Navidrome account for the family. Its playlists are for everyone – and shared devices, in the car or on the kitchen tablet, can play them in Symfonium.')}</p>
        {#if former}<p class="small">{tn(former, 'The former family playlist can move there.', 'The {n} former family playlists can move there.')}</p>{/if}
        <div class="btns">
          <button class="btn primary" onclick={setUp}><Icon name="home" size={16} />{t('Set up the family')}</button>
          {#if setup}<button class="btn ghost" onclick={noFamily}>{t('No family')}</button>{/if}
        </div>
      </div>
    {/if}
    {#each people as p (p.id)}
      {@render card(p)}
    {/each}
    <a class="card no-underline border-dashed grid place-items-center min-h-[160px] text-muted" href="#/person/neu"><!-- i18n-ignore: route -->
      <div class="grid justify-items-center gap-1.5"><Icon name="plus" size={30} /><b>{t('Add person')}</b></div>
    </a>
  </div>
</div>
