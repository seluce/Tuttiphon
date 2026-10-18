<!--
  Connection to Navidrome: address, address for links, admin account, "Test connection" and "Save" (PUT /api/env).
  Used by Settings → Navidrome and the setup assistant. Values from docker-compose.yaml are gray (locked).
-->
<script>
  import { untrack } from 'svelte'
  import { S, loadStatus, loadLibrary } from '../../lib/state.svelte.js'
  import { toast, confirmDialog } from '../../lib/overlay.svelte.js'
  import { api } from '../../lib/api.js'
  import { t } from '../../lib/i18n.svelte.js'

  const env = $derived(S.status?.env || {})
  const locked = $derived(new Set(env.locked || []))

  // inputs: refill when the credentials in the status really change (it is fetched every 30 s)
  let url = $state('')
  let pub = $state('')
  let admin = $state('')
  let pass = $state('')
  const envKey = $derived(JSON.stringify(S.status?.env ?? null))
  $effect(() => {
    envKey
    untrack(() => {
      url = env.url || ''
      pub = env.publicUrl || ''
      admin = env.admin || ''
      pass = ''
    })
  })

  let out = $state({ text: '', cls: '' })
  const values = () => ({ url: url.trim().replace(/\/+$/, ''), user: admin.trim(), password: pass || undefined })

  async function test() {
    out = { text: t('testing …'), cls: 'muted' }
    const r = await api('/api/env/test', { body: values() }).catch((e) => ({ ok: false, error: e.message }))
    out = { text: r.ok ? t('✓ Connected – Navidrome {version}', { version: String(r.version || '').split(' ')[0] }) : `✕ ${r.error}`, cls: r.ok ? 'ok-t' : 'err-t' }
    return r.ok
  }

  async function saveConn() {
    if (!await test() && !await confirmDialog(t('Save anyway?'), t('The connection does not work with these details right now.'), t('Save'))) return
    const v = values()
    const body = {}
    if (!locked.has('NAV_URL') && v.url) body.NAV_URL = v.url
    if (!locked.has('NAV_PUBLIC_URL')) body.NAV_PUBLIC_URL = pub.trim() ? pub.trim().replace(/\/+$/, '') : null
    if (!locked.has('NAV_ADMIN_USER') && v.user) body.NAV_ADMIN_USER = v.user
    if (!locked.has('NAV_ADMIN_PASS') && v.password) body.NAV_ADMIN_PASS = v.password
    try { await api('/api/env', { method: 'PUT', body }) } catch (e) { toast(e.message, { error: true }); return }
    toast(t('Connection saved ✓'))
    pass = ''
    await loadStatus()
    loadLibrary(true).catch(() => {})
  }
</script>

<div class="frow">
  <label class="f">{t('Server address for Tuttiphon')}
    <input class="input w-full" bind:value={url} placeholder="http://192.168.1.10:4533" disabled={locked.has('NAV_URL')} /><!-- i18n-ignore: example address -->
  </label>
  <label class="f">{t('Address in the browser for “Open in Navidrome” links')}
    <input class="input w-full" bind:value={pub} placeholder={t('empty = same as server address')} disabled={locked.has('NAV_PUBLIC_URL')} />
  </label>
</div>
<div class="frow">
  <label class="f">{t('Admin user')}
    <input class="input w-full" bind:value={admin} placeholder="root" disabled={locked.has('NAV_ADMIN_USER')} /><!-- i18n-ignore: example account name -->
  </label>
  <label class="f">{t('Admin password')}
    <input class="input w-full" type="password" autocomplete="new-password" bind:value={pass}
      placeholder={env.adminOk ? t('•••••• leave unchanged') : t('Password')} disabled={locked.has('NAV_ADMIN_PASS')} />
  </label>
</div>
{#if locked.size}
  <div class="note">{t('Gray = set in docker-compose.yaml or as an environment variable and only changeable there: {vars}.', { vars: [...locked].join(', ') })}</div>
{/if}
<div class="btns">
  <button class="btn" onclick={test}>{t('Test connection')}</button>
  <button class="btn primary" onclick={saveConn}>{t('Save')}</button>
  <div class="small {out.cls}">{out.text}</div>
</div>
<div class="hint">{t('Tuttiphon needs the admin account in the background for scans, playlists and their owners. Credentials are only stored on your NAS.')}</div>
