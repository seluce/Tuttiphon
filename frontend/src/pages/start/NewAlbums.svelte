<!-- Recently added albums as a carousel (home page and “For you”). -->
<script>
  import Carousel from '../../components/Carousel.svelte'
  import AlbumCard from './AlbumCard.svelte'
  import { relTime } from '../../lib/format.js'

  let { albums } = $props()
</script>

<Carousel>
  {#each albums as a (a.id)}
    <AlbumCard {a} sub="{a.artist} · {relTime(a.created)}" />
  {/each}
</Carousel>
