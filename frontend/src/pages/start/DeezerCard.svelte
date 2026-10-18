<!--
  "Deezer rating" card (start page): state of the stars and the ways to ask Deezer. Whether stars given by hand are
  overwritten is set in Settings → Deezer stars. todo: "To review" is on the page – it offers "Rate now" itself.
-->
<script>
  import Icon from '../../components/Icon.svelte'
  import { S, runTask } from '../../lib/state.svelte.js'
  import { confirmDialog } from '../../lib/overlay.svelte.js'
  import { fmt, serverDate } from '../../lib/format.js'
  import { cache } from './cache.svelte.js'
  import { t } from '../../lib/i18n.svelte.js'

  let { todo = false } = $props()

  const d = $derived(S.library?.deezer || S.status?.deezer || {})
  const full = $derived(d.fullRun)
  // new songs are already offered under "To review" – no second button for the same thing
  const rateInTodo = $derived(todo && (cache.inbox || []).some((x) => x.key.startsWith('deezer-')))

  async function fullCheck() {
    if (!full && !(await confirmDialog(t('Check everything again?'), t('All {n} songs are looked up on Deezer again; this takes about 45–60 minutes. You can stop at any time – next time it continues from there.', { n: fmt(cache.home?.songs || 0) }), t('Start')))) return
    runTask(['deezer'], { deezer_mode: 'full' })
  }
</script>

{#snippet stat(v, l)}
  <div class="py-4 px-[18px] rounded-card bg-surface border border-line">
    <div class="text-[1.7rem] font-extrabold tracking-[-.03em] tabular-nums">{fmt(v)}</div>
    <div class="text-muted text-[.82rem] font-semibold">{l}</div>
  </div>
{/snippet}

<div class="card">
  <div class="card-head">
    <h2><span class="hi"><Icon name="star" size={18} /></span>{t('Deezer rating')}</h2>
    {#if d.new}<span class="pill warn">{t('{n} new', { n: fmt(d.new) })}</span>{:else}<span class="pill ok">{t('up to date')}</span>{/if}
  </div>
  <div class="grid grid-cols-[repeat(auto-fit,minmax(150px,1fr))] gap-3.5">
    {@render stat((d.known || 0) - (d.notFound || 0), t('rated'))}
    {@render stat(d.notFound || 0, t('not found'))}
    {@render stat(d.new || 0, t('waiting'))}
  </div>
  <p class="muted small my-3">
    {d.lastRun ? t('Last run: {when}', { when: serverDate(d.lastRun) }) : ''}{d.lastFull ? t(' · last full check {when}', { when: serverDate(d.lastFull) }) : ''}
  </p>
  <div class="btns">
    {#if !rateInTodo}
      <button class="btn sm primary" disabled={S.running} onclick={() => runTask(['deezer'], { deezer_mode: 'new' })}>{t('Rate new songs')}</button>
    {/if}
    <button class="btn sm" disabled={S.running} onclick={() => runTask(['deezer'], { deezer_mode: 'missing' })}>{t('Retry songs not found')}</button>
    <button class="btn sm" disabled={S.running} onclick={fullCheck}>
      {full ? t('Continue full check · {done}/{total}', { done: fmt(full.done), total: fmt(full.total) }) : t('Check everything again')}
    </button>
  </div>
</div>
