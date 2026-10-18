<!-- Three (or more) small explanation cards side by side: [[icon, title, text], …] – “For you” and Welcome. -->
<script>
  import Icon from '../../components/Icon.svelte'

  let { items } = $props()
</script>

<div class="grid grid-cols-[repeat(auto-fit,minmax(210px,1fr))] gap-3 w-full text-left">
  {#each items as [ic, title, text] (title)}
    <div class="card grid gap-1.5 content-start">
      <div class="hi"><Icon name={ic} size={18} /></div>
      <b>{title}</b>
      <p class="muted small">{text}</p>
    </div>
  {/each}
</div>
