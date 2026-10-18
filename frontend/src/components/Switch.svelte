<!-- On/off switch. <Switch bind:checked={obj.on} onchange={changed} label="…" /> or checked={…} onchange={(v) => …}
     hidelabel: the label only for screen readers (the text stands next to it anyway). -->
<script>
  let { checked = $bindable(false), onchange = undefined, label = '', hidelabel = false, disabled = false, title = undefined } = $props()
</script>

<label class="switch" {title}>
  <input type="checkbox" {checked} {disabled}
    onchange={(e) => { checked = e.currentTarget.checked; onchange?.(checked) }} />
  {#if label}<span class:sr-only={hidelabel}>{label}</span>{/if}
</label>
