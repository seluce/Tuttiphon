<!-- Round artist picture; without a picture, initials on a color gradient. id: Navidrome artist ID (otherwise from the library). -->
<script>
  import { artistId } from '../lib/state.svelte.js'
  import { gradFor, initials } from '../lib/format.js'

  let { name, id = undefined, size = 48, class: cls = '' } = $props()
  const aid = $derived(id === undefined ? artistId(name) : id)
  let failedId = $state(null)   // picture missing → the initials stay visible
</script>

<div class="av {cls}" title={name}
  style:width="{size}px" style:height="{size}px" style:font-size="{Math.max(11, Math.round(size * 0.36))}px" style:background={gradFor(name)}>
  {initials(name)}
  {#if aid && failedId !== aid}
    <img src="/img/ar-{aid}?s={size > 90 ? 300 : 150}" loading="lazy" alt="" onerror={() => (failedId = aid)} />
  {/if}
</div>
