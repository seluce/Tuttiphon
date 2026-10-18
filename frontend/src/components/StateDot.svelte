<!--
  Colored dot for the state of a playlist (new, changed, paused …) – for administrators only, and only when the
  playlist is not simply up to date in Navidrome (users see nothing: a dot with a tooltip means nothing on a phone).
-->
<script>
  import { STATE } from '../lib/playlist.js'
  import { isAdmin } from '../lib/state.svelte.js'

  let { state } = $props()
  const info = $derived(STATE[state])
</script>

{#if info && state !== 'aktuell' && isAdmin()}<span class="dot-state {info[1]}" role="img" title={info[0]} aria-label={info[0]}></span>{/if}
