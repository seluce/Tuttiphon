<!-- Interface icon by name (see lib/icons.js). <Icon name="plus" size={18} class="animate-spin" /> -->
<script>
  import { ICONS, CUSTOM } from '../lib/icons.js'

  let { name, size = 20, class: cls = '', ...rest } = $props()
  const Lucide = $derived(ICONS[name])
</script>

{#if Lucide}
  <Lucide {size} class={cls} aria-hidden="true" {...rest} />
{:else if CUSTOM[name]}
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"
    stroke-linecap="round" stroke-linejoin="round" class={cls} aria-hidden="true" {...rest}>{@html CUSTOM[name]}</svg>
{/if}
