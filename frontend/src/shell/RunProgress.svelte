<!--
  "Progress" of a run (administrators, in a sheet): how far it is at a glance – step n of m, a bar over the whole run,
  every step with its state and duration, and for the step at work its part with how many of how many (RunPart).
  Below: stop the run and, folded, the live log. Follows S.task (polled every second while running); after the end it
  shows the results.
-->
<script>
  import Icon from '../components/Icon.svelte'
  import RunPart, { duration } from '../components/RunPart.svelte'
  import LiveLog from '../pages/start/LiveLog.svelte'
  import { S } from '../lib/state.svelte.js'
  import { STEP_INFO } from '../lib/settings-info.js'
  import { api } from '../lib/api.js'
  import { toast } from '../lib/overlay.svelte.js'
  import { t } from '../lib/i18n.svelte.js'

  const task = $derived(S.task || {})
  const steps = $derived(task.steps || [])
  const durations = $derived(task.durations || [])
  const pos = $derived(task.running && task.pos != null ? task.pos : null)

  /** State of a step: by its position (a step can come twice, e.g. "scan") */
  function stepState(i) {
    if (pos === i) return 'running'
    if (durations[i] != null) return task.results?.[steps[i]] || 'ok'
    if (!task.running && task.results?.[steps[i]] === 'abgebrochen') return 'abgebrochen'
    return 'open'
  }
  const SYM = { ok: 'check', warnung: 'alert', fehler: 'x', abgebrochen: 'x' }

  // the whole run: finished steps plus the part of the one at work
  const finished = $derived(durations.filter((x) => x != null).length)
  const share = $derived(task.progress?.total ? Math.min(1, task.progress.done / task.progress.total) : 0)
  const overall = $derived(steps.length ? Math.round(((finished + (pos != null ? share : 0)) / steps.length) * 100) : 0)

  let logOpen = $state(false)
  let stopping = $state(false)
  async function stop() {
    stopping = true
    try {
      await api('/api/task/cancel', { body: {} })
      toast(t('Stopping …'))
    } catch (e) { toast(e.message, { error: true }); stopping = false }
  }
</script>

<div class="grid gap-5">
  <div class="grid gap-2">
    <div class="flex justify-between gap-3 items-baseline">
      <b>{task.running
        ? (pos != null ? t('Step {n} of {total}', { n: pos + 1, total: steps.length }) : t('Getting ready …'))
        : t('Done')}</b>
      <span class="muted small">{task.running && task.elapsed != null ? t('running for {time}', { time: duration(task.elapsed) }) : ''}</span>
    </div>
    <div class="track" role="progressbar" aria-label={t('Progress')} aria-valuemin="0" aria-valuemax="100" aria-valuenow={task.running ? overall : 100}>
      <i style:width="{task.running ? overall : 100}%"></i>
    </div>
  </div>

  {#if task.running && pos == null && task.progress}
    <div class="card"><RunPart p={task.progress} /></div>
  {/if}

  <ol class="grid gap-1.5">
    {#each steps as id, i (i)}
      {@const st = stepState(i)}
      <li class="step" class:now={st === 'running'}>
        <span class="dot {st}">
          {#if st === 'running'}<Icon name="refresh" size={15} class="animate-spin" />
          {:else if SYM[st]}<Icon name={SYM[st]} size={15} />
          {:else}{i + 1}{/if}
        </span>
        <div class="min-w-0 grid gap-2">
          <div class="flex justify-between gap-3">
            <span class="font-[650] ell">{STEP_INFO[id]?.[1] || id}</span>
            {#if durations[i] != null}<span class="muted small shrink-0">{duration(durations[i])}</span>{/if}
          </div>
          {#if st === 'running' && task.progress}<RunPart p={task.progress} />{/if}
        </div>
      </li>
    {/each}
  </ol>

  {#if task.running}
    <div class="btns"><button class="btn" disabled={stopping} onclick={stop}><Icon name="x" size={16} />{t('Stop')}</button></div>
  {/if}

  <details class="fold" bind:open={logOpen}>
    <summary><Icon name="list" size={18} />{t('Live log')}</summary>
    <div class="in">{#if logOpen}<LiveLog />{/if}</div>
  </details>
</div>

<style>
  .track { height: 10px; border-radius: 99px; background: var(--surface-2); overflow: hidden; }
  .track i { display: block; height: 100%; border-radius: 99px; background: var(--grad); transition: width .6s var(--ease); }
  .step { display: grid; grid-template-columns: 28px minmax(0, 1fr); gap: 12px; align-items: start; padding: 10px 12px; border-radius: var(--radius-small); }
  .step.now { background: var(--surface-2); }
  .dot { width: 28px; height: 28px; border-radius: 50%; display: grid; place-items: center; font-size: .8rem; font-weight: 750;
    background: var(--surface-2); color: var(--muted); }
  .dot.running { background: var(--accent); color: #fff; }
  .dot.ok { background: color-mix(in srgb, var(--ok) 22%, transparent); color: var(--ok); }
  .dot.warnung { background: color-mix(in srgb, var(--warn) 22%, transparent); color: var(--warn); }
  .dot.fehler { background: color-mix(in srgb, var(--err) 22%, transparent); color: var(--err); }
  .step.now .dot.open { background: var(--surface); }
</style>
