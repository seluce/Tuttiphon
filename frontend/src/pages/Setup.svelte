<!--
  Setup assistant (#/einrichtung, administrators): what should Tuttiphon do? Navidrome → conversion → lyrics →
  understand music → Deezer stars → automation → summary. Every step starts with the current value (on a new
  installation the defaults). The connection is saved right away; everything else is a draft (pages/setup/draft.js)
  until “Finish”. “Finish” and “Skip setup” set settings.setup = {done: true, at}. A new installation leads the first
  administrator here once after signing in (App.svelte); afterwards it is under Settings → General.
-->
<script>
  import { untrack } from 'svelte'
  import Icon from '../components/Icon.svelte'
  import PageHead from '../components/PageHead.svelte'
  import { showChosen } from '../components/Seg.svelte'
  import StepNavidrome from './setup/StepNavidrome.svelte'
  import StepConvert from './setup/StepConvert.svelte'
  import StepLyrics from './setup/StepLyrics.svelte'
  import StepMusic from './setup/StepMusic.svelte'
  import StepDeezer from './setup/StepDeezer.svelte'
  import StepAutomation from './setup/StepAutomation.svelte'
  import StepSummary from './setup/StepSummary.svelte'
  import { PIPELINE, draftFrom, applyDraft } from './setup/draft.js'
  import { S, changed, save, loadStatus, reloadConfig, runTask } from '../lib/state.svelte.js'
  import { toast, confirmDialog } from '../lib/overlay.svelte.js'
  import { go } from '../lib/router.svelte.js'
  import { api } from '../lib/api.js'
  import { startTour } from '../lib/tour.svelte.js'
  import { clone, today } from '../lib/format.js'
  import { t } from '../lib/i18n.svelte.js'

  const STEPS = $derived(['Navidrome', t('Conversion'), t('Lyrics'), t('Understand music'), t('Deezer stars'), t('Automation'), t('Summary')])
  const LAST = 6

  // the draft: a copy of the settings – S.config only changes with “Finish”
  const before = untrack(() => draftFrom($state.snapshot(S.config.settings)))
  const d = $state(clone(before))
  let step = $state(0)
  let start = $state(false)   // “Start the first run now”
  let busy = $state(false)

  const connected = $derived(!!S.status?.navidrome?.ok)

  /** what is installed for the analysis (GET /api/intel – needs the library): loaded once the steps after the
   *  connection are reached; null = not yet, false = no answer */
  let intel = $state.raw(null)
  let asked = false
  $effect(() => {
    if (step < 1 || asked) return
    asked = true
    api('/api/intel').then((r) => { intel = r }).catch(() => { intel = false })
  })

  // without a connection the assistant does not leave the first step (everything after it needs Navidrome)
  const locked = $derived(step === 0 && !connected)
  function show(i) {
    if (i > 0 && locked) return
    step = i
  }
  $effect(() => {
    void step
    untrack(() => window.scrollTo({ top: 0, behavior: 'smooth' }))
  })

  /** Back to the home page; the tour comes afterwards if this account has not seen it yet. */
  function leave() {
    go('#/')
    setTimeout(() => startTour(), 900)
  }

  /** Save – false if the server rejected it (save() then shows the error and reloads the configuration). */
  async function store() {
    const saves = S.saved   // counts successful saves
    changed()
    await save()
    return S.saved > saves
  }

  async function skip() {
    if (busy) return
    if (!await confirmDialog(t('Skip the setup?'), t('Tuttiphon keeps its current settings. You find everything under Settings – and this assistant under Settings → General.'), t('Skip'))) return
    busy = true
    S.config.settings.setup = { done: true, at: today() }
    const ok = await store()
    busy = false
    if (!ok) return
    toast(t('Everything is under Settings whenever you need it.'))
    leave()
  }

  async function finish() {
    if (busy) return
    busy = true
    const spoke = S.config.settings.language
    applyDraft(S.config.settings, $state.snapshot(d), before, today())
    const ok = await store()
    busy = false
    if (!ok) return
    if (S.config.settings.language !== spoke) await reloadConfig().catch(() => {})   // the server renamed the delivered vibes
    loadStatus().catch(() => {})   // “Update everything” on the home page uses the new steps
    if (start && connected) {
      const pipe = S.config.settings.pipeline
      const steps = (S.status?.allSteps?.map((x) => x.id) || PIPELINE).filter((id) => pipe.includes(id))
      if (await runTask(steps)) toast(t('Setup saved – the first run is starting.'))
    } else {
      toast(t('Setup saved ✓'))
    }
    leave()
  }
</script>

<div class="page max-w-[1100px]">
  <PageHead title={t('Set up Tuttiphon')} eyebrow={t('Setup assistant')}
    sub={t('A few questions about what Tuttiphon should do – each with a sensible default. Apart from the connection, nothing changes until you tap “Finish”.')}>
    {#snippet actions()}
      <button class="btn ghost" disabled={busy} onclick={skip}>{t('Skip setup')}</button>
    {/snippet}
  </PageHead>

  <div class="stepper" {@attach showChosen(step)}>
    {#each STEPS as label, i (i)}
      <button class:on={i === step} class:done={i < step} disabled={i > 0 && locked} onclick={() => show(i)}>
        <span class="n">{i < step ? '✓' : i + 1}</span>{label}
      </button>
    {/each}
  </div>

  <div class="min-h-[40vh]">
    {#if step === 0}
      <StepNavidrome {d} />
    {:else if step === 1}
      <StepConvert {d} />
    {:else if step === 2}
      <StepLyrics {d} />
    {:else if step === 3}
      <StepMusic {d} {intel} />
    {:else if step === 4}
      <StepDeezer {d} />
    {:else if step === 5}
      <StepAutomation {d} />
    {:else}
      <StepSummary {d} {intel} goto={(i) => show(i)} bind:start />
    {/if}
  </div>

  <div class="wiz-foot">
    {#if step > 0}
      <button class="btn" onclick={() => show(step - 1)}><Icon name="left" size={16} />{t('Back')}</button>
    {:else}
      <span></span>
    {/if}
    {#if step < LAST}
      <button class="btn primary" disabled={locked} onclick={() => show(step + 1)}>{t('Next')}<Icon name="right" size={16} /></button>
    {:else}
      <button class="btn primary lg" disabled={busy} onclick={finish}>
        <Icon name={start && connected ? 'play' : 'check'} size={18} />{start && connected ? t('Finish and start') : t('Finish')}
      </button>
    {/if}
  </div>
</div>
