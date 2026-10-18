<!-- State of a playlist as a pill. -->
<script>
  import { STATE } from '../lib/playlist.js'

  let { state } = $props()
  const info = $derived(STATE[state] || ['…', 'off'])
  const cls = $derived({ ok: 'ok', new: 'acc', warn: 'warn', off: '' }[info[1]])
</script>

<span class="pill {cls}">{info[0]}</span>
