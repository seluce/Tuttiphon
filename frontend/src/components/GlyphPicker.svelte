<!-- Icon picker (for music worlds, vibes, people). onpick receives "i:name". -->
<script>
  import Icon from './Icon.svelte'
  import { MOTIFS, hasIcon, glyphName } from '../lib/icons.js'

  let { value = '', onpick } = $props()
  let picked = $state(null)
  const current = $derived(picked ?? glyphName(value))
</script>

<div class="grid gap-1.5 grid-cols-[repeat(auto-fill,minmax(40px,1fr))]">
  {#each MOTIFS.filter(hasIcon) as m (m)}
    <button type="button" title={m} aria-label={m} aria-pressed={current === m}
      class="grid place-items-center h-10 rounded-[10px] border transition-colors
        {current === m ? 'bg-accent border-accent text-white' : 'bg-surface border-line text-text-2 hover:border-line-2 hover:text-text'}"
      onclick={() => { picked = m; onpick?.(`i:${m}`) }}>
      <Icon name={m} size={20} />
    </button>
  {/each}
</div>
