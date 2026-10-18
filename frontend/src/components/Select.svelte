<!--
  Dropdown list. options: [[value, text], …] or groups { group: 'Title', options: [[value, text], …] }.
  The value delivered is always a string (as with any <select>).
-->
<script>
  let { options, value = $bindable(), onchange = undefined, ...rest } = $props()
  const same = (v) => String(v) === String(value ?? '')
</script>

<select {...rest} onchange={(e) => { value = e.currentTarget.value; onchange?.(value) }}>
  {#each options as o, i (i)}
    {#if Array.isArray(o)}
      <option value={o[0]} selected={same(o[0])}>{o[1]}</option>
    {:else}
      <optgroup label={o.group}>
        {#each o.options as [v, l] (v)}
          <option value={v} selected={same(v)}>{l}</option>
        {/each}
      </optgroup>
    {/if}
  {/each}
</select>
