<!--
  "Set up the family" (administrators, in a sheet): name and account name. POST /api/family: Tuttiphon creates the
  Navidrome account with a random password and adds the family; the password is shown here once (for shared devices
  in Symfonium). Has Navidrome free accounts (no person, no administrator), one of them can be the family's instead
  ({existing: true} with its password) – one that looks like a family account is chosen right away.
-->
<script>
  import Icon from '../../components/Icon.svelte'
  import PersonAvatar from '../../components/PersonAvatar.svelte'
  import Seg from '../../components/Seg.svelte'
  import Select from '../../components/Select.svelte'
  import { S, save, reloadConfig, loadStatus } from '../../lib/state.svelte.js'
  import { closeSheet, toast } from '../../lib/overlay.svelte.js'
  import { api } from '../../lib/api.js'
  import { users, forgetUsers, takenAccounts, pwOk } from './shared.js'
  import { t } from '../../lib/i18n.svelte.js'

  let name = $state(t('Family'))
  let account = $state(null)   // null: follows the name
  /** Account name from the name as Navidrome accepts it: letters without accents, digits, . _ - */
  const fromName = (s) => s.toLowerCase().normalize('NFKD').replace(/\p{M}/gu, '').replace(/ß/g, 'ss')
    .replace(/[^a-z0-9._-]+/g, '-').replace(/^[^a-z0-9]+|-+$/g, '').slice(0, 40)
  const accountShown = $derived(account ?? fromName(name))
  const avatar = $derived({ id: 'familie', name, icon: 'i:home' })

  let mode = $state('new')   // 'new': Tuttiphon creates the account · 'existing': one Navidrome already has
  let free = $state.raw([])   // Navidrome accounts without a person – no administrators, not the own one
  let picked = $state('')
  let pw = $state('')
  /** Looks like a family account: "familie", "family", "famiglia", "gezin", "rodzina" … in its name or full name. */
  const familyLike = (u) => [u.name, u.fullName || ''].some((x) => /famil|famig|gezin|rodzin/.test(fromName(x)))
  users().then((all) => {
    const taken = takenAccounts()
    const me = (S.me?.user || '').toLowerCase()
    free = all.filter((u) => !u.admin && u.name.toLowerCase() !== me && !taken.has(u.name.toLowerCase()))
    const guess = free.find(familyLike)
    picked = (guess || free[0])?.name || ''
    if (guess) mode = 'existing'
  })

  let busy = $state(false)
  let error = $state('')
  let done = $state(null)   // { account, password } – the password only now (none for an existing account)
  const ready = $derived(mode === 'existing' ? !!picked && (!!pw || pwOk(picked)) : !!accountShown)

  async function create() {
    if (busy) return
    busy = true
    error = ''
    try {
      await save()   // the server changes the configuration – send open changes first
      const body = mode === 'existing' ? { name: name.trim(), account: picked, existing: true, password: pw }
        : { name: name.trim(), account: accountShown }
      const r = await api('/api/family', { body })
      done = { account: r.account, password: r.password || '' }
      forgetUsers()
      await reloadConfig()
      loadStatus()
    } catch (e) {
      error = e.message
    } finally {
      busy = false
    }
  }

  /** Copy – the clipboard of the browser exists only with https (or localhost); otherwise the old way. */
  async function copy(text) {
    try {
      if (navigator.clipboard && window.isSecureContext) await navigator.clipboard.writeText(text)
      else {
        // not read-only and 16 px: Safari on the iPhone selects nothing in a read-only field and zooms into small ones
        const area = Object.assign(document.createElement('textarea'), { value: text })
        area.style.cssText = 'position:fixed;top:0;opacity:0;font-size:16px'
        document.body.append(area)
        area.select()
        area.setSelectionRange(0, text.length)
        const ok = document.execCommand('copy')
        area.remove()
        if (!ok) throw new Error()
      }
      toast(t('Copied'))
    } catch { toast(t('Select the text and copy it'), { error: true }) }
  }
</script>

{#if done}
  <div class="grid gap-4">
    <div class="flex gap-3.5 items-center">
      <PersonAvatar p={avatar} size={56} />
      <b>{t('The family’s account “{account}” is ready.', { account: done.account })}</b>
    </div>
    {#if done.password}
      <div class="note grid gap-2">
        <b>{t('Password – shown only now:')}</b>
        <div class="flex gap-2 items-center">
          <input class="input flex-1 min-w-0 font-mono" readonly value={done.password} aria-label={t('Password')} onfocus={(e) => e.currentTarget.select()} />
          <button class="btn sm" onclick={() => copy(done.password)} aria-label={t('Copy {what}', { what: t('Password') })}><Icon name="copy" size={15} />{t('Copy')}</button>
        </div>
      </div>
    {/if}
    <p class="muted small">{t('Shared devices – in the car, on the kitchen tablet – sign in to Navidrome in Symfonium with this account and play the family playlists. Nobody signs in to Tuttiphon with it.')}</p>
    <div class="btns"><button class="btn primary" onclick={closeSheet}><Icon name="check" size={16} />{t('Done')}</button></div>
  </div>
{:else}
  <div class="grid gap-4">
    {#if free.length}
      <Seg options={[['new', t('New account')], ['existing', t('Existing account')]]} bind:value={mode} onchange={() => (error = '')} />
    {/if}
    <p class="muted small">{mode === 'existing'
      ? t('The family uses an account Navidrome already has – for example the one in the car. Its playlists are for everyone – every account sees them in Navidrome and Symfonium.')
      : t('Tuttiphon creates a Navidrome account for the family. Its playlists are for everyone – every account sees them in Navidrome and Symfonium.')}</p>
    <div class="flex gap-3.5 items-center">
      <PersonAvatar p={avatar} size={56} />
      <label class="f flex-1 min-w-0">{t('Name')}
        <input class="input" bind:value={name} maxlength="60" />
      </label>
    </div>
    {#if mode === 'existing'}
      <label class="f">{t('Navidrome account')}
        <Select options={free.map((u) => [u.name, u.fullName && u.fullName !== u.name ? `${u.name} · ${u.fullName}` : u.name])} value={picked} onchange={(v) => { picked = v; pw = ''; error = '' }} />
      </label>
      {#if pwOk(picked)}
        <div class="note">{t('✓ A password is already stored for this account.')}</div>
      {:else}
        <label class="f">{t('Password of “{user}”', { user: picked })}
          <input class="input" type="password" autocomplete="off" bind:value={pw} />
        </label>
      {/if}
      <div class="hint -mt-2">{t('Tuttiphon checks the password and stores it – for the family’s stars, plays and recap. The account stays as it is.')}</div>
    {:else}
      <label class="f">{t('Navidrome account')}
        <input class="input font-mono" value={accountShown} maxlength="40" autocapitalize="off" autocomplete="off" spellcheck="false"
          oninput={(e) => (account = e.currentTarget.value.trim())} />
      </label>
      <div class="hint -mt-2">{t('Letters, digits, dots, hyphens and underscores. Tuttiphon picks a random password and stores it.')}</div>
    {/if}
    {#if error}<div class="err-t small" role="alert">{error}</div>{/if}
    <div class="btns">
      <button class="btn ghost" onclick={closeSheet}>{t('Cancel')}</button>
      <button class="btn primary" disabled={busy || !name.trim() || !ready} onclick={create}>
        <Icon name="home" size={16} />{busy ? t('One moment …') : t('Set up the family')}
      </button>
    </div>
  </div>
{/if}
