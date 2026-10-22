<!--
  One person: profile with preferences (administrators: anyone, users: only their own).
  #/person/neu is the assistant for a new person (administrators only).
-->
<script>
  import Empty from '../components/Empty.svelte'
  import Profile from './personen/Profile.svelte'
  import NewPerson from './personen/NewPerson.svelte'
  import { S, findPerson, isAdmin } from '../lib/state.svelte.js'
  import { replace } from '../lib/router.svelte.js'
  import { t } from '../lib/i18n.svelte.js'

  let { id } = $props()

  const self = !isAdmin()   // users only edit their own profile
  // derived: after "Undo", S.config is a new object
  const p = $derived(id === 'neu' ? null : findPerson(id))   // i18n-ignore: route id
  const mine = $derived(!self || (!!p && S.me?.own === p.id))

  $effect(() => {
    if (id === 'neu' && self) replace('#/willkommen')   // i18n-ignore: route id – replacing: "back" must not lead here again
  })
</script>

{#if id === 'neu'}<!-- i18n-ignore: route id -->
  {#if !self}<NewPerson />{/if}
{:else if !p}
  <div class="page">
    <Empty icon="user" title={t('This person does not exist')}>
      <a class="btn" href={self ? '#/' : '#/personen'}>{self ? t('Go to “For you”') : t('Go to people')}</a>
    </Empty>
  </div>
{:else if !mine}
  <div class="page">
    <Empty icon="lock" title={t('This is not your profile')} text={t('You can only change your own profile.')}>
      <a class="btn primary" href="#/profil">{t('My profile')}</a>
    </Empty>
  </div>
{:else}
  {#key p}<Profile {p} {self} />{/key}
{/if}
