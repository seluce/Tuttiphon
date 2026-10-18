<!--
  Content of the dialog “Password for <user>” (lib/account.js → passwordModal): input and “Test”.
  The password ends up in form.password – the dialog reads it from there after closing.
-->
<script>
  import { api } from '../../lib/api.js'
  import { t } from '../../lib/i18n.svelte.js'

  let { user, form } = $props()
  let password = $state('')
  let result = $state({ text: '', cls: '' })

  $effect(() => { form.password = password })

  async function test() {
    result = { text: t('testing …'), cls: '' }
    const r = await api('/api/env/test', { body: { user, password: password || undefined } }).catch((e) => ({ ok: false, error: e.message }))
    result = { text: r.ok ? t('✓ works') : `✕ ${r.error}`, cls: r.ok ? 'ok-t' : 'err-t' }
  }
</script>

<p class="muted">{t('With it, Tuttiphon sets stars for this account, shows its personal statistics and takes its stars & favorites into account in the preview. It is stored only on your NAS.')}</p>
<input class="input w-full" type="password" autocomplete="new-password" placeholder={t('Password')} bind:value={password} />
<div class="btns">
  <button type="button" class="btn sm" onclick={test}>{t('Test')}</button>
  <div class="small {result.cls}">{result.text}</div>
</div>
