<!--
  Running task and applying to Navidrome.
  chip: small hint in the header while something is running.
  otherwise: floating bar at the bottom. The bar of a running task can be put away (✕ or swiped aside) until that run
  ends – the chip in the header stays (a night analysis runs for hours). Applying to Navidrome by itself (auto-apply,
  a few seconds after a change) needs no bar – the change was confirmed already; without auto-apply the bar offers
  “Apply”.
-->
<script>
  import Icon from '../components/Icon.svelte'
  import { S, applyNow, pendingCount, isAdmin, isApplyRun } from '../lib/state.svelte.js'
  import { route, go } from '../lib/router.svelte.js'
  import { t, tn } from '../lib/i18n.svelte.js'
  import { smooth } from '../lib/motion.js'

  let { chip = false } = $props()
  const auto = $derived(S.config?.settings.autoApply !== false)
  // Users only see applying to Navidrome (their changes) – no analysis or maintenance runs. With auto-apply the short
  // applying run gets no bar, only the chip in the header while it runs.
  const chipTask = $derived(isAdmin() || isApplyRun(S.task) ? S.task : null)
  const task = $derived(isApplyRun(S.task) && auto ? null : chipTask)
  const n = $derived(pendingCount())

  // the bar of a run put away: that run (its start time) – a later run brings it back, even unseen in between
  let awayRun = $state(null)
  const run = $derived(task?.startedAt ?? task?.name)
  const away = $derived(!!task?.running && awayRun != null && awayRun === run)

  // swiping the bar aside: it follows the finger; far enough (or fast to the bottom) and it is gone
  let drag = $state(null)   // { x, y, dx, dy }
  $effect(() => { if (!task?.running) drag = null })   // the run ended mid-swipe: the next bar starts in place
  function down(e) {
    if (!e.isPrimary || e.button > 0 || e.target.closest('button')) return
    drag = { x: e.clientX, y: e.clientY, dx: 0, dy: 0 }
    e.currentTarget.setPointerCapture?.(e.pointerId)
  }
  function move(e) {
    if (drag) drag = { ...drag, dx: e.clientX - drag.x, dy: Math.max(0, e.clientY - drag.y) }
  }
  function up() {
    if (drag && (Math.abs(drag.dx) > 90 || drag.dy > 40)) awayRun = run
    drag = null
  }
  /** ✕: away – the keyboard focus goes to the indicator in the header, which stays */
  function putAway() {
    awayRun = run
    document.querySelector('[data-task-chip]')?.focus()
  }

  /** "Progress": to the live log on the home page (when already there: just scroll to it) */
  function showProgress() {
    const jump = () => {
      const log = document.getElementById('protokoll')
      if (log) log.open = true
      ;(log || document.querySelector('.hero'))?.scrollIntoView({ behavior: smooth(), block: 'start' })
    }
    if (route.path === '/') jump()
    else {
      go('#/')
      setTimeout(jump, 450)   // let the home page build first
    }
  }
</script>

{#if chip}
  {#if chipTask?.running}
    <button type="button" class="inline-flex items-center gap-2 ml-auto px-3.5 py-[7px] rounded-full text-[.84rem] font-[650] bg-surface border border-accent/50 whitespace-nowrap text-text cursor-pointer"
      data-task-chip aria-label={chipTask.name || t('running …')} title={chipTask.name || t('running …')}
      onclick={() => (isAdmin() ? showProgress() : go('#/'))}><Icon name="refresh" size={16} class="animate-spin" /><span class="max-mobile:hidden">{chipTask.name || t('running …')}</span></button>
  {/if}
{:else if task?.running}
  {#if !away}
    <!-- swiping is a shortcut for ✕ (the button keyboards and screen readers use) -->
    <!-- svelte-ignore a11y_no_static_element_interactions -->
    <div class="applybar swipe" class:dragging={drag} style:--dx="{drag?.dx ?? 0}px" style:--dy="{drag?.dy ?? 0}px"
      style:opacity={drag ? Math.max(0.2, 1 - Math.max(Math.abs(drag.dx) / 160, drag.dy / 80)) : null}
      onpointerdown={down} onpointermove={move} onpointerup={up} onpointercancel={() => (drag = null)}>
      <Icon name="refresh" size={18} class="animate-spin shrink-0" /><span>{task.name} …</span>
      {#if isAdmin()}<button class="btn sm" onclick={showProgress}>{t('Progress')}</button>{/if}
      <button type="button" class="btn icon sm ghost shrink-0" aria-label={t('Close')} title={t('Close')} onclick={putAway}><Icon name="x" size={16} /></button>
    </div>
  {/if}
{:else if n && !auto}
  <div class="applybar"><Icon name="alert" size={18} class="shrink-0" /><span>{tn(n, '{n} change not yet in Navidrome', '{n} changes not yet in Navidrome')}</span><button class="btn sm primary" onclick={applyNow}>{t('Apply')}</button></div>
{/if}

<style>
  .applybar {
    position: fixed; left: calc(var(--sidebar) + 50%); transform: translateX(calc(-50% - var(--sidebar) / 2)); bottom: calc(22px + var(--player)); z-index: 40;
    display: flex; align-items: center; gap: 12px; padding: 10px 12px 10px 18px; border-radius: 99px; background: var(--surface-2);
    border: 1px solid var(--line-2); box-shadow: var(--shadow); font-weight: 650; font-size: .9rem; max-width: calc(100vw - var(--sidebar) - 40px);
    animation: up .3s var(--ease);
  }
  @keyframes up { from { transform: translate(calc(-50% - var(--sidebar) / 2), 20px); opacity: 0; } }
  @media (max-width: 900px) {
    /* phone: full width instead of a narrow pill, text at most two lines */
    .applybar { left: 12px; right: 12px; transform: none; max-width: none; bottom: calc(var(--nav-h) + 20px + var(--player));
      border-radius: 16px; padding: 10px 10px 10px 14px; font-size: .86rem; line-height: 1.3; }
    .applybar > span { flex: 1; min-width: 0; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; }
    @keyframes up { from { transform: translateY(20px); opacity: 0; } }
  }
  .swipe { touch-action: none; user-select: none; -webkit-user-select: none; transform: translate(calc(-50% - var(--sidebar) / 2 + var(--dx)), var(--dy)); }
  .swipe.dragging { transition: none; cursor: grabbing; }
  .swipe:not(.dragging) { transition: transform .2s var(--ease), opacity .2s; }
  @media (max-width: 900px) { .swipe { transform: translate(var(--dx), var(--dy)); } }
  /* the assistant has its own button bar at the bottom – the apply bar would cover it (phone) or sit in it (desktop) */
  :global(body:has(.wiz-foot)) .applybar { display: none; }
</style>
