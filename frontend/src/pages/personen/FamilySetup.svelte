<!--
  "Set up the family" (administrators, in a sheet): name and account name. POST /api/family: Tuttiphon creates the
  Navidrome account with a random password and adds the family; the password is shown here once (for shared devices
  in Symfonium).
-->
<script>
  import Icon from '../../components/Icon.svelte'
  import PersonAvatar from '../../components/PersonAvatar.svelte'
  import { save, reloadConfig, loadStatus } from '../../lib/state.svelte.js'
  import { closeSheet, toast } from '../../lib/overlay.svelte.js'
  import { api } from '../../lib/api.js'
  import { forgetUsers } from './shared.js'
  import { t } from '../../lib/i18n.svelte.js'

  let name = $state(t('Family'))
  let account = $state(null)   // null: follows the name
  /** Account name from the name as Navidrome accepts it: letters without accents, digits, . _ - */
  const fromName = (s) => s.toLowerCase().normalize('NFKD').replace(/\p{M}/gu, '').replace(/ß/g, 'ss')
    .replace(/[^a-z0-9._-]+/g, '-').replace(/^[^a-z0-9]+|-+$/g, '').slice(0, 40)
  const accountShown = $derived(account ?? fromName(name))
  const avatar = $derived({ id: 'familie', name, icon: 'i:home' })

  let busy = $state(false)
  let error = $state('')
  let done = $state(null)   // { account, password } – the password only now

  async function create() {
    if (busy) return
    busy = true
    error = ''
    try {
      await save()   // the server changes the configuration – send open changes first
      const r = await api('/api/family', { body: { name: name.trim(), account: accountShown } })
      done = { account: r.account, password: r.password }
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
    <div class="note grid gap-2">
      <b>{t('Password – shown only now:')}</b>
      <div class="flex gap-2 items-center">
        <input class="input flex-1 min-w-0 font-mono" readonly value={done.password} aria-label={t('Password')} onfocus={(e) => e.currentTarget.select()} />
        <button class="btn sm" onclick={() => copy(done.password)} aria-label={t('Copy {what}', { what: t('Password') })}><Icon name="copy" size={15} />{t('Copy')}</button>
      </div>
    </div>
    <p class="muted small">{t('Shared devices – in the car, on the kitchen tablet – sign in to Navidrome in Symfonium with this account and play the family playlists. Nobody signs in to Tuttiphon with it.')}</p>
    <div class="btns"><button class="btn primary" onclick={closeSheet}><Icon name="check" size={16} />{t('Done')}</button></div>
  </div>
{:else}
  <div class="grid gap-4">
    <p class="muted small">{t('Tuttiphon creates a Navidrome account for the family. Its playlists are for everyone – every account sees them in Navidrome and Symfonium.')}</p>
    <div class="flex gap-3.5 items-center">
      <PersonAvatar p={avatar} size={56} />
      <label class="f flex-1 min-w-0">{t('Name')}
        <input class="input" bind:value={name} maxlength="60" />
      </label>
    </div>
    <label class="f">{t('Navidrome account')}
      <input class="input font-mono" value={accountShown} maxlength="40" autocapitalize="off" autocomplete="off" spellcheck="false"
        oninput={(e) => (account = e.currentTarget.value.trim())} />
    </label>
    <div class="hint -mt-2">{t('Letters, digits, dots, hyphens and underscores. Tuttiphon picks a random password and stores it.')}</div>
    {#if error}<div class="err-t small" role="alert">{error}</div>{/if}
    <div class="btns">
      <button class="btn ghost" onclick={closeSheet}>{t('Cancel')}</button>
      <button class="btn primary" disabled={busy || !name.trim() || !accountShown} onclick={create}>
        <Icon name="home" size={16} />{busy ? t('One moment …') : t('Set up the family')}
      </button>
    </div>
  </div>
{/if}
