<!-- Horizontal row with arrows (they appear on hover). wide: wider cards. -->
<script>
  import Icon from './Icon.svelte'
  import { t } from '../lib/i18n.svelte.js'
  import { smooth } from '../lib/motion.js'

  let { wide = false, children } = $props()
  let track
  const scroll = (dir) => track.scrollBy({ left: dir * track.clientWidth * 0.8, behavior: smooth() })
</script>

<div class="carousel group relative" class:wide>
  <button class="btn icon nav-btn left-[-14px]" onclick={() => scroll(-1)} aria-label={t('Scroll back')}><Icon name="left" /></button>
  <div class="track" bind:this={track}>
    {@render children()}
  </div>
  <button class="btn icon nav-btn right-[-14px]" onclick={() => scroll(1)} aria-label={t('Scroll forward')}><Icon name="right" /></button>
</div>

<style>
  .track { display: grid; grid-auto-flow: column; grid-auto-columns: minmax(170px, 190px); gap: 18px; overflow-x: auto; scroll-snap-type: x mandatory; padding-bottom: 8px; scrollbar-width: none; }
  .track::-webkit-scrollbar { display: none; }
  .track > :global(*) { scroll-snap-align: start; }
  .wide .track { grid-auto-columns: minmax(280px, 320px); }
  .nav-btn { position: absolute; top: 34%; z-index: 2; opacity: 0; transition: opacity .2s; box-shadow: var(--shadow-sm); }
  .carousel:hover .nav-btn { opacity: 1; }
  @media (max-width: 900px) {
    .track { grid-auto-columns: minmax(140px, 150px); }
    .wide .track { grid-auto-columns: minmax(250px, 82vw); }
  }
</style>
