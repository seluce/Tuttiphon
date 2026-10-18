<!-- One side of the comparison “Smart playlist or mix?”: heading with icon, the points (<li>) below. -->
<script>
  import Icon from '../../components/Icon.svelte'

  let { icon, title, children } = $props()
</script>

<div class="card bg-surface-2">
  <h3 class="ih"><span class="hi"><Icon name={icon} size={18} /></span>{title}</h3>
  <ul class="grid gap-1.5 pl-[18px] mt-2.5 mb-[1em] text-[.92rem] list-disc">{@render children()}</ul>
</div>
