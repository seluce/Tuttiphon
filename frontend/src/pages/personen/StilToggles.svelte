<!-- Favorite vibes (groups Genre, Thema = topic, Zeitreise = time travel) as toggles – p.likes.stile is changed directly. -->
<script>
  import Icon from '../../components/Icon.svelte'
  import Glyph from '../../components/Glyph.svelte'
  import { S } from '../../lib/state.svelte.js'
  import { toggleIn } from './shared.js'

  let { p, onchange = () => {} } = $props()
  const stile = $derived(S.config.stile.filter((s) => ['Genre', 'Thema', 'Zeitreise'].includes(s.group)))
</script>

<div class="toggles">
  {#each stile as s (s.id)}
    {@const on = p.likes.stile.includes(s.id)}
    <button class="toggle" class:on aria-pressed={on}
      onclick={() => { toggleIn(p.likes.stile, s.id); onchange() }}><Glyph value={s.icon} size={15} class="mr-1.5" />{s.name}{#if on}<Icon name="check" size={15} />{/if}</button>
  {/each}
</div>
