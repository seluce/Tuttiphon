<!-- Statistics "Overall": from Navidrome's play counters (d from /api/stats). -->
<script>
  import Icon from '../../components/Icon.svelte'
  import Empty from '../../components/Empty.svelte'
  import Section from '../../components/Section.svelte'
  import AlbumCard from '../start/AlbumCard.svelte'
  import ArtistRows from './ArtistRows.svelte'
  import SongRows from './SongRows.svelte'
  import Bars from './Bars.svelte'
  import { S, creatablePersons, snapshot, changed } from '../../lib/state.svelte.js'
  import { toast } from '../../lib/overlay.svelte.js'
  import { go } from '../../lib/router.svelte.js'
  import { fmt, plural, relTime, uid, today } from '../../lib/format.js'
  import { t, tn } from '../../lib/i18n.svelte.js'
  import { compact } from './util.js'

  let { d, person } = $props()
  const tot = $derived(d.totals)
  // users see the family's numbers too – a playlist from them only if they may create the family's playlists
  const canCreate = $derived(creatablePersons().some((x) => x.id === person.id))
  let created = $state(false)   // against double clicks

  function createForgotten() {
    if (created) return
    if (!S.config.stile.some((s) => s.id === 'lieblinge')) { toast(t('The vibe “Favorite songs” is missing'), { error: true }); return }
    created = true
    snapshot()
    const p = { id: uid('vergessene-lieblinge'), name: `${person.prefix || ''}${t('Forgotten favorites')}`, person: person.id, welt: '*', stil: 'lieblinge',
      notPlayedDays: 90, minRating: 0, status: 'aktiv', created: today(), source: 'statistik' }
    S.config.playlists.push(p)
    changed()
    toast(t('“Forgotten favorites” created'), { undo: true, action: { label: t('View'), run: () => go(`#/playlist/${encodeURIComponent(p.id)}`) } })
  }
</script>

{#if !tot.plays}
  <Empty icon="headphones" title={t('No plays counted yet')}
    text={t('Navidrome has not saved any plays for “{user}” yet. In Symfonium, “Scrobbling” or “Report plays to the server” must be turned on.', { user: d.user })} />
{:else}
  <div class="kpis">
    <div class="kpi">
      <div class="l">{t('Plays')}</div>
      <div class="v text-[3rem] leading-[1.05]">{compact(tot.plays)}</div>
      <div class="s">{tn(tot.songsPlayed, 'from {n} different song', 'from {n} different songs')}</div>
    </div>
    <div class="kpi"><div class="l">{t('Listening time')}</div><div class="v">{fmt(Math.round(tot.hours))} h</div><div class="s">{tn(Math.round(tot.hours / 24), '≈ {n} day non-stop', '≈ {n} days non-stop')}</div></div>
    <div class="kpi"><div class="l">{t('Bands played')}</div><div class="v">{fmt(tot.artists)}</div></div>
    <div class="kpi"><div class="l">{t('Favorites')}</div><div class="v">{fmt(tot.loved)}</div><div class="s">{t('marked with ♥')}</div></div>
    <div class="kpi">
      <div class="l">{t('Never played')}</div>
      <div class="v">{compact(d.neverPlayed)}</div>
      <div class="s">{t('{n} % of the library', { n: Math.round((d.neverPlayed / tot.songs) * 100) })}</div>
    </div>
  </div>

  <div class="g-2 section">
    <div class="card">
      <div class="card-head"><h2>{t('Most played bands')}</h2></div>
      <ArtistRows list={d.topArtists} titled />
    </div>
    <div class="card">
      <div class="card-head"><h2>{t('Most played songs')}</h2></div>
      <SongRows list={d.topSongs} ranked right={(s) => `${fmt(s.plays)}×`} />
    </div>
  </div>

  {#if d.topAlbums.length}
    <Section title={t('Favorite albums')}>
      <div class="g-pl">
        {#each d.topAlbums.slice(0, 12) as a, i (i)}
          <AlbumCard {a} cover={a.hasArt ? a.cover : null} size={180} sub="{a.artist} · {plural(a.plays, 'play', 'plays')}" />
        {/each}
      </div>
    </Section>
  {/if}

  <!-- music worlds get the wide column: their names are long -->
  <div class="g-2 section items-start">
    <div class="card">
      <div class="card-head"><h2>{t('Music worlds')}</h2></div>
      <Bars rows={d.welten.filter((w) => w.songs)} label={(w) => w.name} value={(w) => w.plays} wide
        title={(w) => t('{name}: {plays} plays · {never} of {songs} songs never played', { name: w.name, plays: fmt(w.plays), never: fmt(w.neverPlayed), songs: fmt(w.songs) })}
        onclick={(w) => go(`#/welt/${w.id}`)} />
    </div>
    <div class="grid gap-[18px]">
      <div class="card">
        <div class="card-head"><h2>{t('Decades')}</h2></div>
        <Bars rows={d.decades} title={(r) => t('Music from the {decade}: {n} plays', { decade: r[0], n: fmt(r[1]) })} />
      </div>
      <div class="card">
        <div class="card-head"><h2>{t('Genres')}</h2></div>
        <Bars rows={d.genres} title={(r) => t('{name}: {n} plays', { name: r[0], n: fmt(r[1]) })} />
      </div>
    </div>
  </div>

  <div class="g-2 section">
    <div class="card">
      <div class="card-head"><h2>{t('Recently played')}</h2></div>
      <SongRows list={d.recent.slice(0, 12)} right={(s) => relTime(s.played)} />
    </div>
    <div class="card">
      <div class="card-head">
        <h2><span class="hi"><Icon name="heart" size={18} /></span>{t('Forgotten favorites')}</h2>
        <span class="pill">{fmt(d.forgotten.count)}</span>
      </div>
      <p class="muted small mb-3">{t('Favorites and well-liked hits that have not played in over 90 days.')}</p>
      <SongRows list={d.forgotten.sample.slice(0, 8)} right={(s) => (s.played ? relTime(s.played) : t('never'))} />
      {#if d.forgotten.count && canCreate}
        <div class="btns mt-3.5">
          <button class="btn primary sm" disabled={created} onclick={createForgotten}><Icon name="plus" size={16} />{t('Create as playlist')}</button>
        </div>
      {/if}
    </div>
  </div>

  <p class="muted small section">{t('Note: Navidrome only stores how often and when each song last played – it keeps no history over time.')}</p>
{/if}
