<!-- Notifications via the app on this device (lib/push.js): turn on, test, turn off. -->
<script>
  import Icon from './Icon.svelte'
  import { toast } from '../lib/overlay.svelte.js'
  import { S } from '../lib/state.svelte.js'
  import { state as pushState, enable, disable, test } from '../lib/push.js'
  import { fmt } from '../lib/format.js'
  import { t, tn } from '../lib/i18n.svelte.js'

  let st = $state(null)
  let busy = $state(false)
  // Settings → Notifications: the main switch (right away, even before it is saved)
  const enabled = $derived(!!S.config?.settings?.notify?.enabled)
  const load = () => pushState().then((s) => (st = s)).catch((e) => (st = { supported: false, why: 'fehler', error: e.message }))
  load()

  async function run(fn, done) {
    busy = true
    try {
      const r = await fn()
      if (r && r.ok === false) toast(r.error, { error: true })
      else if (done) toast(done)
    } catch (e) {
      toast(e.message, { error: true })
    } finally {
      busy = false
      load()
    }
  }
  const WHY = $derived({
    https: t('To do this, open Tuttiphon via its https address.'),
    homescreen: t('On iPhone, first add Tuttiphon to the Home Screen and open it from there.'),
    browser: t('This browser cannot receive notifications.'),
    server: t('Something is still missing on the server for this – the Docker container includes everything.'),
  })
</script>

{#if !st}
  <div class="skel h-[36px]"></div>
{:else if !st.supported}
  <p class="muted small">{t('Not possible on this device. {why}', { why: WHY[st.why] || st.error || '' })}</p>
{:else if st.permission === 'denied'}
  <p class="muted small">{t('Notifications are blocked for Tuttiphon. Allow them again in the browser settings.')}</p>
{:else if st.on}
  <div class="flex flex-wrap gap-2 items-center">
    <span class="small ok-t flex items-center gap-1.5"><Icon name="check" size={15} />{t('This device receives notifications')}</span>
    <span class="btns ml-auto">
      <button class="btn sm" disabled={busy || !st.enabled} onclick={() => run(test, t('Test message sent'))}>{t('Send test')}</button>
      <button class="btn sm ghost" disabled={busy} onclick={() => run(disable, t('Turned off for this device'))}>{t('Turn off')}</button>
    </span>
  </div>
  {#if st.devices > 1}<div class="hint">{tn(st.devices, '{n} device is registered.', '{n} devices are registered.')}</div>{/if}
{:else}
  <button class="btn sm primary justify-self-start" disabled={busy || !enabled} onclick={() => run(enable, t('Turned on for this device'))}>
    <Icon name="bell" size={15} />{t('Turn on for this device')}
  </button>
  {#if !enabled}<div class="hint">{t('Turn on notifications above first.')}</div>{/if}
{/if}
