<!-- Artist search with pictures (from the library). onpick(name); exclude(): names that are not offered. -->
<script>
  import Icon from './Icon.svelte'
  import Avatar from './Avatar.svelte'
  import { S } from '../lib/state.svelte.js'
  import { plural } from '../lib/format.js'
  import { t } from '../lib/i18n.svelte.js'

  let { placeholder, onpick, exclude = () => [] } = $props()
  let q = $state('')
  let sel = $state(0)
  let open = $state(false)

  const items = $derived.by(() => {
    const s = q.trim().toLowerCase()
    if (!s) return []
    const ex = new Set(exclude())
    return (S.library?.artists || []).filter(([a]) => a.toLowerCase().includes(s) && !ex.has(a))
      .sort((x, y) => (y[0].toLowerCase().startsWith(s) - x[0].toLowerCase().startsWith(s)) || y[1] - x[1]).slice(0, 8)
  })

  function pick(a) {
    q = ''
    open = false
    onpick(a)
  }
  function keydown(e) {
    if (e.key === 'ArrowDown') { sel = Math.min(sel + 1, items.length - 1); e.preventDefault() }
    else if (e.key === 'ArrowUp') { sel = Math.max(sel - 1, 0); e.preventDefault() }
    else if (e.key === 'Enter' && items[sel]) { e.preventDefault(); pick(items[sel][0]) }
    else if (e.key === 'Escape') open = false
  }
</script>

<div class="search max-w-none">
  <Icon name="search" size={18} />
  <input placeholder={placeholder ?? t('Search bands …')} autocomplete="off" bind:value={q}
    oninput={() => { sel = 0; open = true }} onkeydown={keydown} onblur={() => setTimeout(() => (open = false), 150)} />
  {#if open && items.length}
    <div class="search-results">
      {#each items as [a, n, id], i (a)}
        <div class="sr-item" class:sel={i === Math.min(sel, items.length - 1)} role="option" aria-selected={i === sel} tabindex="-1"
          onmousedown={(e) => { e.preventDefault(); pick(a) }}>
          <Avatar name={a} {id} size={34} />
          <div class="ell"><div class="ell">{a}</div><div class="tiny muted">{plural(n, 'song', 'songs')}</div></div>
        </div>
      {/each}
    </div>
  {/if}
</div>
