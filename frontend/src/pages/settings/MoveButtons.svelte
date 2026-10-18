<!-- Buttons ↑ ↓: swap list[i] with its neighbor and save. -->
<script>
  import { changed } from '../../lib/state.svelte.js'
  import { t } from '../../lib/i18n.svelte.js'

  let { list, i } = $props()

  function move(d) {
    const j = i + d
    if (j < 0 || j >= list.length) return
    ;[list[i], list[j]] = [list[j], list[i]]
    changed()
  }
</script>

<button class="btn icon sm ghost" title={t('move up')} aria-label={t('move up')} disabled={i === 0} onclick={() => move(-1)}>↑</button>
<button class="btn icon sm ghost" title={t('move down')} aria-label={t('move down')} disabled={i === list.length - 1} onclick={() => move(1)}>↓</button>
