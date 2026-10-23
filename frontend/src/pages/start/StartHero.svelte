<!-- Head of the start page: greeting, numbers, "Update everything" with its steps (and "only this"). -->
<script>
  import HelpLink from '../../components/HelpLink.svelte'
  import Icon from '../../components/Icon.svelte'
  import Switch from '../../components/Switch.svelte'
  import RunPart from '../../components/RunPart.svelte'
  import { S, runTask, applyNow } from '../../lib/state.svelte.js'
  import { toast } from '../../lib/overlay.svelte.js'
  import { api } from '../../lib/api.js'
  import { STEP_INFO } from '../../lib/settings-info.js'
  import { plural, relTime, greeting } from '../../lib/format.js'
  import { t, locale } from '../../lib/i18n.svelte.js'
  import { cache } from './cache.svelte.js'

  let { showSteps = true } = $props()

  const task = $derived(S.task || {})
  const steps = $derived(S.status?.steps || [])
  const home = $derived(cache.home)
  const active = $derived(S.config.playlists.filter((p) => (p.status || 'aktiv') === 'aktiv').length)
  const lastScan = $derived(S.status?.navidrome?.scan?.lastScan)
  const date = $derived(new Date().toLocaleDateString(locale(), { weekday: 'long', day: 'numeric', month: 'long' }))
  const opts = () => ({ dry_run: !!cache.dryRun, full_scan: !!cache.fullScan })

  // During a run "What happens?" is open (with progress), closed again afterwards
  let open = $state(false)
  const running = $derived(!!S.task?.running)
  $effect(() => {
    open = running
  })

  function stepState(s) {
    if (task.running && task.step === s.id) return 'running'
    if (task.results?.[s.id] && task.steps?.includes(s.id)) return task.results[s.id]
    return ''
  }
  const SYM = { running: '…', ok: '✓', warnung: '!', fehler: '✕', abgebrochen: '–' }

  function stop() {
    api('/api/task/cancel', { body: {} }).then(() => toast(t('Stopping …'))).catch((e) => toast(e.message, { error: true }))
  }
  // a double tap must not start two runs: the buttons wait until the start is through
  let starting = $state(false)
  async function start(fn) {
    if (starting) return
    starting = true
    try { await fn() } finally { starting = false }
  }
</script>

<div class="hero grad compact">
  <div class="eyebrow">{date}</div>
  <h1>{greeting()}<HelpLink /></h1>
  <div class="hero-meta">
    {#if home}
      <span>{plural(home.songs, 'song', 'songs')}</span>
      <span>{plural(home.albums, 'album', 'albums')}</span>
      <span>{plural(home.artists, 'band', 'bands')}</span>
    {/if}
    <span>{plural(active, 'playlist', 'playlists')}</span>
    {#if lastScan}<span class="muted">{t('last scanned {when}', { when: relTime(lastScan) })}</span>{/if}
  </div>
  <div class="btns mt-4" data-guide="update">
    {#if task.running}
      <button class="btn white lg min-w-0" disabled><Icon name="refresh" size={18} class="animate-spin shrink-0" /><span class="ell">{task.name || t('running …')}</span></button>
      <button class="btn lg" onclick={stop}>{t('Stop')}</button>
    {:else}
      <button class="btn white lg" disabled={starting} onclick={() => start(() => runTask(steps.map((s) => s.id), opts()))}><Icon name="refresh" size={18} />{t('Update everything')}</button>
      <button class="btn lg" disabled={starting} onclick={() => start(applyNow)}>{t('Apply playlists only')}</button>
    {/if}
  </div>
  {#if showSteps}
    <details class="fold mt-5 bg-transparent border-line-2" bind:open>
      <summary>{t('What happens?')}</summary>
      <div class="in">
        <div class="steps">
          {#each steps as s, i (s.id)}
            {@const st = stepState(s)}
            <div class="step {st}">
              <span class="st">{SYM[st] || i + 1}</span>
              <div class="min-w-0"><b>{s.title}</b><div class="d">{STEP_INFO[s.id]?.[2]}</div>
                {#if st === 'running' && task.progress}<div class="mt-2.5 max-w-[520px]"><RunPart p={task.progress} /></div>{/if}</div>
              {#if !task.running}
                <button class="btn sm ghost" disabled={starting} onclick={() => start(() => runTask([s.id], opts()))}>{t('Run separately')}</button>
              {/if}
            </div>
          {/each}
        </div>
        <div class="btns">
          <Switch bind:checked={cache.dryRun} label={t('Dry run without changing anything')} />
          <Switch bind:checked={cache.fullScan} label={t('full Navidrome scan')} />
        </div>
      </div>
    </details>
  {/if}
</div>
