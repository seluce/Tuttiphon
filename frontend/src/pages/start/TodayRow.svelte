<!-- "Today" row: the mixes, large with cover (start page and "For you"). -->
<script>
  import PlaylistArt from '../../components/PlaylistArt.svelte'
  import { plStatus } from '../../lib/state.svelte.js'
  import { plName } from '../../lib/playlist.js'
  import { plural } from '../../lib/format.js'
  import { t } from '../../lib/i18n.svelte.js'

  let { mixes } = $props()
  /** Badge by how often the mix renews (p.mix.every) */
  const NEW = $derived({ day: t('New today'), week: t('New this week'), month: t('New this month') })
</script>

<div class="today">
  {#each mixes as p (p.id)}
    {@const st = plStatus(p.id) || {}}
    <a class="today-card" href="#/playlist/{encodeURIComponent(p.id)}">
      <div class="art">
        <PlaylistArt {p} {st} size={600} />
        <span class="badge-mix">{NEW[p.mix?.every || 'day']}</span>
      </div>
      <div class="min-w-0">
        <b class="ell block">{plName(p)}</b>
        <div class="muted small ell">
          {st.count != null ? `${plural(st.count, 'song', 'songs')} · ${(st.topArtists || []).slice(0, 3).map((a) => a[0]).join(', ')}` : '…'}
        </div>
      </div>
    </a>
  {/each}
</div>
