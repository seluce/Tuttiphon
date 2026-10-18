<!-- Setup step 4: understand music – sound analysis, AI (only where it is installed), depth with the time estimate,
     audio fingerprints, night analysis. Changes only the draft d. -->
<script>
  import Switch from '../../components/Switch.svelte'
  import Card from '../settings/Card.svelte'
  import Row from '../settings/Row.svelte'
  import Depth from '../settings/Depth.svelte'
  import { toast } from '../../lib/overlay.svelte.js'
  import { t } from '../../lib/i18n.svelte.js'

  /** d: draft · intel: state of the analysis from GET /api/intel (null = loading, false = no answer) */
  let { d, intel } = $props()
  const an = $derived(d.analysis)
  const noop = () => {}
  const ml = $derived(intel?.ml || {})
  const fp = $derived(intel?.fingerprints || {})

  function setNight(key, e) {
    const el = e.currentTarget
    if (!/^\d{2}:\d{2}$/.test(el.value)) return
    if (el.value === an.night[key === 'from' ? 'to' : 'from']) {
      toast(t('Start and end must not be the same.'), { error: true })
      el.value = an.night[key]
      return
    }
    an.night[key] = el.value
  }
</script>

<Card title={t('Understand music')} icon="brain">
  <p class="muted small">{t('Tuttiphon listens to every song – completely locally, without a cloud and without costs. From that come sound vibes such as “Falling asleep”, mixes with smooth transitions and the classification of new bands. It works gently: mostly at night, during the day only a few minutes per run.')}</p>
  <Row label={t('Turn on sound analysis')} hint={t('Measures tempo, energy, danceability and timbre of every song.')}>
    <Switch checked={an.enabled} onchange={(v) => (an.enabled = v)} />
  </Row>
  {#if an.enabled}
    {#if intel === null}
      <div class="skel h-[44px]"></div>
    {:else if ml.available}
      <Row label={t('Add AI')} hint={t('Also recognizes mood, vocals or instrumental, instruments, themes, key and music style.')}>
        <Switch checked={an.ml} onchange={(v) => (an.ml = v)} />
      </Row>
    {:else if intel}
      <!-- one note: the server's reason (Essentia or models missing) if there is one, otherwise the general one -->
      <div class="note">{ml.reason ? t('AI sound analysis: {reason} The measurement works without it.', { reason: ml.reason })
        : t('The AI sound analysis is not installed here – it is part of the Docker image. The measurement works without it.')}</div>
    {/if}
    <Depth an={an} a={intel?.audio || {}} onchange={noop} />
  {/if}
  <Row label={t('Make audio fingerprints')} hint={t('Finds the same recording stored twice – also as another format, in another folder or on another album. About 3 KB per song.')}>
    <Switch checked={an.fingerprints} onchange={(v) => (an.fingerprints = v)} />
  </Row>
  {#if intel && fp.available === false}
    <div class="small warn-t">{t('fpcalc is {why} – it is included in the Docker image.', { why: fp.why || t('not installed') })}</div>
  {/if}
  <Row label={t('Night analysis')} hint={t('At night Tuttiphon works through whatever is still open, without a time limit. On a NAS the first pass of a large library takes several nights – after that only new songs are left. The nightly Deezer refresh and the weekly cover search also run in this window.')}>
    <Switch checked={an.night.enabled} onchange={(v) => (an.night.enabled = v)} />
  </Row>
  {#if an.night.enabled}
    <Row label={t('Time window')}>
      <span class="flex items-center gap-2">
        <input class="input w-[120px]" type="time" value={an.night.from} onchange={(e) => setNight('from', e)} aria-label={t('Night analysis from')} />
        {t('to')}
        <input class="input w-[120px]" type="time" value={an.night.to} onchange={(e) => setNight('to', e)} aria-label={t('Night analysis until')} />
      </span>
    </Row>
  {/if}
</Card>
