<!--
  Several values as chips (genres, keywords …). items is changed directly (push/splice) –
  it must be a reactive array, e.g. from S.config:  obj.genres ??= []  and then  items={obj.genres}.
  suggestions: [[value, label], …] for the suggestion list.
-->
<script>
  import { changed } from '../lib/state.svelte.js'
  import { t } from '../lib/i18n.svelte.js'

  let { items, onchange = changed, placeholder, suggestions = null } = $props()
  const listId = 'dl-' + Math.random().toString(36).slice(2, 8)
  let text = $state('')
  let input

  function add(v) {
    v = v.trim()
    text = ''
    if (!v || items.includes(v)) return
    items.push(v)
    onchange()
    input?.focus()
  }
  function keydown(e) {
    if (e.key === 'Enter') { e.preventDefault(); add(text) }
    else if (e.key === 'Backspace' && !text && items.length) { items.pop(); onchange() }
  }
  // Take a pick from the suggestion list at once – but not while typing or deleting ("Rocka" ⌫ → "Rock")
  function picked(e) {
    const type = e.inputType || ''
    const v = e.currentTarget.value
    if (suggestions && type !== 'insertText' && !type.startsWith('delete') && suggestions.some(([s]) => s === v)) add(v)
  }
</script>

<div class="chips">
  {#each items as v, i (v)}
    <span class="chip">{v}<button type="button" class="x" title={t('remove')} aria-label={t('Remove “{name}”', { name: v })} onclick={() => { items.splice(i, 1); onchange() }}>×</button></span>
  {/each}
  <input bind:this={input} bind:value={text} placeholder={placeholder ?? t('add … with Enter')} list={suggestions ? listId : undefined}
    onkeydown={keydown} oninput={picked} onblur={() => { if (text.trim()) add(text) }} />
  {#if suggestions}
    <datalist id={listId}>
      {#each suggestions as [v, label] (v)}<option value={v} {label}></option>{/each}
    </datalist>
  {/if}
</div>
