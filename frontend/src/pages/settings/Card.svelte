<!--
  Card of a settings section: heading (optionally with icon), below it rows (Row) and further content.
  The first row directly below the heading has no divider.
-->
<script>
  import Glyph from '../../components/Glyph.svelte'

  let { title = '', icon = '', guide = undefined, children } = $props()
</script>

<div class="card grid grid-cols-[minmax(0,1fr)] gap-3.5" data-guide={guide}>
  {#if title}
    <div class="card-head">
      <h2>{#if icon}<span class="hi"><Glyph value={icon} size={18} /></span>{/if}{title}</h2>
    </div>
  {/if}
  <div class="body contents">{@render children?.()}</div>
</div>

<style>
  .body > :global(.set-row:first-child) { border-top: 0; padding-top: 0; }
</style>
