<!-- Switch for obj[key] (if the value is missing, def applies) – saves right away. -->
<script>
  import Switch from '../../components/Switch.svelte'
  import { changed } from '../../lib/state.svelte.js'

  let { obj, key, def = true } = $props()
</script>

<Switch checked={obj[key] ?? def} onchange={(v) => { obj[key] = v; changed() }} />
