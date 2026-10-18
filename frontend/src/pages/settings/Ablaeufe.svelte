<!-- Settings → Automation: folder watch, steps of “Update everything”, daily refresh. -->
<script>
  import Seg from '../../components/Seg.svelte'
  import Card from './Card.svelte'
  import Row from './Row.svelte'
  import Toggle from './Toggle.svelte'
  import SecItem from './SecItem.svelte'
  import { S, changed } from '../../lib/state.svelte.js'
  import { toast } from '../../lib/overlay.svelte.js'
  import { STEP_INFO } from '../../lib/settings-info.js'
  import { fmt, serverDate } from '../../lib/format.js'
  import { t, locale } from '../../lib/i18n.svelte.js'

  const TAB_OF = { flac: 'opus', lyrics: 'lyrics', cover: 'bibliothek', analyse: 'intel', playlists: 'playlists', scan: 'navidrome', deezer: 'deezer' }
  const DAILY_MODES = $derived([['playlists', t('Playlists')], ['alles', t('Everything')], ['aus', t('Off')]])   // i18n-ignore: the first entries are stored values

  const s = S.config.settings
  s.pipeline ??= ['flac', 'lyrics', 'cover', 'analyse', 'playlists', 'scan', 'deezer']
  S.config.settings.watch ??= {}
  const wt = S.config.settings.watch

  const all = $derived(S.status?.allSteps?.map((x) => x.id) || Object.keys(STEP_INFO))
  const ws = $derived(S.status?.watch || {})
  const last = $derived(S.status?.daily?.date)

  // Rejected switch (last step): redraw the list so it shows as on again
  let stepsKey = $state(0)
  function setStep(id, v) {
    const cur = new Set(s.pipeline)
    v ? cur.add(id) : cur.delete(id)
    if (!cur.size) { toast(t('At least one step'), { error: true }); stepsKey++; return }
    s.pipeline = all.filter((x) => cur.has(x))
    changed()
  }

  function setTime(e) {
    if (/^\d{2}:\d{2}$/.test(e.currentTarget.value)) { s.dailyAt = e.currentTarget.value; changed() }
  }
</script>

<Card title={t('Folder watch')} icon="folder-search" guide="watch">
  <p class="muted small">{t('If you like, Tuttiphon regularly checks whether new music has landed in the music folder, e.g. from Lidarr, and processes it right away: convert, search lyrics, scan Navidrome, rate on Deezer.')}</p>
  <Row label={t('Turn on folder watch')} hint={ws.lastRun ? t('Last on {when} – new files: {n}.', { when: serverDate(ws.lastRun), n: fmt(ws.found || 0) }) : ws.checked ? t('No new music found yet.') : ''}>
    <Toggle obj={wt} key="enabled" def={false} />
  </Row>
  {#if wt.enabled}
    <Row label={t('Check every')}>
      <Seg options={[['5', '5 min'], ['15', '15 min'], ['30', '30 min'], ['60', '1 h']]} value={String(wt.interval || 15)} onchange={(v) => { wt.interval = Number(v); changed() }} />
    </Row>
    <Row label={t('Convert to {codec}', { codec: S.config.settings.opus?.codec === 'aac' ? 'AAC' : 'Opus' })} hint={t('According to the settings under Conversion.')}><Toggle obj={wt} key="convert" /></Row>
    <Row label={t('Search lyrics')} hint={t('Directly from the file tags.')}><Toggle obj={wt} key="lyrics" /></Row>
    <Row label={t('Set Deezer stars')}><Toggle obj={wt} key="deezer" /></Row>
    <div class="hint">{t('Runs as long as Tuttiphon is running – ideally in the Docker container. Freshly copied files get two minutes of rest before they are processed.')}</div>
  {/if}
</Card>

<Card title={t('“Update everything”')} icon="refresh" guide="schritte">
  <p class="muted small mb-3">{t('These steps run one after another when you tap “Update everything” on the home page, and during the daily refresh with “Everything”.')}</p>
  {#key stepsKey}
    <div class="grid gap-1.5">
      {#each all as id (id)}
        {@const [icon, label, desc] = STEP_INFO[id] || ['', id, '']}
        <SecItem on={s.pipeline.includes(id)} onswitch={(v) => setStep(id, v)} {icon} {label} {desc}>
          <a class="btn sm ghost" href="#/einstellungen/{TAB_OF[id]}">{t('Settings')}</a>
        </SecItem>
      {/each}
    </div>
  {/key}
</Card>

<Card title={t('Daily refresh')} icon="sunrise">
  <Row label={t('What happens every day')} hint={t('“Playlists” rebuilds mixes that are due and switches seasons. “Everything” also runs the steps above.')}>
    <Seg options={DAILY_MODES} value={s.dailyMode || 'playlists'} onchange={(v) => { s.dailyMode = v; changed() }} />
  </Row>
  {#if (s.dailyMode || 'playlists') !== 'aus'}
    <Row label={t('Time')} hint={t('Runs as long as Tuttiphon is running, on the PC or in the Docker container on the NAS. Anything missed is caught up at the next start.')}>
      <input class="input w-[120px]" type="time" value={s.dailyAt || '05:30'} onchange={setTime} />
    </Row>
  {/if}
  <div class="hint">{last ? t('Last run: {date}.', { date: new Date(last + 'T12:00').toLocaleDateString(locale(), { weekday: 'long', day: 'numeric', month: 'long' }) }) : t('Has never run so far.')}</div>
</Card>
