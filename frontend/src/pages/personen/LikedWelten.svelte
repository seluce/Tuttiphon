<!-- A person's favorite music worlds (p.likes.welten is changed directly): selection cards with band photos, or
     compact: toggles like the vibes (profile page). -->
<script>
  import Icon from '../../components/Icon.svelte'
  import Glyph from '../../components/Glyph.svelte'
  import Collage from '../../components/Collage.svelte'
  import { S } from '../../lib/state.svelte.js'
  import { toggleIn } from './shared.js'

  let { p, compact = false, onchange = () => {} } = $props()
  const info = $derived(S.library?.weltInfo || {})
</script>

{#if compact}
  <div class="toggles">
    {#each S.config.welten as w (w.id)}
      {@const on = p.likes.welten.includes(w.id)}
      <button class="toggle" class:on aria-pressed={on} onclick={() => { toggleIn(p.likes.welten, w.id); onchange() }}>
        <Glyph value={w.icon} size={15} class="mr-1.5" />{w.name}{#if on}<Icon name="check" size={15} />{/if}
      </button>
    {/each}
  </div>
{:else}
  <div class="pick grid-cols-[repeat(auto-fill,minmax(150px,1fr))]">
    {#each S.config.welten as w (w.id)}
      <button class="pickcard" class:on={p.likes.welten.includes(w.id)} aria-pressed={p.likes.welten.includes(w.id)}
        onclick={() => { toggleIn(p.likes.welten, w.id); onchange() }}>
        <span class="ck"><Icon name="check" size={14} /></span>
        <Collage artists={info[w.id]?.artists || []} icon={w.icon} title={w.name} />
      </button>
    {/each}
  </div>
{/if}
