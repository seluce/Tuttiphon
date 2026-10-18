<!-- Album as a card: large cover, name, a line below. A click opens the artist. a.fav: by a favorite band. -->
<script>
  import Cover from '../../components/Cover.svelte'
  import Icon from '../../components/Icon.svelte'
  import { openArtist } from '../../lib/artist.js'
  import { t } from '../../lib/i18n.svelte.js'

  let { a, sub, cover = a.cover, size = 190 } = $props()
</script>

<button type="button" class="pcard m-0 text-left" onclick={() => openArtist(a.artist)}>
  <div class="relative">
    <Cover id={cover} {size} class="w-full! h-auto! aspect-square rounded-card" />
    {#if a.fav}<span class="pill acc absolute top-2 left-2 shadow-soft backdrop-blur-sm"><Icon name="heart" size={12} />{t('Favorite band')}</span>{/if}
  </div>
  <div class="min-w-0">
    <div class="t">{a.name}</div>
    <div class="s ell block">{sub}</div>
  </div>
</button>
