<!-- Round person picture: icon on the person's color. -->
<script>
  import Glyph from './Glyph.svelte'
  import { hash } from '../lib/format.js'

  let { p, size = 44 } = $props()
  const color = $derived(p?.color || `hsl(${hash(p?.id || 'x') % 360} 60% 50%)`)
</script>

<div class="av" title={p?.name} style:width="{size}px" style:height="{size}px" style:background={color}>
  <Glyph value={p?.icon || 'user'} size={Math.round(size * 0.5)} />
</div>
