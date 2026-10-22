<!-- Recap (week, 30 days, year): from the play counters saved every day (d from /api/rueckblick). -->
<script>
  import Empty from '../../components/Empty.svelte'
  import Section from '../../components/Section.svelte'
  import Avatar from '../../components/Avatar.svelte'
  import AlbumCard from '../start/AlbumCard.svelte'
  import ArtistRows from './ArtistRows.svelte'
  import SongRows from './SongRows.svelte'
  import Bars from './Bars.svelte'
  import { openArtist } from '../../lib/artist.js'
  import { go } from '../../lib/router.svelte.js'
  import { fmt, relTime } from '../../lib/format.js'
  import { compact, MONTHS, dayLabel } from './util.js'
  import Icon from '../../components/Icon.svelte'
  import { api } from '../../lib/api.js'
  import { toast } from '../../lib/overlay.svelte.js'
  import { t, tn, tword, locale } from '../../lib/i18n.svelte.js'

  let { d, kind } = $props()
  const tot = $derived(d.totals)
  const since = $derived(d.since ? new Date(d.since) : null)
  const partial = $derived(since && since > new Date(d.from + 'T00:00'))
  const year = $derived(kind === 'jahr')
  const busiest = $derived(d.busiest
    ? dayLabel(d.busiest.day, year ? { day: 'numeric', month: 'long' } : { weekday: 'long', day: 'numeric', month: 'long' }) : null)
  const top = $derived(d.topArtists[0])

  /** Keep the recap as a fixed playlist in Navidrome – the most played songs, never changes again */
  let keeping = $state(false)
  async function keep() {
    keeping = true
    try {
      const r = await api('/api/rueckblick/keep', { body: { person: d.person, kind, year: year ? d.from.slice(0, 4) : undefined } })
      toast(tn(r.count, '“{name}” saved with {n} song – coming to Symfonium shortly', '“{name}” saved with {n} songs – coming to Symfonium shortly', { name: r.name }))
    } catch (e) { toast(e.message, { error: true }) } finally { keeping = false }
  }

  /* Columns day by day (or month by month) */
  const maxN = $derived(Math.max(1, ...d.series.map((x) => x.n)))
  const colLabel = (x, i) => (year ? MONTHS[i]
    : kind === 'woche' ? dayLabel(x.key, { weekday: 'short' })
      : i % 5 === 0 || i === d.series.length - 1 ? dayLabel(x.key, { day: 'numeric', month: 'numeric' }) : '')
  const colTitle = (x, i) => t('{name}: {n} plays', {
    name: year ? `${MONTHS[i]} ${x.key.slice(0, 4)}` : dayLabel(x.key, { weekday: 'long', day: 'numeric', month: 'long' }),
    n: fmt(x.n),
  })
</script>

