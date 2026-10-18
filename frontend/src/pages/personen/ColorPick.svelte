<!-- A person's color (round swatches). onpick(color) -->
<script>
  import { COLORS } from './shared.js'
  import { t } from '../../lib/i18n.svelte.js'

  let { value, size = 34, onpick } = $props()
</script>

<div class="toggles">
  {#each COLORS as c, i (c)}
    <button class="toggle p-0" class:on={value === c} aria-label={t('Color {n}', { n: i + 1 })} title={t('Color {n}', { n: i + 1 })} aria-pressed={value === c}
      style:width="{size}px" style:height="{size}px" style:background={c} style:border-color={value === c ? 'var(--text)' : 'transparent'}
      onclick={() => onpick(c)}></button>
  {/each}
</div>
