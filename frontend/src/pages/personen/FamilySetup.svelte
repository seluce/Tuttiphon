<!--
  "Set up the family" (administrators, in a sheet): name, account name and – left over from the update to one person
  per account (settings.familySetup) – which of its former playlists move to the family. POST /api/family: Tuttiphon
  creates the Navidrome account with a random password and adds the family; the password is shown here once (for
  shared devices in Symfonium).
-->
<script>
  import { untrack } from 'svelte'
  import { SvelteSet } from 'svelte/reactivity'
  import Icon from '../../components/Icon.svelte'
  import Field from '../../components/Field.svelte'
  import PersonAvatar from '../../components/PersonAvatar.svelte'
  import { S, findPerson, save, reloadConfig, loadStatus } from '../../lib/state.svelte.js'
  import { closeSheet, toast } from '../../lib/overlay.svelte.js'
  import { api } from '../../lib/api.js'
  import { plName } from '../../lib/playlist.js'
  import { forgetUsers } from './shared.js'
  import { t } from '../../lib/i18n.svelte.js'

  // what the update left (look, preferences, former playlists) – read once: the sheet keeps it while it is open
  const setup = untrack(() => $state.snapshot(S.config.settings.familySetup) || null)
  const former = untrack(() => S.config.playlists.filter((x) => (setup?.playlists || []).includes(x.id) && x.status !== 'papierkorb'))
  const picks = new SvelteSet(former.map((x) => x.id))

  let name = $state(t('Family'))
  if (setup?.name) name = setup.name
  let account = $state(null)   // null: follows the name
  /** Account name from the name as Navidrome accepts it: letters without accents, digits, . _ - */
  const fromName = (s) => s.toLowerCase().normalize('NFKD').replace(/\p{M}/gu, '').replace(/ß/g, 'ss')
    .replace(/[^a-z0-9._-]+/g, '-').replace(/^[^a-z0-9]+|-+$/g, '').slice(0, 40)
  const accountShown = $derived(account ?? fromName(name))
  const avatar = $derived({ id: 'familie', name, icon: setup?.icon || 'i:home', color: setup?.color })

  let busy = $state(false)
  let error = $state('')
  let done = $state(null)   // { account, password } – the password only now
  // the old shared person had an account of its own: it stays a person – the administrator decides whether it goes
  const old = $derived(done && setup?.person ? findPerson(setup.person) : null)

  async function create() {
    if (busy) return
    busy = true
    error = ''
    try {
      await save()   // the server changes the configuration – send open changes first
      const r = await api('/api/family', { body: { name: name.trim(), account: accountShown, playlists: [...picks] } })
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
    {#if old}
      <div class="note grid gap-2 justify-items-start">
        <span>{t('“{name}” stays a person with the account “{account}”. If nobody needs it any more, delete it in its profile.', { name: old.name, account: old.user })}</span>
        <a class="btn sm" href="#/person/{old.id}">{t('Open profile')}</a>
      </div>
    {/if}
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
    {#if former.length}
      <Field label={t('Move to the family')}>
        <div class="hint">{t('These playlists were the family’s before – checked ones become family playlists again.')}</div>
        <div class="grid gap-1.5 mt-1">
          {#each former as x (x.id)}
            <label class="member-row cursor-pointer bg-surface-2">
              <input type="checkbox" class="size-[18px] accent-accent shrink-0" checked={picks.has(x.id)}
                onchange={(e) => { if (e.currentTarget.checked) picks.add(x.id); else picks.delete(x.id) }} />
              <span class="ell">{plName(x)}</span>
            </label>
          {/each}
        </div>
      </Field>
    {/if}
    {#if error}<div class="err-t small" role="alert">{error}</div>{/if}
    <div class="btns">
      <button class="btn ghost" onclick={closeSheet}>{t('Cancel')}</button>
      <button class="btn primary" disabled={busy || !name.trim() || !accountShown} onclick={create}>
        <Icon name="home" size={16} />{busy ? t('One moment …') : t('Set up the family')}
      </button>
    </div>
  </div>
{/if}
