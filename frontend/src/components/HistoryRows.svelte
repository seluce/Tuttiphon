<!-- List of runs (history, start page): when, what, result per step – a click shows the log. -->
<script>
  import { STEP_LABEL, summaryText, openLog } from '../lib/history.js'
  import { t, locale } from '../lib/i18n.svelte.js'

  let { list = [] } = $props()
  const BADGE = { ok: 'ok', warnung: 'warn', fehler: 'err' }
  /** Tooltip of a step: its name and how it ended (the results are stored values: ok, warnung, fehler, abgebrochen). */
  const resultText = (s, r) => {
    const step = STEP_LABEL[s] || s
    return r === 'ok' ? t('{step}: ok', { step }) : r === 'warnung' ? t('{step}: warning', { step })
      : r === 'fehler' ? t('{step}: error', { step }) : r === 'abgebrochen' ? t('{step}: canceled', { step }) : `${step}: ${r}`
  }
  const when = (iso) => {
    const d = new Date(iso)
    return d.toLocaleDateString(locale(), { day: '2-digit', month: '2-digit' }) + ' · ' + d.toLocaleTimeString(locale(), { hour: '2-digit', minute: '2-digit' })
  }
</script>

<div class="hist">
  {#each list || [] as e}
    <button type="button" class="hist-row text-[.88rem]" onclick={() => openLog(e)}>
      <span class="when">{when(e.start)}</span>
      <span class="min-w-0">
        <b class="ell block">{e.name}</b>
        <span class="muted small">{summaryText(e)}</span>
      </span>
      <span class="res">
        {#each Object.entries(e.results || {}) as [s, r] (s)}
          <span class="pill {BADGE[r] || ''}" title={resultText(s, r)}>{r === 'ok' ? '✓' : r === 'fehler' ? '✕' : '!'} {STEP_LABEL[s] || s}</span>
        {/each}
      </span>
    </button>
  {:else}
    <div class="muted small">{t('No runs yet.')}</div>
  {/each}
</div>
