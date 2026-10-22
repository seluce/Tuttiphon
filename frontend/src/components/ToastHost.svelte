<!-- Short notice at the bottom (lib/overlay.svelte.js → toast). Swiping it sideways dismisses it right away.
     Errors stay until they are closed (×) and are announced right away by screen readers. -->
<script>
  import { fly } from 'svelte/transition'
  import Icon from './Icon.svelte'
  import { O, hideToast } from '../lib/overlay.svelte.js'
  import { t } from '../lib/i18n.svelte.js'

  let dx = $state(0)
  let start = $state(null)
  let out = $state({ y: 16, duration: 250 })

  function down(e) {
    if (e.target.closest('button')) return   // “Undo” stays a button
    start = e.clientX
    out = { y: 16, duration: 250 }
    e.currentTarget.setPointerCapture?.(e.pointerId)
  }
  function move(e) {
    if (start !== null) dx = e.clientX - start
  }
  function up() {
    if (start === null) return
    start = null
    if (Math.abs(dx) > 60) {   // swiped far enough: out in the swipe direction
      out = { x: Math.sign(dx) * 260, duration: 160 }
      hideToast()
    }
    dx = 0
  }
</script>

{#if O.toast}
  {#key O.toast.id}
    <div class="toast" class:err={O.toast.error} class:drag={start !== null} role={O.toast.error ? 'alert' : 'status'}
      style:transform={dx ? `translateX(${dx}px)` : null} style:opacity={dx ? Math.max(0.2, 1 - Math.abs(dx) / 220) : null}
      in:fly={{ y: 16, duration: 250 }} out:fly={out}
      onpointerdown={down} onpointermove={move} onpointerup={up} onpointercancel={up}>
      <span>{O.toast.msg}</span>
      {#each O.toast.buttons as b (b.label)}
        <button class="btn sm" onclick={() => { hideToast(); b.run() }}>{b.label}</button>
      {/each}
      {#if O.toast.error}
        <button class="close" onclick={hideToast} aria-label={t('Close')}><Icon name="x" size={16} /></button>
      {/if}
    </div>
  {/key}
{/if}

<style>
  .toast { position: fixed; left: 0; right: 0; margin: 0 auto; width: max-content; bottom: calc(92px + var(--player) + env(safe-area-inset-bottom, 0px)); z-index: 80; display: flex; align-items: center; gap: 14px; padding: 12px 14px 12px 18px; border-radius: 14px; background: var(--text); color: var(--bg); font-weight: 650; max-width: calc(100vw - 28px); box-shadow: var(--shadow); touch-action: pan-y; user-select: none; cursor: grab; transition: transform .18s, opacity .18s; }
  .toast.drag { transition: none; cursor: grabbing; }
  .toast.err { background: #c81e1e; color: #fff; padding-right: 8px; }   /* the same red in both themes: white text stays readable */
  .close { display: grid; place-items: center; width: 32px; height: 32px; flex-shrink: 0; border: 0; border-radius: 50%; background: none; color: inherit; cursor: pointer; }
  .close:hover { background: rgba(255, 255, 255, .15); }
  .toast :global(.btn) { background: transparent; color: inherit; border-color: currentColor; }
  @media (max-width: 900px) { .toast { bottom: calc(var(--nav-h) + 82px + var(--player)); } }
</style>
