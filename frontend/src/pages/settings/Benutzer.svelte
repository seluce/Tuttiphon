<!-- Settings → Users & permissions: roles of the Navidrome accounts in Tuttiphon (the family's account has none – nobody
     signs in with it), who may change the family playlists (settings.familyEdit), local administrator. -->
<script>
  import Icon from '../../components/Icon.svelte'
  import Select from '../../components/Select.svelte'
  import Seg from '../../components/Seg.svelte'
  import PersonAvatar from '../../components/PersonAvatar.svelte'
  import Card from './Card.svelte'
  import Row from './Row.svelte'
  import AdminPassword from './AdminPassword.svelte'
  import { S, findPerson, changed } from '../../lib/state.svelte.js'
  import { toast } from '../../lib/overlay.svelte.js'
  import { api } from '../../lib/api.js'
  import { relTime } from '../../lib/format.js'
  import { t } from '../../lib/i18n.svelte.js'

  const ROLE_LABEL = $derived({ admin: t('Administrator'), user: t('User'), none: t('No access') })
  const env = $derived(S.status?.env || {})

  let list = $state.raw(null)
  let error = $state('')
  const load = () => api('/api/accounts').then((d) => { list = d; error = '' }).catch((e) => { error = e.message })
  load()

  const isMe = (u) => !!S.me?.user && u.name.toLowerCase() === S.me.user.toLowerCase()
  const info = (u, person) => (u.family
    ? [t('The family’s account – for shared devices in Symfonium, nobody signs in to Tuttiphon with it'),
      u.passwordStored && u.passwordRejected ? t('stored password no longer works') : null]
    : [
      u.navidromeAdmin ? t('Navidrome admin') : t('Navidrome user'),
      person ? t('Profile: {name}', { name: person.name }) : t('no profile yet'),
      u.lastLogin ? t('last signed in {when}', { when: relTime(u.lastLogin.replace(' ', 'T')) }) : t('never signed in'),
      u.passwordStored ? (u.passwordRejected ? t('stored password no longer works') : t('statistics on')) : null]).filter(Boolean).join(' · ')

  async function setRole(u, v) {
    try {
      await api('/api/accounts', { method: 'PUT', body: { user: u.name, role: v || null } })
      toast(`${u.name}: ${ROLE_LABEL[v || (u.navidromeAdmin ? 'admin' : 'user')]}`)
    } catch (e) {
      toast(e.message, { error: true })
    }
    load()
  }
</script>

<Card title={t('Who may do what?')} icon="users" guide="rechte">
  <p class="muted small">{t('Everyone signs in with their own Navidrome account – with the same name and password as in Symfonium.')}</p>
  <div class="grid grid-cols-[repeat(auto-fit,minmax(200px,1fr))] gap-2.5 mt-3 mb-4">
    <div class="role-card"><b><Icon name="shield" size={16} />{ROLE_LABEL.admin}</b><p class="muted small">{t('Sees and changes everything: all playlists, music worlds, vibes, people and all settings – including Deezer, lyrics and conversion.')}</p></div>
    <div class="role-card"><b><Icon name="user" size={16} />{ROLE_LABEL.user}</b><p class="muted small">{t('Has their own “For you” home page, their own playlists and their own profile. Listens to the family playlists – and changes them unless only administrators may.')}</p></div>
    <div class="role-card"><b><Icon name="ban" size={16} />{ROLE_LABEL.none}</b><p class="muted small">{t('Cannot sign in to Tuttiphon. Navidrome and Symfonium keep working.')}</p></div>
  </div>
  <div>
    {#if error}
      <div class="err-t small">{error}</div>
    {:else if !list}
      <div class="skel h-[160px]"></div>
    {:else}
      <!-- rebuilt on every load (key = object): shows the saved role even if changing it failed -->
      <div class="grid gap-2">
        {#each list as u (u)}
          {@const person = u.persons.map(findPerson).find(Boolean)}
          {@const mine = isMe(u)}
          <div class="member-row flex-wrap">
            {#if person}
              <PersonAvatar p={person} size={40} />
            {:else}
              <div class="av size-10 !bg-surface-3 !text-muted"><Icon name="user" size={20} /></div>
            {/if}
            <div class="grow basis-[10rem] min-w-0">
              <b>{u.fullName && u.fullName !== u.name ? `${u.fullName} · ${u.name}` : u.name}{#if mine}<span class="pill acc ml-1.5">{t('you')}</span>{/if}</b>
              <div class="tiny muted">{info(u, person)}</div>
            </div>
            {#if u.family}
              <span class="pill acc"><Icon name="home" size={12} />{t('Family')}</span>
            {:else}
              <Select class="basis-full sm:basis-auto sm:max-w-[220px]" options={[['', t('Default: {role}', { role: ROLE_LABEL[u.navidromeAdmin ? 'admin' : 'user'] })], ['admin', ROLE_LABEL.admin], ['user', ROLE_LABEL.user], ['none', ROLE_LABEL.none]]}
                value={u.override || ''} onchange={(v) => setRole(u, v)}
                disabled={mine} title={mine ? t('You cannot change your own role') : ''} />
            {/if}
          </div>
        {/each}
      </div>
      <div class="hint mt-2.5">{t('“Default” means: whoever is an admin in Navidrome is one here too. Changes apply on the next page the person opens.')}</div>
    {/if}
  </div>
  <Row label={t('Family playlists – who may change them?')} hint={t('Everyone listens to them. With “Administrators only”, users get their own version with “Copy for me”.')}>
    <Seg options={[['all', t('Everyone')], ['admins', t('Administrators only')]]} value={S.config.settings.familyEdit || 'all'}
      onchange={(v) => { S.config.settings.familyEdit = v; changed() }} />
  </Row>
</Card>

<Card title={t('Local administrator')} icon="shield">
  <p class="muted small">{env.auth
    ? t('Besides the Navidrome accounts there is Tuttiphon’s own administrator: choose “Local administrator” on the sign-in page and enter its password. It has all rights and works even when Navidrome cannot be reached.')
    : t('Not set up yet: Tuttiphon only asks for a sign-in once the local administrator has a password. Without it, Tuttiphon can only be reached from its own computer.')}</p>
  <AdminPassword />
</Card>

<style>
  .role-card { display: grid; gap: 6px; padding: 12px 14px; border-radius: var(--radius-card); background: var(--surface-2); }
  .role-card b { display: flex; gap: 8px; align-items: center; }
</style>
