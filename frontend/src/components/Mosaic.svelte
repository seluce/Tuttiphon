<!--
  Playlist picture from album covers: 4 covers as a grid, 1 cover large, otherwise a color gradient with icons.
  marks: icons (list or single, e.g. plEmoji(p)) – the first one sits small in the corner.
-->
<script>
  import Glyph from './Glyph.svelte'

  let { covers = [], marks = [], size = 300, class: cls = '' } = $props()
  const list = $derived((covers || []).filter(Boolean))
  const res = $derived(size > 200 ? 300 : 150)
  const m = $derived((Array.isArray(marks) ? marks : marks ? [marks] : []).filter(Boolean))
  const hide = (e) => (e.currentTarget.style.visibility = 'hidden')
</script>

<div class="mosaic {cls}" class:m4={list.length >= 4}>
  {#if list.length >= 4}
    {#each list.slice(0, 4) as id, i (i)}
      <img src="/img/{id}?s={res === 300 ? 150 : 64}" loading="lazy" alt="" onerror={hide} />
    {/each}
  {:else if list.length}
    <img src="/img/{list[0]}?s={res}" loading="lazy" alt="" onerror={hide} />
  {:else}
    <div class="ph">
      {#each (m.length ? m : ['music']).slice(0, 2) as g, i (i)}
        <Glyph value={g} size={size > 200 ? 46 : 28} />
      {/each}
    </div>
  {/if}
  {#if m.length && list.length}
    <span class="badge-ico"><Glyph value={m[0]} size={15} /></span>
  {/if}
</div>
