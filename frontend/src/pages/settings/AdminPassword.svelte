<!-- Password of the local administrator (Settings → Users & permissions): set it (Tuttiphon on its own computer,
     without sign-in) or change it – kept on the server as a hash only. A password from docker-compose.yaml can only be
     changed there. -->
<script>
  import { S, loadStatus } from '../../lib/state.svelte.js'
  import { toast } from '../../lib/overlay.svelte.js'
  import { api } from '../../lib/api.js'
  import { t } from '../../lib/i18n.svelte.js'

  const source = $derived(S.status?.env?.adminPassword || '')   // env · stored · '' (none yet)

  let current = $state('')
  let password = $state('')
  let password2 = $state('')
  let out = $state({ text: '', cls: '' })
  let busy = $state(false)

  async function save() {
    if (source === 'stored' && !current) { out = { text: t('Please enter the current password.'), cls: 'err-t' }; return }
    if (password.length < 8) { out = { text: t('The password needs at least 8 characters.'), cls: 'err-t' }; return }
    if (password !== password2) { out = { text: t('The two passwords are not the same.'), cls: 'err-t' }; return }
    busy = true
    out = { text: t('checking …'), cls: 'muted' }
    const first = source === ''
    try {
      await api('/api/admin-password', { body: { current, password } })
      current = password = password2 = ''
      out = { text: '', cls: '' }
      if (first) {   // sign-in is on from now on – this browser is signed in as local administrator
        location.reload()
        return
      }
      toast(t('Password changed ✓'))
      loadStatus()
    } catch (e) {
      out = { text: e.message, cls: 'err-t' }
    }
    busy = false
  }
</script>

{#if source === 'env'}
  <div class="note">{t('Its password is set in docker-compose.yaml as TUTTIPHON_ADMIN_PASSWORD and can only be changed there.')}</div>
{:else}
  <div class="grid gap-2.5">
    <div class="frow">
      {#if source === 'stored'}
        <label class="f">{t('Current password')}
          <input class="input w-full" type="password" autocomplete="current-password" bind:value={current} />
        </label>
      {/if}
      <label class="f">{source === 'stored' ? t('New password') : t('Password of the local administrator')}
        <input class="input w-full" type="password" autocomplete="new-password" bind:value={password} />
      </label>
      <label class="f">{t('Repeat password')}
        <input class="input w-full" type="password" autocomplete="new-password" bind:value={password2} />
      </label>
    </div>
    <div class="btns">
      <button class="btn primary" disabled={busy} onclick={save}>{source === 'stored' ? t('Change password') : t('Set password')}</button>
      <div class="small {out.cls}" role="status">{out.text}</div>
    </div>
    <div class="hint">{source === 'stored'
      ? t('Tuttiphon keeps only a fingerprint of the password, not the password itself. Forgotten? Delete the file admin_password.json in the folder state of the data folder – Tuttiphon then asks for a new one with a setup code from the container log.')
      : t('With a password, Tuttiphon asks everyone to sign in – with their Navidrome account or as local administrator.')}</div>
  </div>
{/if}