{#snippet fact(text, value)}
  {@const [before, after = ''] = text.split('{n}')}
  <span>{before}<b>{value}</b>{after}</span>
{/snippet}

{#if !tot.plays}
  <Empty icon="trending" title={t('Nothing counted yet')} text={since
    ? t('Tuttiphon has been keeping track of plays since {date}. As soon as you listen, the most played music shows up here.', { date: since.toLocaleDateString(locale(), { day: 'numeric', month: 'long', year: 'numeric' }) })
    : t('From now on Tuttiphon remembers every day what you listened to – Navidrome itself keeps no history.')} />
{:else}
  <div class="wrap-hero" class:year>
    <div class="eyebrow">{partial ? t('{title} · counted since {date}', { title: d.title, date: since.toLocaleDateString(locale(), { day: 'numeric', month: 'long' }) }) : d.title}</div>
    <div class="wrap-big"><b>{compact(tot.plays)}</b><span>{t('Plays')}</span></div>
    <div class="wrap-facts">
      <!-- {n} marks the bold value inside each translated text -->
      {@render fact(t('{n} of music'), `${fmt(Math.round(tot.hours))} h`)}
      {@render fact(tword(tot.artists, '{n} band', '{n} bands'), fmt(tot.artists))}
      {@render fact(tword(tot.songs, '{n} different song', '{n} different songs'), fmt(tot.songs))}
      {#if tot.newSongs}{@render fact(t('{n} newly discovered'), fmt(tot.newSongs))}{/if}
      {#if busiest}{@render fact(t('most music on {n}'), busiest)}{/if}
    </div>
    <div class="btns">
      <button class="btn sm" disabled={keeping} onclick={keep}><Icon name="pin" size={15} />{t('Keep as playlist')}</button>
    </div>
    {#if top}
      <button type="button" class="wrap-top" onclick={() => openArtist(top.name)}>
        <Avatar name={top.name} id={top.id} size={72} />
        <div>
          <div class="eyebrow">{year ? t('Band of the year') : t('Most played')}</div>
          <b>{top.name}</b>
          <div class="muted small">{t('{plays} plays from {songs} songs', { plays: fmt(top.plays), songs: fmt(top.songs) })}</div>
        </div>
      </button>
    {/if}
  </div>

  <div class="card section">
    <div class="card-head"><h2>{year ? t('Over the year') : t('Day by day')}</h2></div>
    <div class="cols" class:dense={kind === 'monat'}>
      {#each d.series as x, i (x.key)}
        <div class="col" title={colTitle(x, i)}>
          <div class="cbar">
            {#if x.n}<span class="cv">{kind === 'monat' ? '' : fmt(x.n)}</span>{/if}
            <i style:height="{x.n ? Math.max(3, (x.n / maxN) * 100) : 0}%"></i>
          </div>
          <span class="cl">{colLabel(x, i)}</span>
        </div>
      {/each}
    </div>
  </div>

  <div class="g-2 section">
    <div class="card">
      <div class="card-head"><h2>{t('Most played bands')}</h2></div>
      <ArtistRows list={d.topArtists} />
    </div>
    <div class="card">
      <div class="card-head"><h2>{t('Most played songs')}</h2></div>
      <SongRows list={d.topSongs} ranked right={(s) => `${fmt(s.plays)}×`} />
    </div>
  </div>

  {#if d.discoveries.length}
    <Section title={t('Newly discovered')} icon="sparkles">
      <div class="grid grid-cols-[repeat(auto-fill,minmax(120px,1fr))] gap-3.5">
        {#each d.discoveries as a, i (i)}
          <button type="button" class="acard" onclick={() => openArtist(a.name)}>
            <Avatar name={a.name} id={a.id} size={72} />
            <div class="nm">{a.name}</div>
            <div class="tiny muted">{tn(a.songs, '{n} new song', '{n} new songs')}</div>
          </button>
        {/each}
      </div>
    </Section>
  {/if}

  {#if d.topAlbums.length}
    <Section title={t('Favorite albums')}>
      <div class="g-pl">
        {#each d.topAlbums as a, i (i)}
          <AlbumCard {a} cover={a.hasArt ? a.cover : null} size={180} sub="{a.artist} · {fmt(a.plays)}×" />
        {/each}
      </div>
    </Section>
  {/if}

  {#if d.welten.length || d.decades.length}
    <div class="g-2 section items-start">
      {#if d.welten.length}
        <div class="card">
          <div class="card-head"><h2>{t('Music worlds')}</h2></div>
          <Bars rows={d.welten} label={(w) => w.name} value={(w) => w.plays} wide onclick={(w) => go(`#/welt/${w.id}`)} />
        </div>
      {/if}
      {#if d.decades.length}
        <div class="card">
          <div class="card-head"><h2>{t('Decades')}</h2></div>
          <Bars rows={d.decades} title={(r) => t('Music from the {decade}: {n} plays', { decade: r[0], n: fmt(r[1]) })} />
        </div>
      {/if}
    </div>
  {/if}

  <p class="muted small section">{t('For the Navidrome account “{user}”. Tuttiphon records its play counts every day – most recently {when}.', { user: d.user, when: d.lastSnapshot ? relTime(d.lastSnapshot) : '–' })}</p>
{/if}

<style>
  .wrap-hero {
    position: relative; overflow: hidden; display: grid; gap: 14px; padding: 28px; border-radius: var(--radius-big); border: 1px solid var(--line);
    background: radial-gradient(900px 340px at 0% 0%, rgba(139, 92, 246, .42), transparent 60%),
      radial-gradient(700px 300px at 100% 100%, rgba(236, 72, 153, .32), transparent 60%), var(--surface);
  }
  .wrap-hero.year { background: var(--grad); color: #fff; border: 0; }
  .wrap-hero.year .eyebrow, .wrap-hero.year .muted { color: rgba(255, 255, 255, .82); }
  .wrap-big { display: flex; align-items: baseline; gap: 12px; flex-wrap: wrap; }
  .wrap-big b { font-size: clamp(2.6rem, 8vw, 4.4rem); line-height: 1; font-weight: 850; letter-spacing: -.03em; }
  .wrap-big span { font-size: 1.1rem; font-weight: 650; opacity: .85; }
  .wrap-facts { display: flex; flex-wrap: wrap; gap: 8px 20px; font-size: .95rem; }
  .wrap-top { display: flex; gap: 16px; align-items: center; padding: 12px; border-radius: var(--radius-card); background: rgba(255, 255, 255, .08); cursor: pointer; max-width: 520px; text-align: left; }
  .wrap-top b { font-size: 1.2rem; }

  .cols { display: grid; grid-auto-flow: column; grid-auto-columns: minmax(0, 1fr); gap: 6px; align-items: end; height: 180px; }
  .cols.dense { gap: 3px; }
  .col { display: grid; grid-template-rows: 1fr auto; gap: 6px; height: 100%; min-width: 0; }
  .cbar { position: relative; display: flex; flex-direction: column; justify-content: flex-end; align-items: stretch; min-height: 0; }
  .cbar i { display: block; background: var(--accent); border-radius: 4px 4px 0 0; min-height: 0; }
  .cv { font-size: .72rem; color: var(--text-2); text-align: center; margin-bottom: 4px; font-variant-numeric: tabular-nums; }
  .cl { font-size: .72rem; color: var(--muted); text-align: center; white-space: nowrap; overflow: visible; }
  @media (max-width: 900px) {
    .wrap-hero { padding: 20px; }
    .cols { height: 140px; }
    .cv { display: none; }
  }
</style>
