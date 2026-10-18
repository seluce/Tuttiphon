<!-- Small (?) next to the page title – opens the explanation of this page as a sheet, with the matching
     "Show me" guide. Without a matching topic it leads to the section in Help. -->
<script>
  import Icon from './Icon.svelte'
  import HelpSheet from '../pages/help/HelpSheet.svelte'
  import { route } from '../lib/router.svelte.js'
  import { isAdmin } from '../lib/state.svelte.js'
  import { openSheet } from '../lib/overlay.svelte.js'
  import { guidesFor, guideById } from '../lib/guides.js'
  import { t } from '../lib/i18n.svelte.js'

  let { topic = undefined } = $props()
  const HELP_FOR = [[/^\/$/, 'start'], [/^\/playlists?/, 'playlists'], [/^\/neu/, 'neu'], [/^\/entdecken/, 'entdecken'], [/^\/welt/, 'welten'],   // i18n-ignore: topic ids
    [/^\/richtungen/, 'richtungen'], [/^\/(person|profil|willkommen)/, 'personen'], [/^\/statistik/, 'statistik'],
    [/^\/einstellungen\/(konto|benutzer)/, 'konten'], [/^\/einstellungen\/lyrics/, 'lyrics'], [/^\/einstellungen\/opus/, 'opus'],
    [/^\/einstellungen\/deezer/, 'aktualisieren'], [/^\/einstellungen\/allgemein/, 'allgemein'], [/^\/einstellungen\/speicher/, 'docker'],
    [/^\/einstellungen\/ablaeufe/, 'watch'], [/^\/einstellungen\/sicherung/, 'sicherung'], [/^\/einstellungen\/intel/, 'intel'],
    [/^\/einstellungen\/bibliothek/, 'bibliothek'], [/^\/einstellungen\/benachrichtigungen/, 'benachrichtigungen'], [/^\/einstellungen/, 'einstellungen'],
    [/^\/verlauf/, 'start'], [/^\/einrichtung/, 'einrichtung']]
  const target = $derived.by(() => {
    let id = topic ?? HELP_FOR.find(([re]) => re.test(route.path))?.[1]
    if (!isAdmin() && id === 'einstellungen') id = 'konten'   // users only have "My account"
    return id
  })

  // The help texts are large and only load on first opening (own file in the build). If that file cannot be loaded
  // (e.g. replaced by an update in the meantime), the link leads to Help instead.
  async function show(e) {
    e.preventDefault()
    const admin = isAdmin()
    let topics
    try {
      topics = admin ? (await import('../pages/help/AdminTopics.svelte')).ADMIN_TOPICS
        : (await import('../pages/help/UserTopics.svelte')).USER_TOPICS
    } catch {
      location.hash = `#/hilfe/${target}`
      return
    }
    const tp = topics.find((x) => x.id === target)
    if (!tp) { location.hash = `#/hilfe/${target}`; return }   // then go to Help instead
    const mine = guidesFor(admin)
    const guides = (tp.guides || []).map(guideById).filter((g) => mine.includes(g))
    openSheet({ title: tp.title, component: HelpSheet, props: { topic: tp, guides } })
  }
</script>

{#if target}
  <a href="#/hilfe/{target}" title={t('Help for this page')} aria-label={t('Help')} onclick={show}
    class="inline-grid place-items-center size-7 ml-2.5 align-middle rounded-full text-muted bg-surface-2 hover:text-text hover:bg-surface-3 transition-colors">
    <Icon name="help" size={18} />
  </a>
{/if}
