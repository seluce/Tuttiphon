<!--
  "For you" – the start page for users: own mixes, recommendations, own and shared playlists,
  listening week, new music and a short explanation.
-->
<script>
  import HelpLink from '../components/HelpLink.svelte'
  import InstallHint from '../components/InstallHint.svelte'
  import { untrack } from 'svelte'
  import Icon from '../components/Icon.svelte'
  import Section from '../components/Section.svelte'
  import Empty from '../components/Empty.svelte'
  import Carousel from '../components/Carousel.svelte'
  import PlaylistCard from '../components/PlaylistCard.svelte'
  import TodayRow from './start/TodayRow.svelte'
  import WeekCard from './start/WeekCard.svelte'
  import NewAlbums from './start/NewAlbums.svelte'
  import IdeaCard from './home/IdeaCard.svelte'
  import TipCards from './welcome/TipCards.svelte'
  import { S, defaultPerson, changed, snapshot } from '../lib/state.svelte.js'
  import { toast } from '../lib/overlay.svelte.js'
  import { api } from '../lib/api.js'
  import { accept } from '../lib/discover.js'
  import { plural, greeting } from '../lib/format.js'
  import { t, tn, locale } from '../lib/i18n.svelte.js'
  import { cache, loadHome, loadInbox } from './start/cache.svelte.js'

  const isActive = (p) => (p.status || 'aktiv') === 'aktiv'
  const me = $derived(S.me || {})
  const own = $derived(new Set(me.own || []))
  const mine = $derived(S.config.playlists.filter((p) => own.has(p.person) && isActive(p)))
  const shared = $derived(S.config.playlists.filter((p) => !own.has(p.person) && isActive(p)))
  const mixes = $derived(mine.filter((p) => p.type === 'mix'))
  const date = $derived(new Date().toLocaleDateString(locale(), { weekday: 'long', day: 'numeric', month: 'long' }))

  /* --- Next steps (only if there are any). Without an own playlist, "Let's go" takes over the first one. */
  const STEP_ICONS = { profil: 'user', likes: 'heart', 'erste-playlist': 'playlists', passwort: 'key', unused: 'pause', dup: 'copy' }
  const newcomer = $derived(!mine.length)
  const steps = $derived((cache.inbox || []).filter((x) => !S.config.ignored.includes(x.key) && !(newcomer && x.key === 'erste-playlist')))
  const pwStep = $derived(steps.some((x) => x.key === 'passwort'))
  function later(it) {
    S.config.ignored.push(it.key)
    changed()
  }

  /* --- Suggestions */
  let sgError = $state(null)
  const ideas = $derived((cache.sg || []).filter((x) => x.playlist && own.has(x.person) && !S.config.dismissed.includes(x.key) && !x.shared).slice(0, 6))
  // one-tap mixes – only those "Discovered for you" doesn't already show as a card
  const mixIdeas = $derived((cache.sg || []).filter((x) => x.playlist?.type === 'mix' && !S.config.dismissed.includes(x.key) && !ideas.includes(x)).slice(0, 3))
  function take(s) {
    accept(s)
    cache.sg = cache.sg.filter((x) => x !== s)
  }
  function dismiss(s) {
    snapshot()
    S.config.dismissed.push(s.key)
    changed()
    toast(t('Hidden'), { undo: true })
  }

  /* --- Loading: when opened and after every run */
  let woche = $state(null)   // { d } | { error, noPw } | { none: true }
  const loadSuggestions = () => api('/api/suggestions').then((d) => { cache.sg = d; sgError = null }).catch((e) => (sgError = e.message))
  function loadWoche() {
    const pid = defaultPerson()
    if (!pid) { woche = { none: true }; return }
    api(`/api/rueckblick?kind=woche&person=${encodeURIComponent(pid)}`).then((d) => (woche = { d }))
      .catch((e) => (woche = { error: e.message, noPw: /passwor[dt]/i.test(e.message) }))   // the server's error text, German or English
  }
  $effect(() => {
    S.done
    untrack(() => {
      loadSuggestions()
      loadWoche()
    })
  })
  loadInbox()
  loadHome()

  const recent = (d) => d.since && new Date(d.since) > new Date(Date.now() - 7 * 864e5)
