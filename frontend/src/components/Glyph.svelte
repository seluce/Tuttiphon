<!-- Icon of a music world, vibe or person: "i:teddy" or an icon name (anything else is shown as text). -->
<script>
  import Icon from './Icon.svelte'
  import { glyphName } from '../lib/icons.js'

  let { value, size = 20, class: cls = '' } = $props()
  const name = $derived(glyphName(value))
</script>

{#if name}
  <Icon {name} {size} class={cls} />
{:else if value}
  <span class={cls} style:font-size="{Math.round(size * 0.9)}px" style:line-height="1">{value}</span>
{/if}
