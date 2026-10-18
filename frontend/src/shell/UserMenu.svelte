<!-- "Signed in as …": button in the sidebar (compact: picture only, header on the phone) – opens the account menu. -->
<script>
  import Icon from '../components/Icon.svelte'
  import PersonAvatar from '../components/PersonAvatar.svelte'
  import { S, isAdmin, myPerson } from '../lib/state.svelte.js'
  import { openSheet, closeSheet } from '../lib/overlay.svelte.js'
  import { logout } from '../lib/account.js'
  import { t } from '../lib/i18n.svelte.js'

  let { compact = false } = $props()
  const me = $derived(S.me)
  const person = $derived(myPerson() || { icon: 'i:user', id: me?.user })

  function menu() {
    openSheet({ title: me.fullName || me.name, body: menuBody })
  }
</script>

{#snippet menuBody()}
  <div class="grid gap-2.5">
    <div class="member-row">
      <PersonAvatar p={person} size={44} />
      <div>
        <b>{me.fullName || me.name}</b>
        <div class="tiny muted">{me.notfall ? t('Local administrator · all rights')
          : me.role === 'admin' ? t('Navidrome account “{user}” · Administrator', { user: me.user }) : t('Navidrome account “{user}” · User', { user: me.user })}</div>
      </div>
    </div>
    {#if !isAdmin()}
      <a class="member-row p-3 no-underline" href="#/profil" onclick={closeSheet}><Icon name="user" /><b>{t('My profile & preferences')}</b></a>
    {/if}
    <a class="member-row p-3 no-underline" href="#/einstellungen/konto" onclick={closeSheet}><Icon name="key" /><b>{t('My account')}</b></a>
    <button class="btn" onclick={logout}><Icon name="logout" size={16} />{t('Sign out')}</button>
  </div>
{/snippet}

{#if me?.user}
  {#if compact}
    <button class="rounded-full shrink-0 ml-2" onclick={menu} aria-label={t('My account')}><PersonAvatar p={person} size={32} /></button>
  {:else}
    <button class="grid grid-cols-[32px_minmax(0,1fr)] gap-2.5 items-center w-full px-2.5 py-2 rounded-xl border border-line bg-surface text-left hover:border-line-2"
      onclick={menu} title={t('My account')}>
      <PersonAvatar p={person} size={32} />
      <span class="grid min-w-0">
        <b class="ell">{me.name || me.user}</b>
        <small class="muted text-[.74rem]">{me.notfall ? t('Local administrator') : me.role === 'admin' ? t('Administrator') : t('Signed in')}</small>
      </span>
    </button>
  {/if}
{/if}
