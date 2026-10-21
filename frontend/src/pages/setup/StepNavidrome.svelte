<!-- Setup step 1: connection to Navidrome – the status and, if something can be changed, the form of
     Settings → Navidrome (saved right away). Without a working connection the assistant does not go on. Below the
     language of the server (the names in Navidrome) – only in the draft d. -->
<script>
  import Icon from '../../components/Icon.svelte'
  import Card from '../settings/Card.svelte'
  import Connection from '../settings/Connection.svelte'
  import Row from '../settings/Row.svelte'
  import Select from '../../components/Select.svelte'
  import { S, loadStatus } from '../../lib/state.svelte.js'
  import { LANGUAGES, t } from '../../lib/i18n.svelte.js'

  let { d } = $props()

  const nav = $derived(S.status?.navidrome)
  const env = $derived(S.status?.env || {})
  // everything the form could change comes from docker-compose.yaml – then there is nothing to type here
  const fixed = $derived(['NAV_URL', 'NAV_ADMIN_USER', 'NAV_ADMIN_PASS'].every((k) => (env.locked || []).includes(k)))
  let checking = $state(false)
  async function again() {
    checking = true
    await loadStatus().catch(() => {})
    checking = false
  }
</script>

<Card title={t('Connect to Navidrome')} icon="plug">
  <p class="muted small">{t('Tuttiphon reads your library from Navidrome and writes the playlists back there. For that it needs the address of Navidrome and an admin account – in the background, for scans, playlists and their owners.')}</p>
  {#if !S.status}
    <div class="skel h-[52px]"></div>
  {:else if nav?.ok}
    <div class="member-row">
      <Icon name="check" size={18} class="ok-t shrink-0" />
      <div class="flex-1 min-w-0">
        <b>{t('Connected – Navidrome {version}', { version: String(nav.version || '').split(' ')[0] })}</b>
        {#if env.url}<div class="tiny muted ell">{env.url}</div>{/if}
      </div>
    </div>
  {:else}
    <div class="note border border-warn/40 flex items-start gap-2.5 flex-wrap">
      <Icon name="alert" size={18} class="warn-t shrink-0 mt-0.5" />
      <span class="flex-1 min-w-[200px]">{nav?.error ? t('Tuttiphon cannot reach Navidrome yet: {error}', { error: nav.error }) : t('Tuttiphon cannot reach Navidrome yet.')}</span>
      <button class="btn sm" disabled={checking} onclick={again}><Icon name="refresh" size={14} />{t('Check again')}</button>
    </div>
  {/if}
  {#if S.status}
    {#if fixed}
      <div class="note">{t('The connection is set in docker-compose.yaml – it can only be changed there.')}</div>
    {:else if nav?.ok}
      <details class="fold">
        <summary><Icon name="edit" size={16} />{t('Change connection')}</summary>
        <div class="in"><Connection /></div>
      </details>
    {:else}
      <Connection />
    {/if}
    {#if !nav?.ok}
      <div class="hint">{t('Without a working connection Tuttiphon can neither read your library nor write playlists – so the next steps only make sense once it works. Can’t get it to work right now? Skip the setup and connect later under Settings → Navidrome.')}</div>
    {/if}
  {/if}
  <Row label={t('Language of the server')} hint={t('For run logs, notifications and the names Tuttiphon gives playlists and music worlds by itself. Delivered vibes that still have their original name are renamed too.')}>
    <Select options={LANGUAGES.map((l) => [l.key, l.name])} value={d.language} onchange={(v) => (d.language = v)} aria-label={t('Language of the server')} />
  </Row>
</Card>
