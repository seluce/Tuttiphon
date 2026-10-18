<!-- Overlapping artist pictures. artists: [[name, count, ID], …] -->
<script>
  import Avatar from './Avatar.svelte'

  let { artists = [], n = 4, size = 28 } = $props()
</script>

<div class="stack">
  {#each artists.slice(0, n) as [name, , id] (name)}
    <Avatar {name} {id} {size} />
  {/each}
</div>
