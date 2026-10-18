<!--
  Settings in sections, grouped (account, family, connection, music, operation). Users see only General and My
  account, administrators see everything. Computer: the list on the left, the section on the right. Phone:
  #/einstellungen shows the list, each section opens as its own page with a way back (#/einstellungen/<tab>).
-->
<script>
  import { MediaQuery } from 'svelte/reactivity'
  import Icon from '../components/Icon.svelte'
  import PageHead from '../components/PageHead.svelte'
  import { S, isAdmin } from '../lib/state.svelte.js'
  import { t } from '../lib/i18n.svelte.js'
  import Allgemein from './settings/Allgemein.svelte'
  import Konto from './settings/Konto.svelte'
  import Benutzer from './settings/Benutzer.svelte'
  import Startseite from './settings/Startseite.svelte'
  import Navidrome from './settings/Navidrome.svelte'
  import Speicherorte from './settings/Speicherorte.svelte'
  import Playlists from './settings/Playlists.svelte'
  import Deezer from './settings/Deezer.svelte'
  import Lyrics from './settings/Lyrics.svelte'
  import Opus from './settings/Opus.svelte'
  import Intelligenz from './settings/Intelligenz.svelte'
  import Ablaeufe from './settings/Ablaeufe.svelte'
  import Sicherung from './settings/Sicherung.svelte'
  import Bibliothek from './settings/Bibliothek.svelte'
  import Benachrichtigungen from './settings/Benachrichtigungen.svelte'
  import { smooth } from '../lib/motion.js'

  /** section from the address – empty: the list on the phone, the first section on the computer */
  let { tab = '' } = $props()

  const GROUPS = $derived([
    ['account', t('Account')],
    ['family', t('Family')],
    ['connection', t('Connection')],
    ['music', t('Music')],
    ['operation', t('Operation')],
  ])
  // [id, icon, title, short description, page, group] – in the order of the groups
  const TABS = $derived([
    ['allgemein', 'palette', t('General'), t('Theme, install as app'), Allgemein, 'account'],
    ['konto', 'key', t('My account'), t('Sign-in, password, tour'), Konto, 'account'],
    ['benutzer', 'users', t('Users & permissions'), t('Who may do what in Tuttiphon'), Benutzer, 'family'],
    ['start', 'home', t('Home page'), t('What the home page shows'), Startseite, 'family'],
    ['benachrichtigungen', 'bell', t('Notifications'), t('To your phone via the app or ntfy'), Benachrichtigungen, 'family'],
    ['navidrome', 'server', 'Navidrome', t('Server, accounts, scan'), Navidrome, 'connection'],
    ['speicher', 'drive', t('Storage locations'), t('Music, playlists, archive'), Speicherorte, 'connection'],
    ['playlists', 'playlists', t('Playlists'), t('Basic rules & applying'), Playlists, 'music'],
    ['deezer', 'star', t('Deezer stars'), t('Popularity → stars'), Deezer, 'music'],
    ['lyrics', 'mic', t('Lyrics'), t('Providers, search & cleanup'), Lyrics, 'music'],
    ['opus', 'headphones', t('Conversion'), 'FLAC → Opus', Opus, 'music'],
    ['intel', 'brain', t('Intelligence'), t('Sound, Last.fm, classification'), Intelligenz, 'music'],
    ['bibliothek', 'eraser', t('Check library'), t('Duplicates, covers, gaps'), Bibliothek, 'music'],
    ['ablaeufe', 'route', t('Automation'), t('Update everything, daily, folder watch'), Ablaeufe, 'operation'],
    ['sicherung', 'archive', t('Backup'), t('Daily backup, restore'), Sicherung, 'operation'],
  ])
  const USER_TABS = ['allgemein', 'konto']

  const admin = isAdmin()
  const tabs = $derived(admin ? TABS : TABS.filter(([id]) => USER_TABS.includes(id)))
  // only groups with sections; headings only if there is more than one group
  const groups = $derived(GROUPS.map(([id, title]) => ({ id, title, list: tabs.filter((x) => x[5] === id) })).filter((g) => g.list.length))

  const phone = new MediaQuery('max-width: 900px')
  const found = $derived(tabs.find(([id]) => id === tab))
  const current = $derived(found || tabs[0])
  const View = $derived(current[4])
  const currentId = $derived(current[0])   // a language switch rebuilds the tabs – the section stays the same
  /** phone without a (valid) section: the list instead of a section */
  const showList = $derived(phone.current && !found)
  const shown = $derived(showList ? '' : currentId)

  const descOf = (id, desc) => id === 'opus' ? `FLAC → ${S.config.settings.opus?.codec === 'aac' ? 'AAC' : 'Opus'}` : desc

  let nav, content
  /** scroll position of the list on the phone – back from a section, it is there again */
  let listY = 0
  let last = null
  // Section changed (the page itself stays). Phone: a section opens at the top like its own page, the list where it was
  // left. Computer: keep the active section visible in the list; scroll up only if the start of the section is above the
  // viewport (no jump to the very top).
  $effect(() => {
    const now = shown, onPhone = phone.current
    const before = last
    last = now
    requestAnimationFrame(() => {
      if (onPhone) {
        if (before !== null && before !== now) window.scrollTo(0, now ? 0 : listY)
        return
      }
      keepInList()
      const top = content?.getBoundingClientRect().top ?? 0
      if (top < 84) window.scrollBy({ top: top - 96, behavior: smooth() })
    })
  })

  /** Computer: the list scrolls on its own when it is taller than the window – the active section stays in view. */
  function keepInList() {
    const on = nav?.querySelector('a.on')
    if (!on || nav.scrollHeight <= nav.clientHeight) return
    const top = on.offsetTop, bottom = top + on.offsetHeight
    if (top < nav.scrollTop || bottom > nav.scrollTop + nav.clientHeight) nav.scrollTop = top - (nav.clientHeight - on.offsetHeight) / 2
  }
