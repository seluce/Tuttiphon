<!-- "Played this week" / "Your week": key figures and the five most played bands (d from /api/rueckblick). -->
<script>
  import ArtistRows from '../stats/ArtistRows.svelte'
  import { fmt } from '../../lib/format.js'
  import { t } from '../../lib/i18n.svelte.js'

  let { d } = $props()
</script>

<div class="card">
  <div class="kpis mini">
    <div class="kpi"><div class="l">{t('Plays')}</div><div class="v">{fmt(d.totals.plays)}</div></div>
    <div class="kpi"><div class="l">{t('Listening time')}</div><div class="v">{fmt(Math.round(d.totals.hours))} h</div></div>
    <div class="kpi"><div class="l">{t('Bands')}</div><div class="v">{fmt(d.totals.artists)}</div></div>
    {#if d.totals.newSongs}
      <div class="kpi"><div class="l">{t('Newly discovered')}</div><div class="v">{fmt(d.totals.newSongs)}</div></div>
    {/if}
  </div>
  <ArtistRows list={d.topArtists.slice(0, 5)} max={d.topArtists[0]?.plays || 1} />
</div>
