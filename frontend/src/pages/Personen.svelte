<!-- People: overview – who playlists are for, which Navidrome account, whether the password is there, what they like. -->
<script>
  import Icon from '../components/Icon.svelte'
  import PageHead from '../components/PageHead.svelte'
  import PersonAvatar from '../components/PersonAvatar.svelte'
  import { S, findWelt, defaultPerson } from '../lib/state.svelte.js'
  import { pwOk } from './personen/shared.js'
  import { t } from '../lib/i18n.svelte.js'
  import { plural } from '../lib/format.js'

  const countOf = (p) => S.config.playlists.filter((x) => (x.person || defaultPerson()) === p.id && (x.status || 'aktiv') === 'aktiv').length
  const weltenOf = (p) => (p.likes?.welten || []).map((id) => findWelt(id)).filter(Boolean)
</script>

<div class="page">
  <PageHead title={t('People')} sub={t('Who is a playlist for? The person decides the owner in Navidrome and so whose stars & favorites count, who sees it – and what never goes in.')}>
    {#snippet actions()}
      <a class="btn primary" data-guide="person-neu" href="#/person/neu"><Icon name="plus" size={18} />{t('Add person')}</a><!-- i18n-ignore: route -->
    {/snippet}
  </PageHead>

  <div class="grid gap-[18px] grid-cols-[repeat(auto-fill,minmax(280px,1fr))]">
    {#each S.config.personen as p (p.id)}
      {@const n = countOf(p)}
      {@const welten = weltenOf(p)}
      <a class="card no-underline grid gap-3.5 transition-[border-color] duration-200" href="#/person/{p.id}">
        <div class="flex gap-3.5 items-center">
          <PersonAvatar {p} size={64} />
          <div class="min-w-0">
            <h2>{p.name}</h2>
            <div class="muted small">Navidrome: {p.user} · {p.public ? t('visible to everyone') : t('private')}</div>
          </div>
          {#if p.id === defaultPerson()}<span class="pill acc ml-auto">{t('Default')}</span>{/if}
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
    {/each}
    <a class="card no-underline border-dashed grid place-items-center min-h-[160px] text-muted" href="#/person/neu"><!-- i18n-ignore: route -->
      <div class="grid justify-items-center gap-1.5"><Icon name="plus" size={30} /><b>{t('Add person')}</b></div>
    </a>
  </div>
</div>
