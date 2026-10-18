<!--
  Running task and applying to Navidrome.
  chip: small hint in the header while something is running.
  otherwise: floating bar at the bottom ("Changes reach Navidrome in 8 s – Now").
-->
<script>
  import Icon from '../components/Icon.svelte'
  import { S, applyNow, pendingCount, isAdmin, isApplyRun } from '../lib/state.svelte.js'
  import { route, go } from '../lib/router.svelte.js'
  import { t, tn } from '../lib/i18n.svelte.js'
  import { smooth } from '../lib/motion.js'

  let { chip = false } = $props()
  // Users only see applying to Navidrome (their changes) – no analysis or maintenance runs.
  const task = $derived(isAdmin() || isApplyRun(S.task) ? S.task : null)
  const n = $derived(pendingCount())
  const auto = $derived(S.config?.settings.autoApply !== false)

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
  {#if task?.running}
    <button type="button" class="inline-flex items-center gap-2 ml-auto px-3.5 py-[7px] rounded-full text-[.84rem] font-[650] bg-surface border border-accent/50 whitespace-nowrap text-text cursor-pointer"
      onclick={() => (isAdmin() ? showProgress() : go('#/'))}><Icon name="refresh" size={16} class="animate-spin" /><span class="max-mobile:hidden">{task.name || t('running …')}</span></button>
  {/if}
{:else if task?.running}
  <div class="applybar"><Icon name="refresh" size={18} class="animate-spin shrink-0" /><span>{task.name} …</span>{#if isAdmin()}<button class="btn sm" onclick={showProgress}>{t('Progress')}</button>{/if}</div>
{:else if S.auto?.waiting && n}
  <div class="applybar"><Icon name="clock" size={18} class="shrink-0" /><span>{t('Changes follow after the running task')}</span></div>
{:else if S.auto?.due != null}
  <div class="applybar"><Icon name="clock" size={18} class="shrink-0" /><span>{t('Changes reach Navidrome in {n} s', { n: S.auto.due })}</span><button class="btn sm primary" onclick={applyNow}>{t('Now')}</button></div>
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
    .applybar { left: 12px; right: 12px; transform: none; max-width: none; bottom: calc(78px + env(safe-area-inset-bottom, 0px) + var(--player));
      border-radius: 16px; padding: 10px 10px 10px 14px; font-size: .86rem; line-height: 1.3; }
    .applybar > span { flex: 1; min-width: 0; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; }
    @keyframes up { from { transform: translateY(20px); opacity: 0; } }
  }
  /* the assistant has its own button bar at the bottom – the apply bar would cover it (phone) or sit in it (desktop) */
  :global(body:has(.wiz-foot)) .applybar { display: none; }
</style>
