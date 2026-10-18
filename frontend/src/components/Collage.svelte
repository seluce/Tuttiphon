<!-- Header image of a music world: six band photos with icon, title and subtitle on top. artists: [[name, count, ID], …] -->
<script>
  import Glyph from './Glyph.svelte'
  import { gradFor } from '../lib/format.js'

  let { artists = [], icon = '', title = '', sub = '', class: cls = '' } = $props()
  const cells = $derived.by(() => {
    const list = (artists || []).filter((a) => a[2]).slice(0, 6).map(([n, , id]) => ({ n, id }))
    while (list.length < 6) list.push({ n: title + list.length, id: null })
    return list
  })
  let broken = $state({})
</script>

<div class="collage {cls}">
  {#each cells as c, i (i)}
    {#if c.id && !broken[c.id]}
      <img src="/img/ar-{c.id}?s=150" loading="lazy" alt={c.n} onerror={() => (broken[c.id] = true)} />
    {:else}
      <div class="ph" style:background={gradFor(c.n)}></div>
    {/if}
  {/each}
  <div class="on-top">
    {#if icon}<span class="ico"><Glyph value={icon} size={28} /></span>{/if}
    <div>
      <h3>{title}</h3>
      {#if sub}<div class="tiny opacity-85">{sub}</div>{/if}
    </div>
  </div>
</div>
