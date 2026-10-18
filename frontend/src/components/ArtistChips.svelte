<!-- Artist list as chips with pictures, below it the artist search. items is changed directly (reactive array). -->
<script>
  import Avatar from './Avatar.svelte'
  import ArtistPicker from './ArtistPicker.svelte'
  import { changed } from '../lib/state.svelte.js'
  import { t } from '../lib/i18n.svelte.js'

  let { items, onchange = changed, placeholder } = $props()
</script>

<div class="field">
  <div class="chips">
    {#each items as a, i (a)}
      <span class="chip has-av"><Avatar name={a} size={24} />{a}<button type="button" class="x" title={t('remove')}
        aria-label={t('Remove “{name}”', { name: a })} onclick={() => { items.splice(i, 1); onchange() }}>×</button></span>
    {:else}
      <span class="muted small px-1.5 py-1">{t('– nobody yet –')}</span>
    {/each}
  </div>
  <ArtistPicker placeholder={placeholder ?? t('Add band …')} exclude={() => items} onpick={(a) => { items.push(a); onchange() }} />
</div>
