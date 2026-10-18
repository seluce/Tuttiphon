<!-- Setup step 6: what runs by itself – the daily refresh (off / playlists / everything) with its time, and the folder
     watch for new music. Changes only the draft d. -->
<script>
  import Seg from '../../components/Seg.svelte'
  import Switch from '../../components/Switch.svelte'
  import Card from '../settings/Card.svelte'
  import Row from '../settings/Row.svelte'
  import { t } from '../../lib/i18n.svelte.js'

  let { d } = $props()
  const DAILY_MODES = $derived([['playlists', t('Playlists')], ['alles', t('Everything')], ['aus', t('Off')]])   // i18n-ignore: the first entries are stored values

  function setTime(e) {
    if (/^\d{2}:\d{2}$/.test(e.currentTarget.value)) d.dailyAt = e.currentTarget.value
  }
</script>

<Card title={t('What should run by itself?')} icon="sunrise">
  <p class="muted small">{t('Tuttiphon can keep everything up to date by itself every day – and pick up new music as soon as it lands in the music folder. Both run as long as Tuttiphon is running, ideally in the Docker container on the NAS.')}</p>
  <Row label={t('What happens every day')} hint={t('“Playlists” rebuilds the mixes that are due and switches seasons. “Everything” also runs the steps of “Update everything” – conversion, lyrics, covers, understanding music and Deezer, as far as they are on.')}>
    <Seg options={DAILY_MODES} value={d.dailyMode} onchange={(v) => (d.dailyMode = v)} />
  </Row>
  {#if d.dailyMode !== 'aus'}
    <Row label={t('Time')} hint={t('Anything missed is caught up at the next start.')}>
      <input class="input w-[120px]" type="time" value={d.dailyAt} onchange={setTime} aria-label={t('Time')} />
    </Row>
  {/if}
  <Row label={t('Turn on folder watch')} hint={t('If you like, Tuttiphon regularly checks whether new music has landed in the music folder, e.g. from Lidarr, and processes it right away: convert, search lyrics, scan Navidrome, rate on Deezer.')}>
    <Switch checked={d.watch.enabled} onchange={(v) => (d.watch.enabled = v)} />
  </Row>
  {#if d.watch.enabled}
    <Row label={t('Check every')}>
      <Seg options={[['5', '5 min'], ['15', '15 min'], ['30', '30 min'], ['60', '1 h']]} value={String(d.watch.interval)} onchange={(v) => (d.watch.interval = Number(v))} />
    </Row>
  {/if}
</Card>
