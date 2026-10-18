<!--
  Tour and "Show me" guides (lib/tour.svelte.js, lib/guides.js): switches to the step's page if needed (reset: rebuilds
  it even when it is open), waits for the target, scrolls it into view, dims the rest and shows the hint next to it – to
  the right, below, above or, on the phone, at the bottom edge, wherever there is room. Without a target the hint is
  centered.
  A tap on the highlighted target ends the guide and triggers it – so it can be tried right away.
  A tap elsewhere ends it as well. Keys: Esc ends, → next, ← back.
-->
<script>
  import { untrack, tick } from 'svelte'
  import { tour, endTour, nextStep, prevStep, skipStep } from '../lib/tour.svelte.js'
  import { go, route } from '../lib/router.svelte.js'
  import { t } from '../lib/i18n.svelte.js'

  let vw = $state(innerWidth)
  let vh = $state(innerHeight)
  /** Position of the highlighted target in the window (null = no target) */
  let rect = $state(null)
  /** Target found and in view – only then does the hint appear */
  let ready = $state(false)
  let box = $state()
  let bh = $state(180)
  let layer = $state()
  let target = null
  let run = 0
  /** Page the step is on – if it changes from outside (back button), the tour ends */
  let expect = null

  const step = $derived(tour.active ? tour.steps[tour.i] : null)
  const last = $derived(!!step && (step.last || tour.i === tour.steps.length - 1))
  const fromHelp = $derived(tour.guide && tour.back.startsWith('#/hilfe'))

  const sleep = (ms) => new Promise((r) => setTimeout(r, ms))
  const visible = (el) => {
    if (!el) return false
    const r = el.getBoundingClientRect()
    return r.width > 0 && r.height > 0 && getComputedStyle(el).visibility !== 'hidden'
  }
  const find = (s) => (s.sel || []).map((q) => document.querySelector(q)).find(visible) || null
  const pathOf = (hash) => hash.replace(/^#/, '').split('?')[0] || '/'
  const here = (hash) => (location.hash || '#/') === hash

  // On every step: switch page, find the target, bring it into view, measure it
  $effect(() => {
    const s = step
    if (!s) { run++; target = null; rect = null; ready = false; expect = null; return }   // ended: drop the running search
    const my = ++run
    untrack(() => locate(s, my))
  })

  async function locate(s, my) {
    ready = false
    target = null
    rect = null
    expect = null
    if (s.go && (!here(s.go) || s.reset)) {
      const before = route.key
      go(s.go)   // already there: go() rebuilds the page (route.key) – reset: e.g. the assistant starts from scratch
      for (let k = 0; k < 40 && route.path !== pathOf(s.go); k++) await sleep(25)
      if (route.key !== before) await tick()   // the old page is gone before looking for the target
      await sleep(40)
    }
    // Find the target: up to 8 s while the page is still loading, otherwise 1.5 s. If a required target does not show
    // up right away, the hint appears centered and moves to the target as soon as it is there.
    let el = null
    for (const start = Date.now(); my === run && s.sel;) {
      el = find(s)
      const waited = Date.now() - start
      if (el || waited > 8000 || (waited > 1500 && !document.querySelector('main [data-loading]'))) break
      if (!s.optional && waited > 600) ready = true
      await sleep(100)
    }
    if (my !== run) return
    if (!el && s.optional) { skipStep(); return }
    target = el
    if (el) {
      // only once the page has finished fading in (.page slides a few pixels when opening)
      await Promise.all((el.closest('.page')?.getAnimations() ?? []).map((a) => a.finished.catch(() => {})))
      if (my !== run) return
      bringIntoView(el)
      await sleep(350)
      if (my !== run) return
    }
    expect = route.path
    measure()
    ready = true
  }
  $effect(() => {
    const path = route.path
    untrack(() => { if (tour.active && ready && expect && path !== expect) endTour() })
  })

  /** Is the target fixed in the window, e.g. in the sidebar or the bottom bar? Then scrolling does not help. */
  const pinned = (el) => {
    for (let e = el; e && e !== document.body; e = e.parentElement) {
      if (/fixed|sticky/.test(getComputedStyle(e).position)) return true
    }
    return false
  }

  /** Scroll the target into view between header and bottom bar – large targets start at the top */
  function bringIntoView(el) {
    if (pinned(el)) return
    const r = el.getBoundingClientRect()
    const head = (document.querySelector('.topbar')?.offsetHeight || 60) + 12
    const foot = innerHeight - (document.querySelector('.bottomnav')?.offsetHeight || 0) - 12
    if (r.top >= head && r.bottom <= foot) return
    const room = foot - head
    const y = r.height > room * 0.7 ? r.top - head : r.top - head - (room - r.height) / 2
    window.scrollTo({ top: Math.max(0, scrollY + y), behavior: 'smooth' })
  }

  let frame = 0
  function measure() {
    cancelAnimationFrame(frame)
    frame = requestAnimationFrame(() => {
      if (!target?.isConnected || !visible(target)) {   // e.g. after rotating: sidebar gone, bottom bar there
        target = step ? find(step) : null
        if (!target) { rect = null; return }
      }
      const r = target.getBoundingClientRect()
      rect = { left: r.left, top: r.top, right: r.right, bottom: r.bottom, width: r.width, height: r.height }
    })
  }
  $effect(() => {
    void vw, vh
    if (untrack(() => ready)) measure()
  })
  $effect(() => {
    if (ready) box?.querySelector('.btn.primary')?.focus({ preventScroll: true })
  })

  const pad = 6
  const spotStyle = $derived.by(() => {
    if (!rect) return 'opacity:0'
    const top = Math.max(rect.top - pad, 4)
    const bottom = Math.min(rect.bottom + pad, vh - 4)
    return `left:${rect.left - pad}px;top:${top}px;width:${rect.width + pad * 2}px;height:${Math.max(0, bottom - top)}px;opacity:1`
  })
  const boxStyle = $derived.by(() => {
    const bw = Math.min(360, vw - 24)
    if (!rect) return `left:50%;top:50%;transform:translate(-50%,-50%);width:${bw}px`   // without a target: centered
    const r = rect
    const gap = 16
    const m = 12
    const x = Math.max(m, Math.min(r.left + r.width / 2 - bw / 2, vw - bw - m))
    if (r.left < vw / 3 && r.right + gap + bw + m <= vw)   // to the right, e.g. next to the sidebar
      return `left:${r.right + gap}px;top:${Math.max(m, Math.min(r.top, vh - bh - m))}px;width:${bw}px`
    const clamp = (top) => Math.max(m, Math.min(top, vh - bh - m))
    if (vh - r.bottom - gap - m >= bh) return `left:${x}px;top:${clamp(r.bottom + gap)}px;width:${bw}px`   // below
    if (r.top - gap - m >= bh) return `left:${x}px;top:${clamp(r.top - gap - bh)}px;width:${bw}px`   // above
    return `left:${x}px;bottom:${m}px;width:${bw}px`   // no room next to it: at the bottom edge
  })

  /** Tap on the dimmed area: end – if it was inside the target, trigger the target underneath */
  function backdrop(e) {
    const r = rect
    const inside = r && e.clientX >= r.left && e.clientX <= r.right && e.clientY >= r.top && e.clientY <= r.bottom
    let hit = null
    if (inside && layer) {
      layer.style.pointerEvents = 'none'
      hit = document.elementFromPoint(e.clientX, e.clientY)
      layer.style.pointerEvents = ''
    }
    const el = hit && target?.contains(hit) ? hit.closest('a, button, label, summary, [role=button], input, select, textarea') : null
    endTour()
    if (!el) return
    if (el.matches('input:not([type=checkbox]):not([type=radio]), textarea, select')) el.focus()
    else el.click()
  }

  function back() {
    const to = tour.back
    endTour()
    go(to)
  }

  function key(e) {
    if (!tour.active) return
    if (e.key === 'Tab' && box) {   // focus stays inside the hint
      const items = [...box.querySelectorAll('button')]
      const i = items.indexOf(document.activeElement)
      e.preventDefault()
      items[(i + (e.shiftKey ? -1 : 1) + items.length) % items.length]?.focus()
      return
    }
    if (e.key === 'Escape') endTour()
    else if (e.key === 'ArrowRight') nextStep()
    else if (e.key === 'ArrowLeft') prevStep()
  }
</script>

<svelte:window bind:innerWidth={vw} bind:innerHeight={vh} onkeydown={key} onscroll={() => ready && measure()} />

{#if step}
  <div bind:this={layer} class="fixed inset-0 z-[200]">
    <div class="absolute inset-0 {rect ? '' : 'bg-[rgba(5,5,12,.62)]'}" role="presentation" onclick={backdrop}></div>
    <div class="fixed rounded-[14px] pointer-events-none transition-all duration-300 ease-soft shadow-[0_0_0_9999px_rgba(5,5,12,.62),0_0_0_3px_var(--accent)]"
      style={spotStyle}></div>
    <div bind:this={box} bind:offsetHeight={bh} class="fixed grid gap-2 bg-bg-2 text-text border border-line-2 rounded-big pt-4 px-[18px] pb-3.5
      shadow-[0_24px_60px_rgba(0,0,0,.45)] transition-opacity duration-200 {ready ? 'opacity-100 animate-[fade_.25s]' : 'opacity-0 pointer-events-none'}"
      role="dialog" aria-modal="true" aria-live="polite" aria-label={tour.title || t('Tour')} style={boxStyle}>
      <div class="flex justify-between gap-3 text-[.72rem] font-extrabold tracking-[.08em] text-muted">
        <span class="ell uppercase">{tour.title}</span>
        <span class="shrink-0">{tour.i + 1} / {tour.steps.length}</span>
      </div>
      <h3 class="text-[1.1rem]">{step.title}</h3>
      <p class="text-text-2 leading-[1.55] text-[.92rem]">{step.text}</p>
      <div class="btns justify-end mt-1">
        {#if tour.i && Array.from({ length: tour.i }, (_, k) => k).some((k) => !tour.skipped.includes(k))}
          <button class="btn sm ghost" onclick={prevStep}>{t('Back')}</button>
        {:else if !last}
          <button class="btn sm ghost" onclick={endTour}>{tour.guide ? t('End') : t('Skip')}</button>
        {/if}
        {#if last && tour.guide}
          {#if fromHelp}<button class="btn sm" onclick={back}>{t('Back to help')}</button>{/if}
          <button class="btn sm primary" onclick={endTour}>{t('Done')}</button>
        {:else if last}
          <button class="btn sm" onclick={() => { endTour(); go('#/hilfe') }}>{t('Go to help')}</button>
          <button class="btn sm primary" onclick={endTour}>{t('Let’s go')}</button>
        {:else}
          <button class="btn sm primary" onclick={nextStep}>{tour.i || tour.guide ? t('Next') : t('Show me')}</button>
        {/if}
      </div>
    </div>
  </div>
{/if}
