<!-- Settings → My account: sign-in, own password for statistics & stars, own profiles, tour. -->
<script>
  import { hiddenCount } from '../../lib/discover.js'
  import Icon from '../../components/Icon.svelte'
  import PersonAvatar from '../../components/PersonAvatar.svelte'
  import Card from './Card.svelte'
  import Row from './Row.svelte'
  import { S, findPerson, changed } from '../../lib/state.svelte.js'
  import { toast, confirmDialog } from '../../lib/overlay.svelte.js'
  import { api } from '../../lib/api.js'
  import { logout } from '../../lib/account.js'
  import { startTour } from '../../lib/tour.svelte.js'
  import { fmt } from '../../lib/format.js'
  import { t } from '../../lib/i18n.svelte.js'

  const me = $derived(S.me || {})
  const own = $derived((me.own || []).map(findPerson).filter(Boolean))
  const roleText = $derived(me.notfall ? t('Local administrator with all rights')
    : me.role === 'admin' ? t('Administrator – may change all settings') : t('User – own playlists and own profile'))

  let password = $state('')
  let pwOut = $state({ text: '', cls: '' })

  async function savePw() {
    if (!password) { toast(t('Please enter the password'), { error: true }); return }
    pwOut = { text: t('checking …'), cls: 'muted' }
    const renewing = rejected
    try {
      await api('/api/me/password', { body: { password } })
      S.me = await api('/api/me')
      password = ''
      pwOut = { text: '', cls: '' }
      toast(renewing ? t('Saved ✓') : t('Turned on ✓ – your statistics will be there in a moment'))
    } catch (e) {
      pwOut = { text: e.message, cls: 'err-t' }
    }
  }

  async function forget() {
    if (!await confirmDialog(t('Forget password?'), t('Then there are no personal statistics and no Deezer stars of your own until you enter it again. You can still sign in.'), t('Forget'))) return
    try {
      await api('/api/me/password', { body: { password: null } })
      S.me = await api('/api/me')
      toast(t('Password forgotten'))
    } catch (e) {
      toast(e.message, { error: true })
    }
  }
  /** the stored password no longer works (changed in Navidrome) – enter the new one */
  const rejected = $derived(!!(me.passwordStored && me.passwordRejected))

  function showAll() {
    S.config.dismissed = S.config.dismissed.filter((k) => k.startsWith('scene|'))   // deleted music worlds stay gone
    S.config.ignored = []
    changed()
    toast(t('Everything visible again'))
  }
</script>

{#if !me.user}
  <Card title={t('Sign-in')} icon="key">
    <p class="muted small">{t('Sign-in is currently turned off – anyone who can open Tuttiphon is automatically an administrator. This only makes sense as long as Tuttiphon runs on this computer alone.')}</p>
    <p class="muted small">{@html t('If an administrator password is set in docker-compose.yaml as TUTTIPHON_ADMIN_PASSWORD, everyone signs in with their own Navidrome account and gets their own view. <a class="link" href="#/hilfe/konten">How it works →</a>')}</p>
  </Card>
{:else}
  <Card title={t('Signed in')} icon="user">
    <div class="member-row">
      <PersonAvatar p={own[0] || { icon: 'i:user', id: me.user }} size={48} />
      <div class="flex-1 min-w-0">
        <b>{me.fullName || me.name}</b>
        <div class="tiny muted">{me.notfall ? roleText : t('Navidrome account “{user}” · {role}', { user: me.user, role: roleText })}</div>
      </div>
      <button class="btn" onclick={logout}><Icon name="logout" size={16} />{t('Sign out')}</button>
    </div>
    <div class="hint">{me.notfall ? t('The password of the local administrator is set in docker-compose.yaml (TUTTIPHON_ADMIN_PASSWORD).')
      : me.passwordStored ? t('You change your password in Navidrome, in the profile at the top right. Then enter the new one here under “Statistics & stars” as well.')
      : t('You change your password in Navidrome, in the profile at the top right.')}</div>
  </Card>

  <Card title={t('Statistics & stars')} icon="chart" guide="statistik">
    {#if me.notfall}
      <p class="muted small">{t('The local administrator has no Navidrome account of its own.')}</p>
    {:else if me.passwordStored && !rejected}
      <div class="member-row">
        <Icon name="check" size={18} class="ok-t" />
        <div class="flex-1 min-w-0">
          <b>{t('Turned on')}</b>
          <div class="tiny muted">{t('Tuttiphon knows your plays, stars and favorites – for your statistics, your stars and more accurate suggestions.')}</div>
        </div>
        <button class="btn sm ghost" onclick={forget}>{t('Turn off')}</button>
      </div>
    {:else}
      <div class="grid gap-2.5">
        {#if rejected}
          <div class="note flex items-start gap-2.5 border border-warn/40" role="status">
            <Icon name="alert" size={18} class="shrink-0 mt-0.5 warn-t" />
            <span>{t('The stored password no longer works – probably it was changed in Navidrome. Enter the new one so your statistics and stars keep working.')}</span>
          </div>
        {:else}
          <p class="muted small">{t('For Tuttiphon to show your statistics and set Deezer stars in your account, it needs your Navidrome password once – the same as in Symfonium. It stays on your NAS.')}</p>
        {/if}
        <div class="frow">
          <label class="f">{t('Password')}
            <input class="input w-full" type="password" autocomplete="current-password" placeholder={t('your Navidrome password')} bind:value={password} />
          </label>
        </div>
        <div class="btns">
          <button class="btn primary" onclick={savePw}>{rejected ? t('Save new password') : t('Turn on')}</button>
          {#if rejected}<button class="btn ghost" onclick={forget}>{t('Turn off')}</button>{/if}
          <div class="small {pwOut.cls}" role="status">{pwOut.text}</div>
        </div>
      </div>
    {/if}
  </Card>

  {#if !me.notfall}
    <Card title={t('Your profiles')} icon="heart">
      {#if own.length}
        <div class="grid gap-2">
          {#each own as p (p.id)}
            <a class="member-row no-underline" href="#/person/{p.id}">
              <PersonAvatar {p} size={36} />
              <div class="flex-1 min-w-0">
                <b>{p.name}</b>
                <div class="tiny muted">{p.public ? t('Playlists visible to everyone') : t('Playlists only for you')}</div>
              </div>
              <Icon name="right" size={16} />
            </a>
          {/each}
        </div>
      {:else}
        <div class="btns"><a class="btn primary" href="#/willkommen"><Icon name="plus" size={16} />{t('Create profile')}</a></div>
      {/if}
      <div class="hint">{t('This is where your favorite worlds, bands and dislikes are – your suggestions come from them.')}</div>
    </Card>
  {/if}
{/if}

<Card title={t('Introduction')} icon="compass" guide="einfuehrung">
  <Row label={t('Tour')} hint={t('Shows in a few steps where to find what.')}>
    <button class="btn sm" onclick={() => startTour(true)}><Icon name="play" size={15} />{t('Start tour')}</button>
  </Row>
  <Row label={t('Hidden items')} hint={t('{suggestions} suggestions · {tips} tips are hidden. Suggestions come back on their own after half a year.', { suggestions: fmt(hiddenCount()), tips: fmt(S.config.ignored.length) })}>
    <button class="btn sm" disabled={!hiddenCount() && !S.config.ignored.length} onclick={showAll}>{t('show again')}</button>
  </Row>
</Card>
