<!-- Bulleted list in the help: <Bullets><li>…</li></Bullets> -->
<script>
  let { children } = $props()
</script>

<ul class="grid gap-2 pl-5 my-[1em] list-disc">{@render children()}</ul>
