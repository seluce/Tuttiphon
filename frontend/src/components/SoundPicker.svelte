<!--
  Instruments or themes of a sound filter (AI sound analysis): toggles from GET /api/sound/catalog, most frequent
  first, with the number of songs in which the AI hears them – a song fits if at least one of them is in it.
  kind: 'instruments' | 'themes', value: chosen ids, onchange(ids). Hidden while the AI knows none of that kind,
  unless some are already chosen (so they can be removed).
-->
<script>
  import Field from './Field.svelte'
  import { loadCatalog, soundCatalog } from '../lib/sound.svelte.js'
  import { fmt } from '../lib/format.js'
  import { t } from '../lib/i18n.svelte.js'

  let { kind = 'instruments', value = [], onchange } = $props()
  const FIRST = 12   // shown before “Show all”
  let all = $state(false)

  $effect(() => { loadCatalog().catch(() => {}) })   // again after a language switch (labels)

  const cat = soundCatalog()
  const themes = $derived(kind === 'themes')
  const items = $derived((themes ? cat.themes : cat.items) || [])
  const available = $derived(themes ? cat.themesAvailable : cat.available)
  const chosen = $derived(new Set(value))
  // with songs or chosen, most songs first
  const list = $derived(items.filter((x) => x.songs > 0 || chosen.has(x.id))
    .sort((a, b) => b.songs - a.songs || a.label.localeCompare(b.label)))
  const shown = $derived(all ? list : list.filter((x, i) => i < FIRST || chosen.has(x.id)))
  const visible = $derived(list.length > 0 && (available || chosen.size > 0))

  function toggle(id) {
    onchange?.(chosen.has(id) ? value.filter((x) => x !== id) : [...value, id])
  }
</script>

{#if visible}
  <Field label={themes ? t('Themes – one of them is enough') : t('Instruments – one of them is enough')}>
    <div class="toggles">
      {#each shown as x (x.id)}
        <button type="button" class="toggle" class:on={chosen.has(x.id)} aria-pressed={chosen.has(x.id)} onclick={() => toggle(x.id)}>
          {x.label}{#if x.songs}<span class="n">{fmt(x.songs)}</span>{/if}
        </button>
      {/each}
      {#if list.length > FIRST}
        <button type="button" class="link" onclick={() => (all = !all)}>{all ? t('less') : t('Show all {n}', { n: list.length })}</button>
      {/if}
    </div>
    <div class="hint">{themes ? t('Recognized by the AI sound analysis. The number says in how many songs the AI hears the theme.')
      : t('Recognized by the AI sound analysis. The number says in how many songs the instrument can clearly be heard.')}</div>
  </Field>
{/if}
