<!-- Numbered steps in the help: <Steps><li>…</li><li>…</li></Steps> – with round numbers in front. -->
<script>
  let { children } = $props()
</script>

<ol class="grid gap-2 p-0 my-[1em] list-none">{@render children()}</ol>

<style>
  ol { counter-reset: st; }
  ol > :global(li) { counter-increment: st; display: grid; grid-template-columns: 28px minmax(0, 1fr); gap: 10px; align-items: baseline; }
  ol > :global(li)::before {
    content: counter(st); display: grid; place-items: center; width: 26px; height: 26px; border-radius: 50%;
    background: var(--accent-soft); color: var(--accent); font-weight: 800; font-size: .85rem;
  }
</style>
