<!-- "My profile": users with one profile land right there, administrators on "People". -->
<script>
  import Icon from '../components/Icon.svelte'
  import PageHead from '../components/PageHead.svelte'
  import Empty from '../components/Empty.svelte'
  import PersonAvatar from '../components/PersonAvatar.svelte'
  import Personen from './Personen.svelte'
  import { isAdmin, ownPersons } from '../lib/state.svelte.js'
  import { t } from '../lib/i18n.svelte.js'

  const own = ownPersons()
  if (!isAdmin() && own.length === 1) location.replace(`#/person/${own[0].id}`)
</script>

{#if isAdmin()}
  <Personen />
{:else if own.length !== 1}
  <div class="page">
    <PageHead title={t('My profile')} sub={t('Choose whose preferences you want to edit.')} />
    {#if own.length}
      <div class="grid gap-2.5 max-w-[640px]">
        {#each own as p (p.id)}
          <a class="member-row p-3.5 no-underline" href="#/person/{p.id}">
            <PersonAvatar {p} size={44} />
            <div class="flex-1"><b>{p.name}</b><div class="tiny muted">{p.public ? t('visible to everyone') : t('private')}</div></div>
            <Icon name="right" size={18} />
          </a>
        {/each}
      </div>
    {:else}
      <Empty title={t('No profile yet')} icon="user"><a class="btn primary" href="#/willkommen">{t('Create profile')}</a></Empty>
    {/if}
  </div>
{/if}
