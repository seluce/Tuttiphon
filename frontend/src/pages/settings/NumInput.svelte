<!-- Number field for obj[key]: empty = default (remove the key), otherwise limited to min…max; saves right away. -->
<script>
  import { changed } from '../../lib/state.svelte.js'

  let { obj, key, min = undefined, max = undefined, step = 1, placeholder = '', width = 110 } = $props()

  function onchange(e) {
    const el = e.currentTarget
    if (el.value === '') { delete obj[key]; changed(); return }
    let v = Number(el.value)
    if (Number.isNaN(v)) return
    v = Math.min(max ?? v, Math.max(min ?? v, v))
    el.value = v
    obj[key] = v
    changed()
  }
</script>

<input class="input" type="number" {min} {max} {step} {placeholder} value={obj[key] ?? ''} style:width="{width}px" {onchange} />
