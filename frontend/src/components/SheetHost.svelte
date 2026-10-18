<!-- Draws the open sheet (lib/overlay.svelte.js → openSheet). On the right, on the phone from the bottom.
     While it is open: the page behind it does not scroll, Tab stays inside the sheet, the back button closes it. -->
<script>
  import Icon from './Icon.svelte'
  import { O, closeSheet } from '../lib/overlay.svelte.js'
  import { t } from '../lib/i18n.svelte.js'

  // a new sheet gets the focus – not its first field, otherwise the keyboard pops up on the phone
  const focusPanel = (panel) => { requestAnimationFrame(() => panel.focus({ preventScroll: true })) }
  function keydown(e) {
    if (e.key === 'Escape' && O.sheet && !O.modal) closeSheet()
  }

  const FOCUSABLE = 'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), summary, [tabindex]:not([tabindex="-1"])'
  /** Tab at the end of the sheet goes back to its start (and Shift+Tab the other way) */
  function trap(e) {
    if (e.key !== 'Tab') return
    const panel = e.currentTarget
    const items = [...panel.querySelectorAll(FOCUSABLE)].filter((el) => el.getClientRects().length)
    if (!items.length) { e.preventDefault(); return }
    const first = items[0]
    const last = items.at(-1)
    const at = document.activeElement
    if (e.shiftKey && (at === first || at === panel)) { e.preventDefault(); last.focus() }
    else if (!e.shiftKey && at === last) { e.preventDefault(); first.focus() }
  }

  // the page behind the sheet does not scroll along (the width of the vanished scroll bar is kept)
  const open = $derived(!!O.sheet)
  $effect(() => {
    if (!open) return
    const html = document.documentElement
    const bar = innerWidth - html.clientWidth
    html.classList.add('sheet-open')
    if (bar > 0) html.style.paddingRight = `${bar}px`
    return () => {
      html.classList.remove('sheet-open')
      html.style.paddingRight = ''
    }
  })
</script>

<svelte:window onkeydown={keydown} />

<!-- {#each} instead of {#if}: when closing, s stays valid until the sheet is torn down (otherwise {...s.props} reads null) -->
{#each O.sheet ? [O.sheet] : [] as s (s.id)}
  <div class="back" onclick={closeSheet} role="presentation"></div>
  <div class="sheet" class:wide={s.wide} role="dialog" aria-modal="true" aria-label={s.title || undefined} tabindex="-1"
    onkeydown={trap} {@attach focusPanel}>
    <div class="head flex items-center justify-between gap-2.5 px-5 py-4 border-b border-line">
      {#if s.head}{@render s.head()}{:else}<h2 class="ell">{s.title}</h2>{/if}
      <button class="btn icon ghost shrink-0" onclick={closeSheet} aria-label={t('Close')}><Icon name="x" /></button>
    </div>
    <div class="body overflow-auto p-5 grid grid-cols-[minmax(0,1fr)] gap-5 content-start flex-1" class:last={!s.foot}>
      {#if s.component}<s.component {...s.props} />{:else}{@render s.body?.()}{/if}
    </div>
    {#if s.foot}
      <div class="foot flex gap-2.5 px-5 py-3.5 border-t border-line items-center flex-wrap">{@render s.foot()}</div>
    {/if}
  </div>
{/each}

<style>
  :global(html.sheet-open) { overflow: hidden; }
  .back { position: fixed; inset: 0; background: rgba(5, 5, 12, .6); z-index: 60; animation: fade .2s; }
  .sheet { position: fixed; top: 0; right: 0; bottom: 0; width: min(560px, 100vw); z-index: 61; background: var(--bg-2); border-left: 1px solid var(--line); display: flex; flex-direction: column; animation: slide .3s var(--ease); box-shadow: -20px 0 60px rgba(0, 0, 0, .4); }
  .sheet:focus { outline: none; }
  .sheet.wide { width: min(760px, 100vw); }
  .body { overscroll-behavior: contain; }
  /* installed app on the iPhone: keep clear of the status bar, the home indicator and (landscape) the notch */
  .head { padding-top: calc(16px + env(safe-area-inset-top, 0px)); padding-right: calc(20px + env(safe-area-inset-right, 0px)); }
  .body, .foot { padding-right: calc(20px + env(safe-area-inset-right, 0px)); }
  .foot { padding-bottom: calc(14px + env(safe-area-inset-bottom, 0px)); }
  .body.last { padding-bottom: calc(20px + env(safe-area-inset-bottom, 0px)); }
  @keyframes slide { from { transform: translateX(40px); opacity: 0; } }
  @media (max-width: 900px) {
    .sheet, .sheet.wide { width: 100vw; top: max(6vh, calc(env(safe-area-inset-top, 0px) + 12px)); border-radius: 22px 22px 0 0; border-left: 0; animation-name: slide-up; }
    .head { padding-top: 16px; }
    .head, .body, .foot { padding-left: calc(20px + env(safe-area-inset-left, 0px)); }
    @keyframes slide-up { from { transform: translateY(40px); opacity: 0; } }
  }
</style>
