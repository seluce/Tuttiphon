<!-- Song list of the statistics: (rank,) cover, title & artist, a value on the right (plays, last played …). -->
<script>
  import Cover from '../../components/Cover.svelte'

  let { list, ranked = false, right } = $props()
</script>

<div class="grid gap-0.5">
  {#each list as s, i (i)}
    <div class="grid gap-3 items-center py-1.5 px-2 rounded-xl hover:bg-surface-2
      {ranked ? 'grid-cols-[22px_44px_minmax(0,1fr)_auto]' : 'grid-cols-[44px_minmax(0,1fr)_auto]'}">
      {#if ranked}<span class="rank">{i + 1}</span>{/if}
      <Cover id={s.cover} size={44} />
      <div class="min-w-0">
        <div class="ell font-[650]">{s.title}</div>
        <div class="muted small ell">{s.artist}</div>
      </div>
      <span class="text-muted tabular-nums text-[.86rem]">{right(s)}</span>
    </div>
  {/each}
</div>
