<!-- Settings → Notifications: through the app (web push, this device) and optionally ntfy – server, topic,
     Tuttiphon address, events, test. -->
<script>
  import Icon from '../../components/Icon.svelte'
  import Card from './Card.svelte'
  import Row from './Row.svelte'
  import Toggle from './Toggle.svelte'
  import PushDevice from '../../components/PushDevice.svelte'
  import { S, changed, save } from '../../lib/state.svelte.js'
  import { api } from '../../lib/api.js'
  import { toast } from '../../lib/overlay.svelte.js'
  import { t } from '../../lib/i18n.svelte.js'

  S.config.settings.notify ??= {}
  const nt = S.config.settings.notify
  nt.events ??= {}
  const EVENTS = $derived([
    ['failed', t('A run failed'), t('To the administrators’ devices and your topic.')],
    ['newMusic', t('New music has been processed'), t('After the folder watch, to the administrators’ devices and your topic.')],
    ['autoAssigned', t('New bands were classified'), t('Which band went into which music world, to the administrators’ devices and your topic.')],
    ['favorites', t('News from favorite bands'), t('To the person concerned, on their devices and their topic from the profile.')],
    ['review', t('The monthly recap is here'), t('On the first of the month to the person, if they have “Your month”.')],
    ['weekly', t('New for you this week'), t('On Mondays to the person, if they have “Discovered for you” or “Album of the week”.')],
    ['year', t('Your year in music'), t('In the first week of December to the person – listening time, band of the year and discoveries as a story.')],
  ])
  const set = (k, v) => { if (v) nt[k] = v; else delete nt[k]; changed() }
  const withTopic = $derived(S.config.personen.filter((p) => p.push).map((p) => p.name))

  async function test() {
    try {
      await save()   // an address or topic just changed applies right away
      const r = await api('/api/notify/test', { body: { topic: nt.topic } })
      toast(r.ok ? t('Test message sent') : r.error, { error: !r.ok })
    } catch (e) { toast(e.message, { error: true }) }
  }
</script>

<Card title={t('Notifications on your phone')} icon="bell" guide="notify">
  <p class="muted small">{t('Tuttiphon notifies you directly through the app, on every device where you turn it on. Each person turns on their devices in their profile. Optionally it also works via ntfy.')}</p>
  <Row label={t('Notifications')} hint={t('Turns everything on or off.')}>
    <Toggle label={t('Notifications')} obj={nt} key="enabled" def={false} />
  </Row>
  <Row label={t('This device')} hint={t('Gets the notifications for administrators and those of your people.')} full>
    <PushDevice />
  </Row>
</Card>

<Card title={t('Via ntfy')} icon="smartphone">
  <p class="muted small">{t('Instead of or in addition to the app: short messages via ntfy, free via ntfy.sh or your own ntfy server. Install the ntfy app on your phone and subscribe to the topic. Each person can enter their own topic in their profile.')}</p>
  <Row label={t('ntfy server')} hint={t('Without your own server, just leave https://ntfy.sh.')}>
    <input class="input w-[260px] max-mobile:w-full" value={nt.server || ''} placeholder="https://ntfy.sh" onchange={(e) => set('server', e.currentTarget.value.trim())} /><!-- i18n-ignore: example address -->
  </Row>
  <Row label={t('Your topic')} hint={t('For notifications to you. Only letters, digits, - and _. Anyone who knows the topic can read along.')}>
    <div class="flex gap-2 items-center max-mobile:w-full">
      <input class="input w-[200px] max-mobile:flex-1" value={nt.topic || ''} placeholder="tuttiphon-admin-…" onchange={(e) => set('topic', e.currentTarget.value.trim())} /><!-- i18n-ignore: example topic -->
      <button class="btn sm" disabled={!nt.enabled || !nt.topic} onclick={test}>{t('Send test')}</button>
    </div>
  </Row>
  <Row label={t('Tuttiphon address')} hint={t('Tapping a message opens Tuttiphon – e.g. the address via the reverse proxy.')}>
    <input class="input w-[260px] max-mobile:w-full" value={nt.url || ''} placeholder="https://tuttiphon.example.de" onchange={(e) => set('url', e.currentTarget.value.trim())} /><!-- i18n-ignore: example address -->
  </Row>
  <Row label={t('Own topic in the profile')} hint={t('People with their own topic get their notifications directly.')}>
    <span class="small">{withTopic.length ? withTopic.join(', ') : t('nobody yet')}</span>
  </Row>
  <div class="hint">{t('Protected topics on your own server: enter an access token as NTFY_TOKEN in the .env or in docker-compose.')}{#if S.status?.env?.ntfyToken}{t(' A token is stored.')}{/if}</div>
</Card>

<Card title={t('What to notify about?')} icon="sparkles">
  {#each EVENTS as [key, label, hint] (key)}
    <Row {label} {hint}><Toggle label={t('Own topic in the profile')} obj={nt.events} {key} /></Row>
  {/each}
</Card>
