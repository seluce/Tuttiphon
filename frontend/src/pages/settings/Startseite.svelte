<!-- Settings → Home page: sections on/off and their order, header area. -->
<script>
  import Card from './Card.svelte'
  import Row from './Row.svelte'
  import Toggle from './Toggle.svelte'
  import SecItem from './SecItem.svelte'
  import MoveButtons from './MoveButtons.svelte'
  import { S, changed } from '../../lib/state.svelte.js'
  import { START_SECTIONS } from '../../lib/settings-info.js'
  import { t } from '../../lib/i18n.svelte.js'

  S.config.settings.start ??= {}
  const conf = S.config.settings.start
  conf.sections ??= Object.keys(START_SECTIONS).map((id) => ({ id, on: true }))
  for (const id of Object.keys(START_SECTIONS)) if (!conf.sections.some((x) => x.id === id)) conf.sections.push({ id, on: false })

  const stepsText = $derived((S.status?.steps || []).map((s) => s.title).join(' → ') || '–')
</script>

<Card title={t('Home page sections')} icon="home">
  <p class="muted small mb-3">{t('Turn them on and off and sort them with ↑ ↓ – the home page shows them in this order.')}</p>
  <div class="grid gap-1.5">
    {#each conf.sections as sct, i (sct.id)}
      {@const [label, desc, icon] = START_SECTIONS[sct.id] || [sct.id, '', 'info']}
      <SecItem on={sct.on} onswitch={(v) => { sct.on = v; changed() }} {icon} {label} {desc}>
        <MoveButtons list={conf.sections} {i} />
      </SecItem>
    {/each}
  </div>
</Card>

<Card title={t('At the top of the header')}>
  <Row label={t('Show steps')} hint={t('Show below the big buttons, as a fold-out, what “Update everything” does.')}>
    <Toggle obj={conf} key="showSteps" />
  </Row>
  <Row label={t('“Update everything”')} hint={t('Runs: {steps}.', { steps: stepsText })}>
    <a class="btn sm" href="#/einstellungen/ablaeufe">{t('Choose steps →')}</a>
  </Row>
</Card>
