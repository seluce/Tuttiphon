<!-- Album cover (square) with a record as placeholder. id: coverArt ID from Navidrome. -->
<script>
  import Icon from './Icon.svelte'

  let { id = null, size = 44, class: cls = '' } = $props()
  let failedId = $state(null)
</script>

<div class="cover {cls}" style:width="{size}px" style:height="{size}px">
  <Icon name="disc" size={Math.round(size * 0.45)} />
  {#if id && failedId !== id}
    <img src="/img/{id}?s={size > 140 ? 300 : 150}" loading="lazy" alt="" onerror={() => (failedId = id)} />
  {/if}
</div>
