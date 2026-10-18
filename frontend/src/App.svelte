<!--
  Frame of the app: sidebar, header (search, running task, account), page, bottom navigation (phone),
  apply bar, sheets and tour. Picks the page from the address (lib/router.svelte.js).
-->
<script>
  import { untrack } from 'svelte'
  import Icon from './components/Icon.svelte'
  import Empty from './components/Empty.svelte'
  import SheetHost from './components/SheetHost.svelte'
  import ModalHost from './components/ModalHost.svelte'
  import ToastHost from './components/ToastHost.svelte'
  import Nav from './shell/Nav.svelte'
  import Search from './shell/Search.svelte'
  import UserMenu from './shell/UserMenu.svelte'
  import TaskBar from './shell/TaskBar.svelte'
  import AdminOnly from './shell/AdminOnly.svelte'
  import Tour from './components/Tour.svelte'
  import MiniPlayer from './components/MiniPlayer.svelte'
  import { S, isAdmin, ownPersons, loadStatus, loadLibrary, loadPlaylists, startPolling, save } from './lib/state.svelte.js'
  import { route, replace } from './lib/router.svelte.js'
  import { O, closeSheet } from './lib/overlay.svelte.js'
  import { api } from './lib/api.js'
  import { applyTheme } from './lib/theme.js'
  import { startTour } from './lib/tour.svelte.js'
  import { initInstall } from './lib/install.svelte.js'
  import { t } from './lib/i18n.svelte.js'

  // the pages opened most often are part of the app itself …
  import Start from './pages/Start.svelte'
  import Home from './pages/Home.svelte'
  import Playlists from './pages/Playlists.svelte'
  import Playlist from './pages/Playlist.svelte'
  // … all others are files of their own, loaded when first opened (and in the background shortly after the start)
  import Lazy, { preload } from './components/Lazy.svelte'
  const PAGES = {
    welcome: () => import('./pages/Welcome.svelte'),
    profil: () => import('./pages/Profil.svelte'),
    wizard: () => import('./pages/Wizard.svelte'),
    setup: () => import('./pages/Setup.svelte'),
    discover: () => import('./pages/Discover.svelte'),
    welten: () => import('./pages/Welten.svelte'),
    welt: () => import('./pages/Welt.svelte'),
    richtungen: () => import('./pages/Richtungen.svelte'),
    personen: () => import('./pages/Personen.svelte'),
    person: () => import('./pages/Person.svelte'),
    settings: () => import('./pages/Settings.svelte'),
    history: () => import('./pages/History.svelte'),
    stats: () => import('./pages/Stats.svelte'),
    help: () => import('./pages/Help.svelte'),
  }
  const ADMIN_PAGES = ['setup', 'richtungen', 'personen', 'history']
  const lazy = (name, props = {}) => ({ C: Lazy, props: { load: PAGES[name], props } })

  let ready = $state(false)
  let failure = $state(null)   // error at the start (Error with .offline when Tuttiphon cannot be reached)
  let scrolled = $state(false)

  /** Which page with which props? (null = unknown address → home) */
  const page = $derived.by(() => {
    const [a, b] = route.parts
    const admin = isAdmin()
    switch (a) {
      case undefined: return { C: admin ? Start : Home }
      case 'willkommen': return lazy('welcome')
      case 'einrichtung': return admin ? lazy('setup') : { C: AdminOnly }
      case 'profil': return lazy('profil')
      case 'playlists': return { C: Playlists }
      case 'playlist': return b ? { C: Playlist, props: { id: b } } : null
      case 'neu': return lazy('wizard', { query: route.query })   // i18n-ignore: route
      case 'entdecken': return lazy('discover')
      case 'welten': return lazy('welten')
      case 'welt': return b ? lazy('welt', { id: b }) : null
      case 'richtungen': return admin ? lazy('richtungen') : { C: AdminOnly }
      case 'personen': return admin ? lazy('personen') : { C: AdminOnly }
      case 'person': return b ? lazy('person', { id: b }) : null
      case 'einstellungen': return lazy('settings', { tab: b || '' })   // without a section: the list on the phone
      case 'verlauf': return admin ? lazy('history') : { C: AdminOnly }
      case 'statistik': return lazy('stats', { kind: b || 'gesamt' })
      case 'hilfe': return lazy('help', { topic: b || null })
      default: return null
    }
  })
  // unknown address: to the home page – replacing it, otherwise "back" would lead to it (and here) again
  $effect(() => {
    if (ready && !page) untrack(() => replace('#/'))
  })

  // Help and settings: the section in the address is only a target on the same page – the page stays
  // and scrolls by itself (otherwise it jumped to the top first and then to the target)
  const SAME_PAGE = ['hilfe', 'einstellungen']
  const section = (path) => {
    const first = path.split('/').filter(Boolean)[0] || ''
    return SAME_PAGE.includes(first) ? first : path
  }
  const pageKey = $derived(`${section(route.path)}|${route.query}|${route.key}`)

  // Page change: an open sheet belongs to the old page, scroll to the top. Same page again (route.key): position stays.
  let lastPath = route.path
  $effect(() => {
    const path = route.path
    untrack(() => {
      if (path === lastPath) return
      const same = section(path) === section(lastPath)
      lastPath = path
      closeSheet()
      if (!same) window.scrollTo(0, 0)
    })
  })

  /** User without a profile – or with a profile but without preferences and playlists (and never saw the assistant). */
  function needsWelcome() {
    if (!S.me.own.length) return true
    let seen = !!S.me.welcomeSeen   // remembered on the server per account – applies to all devices
    try { seen ||= !!localStorage.getItem(`nt-welcome:${(S.me.user || '').toLowerCase()}`) } catch { /* private mode */ }
    const own = ownPersons()
    return !seen && !own.some((p) => p.likes?.welten?.length || p.likes?.artists?.length) && !S.config.playlists.some((x) => S.me.own.includes(x.person))
  }

  /** New installation, not set up yet (settings.setup.done false): administrators go to the setup assistant –
   *  once per browser session, so whoever looks around first is not sent back after every reload. */
  function needsSetup() {
    if (!isAdmin() || S.config.settings?.setup?.done !== false) return false
    try {
      if (sessionStorage.getItem('nt-setup')) return false
      sessionStorage.setItem('nt-setup', '1')
    } catch { /* private mode: at every start */ }
    return true
  }

  let retryTimer
  async function init() {
    applyTheme()
    clearTimeout(retryTimer)
    failure = null
    try {
      S.me = await api('/api/me')
      S.config = await api('/api/config')
    } catch (e) {
      failure = e
      if (e.offline) retryTimer = setTimeout(init, 10000)   // starts by itself as soon as Tuttiphon is back
      return
    }
    // New here (no profile yet or nothing set up at all)? Then the welcome assistant first
    // (replacing the address: "back" must not lead to the page that sent here)
    if (!isAdmin() && needsWelcome() && !/^#\/(willkommen|hilfe)/.test(location.hash)) {
      replace('#/willkommen')   // right away – otherwise "For you" briefly builds before the assistant takes over
    }
    if (!/^#\/(einrichtung|hilfe)/.test(location.hash) && needsSetup()) {
      replace('#/einrichtung')
    }
    loadStatus()
    const lib = loadLibrary().catch(() => {})
    // pages that can show little without library data wait briefly for it
    if (/^#\/(welt|neu|person|richtungen)/.test(location.hash)) await lib
    ready = true
    loadPlaylists().catch(() => {})
    startPolling()
    // status every 30 s – not in a hidden tab (it is fetched again as soon as the page is visible)
    setInterval(() => { if (!S.running && !document.hidden) loadStatus() }, 30000)
    // installable as an app (service workers only exist over https or localhost)
    if ('serviceWorker' in navigator) navigator.serviceWorker.register('/sw.js').catch(() => {})
    initInstall()
    // the other pages in the background once everything is there: opening them later needs no server
    // (also after an update, when the files of the old version would be gone)
    const idle = window.requestIdleCallback || ((fn) => setTimeout(fn, 2500))
    idle(() => { for (const [name, load] of Object.entries(PAGES)) if (isAdmin() || !ADMIN_PAGES.includes(name)) preload(load) })
    // tour on the very first visit – not over an assistant (the setup assistant starts it when it is done)
    if ((isAdmin() || S.me.own.length) && !/^#\/(willkommen|einrichtung)/.test(location.hash)) setTimeout(() => startTour(), 1500)
  }
  init()

  const conn = $derived(S.status?.navidrome)
  /** a newer version on the server: save open changes, then load it */
  const reload = () => save().finally(() => location.reload())
</script>

<svelte:window onscroll={() => (scrolled = window.scrollY > 8)} />

{#snippet brand(size)}
  <a class="flex items-center gap-[11px] font-extrabold text-[1.15rem] tracking-[-.02em] no-underline" href="#/">
    <span class="grid place-items-center size-9 rounded-[11px] text-white bg-[image:var(--grad)] shadow-[0_6px_18px_rgba(217,70,239,.35)]">
      <Icon name="music" {size} />
    </span>
    <span class="brand-name">Tuttiphon</span>
  </a>
{/snippet}

<!-- inert while a sheet is open: Tab and screen readers stay in the sheet -->
<aside class="sidebar" inert={!!O.sheet}>
  <div class="px-2.5 pb-[18px]">{@render brand(20)}</div>
  {#if S.config}<Nav />{/if}
  <div class="mt-auto grid gap-2.5 px-1">
    <a class="btn primary justify-center" href="#/neu" data-tour="new"><Icon name="plus" size={18} />{t('New playlist')}</a><!-- i18n-ignore: route -->
    <UserMenu />
    <div class="flex items-center gap-2 text-[.8rem] text-muted px-2">
      {#if S.offline}
        <span class="size-2 rounded-full shrink-0 bg-err"></span><span>{t('Tuttiphon unreachable')}</span>
      {:else}
        <span class="size-2 rounded-full shrink-0 {conn?.ok ? 'bg-ok shadow-[0_0_0_3px_rgba(34,197,94,.18)]' : conn ? 'bg-err' : 'bg-muted'}"></span>
        <span>{conn?.ok ? `Navidrome ${String(conn.version).split(' ')[0]}` : conn ? t('Navidrome unreachable') : t('connecting …')}</span>
      {/if}
    </div>
  </div>
</aside>

<div class="app" inert={!!O.sheet}>
  <header class="topbar" class:scrolled>
    <div class="mobile-brand">{@render brand(18)}</div>
    {#if S.config}<Search />{/if}
    <TaskBar chip />
    <div class="mobile-only"><UserMenu compact /></div>
  </header>
  <main>
    {#if S.newVersion}
      <div class="note mb-4 flex items-center gap-2.5 flex-wrap border border-accent/40" role="status">
        <Icon name="sparkles" size={18} class="shrink-0 text-accent" />
        <span class="flex-1 min-w-[12rem]">{t('A new version of Tuttiphon is ready – reload to use it.')}</span>
        <button class="btn sm primary" onclick={reload}><Icon name="refresh" size={15} />{t('Reload')}</button>
      </div>
    {/if}
    {#if ready && S.offline}
      <!-- Tuttiphon itself is gone (server stopped, network) – not Navidrome -->
      <div class="note mb-4 flex items-center gap-2.5 border border-err/40" role="status"><Icon name="alert" size={18} class="shrink-0 err-t" />
        <span>{t('Tuttiphon can’t be reached right now – changes are saved as soon as it’s back.')}</span>
      </div>
    {:else if ready && conn && !conn.ok && route.parts[0] !== 'einrichtung'}
      <!-- also visible on the phone (there is no sidebar there); the setup assistant says it itself -->
      <div class="note mb-4 flex items-center gap-2.5 border border-warn/40"><Icon name="alert" size={18} class="shrink-0 warn-t" />
        <span>{isAdmin() ? t('Navidrome cannot be reached – lists and numbers are missing until it runs again. Check the connection under Settings → Navidrome.') : t('Navidrome cannot be reached right now – lists and numbers are missing until it runs again.')}</span>
      </div>
    {/if}
    {#if failure}
      <Empty icon="alert" title={failure.offline ? t('Server unreachable') : t('Tuttiphon could not start')}
        text={failure.offline ? t('Tuttiphon cannot be reached right now. It starts by itself as soon as the server is back.') : failure.message}>
        <button class="btn primary" onclick={init}><Icon name="refresh" size={16} />{t('Try again')}</button>
      </Empty>
    {:else if !ready}
      <div class="empty border-0 mt-[20vh]"><div>{t('Tuttiphon is starting …')}</div></div>
    {:else if page}
      {#key pageKey}
        <page.C {...page.props} />
      {/key}
    {/if}
  </main>
</div>

{#if S.config}<Nav bottom />{/if}
<MiniPlayer />
<TaskBar />
<SheetHost />
<ModalHost />
<ToastHost />
{#if ready}<Tour />{/if}

<style>
  .sidebar {
    position: fixed; inset: 0 auto 0 0; width: var(--sidebar); z-index: 30;
    display: flex; flex-direction: column; gap: 6px;
    /* installed app (iPad): keep clear of the status bar and the home indicator */
    padding: calc(22px + env(safe-area-inset-top, 0px)) 14px calc(16px + env(safe-area-inset-bottom, 0px)) calc(14px + env(safe-area-inset-left, 0px));
    background: var(--bg-2); border-right: 1px solid var(--line);
  }
  .app { margin-left: var(--sidebar); min-height: 100vh; }
  .topbar {
    position: sticky; top: 0; z-index: 20; display: flex; align-items: center; gap: 14px;
    padding: calc(12px + env(safe-area-inset-top, 0px)) calc(32px + env(safe-area-inset-right, 0px)) 12px 32px;
    background: color-mix(in srgb, var(--bg) 82%, transparent); backdrop-filter: blur(16px);
    border-bottom: 1px solid transparent;
  }
  .topbar.scrolled { border-bottom-color: var(--line); }
  .mobile-brand, .mobile-only { display: none; }
  main { padding: 8px 32px calc(120px + var(--player)); max-width: 1480px; margin: 0 auto; }
  @media (max-width: 900px) {
    .sidebar { display: none; }
    .app { margin-left: 0; }
    /* installed app on the iPhone (status bar over the page): below the status bar, beside the notch */
    .topbar { padding: calc(10px + env(safe-area-inset-top, 0px)) calc(16px + env(safe-area-inset-right, 0px)) 10px calc(16px + env(safe-area-inset-left, 0px)); gap: 10px; }
    .mobile-brand, .mobile-only { display: block; }
    .mobile-brand :global(.brand-name) { display: none; }
    main { padding: 4px calc(16px + env(safe-area-inset-right, 0px)) calc(140px + var(--player)) calc(16px + env(safe-area-inset-left, 0px)); }
  }
</style>
