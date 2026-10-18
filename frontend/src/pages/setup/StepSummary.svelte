<!-- Setup step 7: summary of the draft – one row per step with “Change”, and the switch for the first run
     (“Update everything” with the chosen steps, only when it is turned on). -->
<script>
  import Icon from '../../components/Icon.svelte'
  import Switch from '../../components/Switch.svelte'
  import Card from '../settings/Card.svelte'
  import Row from '../settings/Row.svelte'
  import { S } from '../../lib/state.svelte.js'
  import { STEP_INFO } from '../../lib/settings-info.js'
  import { pipelineOf } from './draft.js'
  import { t } from '../../lib/i18n.svelte.js'

  /** d: draft · intel: GET /api/intel (is the AI installed?) · goto(i): back to a step ·
   *  start: start the first run after “Finish” */
  let { d, intel, goto, start = $bindable(false) } = $props()

  const nav = $derived(S.status?.navidrome)
  const users = $derived((S.status?.env?.users || []).map((u) => u.name))
  const DEPTH = $derived({ schnell: t('Fast'), standard: t('Standard'), gruendlich: t('Thorough'), tief: t('Deep') })   // i18n-ignore: stored values
  const ORIGINAL = $derived({ archive: t('originals to the archive'), keep: t('originals are kept'), delete: t('originals are deleted') })
  const DAILY = $derived({ playlists: t('playlists'), alles: t('everything') })   // i18n-ignore: stored values

  const rows = $derived.by(() => {
    const op = d.opus, ly = d.lyrics, an = d.analysis, dz = d.deezer
    const providers = ly.providers.filter((p) => p.on).map((p) => (p.id === 'lrclib' ? 'LRCLIB' : 'NetEase'))
    const accounts = dz.users ?? users
    return [
      ['plug', 'Navidrome', nav?.ok ? t('Connected – Navidrome {version}', { version: String(nav.version || '').split(' ')[0] }) : t('Not connected')],
      ['headphones', t('Conversion'), op.enabled
        ? [`${op.codec === 'aac' ? 'AAC' : 'Opus'} · ${op.codec === 'aac' ? op.aacBitrate : op.bitrate} kbit/s`, ORIGINAL[op.original]].join(' · ')
        : t('Off – files stay as they are')],
      ['mic', t('Lyrics'), [
        ly.fetch ? t('search with {providers}', { providers: providers.join(', ') }) : t('no search'),
        ly.fetch && ly.savePlain ? t('also text only') : null,
        ly.fetch && ly.upgradePlain ? t('“text only” is replaced by synced lyrics later') : null,
        ly.cleanup ? t('duplicate lyrics files are deleted') : null,
      ].filter(Boolean).join(' · ')],
      ['brain', t('Understand music'), [
        an.enabled ? (an.ml && intel?.ml?.available ? t('measurement and AI · {depth}', { depth: DEPTH[an.depth] }) : t('measurement · {depth}', { depth: DEPTH[an.depth] })) : t('no sound analysis'),
        an.fingerprints ? t('audio fingerprints') : null,
        an.night.enabled ? t('at night {from}–{to}', { from: an.night.from, to: an.night.to }) : t('no night analysis'),
      ].filter(Boolean).join(' · ')],
      ['star', t('Deezer stars'), dz.on
        ? [accounts.length ? t('for {accounts}', { accounts: accounts.join(', ') }) : t('no accounts yet'),
          dz.overwriteManual ? t('overwrites stars given by hand') : t('stars given by hand stay')].join(' · ')
        : t('Off')],
      ['sunrise', t('Automation'), [
        d.dailyMode === 'aus' ? t('no daily refresh') : t('every day at {time}: {what}', { time: d.dailyAt, what: DAILY[d.dailyMode] }),
        d.watch.enabled ? t('folder watch every {n} min', { n: d.watch.interval }) : t('no folder watch'),
      ].join(' · ')],
    ]
  })
  const steps = $derived(pipelineOf(S.config.settings, d).map((id) => STEP_INFO[id]?.[1] || id).join(', '))
</script>

<Card title={t('All set?')} icon="check-circle">
  <p class="muted small">{t('This is what Tuttiphon will do. Everything can be changed later under Settings – and this assistant is under Settings → General.')}</p>
  <div class="grid grid-cols-[minmax(0,1fr)] gap-1.5">
    {#each rows as [icon, title, value], i (title)}
      <div class="member-row items-start bg-surface-2">
        <span class="hi shrink-0"><Icon name={icon} size={18} /></span>
        <div class="flex-1 min-w-0">
          <b>{title}</b>
          <div class="small muted">{value}</div>
        </div>
        <button class="btn sm ghost shrink-0" onclick={() => goto(i)}>{t('Change')}</button>
      </div>
    {/each}
  </div>
  <Row label={t('Start the first run now')} hint={nav?.ok
    ? t('Runs “Update everything” once after “Finish”: {steps}. With a large library the first run takes a while – you can follow it on the home page and stop it at any time.', { steps })
    : t('Only possible with a working connection to Navidrome.')}>
    <Switch bind:checked={start} disabled={!nav?.ok} />
  </Row>
</Card>
