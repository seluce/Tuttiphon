<!--
  People: overview – the family first (or a card to set it up: FamilySetup.svelte in a sheet), then one person per
  Navidrome account: account, password, what they like.
-->
<script>
  import Icon from '../components/Icon.svelte'
  import PageHead from '../components/PageHead.svelte'
  import PersonAvatar from '../components/PersonAvatar.svelte'
  import FamilySetup from './personen/FamilySetup.svelte'
  import { S, findWelt, familyPerson } from '../lib/state.svelte.js'
  import { openSheet } from '../lib/overlay.svelte.js'
  import { pwOk } from './personen/shared.js'
  import { t } from '../lib/i18n.svelte.js'
  import { plural } from '../lib/format.js'

  const countOf = (p) => S.config.playlists.filter((x) => x.person === p.id && (x.status || 'aktiv') === 'aktiv').length
  const weltenOf = (p) => (p.likes?.welten || []).map((id) => findWelt(id)).filter(Boolean)
  const family = $derived(familyPerson())
  const people = $derived(S.config.personen.filter((p) => !p.family))

  const setUp = () => openSheet({ title: t('Set up the family'), component: FamilySetup })
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

  <div class="grid gap-[18px] grid-cols-[repeat(auto-fill,minmax(280px,1fr))]">
    {#if family}
      <div class="grid" data-guide="familie">{@render card(family)}</div>
    {:else}
      <div class="card grid gap-3.5 content-start border-dashed" data-guide="familie">
        <div class="flex gap-3.5 items-center">
          <PersonAvatar p={{ id: 'familie', icon: 'i:home' }} size={64} />
          <h2>{t('Family')}</h2>
        </div>
        <p class="muted small">{t('Tuttiphon creates a Navidrome account for the family or takes one that already exists. Its playlists are for everyone – and shared devices, in the car or on the kitchen tablet, can play them in Symfonium.')}</p>
        <div class="btns">
          <button class="btn primary" onclick={setUp}><Icon name="home" size={16} />{t('Set up the family')}</button>
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
