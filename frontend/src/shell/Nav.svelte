<!-- Navigation: sidebar on the computer, bar at the bottom on the phone (the first four entries + "More"). -->
<script>
  import Icon from '../components/Icon.svelte'
  import { S, isAdmin, pendingCount } from '../lib/state.svelte.js'
  import { route } from '../lib/router.svelte.js'
  import { openSheet, closeSheet } from '../lib/overlay.svelte.js'
  import { logout } from '../lib/account.js'
  import { t } from '../lib/i18n.svelte.js'

  let { bottom = false } = $props()

  const ADMIN_NAV = $derived([
    ['#/', 'home', t('Home'), /^\/$/],
    ['#/playlists', 'playlists', t('Playlists'), /^\/playlist/],
    ['#/entdecken', 'compass', t('Discover'), /^\/entdecken/],
    ['#/welten', 'globe', t('Music worlds'), /^\/welt/],
    ['#/richtungen', 'sliders', t('Vibes'), /^\/richtungen/],
    ['#/personen', 'users', t('People'), /^\/person/],
    ['#/statistik', 'chart', t('Statistics'), /^\/statistik/],
    null,
    ['#/verlauf', 'clock', t('History'), /^\/verlauf/],
    ['#/einstellungen', 'settings', t('Settings'), /^\/einstellungen/],
    ['#/hilfe', 'help', t('Help'), /^\/hilfe/],
  ])
  // Users: only what concerns them – easy to grasp
  const USER_NAV = $derived([
    ['#/', 'home', t('For you'), /^\/$/],
    ['#/playlists', 'playlists', t('My playlists'), /^\/playlist/],
    ['#/entdecken', 'compass', t('Discover'), /^\/entdecken/],
    ['#/welten', 'globe', t('Music worlds'), /^\/welt/],
    ['#/statistik', 'chart', t('My statistics'), /^\/statistik/],
    null,
    ['#/profil', 'user', t('My profile'), /^\/(profil|person)/],
    ['#/einstellungen', 'settings', t('Settings'), /^\/einstellungen/],
    ['#/hilfe', 'help', t('Help'), /^\/hilfe/],
  ])
  const items = $derived(isAdmin() ? ADMIN_NAV : USER_NAV)
  const pending = $derived(pendingCount())
  const moreOn = $derived(/^\/(person|profil|richtungen|einstellungen|verlauf|statistik|hilfe)/.test(route.path))

  function moreMenu() {
    openSheet({ title: t('More'), body: moreBody })
  }
  const moreEntries = $derived(isAdmin()
    ? [['#/neu', 'plus', t('New playlist')], ['#/statistik', 'chart', t('Statistics')], ['#/personen', 'users', t('People')], ['#/richtungen', 'sliders', t('Vibes')],   // i18n-ignore: route
      ['#/verlauf', 'clock', t('History')], ['#/einstellungen', 'settings', t('Settings')], ['#/hilfe', 'help', t('Help & guides')]]
    : [['#/neu', 'plus', t('New playlist')], ['#/statistik', 'chart', t('My statistics')], ['#/profil', 'user', t('My profile')],   // i18n-ignore: route
      ['#/einstellungen', 'settings', t('Settings')], ['#/hilfe', 'help', t('Help & guides')]])
</script>

{#snippet moreBody()}
  <div class="grid gap-2">
    {#each moreEntries as [href, ic, label] (href)}
      <a class="member-row p-3.5 no-underline" {href} onclick={closeSheet}><Icon name={ic} /><b>{label}</b></a>
    {/each}
    {#if S.me?.user}
      <button class="member-row p-3.5 w-full text-left" onclick={logout}><Icon name="logout" /><b>{t('Sign out')}</b></button>
    {/if}
  </div>
{/snippet}

{#snippet link([href, ic, label, re])}
  <a {href} class:on={re.test(route.path)} aria-current={re.test(route.path) ? 'page' : undefined}>
    <Icon name={ic} />
    <span>{label}</span>
    {#if href === '#/playlists' && pending}<span class="count">{pending}</span>{/if}
  </a>
{/snippet}

{#if bottom}
  <nav class="bottomnav" aria-label={t('Navigation')} data-tour="bottomnav">
    {#each items.filter(Boolean).slice(0, 4) as item (item[0])}{@render link(item)}{/each}
    <button type="button" data-tour="more" class:on={moreOn} aria-haspopup="dialog" onclick={moreMenu}><Icon name="more" /><span>{t('More')}</span></button>
  </nav>
{:else}
  <nav class="nav" aria-label={t('Navigation')} data-tour="nav">
    {#each items as item, i (item?.[0] ?? `sep${i}`)}
      {#if item}{@render link(item)}{:else}<div class="h-px bg-line mx-2 my-2.5"></div>{/if}
    {/each}
  </nav>
{/if}

<style>
  .nav { display: grid; gap: 2px; }
  .nav a { display: flex; align-items: center; gap: 12px; padding: 10px 12px; border-radius: 12px; color: var(--muted); text-decoration: none; font-weight: 600; transition: background .15s, color .15s; }
  .nav a:hover { background: var(--surface); color: var(--text); }
  .nav a.on { background: var(--surface-2); color: var(--text); }
  .nav a.on :global(svg) { color: var(--accent); }
  .count { margin-left: auto; font-size: .72rem; background: var(--warn); color: var(--bg); border-radius: 99px; padding: 0 7px; font-weight: 800; }

  .bottomnav { display: none; }
  @media (max-width: 900px) {
    .bottomnav {
      display: grid; grid-template-columns: repeat(5, 1fr); position: fixed; left: 0; right: 0; bottom: 0; z-index: 35;
      background: color-mix(in srgb, var(--bg-2) 92%, transparent); backdrop-filter: blur(16px); border-top: 1px solid var(--line);
      padding: 6px 4px calc(6px + env(safe-area-inset-bottom));
    }
    .bottomnav a, .bottomnav button { display: grid; justify-items: center; gap: 2px; font-size: .68rem; font-weight: 650; color: var(--muted); text-decoration: none; padding: 4px 0; position: relative; }
    .bottomnav .on { color: var(--text); }
    .bottomnav .on :global(svg) { color: var(--accent); }
    .bottomnav .count { position: absolute; top: 0; right: calc(50% - 22px); margin: 0; font-size: .62rem; padding: 0 5px; }
  }
</style>
