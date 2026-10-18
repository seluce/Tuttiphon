<!-- Setup assistant: options as cards with a radio button, a title and a short explanation (.choice) – one is chosen.
     options: [[value, title, explanation], …] · onchange(value) -->
<script>
  let { name, value, options, onchange } = $props()
</script>

<div class="grid grid-cols-[repeat(auto-fit,minmax(210px,1fr))] gap-2.5" role="radiogroup">
  {#each options as [val, title, desc] (val)}
    <label class="choice">
      <input type="radio" {name} value={val} checked={val === value} onchange={() => onchange(val)} />
      <b>{title}</b>
      <span>{desc}</span>
    </label>
  {/each}
</div>
