<!--
  Start page (administrator): greeting with "Update everything", today's mixes, to-dos, listening week,
  new albums, playlists, Deezer & library, history and the live log.
  Which sections appear in which order is set in settings.start.sections (Settings → Start page).
-->
<script>
  import { untrack } from 'svelte'
  import Icon from '../components/Icon.svelte'
  import Section from '../components/Section.svelte'
  import Empty from '../components/Empty.svelte'
  import Carousel from '../components/Carousel.svelte'
  import PlaylistCard from '../components/PlaylistCard.svelte'
  import HistoryRows from '../components/HistoryRows.svelte'
  import StartHero from './start/StartHero.svelte'
  import InstallHint from '../components/InstallHint.svelte'
  import TodoList from './start/TodoList.svelte'
  import TodayRow from './start/TodayRow.svelte'
  import WeekCard from './start/WeekCard.svelte'
  import YearCard from './start/YearCard.svelte'
  import NewAlbums from './start/NewAlbums.svelte'
  import DeezerCard from './start/DeezerCard.svelte'
  import LibraryCard from './start/LibraryCard.svelte'
  import LiveLog from './start/LiveLog.svelte'
  import { S, defaultOwner, loadHistory } from '../lib/state.svelte.js'
  import { api } from '../lib/api.js'
  import { accept } from '../lib/discover.js'
  import { START_SECTIONS } from '../lib/settings-info.js'
  import { cache, loadHome, loadInbox } from './start/cache.svelte.js'
  import { t, locale } from '../lib/i18n.svelte.js'

  const BLOCKS = ['heute', 'todo', 'woche', 'neu', 'playlists', 'karten', 'verlauf']   // i18n-ignore: section ids
  const isActive = (p) => (p.status || 'aktiv') === 'aktiv'

  const conf = $derived(S.config.settings.start || {})
  const order = $derived((conf.sections || Object.keys(START_SECTIONS).map((id) => ({ id, on: true })))
    .filter((x) => x.on && BLOCKS.includes(x.id)).map((x) => x.id))
  const active = $derived(S.config.playlists.filter(isActive))
  const mixes = $derived(active.filter((p) => p.type === 'mix'))
  const ideas = $derived((cache.sg || []).filter((x) => x.playlist?.type === 'mix' && !S.config.dismissed.includes(x.key)).slice(0, 3))

  /* --- Loading: when opened and after every run */
  let woche = $state(null)   // { d } or { error } – your own person's week (without one: the family's)
  function loadWoche() {
    const owner = defaultOwner()?.id
    api(`/api/rueckblick?kind=woche${owner ? `&person=${encodeURIComponent(owner)}` : ''}`)
      .then((d) => (woche = { d })).catch((e) => (woche = { error: e.message }))
  }
  $effect(() => {
    S.done
    untrack(() => {
      loadHome()
      loadInbox()
      if (order.includes('woche')) loadWoche()
    })
  })
  loadHistory()

  // No mix yet: ideas from the suggestions – fetched again on every visit (the cached ones show meanwhile; they may
  // be outdated or in the language before a switch)
  let sgLoading = false
  let sgFresh = false
  $effect(() => {
    if (order.includes('heute') && !mixes.length && !sgFresh && !sgLoading) {   // i18n-ignore: section id
      sgLoading = true
      api('/api/suggestions').then((d) => { cache.sg = d; sgFresh = true }).catch(() => {}).finally(() => (sgLoading = false))
    }
  })
  function acceptIdea(x) {
    accept(x)
    cache.sg = cache.sg.filter((y) => y !== x)
  }

  let logOpen = $state(false)
  $effect(() => {
    if (S.running) logOpen = true
  })

  const since = (d) => d.since && new Date(d.since) > new Date(Date.now() - 7 * 864e5)
</script>

