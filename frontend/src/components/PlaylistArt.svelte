<!-- Picture of a playlist: own/designed cover from Navidrome, otherwise a mosaic of album covers. st: entry from /api/playlists -->
<script>
  import Mosaic from './Mosaic.svelte'
  import { plStatus } from '../lib/state.svelte.js'
  import { plEmoji } from '../lib/playlist.js'

  let { p, st = undefined, size = 300, class: cls = '' } = $props()
  const s = $derived(st ?? plStatus(p.id) ?? {})
  const src = $derived(s.cover && s.navidrome ? `/live/pl-${s.navidrome.id}?s=${size > 300 ? 600 : 300}&v=${encodeURIComponent(s.cover.v)}` : null)
  let failedSrc = $state(null)
</script>

{#if src && failedSrc !== src}
  <img class="plcover {cls}" alt="" loading="lazy" {src} onerror={() => (failedSrc = src)} />
{:else}
  <Mosaic covers={s.covers} marks={plEmoji(p)} {size} class={cls} />
{/if}