</script>

{#snippet list()}
  <nav class="set-nav" bind:this={nav} aria-label={t('Settings')}>
    {#each groups as g (g.id)}
      <div class="grp" role="group" aria-label={groups.length > 1 ? g.title : undefined}>
        {#if groups.length > 1}<div class="grp-title">{g.title}</div>{/if}
        <div class="grp-items">
          {#each g.list as [id, icon, label, desc] (id)}
            <a href="#/einstellungen/{id}" class:on={!showList && id === currentId} aria-current={!showList && id === currentId ? 'page' : undefined}
              onclick={() => { listY = window.scrollY }}>
              <span class="emo"><Icon name={icon} size={18} /></span>
              <span class="txt"><b>{label}</b><small>{descOf(id, desc)}</small></span>
              <span class="chev"><Icon name="right" size={16} /></span>
            </a>
          {/each}
        </div>
      </div>
    {/each}
  </nav>
{/snippet}

{#snippet section()}
  <div class="grid gap-[18px] min-w-0" bind:this={content}>
    <!-- When the whole configuration is replaced (undo), rebuild the section -->
    {#key S.config}<View />{/key}
  </div>
{/snippet}

<!-- On the phone, list and sections are pages of their own (fade in like a page) -->
{#key phone.current ? shown : '-'}
  <div class="page">
    {#if phone.current && !showList}
      <a href="#/einstellungen" class="link inline-flex gap-1.5 items-center mt-2.5"><Icon name="left" size={16} />{t('Settings')}</a>
      <PageHead title={current[2]} />
      {@render section()}
    {:else}
      <PageHead title={t('Settings')} sub={admin
        ? t('Everything Tuttiphon does can be adjusted here – changes apply immediately.')
        : t('Appearance and your account. To change your music taste, go to “My profile”.')} />
      {#if showList}
        {@render list()}
      {:else}
        <div class="grid grid-cols-[250px_minmax(0,1fr)] gap-[26px] items-start">
          {@render list()}
          {@render section()}
        </div>
      {/if}
    {/if}
  </div>
{/key}

<style>
  /* Computer: list on the left, sticky; scrolls on its own if it is taller than the window */
  .set-nav { position: sticky; top: 84px; display: grid; gap: 14px; max-height: calc(100vh - 100px); overflow-y: auto;
    overscroll-behavior: contain; scrollbar-width: thin; padding: 3px; margin: -3px; }
  .grp-title { padding: 0 12px 4px; font-size: .72rem; font-weight: 700; letter-spacing: .08em; text-transform: uppercase; color: var(--muted); }
  .grp-items { display: grid; gap: 2px; }
  .set-nav a { display: flex; gap: 12px; align-items: center; padding: 8px 12px; border-radius: 12px; color: var(--text-2); text-decoration: none; transition: background .15s; }
  .set-nav a:hover { background: var(--surface); }
  .set-nav a.on { background: var(--surface); box-shadow: inset 3px 0 0 var(--accent); }
  .emo { display: grid; place-items: center; width: 34px; height: 34px; flex-shrink: 0; border-radius: 10px; background: var(--surface-2); color: var(--accent); }
  .on .emo { background: var(--accent); color: #fff; }
  .txt { display: grid; flex: 1; min-width: 0; }
  small { color: var(--muted); font-size: .76rem; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .chev { display: none; }
  /* Phone: the list is a page of its own – groups as cards with rows */
  @media (max-width: 900px) {
    .set-nav { position: static; max-height: none; overflow: visible; gap: 18px; padding: 0; margin: 0; }
    .grp-title { padding: 0 4px 8px; }
    .grp-items { gap: 0; overflow: hidden; background: var(--surface); border: 1px solid var(--line); border-radius: var(--radius-card); }
    .set-nav a { padding: 12px 14px; border-radius: 0; color: var(--text); }
    .set-nav a + a { border-top: 1px solid var(--line); }
    .set-nav a:hover { background: var(--surface-2); }
    .chev { display: grid; flex-shrink: 0; color: var(--muted); }
  }
</style>
