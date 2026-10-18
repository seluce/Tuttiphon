<!-- Ranking of the most played bands with bars. titled: plays and songs as a tooltip. -->
<script>
  import Avatar from '../../components/Avatar.svelte'
  import { openArtist } from '../../lib/artist.js'
  import { fmt } from '../../lib/format.js'
  import { t } from '../../lib/i18n.svelte.js'

  let { list, max = list[0]?.plays || 1, titled = false } = $props()
</script>

<div class="arows">
  {#each list as a, i (i)}
    <button type="button" class="arow w-full text-left grid-cols-[22px_40px_minmax(0,1fr)_110px_46px] max-mobile:grid-cols-[22px_40px_minmax(0,1fr)_44px]"
      title={titled ? t('{name}: {plays} plays from {songs} songs', { name: a.name, plays: fmt(a.plays), songs: fmt(a.songs) }) : undefined}
      onclick={() => openArtist(a.name)}>
      <span class="rank">{i + 1}</span>
      <Avatar name={a.name} id={a.id} size={40} />
      <b class="ell">{a.name}</b>
      <div class="bar"><i style:width="{(a.plays / max) * 100}%"></i></div>
      <span class="n">{fmt(a.plays)}</span>
    </button>
  {/each}
</div>
