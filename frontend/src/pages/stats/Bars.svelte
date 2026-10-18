<!--
  A bar per row (music worlds, decades, genres). rows: any entries; label/value read from them,
  title: tooltip, onclick: row clickable, wide: more room for long names (music worlds).
-->
<script>
  import { fmt } from '../../lib/format.js'

  let { rows, label = (r) => r[0], value = (r) => r[1], title = null, onclick = null, wide = false } = $props()
  const cols = $derived(wide ? 'grid-cols-[minmax(120px,46%)_minmax(40px,1fr)_58px]' : '')
  const wrap = $derived(wide ? 'whitespace-normal leading-snug line-clamp-2' : '')   // long names: two lines instead of cutting them off
  const max = $derived(Math.max(1, ...rows.map(value)))
  const tip = (r) => (title ? title(r) : `${label(r)}: ${fmt(value(r))}`)
</script>

{#snippet inner(r)}
  <span class="k {wrap}">{label(r)}</span>
  <div class="tr"><i style:width="{Math.max(1.5, (value(r) / max) * 100)}%"></i></div>
  <span class="n">{fmt(value(r))}</span>
{/snippet}

<div class="sbars">
  {#each rows as r, i (i)}
    {#if onclick}
      <button type="button" class="sbar w-full text-left cursor-pointer {cols}" title={tip(r)} onclick={() => onclick(r)}>{@render inner(r)}</button>
    {:else}
      <div class="sbar {cols}" title={tip(r)}>{@render inner(r)}</div>
    {/if}
  {/each}
</div>