</script>

{#snippet link(href, text)}<a {href}>{text}</a>{/snippet}
{#snippet allIdeas()}{@render link('#/entdecken', t('See all →'))}{/snippet}
{#snippet allSee()}{@render link('#/playlists', t('See all →'))}{/snippet}
{#snippet review()}{@render link('#/statistik/woche', t('Your recap →'))}{/snippet}
{#snippet helpLink()}{@render link('#/hilfe', t('Help & guide →'))}{/snippet}

<div class="page">
  <!-- Greeting: short – the space belongs to the mixes and suggestions -->
  <div class="hero grad compact">
    <div class="eyebrow">{date}</div>
    <h1>{me.name ? t('{greeting}, {name}!', { greeting: greeting(), name: me.name }) : t('{greeting}!', { greeting: greeting() })}<HelpLink /></h1>
    {#if !mine.length}
      <p class="lead max-w-[620px] opacity-92">{t('This is where your own playlists are made. Pick a suggestion below – one tap creates it and it shows up in Symfonium.')}</p>
    {/if}
    <div class="hero-meta">
      <span>{tn(mine.length, '{n} playlist of your own', '{n} playlists of your own')}</span>
      {#if mixes.length}<span>{plural(mixes.length, 'mix', 'mixes')}</span>{/if}
      {#if cache.home}<span>{plural(cache.home.songs, 'song', 'songs')}</span>{/if}
    </div>
    <div class="btns mt-4">
      <a class="btn white" href="#/neu"><Icon name="plus" size={17} />{t('New playlist')}</a><!-- i18n-ignore: route -->
      <a class="btn" href="#/entdecken"><Icon name="compass" size={17} />{t('Discover')}</a>
    </div>
  </div>

  <InstallHint />

  {#if steps.length}
    <Section title={t('Next steps')} icon="check-circle">
      <div class="todo">
        {#each steps as it (it)}
          <div class="todo-item {it.level}">
            <div class="ic"><Icon name={STEP_ICONS[it.key.split('|')[0]] || 'info'} size={18} /></div>
            <div class="min-w-0">
              <b>{it.title}</b>
              <div class="t">{it.text}</div>
              <div class="btns">
                {#each it.actions as a, i (i)}<a class="btn sm primary" href={a.href || '#/'}>{a.label}</a>{/each}
                <button class="btn sm ghost ml-auto" title={t('Don’t show again')} onclick={() => later(it)}>{t('hide')}</button>
              </div>
            </div>
          </div>
        {/each}
      </div>
    </Section>
  {/if}

  {#if newcomer}
    <!-- no own playlist yet: one card instead of several empty sections -->
    <Section title={t('Let’s go')} icon="sparkles">
      <div class="card grid gap-3.5">
        <p class="muted small">{t('The easiest start is a mix: a playlist that renews itself, with ever-changing music you like. One tap creates it.')}</p>
        <!-- "New playlist" and "Discover" are in the greeting above -->
        {#if mixIdeas.length}
          <div class="btns">
            {#each mixIdeas as x (x)}
              <button class="btn sm" onclick={() => take(x)}><Icon name="plus" size={14} />{x.title}</button>
            {/each}
          </div>
        {/if}
      </div>
    </Section>
  {:else}
    <Section title={t('Your mixes')} icon="sunrise">
      {#if mixes.length}
        <TodayRow {mixes} />
      {:else}
        <div class="card grid gap-3">
          <p class="muted small">{t('A mix renews itself – daily, weekly or monthly.')}</p>
          <div class="btns">
            {#each mixIdeas as x (x)}
              <button class="btn sm" onclick={() => take(x)}><Icon name="plus" size={14} />{x.title}</button>
            {/each}
            <a class="btn primary sm" href="#/neu?type=mix"><Icon name="dice" size={15} />{t('Create your own mix')}</a><!-- i18n-ignore: route -->
          </div>
        </div>
      {/if}
    </Section>
  {/if}

  {#if sgError || !cache.sg || ideas.length}
    <Section title={t('Discovered for you')} icon="sparkles" action={allIdeas}>
      {#if sgError}
        <p class="muted small">{sgError}</p>
      {:else if !cache.sg}
        <div class="skel h-[150px]"></div>
      {:else}
        <div class="g-cards">
          {#each ideas as s (s)}
            <IdeaCard {s} multi={own.size > 1} onaccept={() => take(s)} ondismiss={() => dismiss(s)} />
          {/each}
        </div>
      {/if}
    </Section>
  {/if}

  <!-- no listening week without an own profile; a missing password is already listed under "Next steps" -->
  {#if !woche?.none && !(woche?.noPw && pwStep)}
  <Section title={t('Your week')} icon="trending" action={review}>
    {#if !woche}
      <div class="skel h-[120px]"></div>
    {:else if woche.error}
      <div class="card">
        <p class="muted">{woche.noPw ? t('For your personal listening stats, Tuttiphon needs your Navidrome password once – the same one as in Symfonium. It stays on your NAS.') : woche.error}</p>
        {#if woche.noPw}<a class="btn sm primary" href="#/einstellungen/konto"><Icon name="key" size={15} />{t('Turn on stats')}</a>{/if}
      </div>
    {:else if !woche.d.totals.plays}
      <div class="card">
        <p class="muted">
          {recent(woche.d)
            ? t('Tuttiphon has been counting since {date} – as soon as you listen, this shows what you played most.', { date: new Date(woche.d.since).toLocaleDateString(locale(), { day: 'numeric', month: 'long' }) })
            : t('You haven’t listened to anything this week yet – or Symfonium hasn’t reported the plays yet.')}
        </p>
      </div>
    {:else}
      <WeekCard d={woche.d} />
    {/if}
  </Section>
  {/if}

  {#if mine.length}
    <Section title={t('Your own playlists')} icon="playlists" action={allSee}>
      <Carousel>{#each mine as p (p.id)}<PlaylistCard {p} />{/each}</Carousel>
    </Section>
  {/if}

  {#if shared.length}
    <Section title={t('Shared by the family')} icon="users">
      <p class="muted small -mt-1.5 mb-3">{t('Others have shared these playlists with everyone. You can listen to them in Symfonium – and create your own copy here to adjust.')}</p>
      <Carousel>{#each shared as p (p.id)}<PlaylistCard {p} />{/each}</Carousel>
    </Section>
  {/if}

  <Section title={t('New in your library')} icon="disc">
    {#if !cache.home && cache.failed.home}
      <!-- loading failed: the error and "Try again" instead of a placeholder forever -->
      <div class="card flex items-center gap-3 flex-wrap">
        <span class="muted small flex-1 min-w-[12rem]">{cache.failed.home}</span>
        <button class="btn sm" onclick={loadHome}><Icon name="refresh" size={15} />{t('Try again')}</button>
      </div>
    {:else if !cache.home}
      <div class="skel h-[230px]"></div>
    {:else if !cache.home.newAlbums.length}
      <p class="muted small">{t('Nothing new has been added lately.')}</p>
    {:else}
      <NewAlbums albums={cache.home.newAlbums} />
    {/if}
  </Section>

  {#if newcomer}
    <Section title={t('How it works')} icon="help" action={helpLink}>
      <TipCards items={[
        ['heart', t('Your taste'), t('In “My profile” you set your favorite worlds, favorite bands and dislikes. The suggestions are based on them.')],
        ['smartphone', t('Listen in Symfonium'), t('New playlists go to Navidrome automatically. They show up in Symfonium after the next sync.')],
        ['eye', t('Just for you or for everyone'), t('You choose in your profile whether others see your playlists. Only you can edit them.')],
      ]} />
    </Section>
  {/if}
</div>
