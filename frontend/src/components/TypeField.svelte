<!--
  Kind of playlist: smart playlist (Navidrome shuffles on every load) or mix (Tuttiphon picks the songs and renews
  the list daily/weekly/monthly – in between it stays the same, ideal for offline).
  p is changed directly (p.type), then onchange(). Sound vibes are only available as a mix.
-->
<script>
  import Field from './Field.svelte'
  import Seg from './Seg.svelte'
  import { soundOf } from '../lib/state.svelte.js'
  import { t } from '../lib/i18n.svelte.js'

  let { p, onchange } = $props()
  const sound = $derived(!!soundOf(p))
  const ownSound = $derived(!!p.sound)   // the playlist's own sound filter, e.g. a mood from the search – not the vibe's

  // sound vibe: Navidrome cannot filter by sound -> always a mix
  $effect.pre(() => {
    if (sound && p.type !== 'mix') {
      p.type = 'mix'
      p.mix ??= { size: 40, perArtist: 3, every: 'week' }
    }
  })

  function pick(v) {
    if (v === 'mix') p.type = 'mix'
    else delete p.type
    onchange?.()
  }
</script>

<Field label={t('Type')}>
  {#if sound}
    <div class="note">{ownSound
      ? t('Mix – renews itself. The songs are picked by their sound; only Tuttiphon can do that, so it is only available as a mix.')
      : t('Mix – renews itself. This vibe picks by sound; only Tuttiphon can do that, so it is only available as a mix.')}</div>
  {:else}
    <Seg options={[['smart', t('Smart playlist')], ['mix', t('Mix – renews itself')]]} value={p.type === 'mix' ? 'mix' : 'smart'} onchange={pick} />
    <div class="hint">
      {p.type === 'mix'
        ? t('Tuttiphon rebuilds the list regularly: a few songs per band, never the same band twice in a row. In between it stays the same – ideal if Symfonium should save it offline and update it automatically.')
        : t('Navidrome reshuffles from all matching songs every time the playlist is loaded – always fresh, but unsuitable for offline downloads in Symfonium because the list keeps changing.')}
    </div>
  {/if}
</Field>