{#snippet link(href, text)}<a {href}>{text}</a>{/snippet}
<!-- loading failed (and nothing from before): the error and "Try again" instead of a placeholder forever -->
{#snippet failed(error, retry)}
  <div class="card flex items-center gap-3 flex-wrap">
    <span class="muted small flex-1 min-w-[12rem]">{error}</span>
    <button class="btn sm" onclick={retry}><Icon name="refresh" size={15} />{t('Try again')}</button>
  </div>
{/snippet}
{#snippet weekLink()}{@render link('#/statistik/woche', t('Full recap →'))}{/snippet}
{#snippet allSee()}{@render link('#/playlists', t('See all →'))}{/snippet}
{#snippet historyLink()}{@render link('#/verlauf', t('See all →'))}{/snippet}

<div class="page">
  <StartHero showSteps={conf.showSteps !== false} />
  <InstallHint />
  <YearCard person={defaultOwner()} />

  {#each order as id (id)}
    {#if id === 'heute'}<!-- i18n-ignore: section id -->
      <Section title={t('Today for you')} icon="sunrise" action={allSee}>
        {#if mixes.length}
          <TodayRow {mixes} />
        {:else}
          <div class="card grid gap-3.5">
            <div>
              <b>{t('No mix yet')}</b>
              <p class="muted small">{t('A mix puts itself together anew regularly – daily, weekly or monthly, with at most a few songs per band and never the same band twice in a row.')}</p>
            </div>
            <!-- one row: the ideas with one tap, or your own mix – more suggestions are under "Discover" -->
            <div class="btns">
              {#each ideas as x (x)}
                <button class="btn sm" onclick={() => acceptIdea(x)}><Icon name="plus" size={14} />{x.title}</button>
              {/each}
              <a class="btn primary sm" href="#/neu?type=mix"><Icon name="dice" size={15} />{t('Create a mix')}</a><!-- i18n-ignore: route -->
            </div>
          </div>
        {/if}
      </Section>
    {:else if id === 'todo'}
      <Section title={t('To review')} icon="check-circle">
        {#if !cache.inbox && cache.failed.inbox}{@render failed(cache.failed.inbox, loadInbox)}{:else}<TodoList />{/if}
      </Section>
    {:else if id === 'woche'}
      <Section title={t('Played this week')} icon="trending" action={weekLink}>
        {#if !woche}
          <div class="skel h-[120px]"></div>
        {:else if woche.error}
          <div class="card muted small">{woche.error}</div>
        {:else if !woche.d.totals.plays}
          <div class="card">
            <p class="muted">
              {since(woche.d)
                ? t('Tuttiphon has been counting since {date} – once the family listens, this shows what played most.', { date: new Date(woche.d.since).toLocaleDateString(locale(), { day: 'numeric', month: 'long' }) })
                : t('Nothing has been played this week yet – or Symfonium is not reporting any plays.')}
            </p>
          </div>
        {:else}
          <WeekCard d={woche.d} />
        {/if}
      </Section>
    {:else if id === 'neu'}<!-- i18n-ignore: section id -->
      <Section title={t('New in your library')} icon="disc">
        {#if cache.home}<NewAlbums albums={cache.home.newAlbums} />
        {:else if cache.failed.home}{@render failed(cache.failed.home, loadHome)}
        {:else}<div class="skel h-[230px]"></div>{/if}
      </Section>
    {:else if id === 'playlists'}
      <Section title={t('All playlists')} icon="playlists" action={allSee}>
        {#if active.length}
          <Carousel>{#each active as p (p.id)}<PlaylistCard {p} />{/each}</Carousel>
        {:else}
          <Empty icon="playlists" title={t('No playlists yet')} text={t('Create the first one with the assistant or have a look at the suggestions.')}>
            <div class="btns">
              <a class="btn primary" href="#/neu"><Icon name="plus" size={16} />{t('New playlist')}</a><!-- i18n-ignore: route -->
              <a class="btn" href="#/entdecken">{t('Suggestions')}</a>
            </div>
          </Empty>
        {/if}
      </Section>
    {:else if id === 'karten'}
      <div class="g-2 section"><DeezerCard todo={order.includes('todo')} /><LibraryCard /></div>
    {:else if id === 'verlauf'}
      <Section title={t('History')} icon="clock" action={historyLink}><HistoryRows list={S.history.slice(0, 5)} /></Section>
    {/if}
  {/each}

  <div class="section">
    <details class="fold scroll-mt-24" id="protokoll" bind:open={logOpen}>
      <summary><Icon name="list" size={18} />{t('Live log')}</summary>
      <div class="in"><LiveLog /></div>
    </details>
  </div>
  <div class="section text-center">
    <a class="link small muted inline-flex items-center gap-1" href="#/einstellungen/start"><Icon name="sliders" size={14} />{t('Customize start page')}</a>
  </div>
</div>
