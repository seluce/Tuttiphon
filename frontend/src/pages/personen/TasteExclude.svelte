<!-- Music worlds that do not count for a person's taste (p.tasteExclude, changed directly) – e.g. the children's music
     that plays on a parent's account. Toggles for the separate worlds (children, audio plays …) and the ones already
     left out; any other world can be added. -->
<script>
  import Icon from '../../components/Icon.svelte'
  import Glyph from '../../components/Glyph.svelte'
  import Select from '../../components/Select.svelte'
  import { S } from '../../lib/state.svelte.js'
  import { t } from '../../lib/i18n.svelte.js'

  let { p, self = false, onchange = () => {} } = $props()
  const list = $derived(p.tasteExclude || [])
  let added = $state([])   // worlds picked from the list in this visit – they stay visible after being switched off
  const shown = $derived(S.config.welten.filter((w) => w.separate || list.includes(w.id) || added.includes(w.id)))
  const others = $derived(S.config.welten.filter((w) => !shown.includes(w)).map((w) => [w.id, w.name]))

  function toggle(id) {
    p.tasteExclude = list.includes(id) ? list.filter((x) => x !== id) : [...list, id]
    onchange()
  }
  function add(id) {
    if (!id) return
    added = [...added, id]
    if (!list.includes(id)) toggle(id)
  }
</script>

<div class="card grid gap-3" data-guide="geschmack-ohne">
  <h2 class="ih"><span class="hi"><Icon name="sliders" size={18} /></span>{self ? t('Not part of your taste') : t('Not part of {name}’s taste', { name: p.name })}</h2>
  <p class="muted small -mt-1">{self
    ? t('Music that plays on your account for someone else – e.g. children’s music. It stays in the family playlists, but your discoveries, album of the week, own sound and good morning follow your own music.')
    : t('Music that plays on {name}’s account for someone else – e.g. children’s music. It stays in the family playlists, but {name}’s discoveries, album of the week, own sound and good morning follow {name}’s own music.', { name: p.name })}</p>
  <div class="toggles">
    {#each shown as w (w.id)}
      {@const on = list.includes(w.id)}
      <button class="toggle" class:on aria-pressed={on} onclick={() => toggle(w.id)}>
        <Glyph value={w.icon} size={15} class="mr-1.5" />{w.name}{#if on}<Icon name="check" size={15} />{/if}
      </button>
    {/each}
  </div>
  {#if others.length}
    <label class="f max-w-[340px]">{t('Leave out another music world')}
      <Select options={[['', t('Choose …')], ...others]} value="" onchange={add} />
    </label>
  {/if}
</div>
