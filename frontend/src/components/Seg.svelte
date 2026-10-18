<!-- Segmented control (one option active). options: [[value, text], …] – too narrow (phone): scrolls sideways. -->
<script module>
  /** For a row that scrolls sideways (segmented control, step bar): bring the chosen option (.on) into view – only
   *  sideways, the page itself never moves. Attachment: {@attach showChosen(value)} runs again when value changes. */
  export function showChosen(_value) {
    return (node) => {
      const frame = requestAnimationFrame(() => {
        const on = node.querySelector('.on')
        if (!on || node.scrollWidth <= node.clientWidth) return
        const box = node.getBoundingClientRect()
        const r = on.getBoundingClientRect()
        if (r.left < box.left) node.scrollLeft -= box.left - r.left + 8
        else if (r.right > box.right) node.scrollLeft += r.right - box.right + 8
      })
      return () => cancelAnimationFrame(frame)
    }
  }
</script>

<script>
  let { options, value = $bindable(), onchange = undefined, class: cls = '' } = $props()
</script>

<div class="seg {cls}" role="group" {@attach showChosen(value)}>
  {#each options as [val, label] (val)}
    <button type="button" class:on={val === value} aria-pressed={val === value}
      onclick={() => { value = val; onchange?.(val) }}>{label}</button>
  {/each}
</div>
