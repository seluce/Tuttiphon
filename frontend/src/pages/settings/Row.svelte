<!--
  One setting: label + explanation on the left, input on the right (below it on the phone).
  full: content below the label across the full width (lists, tiles).
-->
<script>
  let { label, hint = '', full = false, children } = $props()
</script>

<div class={['set-row grid gap-4 items-center py-3 border-t border-line max-mobile:gap-2',
  full ? 'grid-cols-[minmax(0,1fr)]' : 'grid-cols-[minmax(0,1fr)_auto] max-mobile:grid-cols-[minmax(0,1fr)]']}>
  <div class="grid gap-[3px] min-w-0">
    <b>{label}</b>
    {#if hint}<div class="hint">{hint}</div>{/if}
  </div>
  {#if full}
    {@render children?.()}
  {:else}
    <div class="flex justify-end min-w-0 max-mobile:justify-start">{@render children?.()}</div>
  {/if}
</div>
