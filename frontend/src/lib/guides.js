// "Show me" guides: lead step by step through the real interface – on the phone as on the PC.
// Shown by the tour (components/Tour.svelte), started with startGuide(id) from lib/tour.svelte.js:
// in Help ("What do you want to do?") and in the help sheet behind the (?) next to every page title.
//
// A guide: id, icon, title, short (three short steps for the card in Help), href ("Jump right in" – a route, or
// href(admin) when it depends on the role), keys (more search words), who ('admin' | 'user' | both), show(admin)
// (only show if …) and steps(ctx) → steps.
// A step: go (route, navigate there first), reset (rebuild the page even if it is already open, e.g. the assistant
// with a half-filled draft), sel (targets, the first visible one is highlighted), title, text, optional (if the target
// is missing, the step is skipped). Without sel the hint is centered.
import { S, isAdmin, ownPersons, defaultPerson } from './state.svelte.js'
import { t, translated } from './i18n.svelte.js'

/** What the guides need to know about the account: role, own profile, an own playlist or mix */
function context() {
  const admin = isAdmin()
  const persons = ownPersons()
  const me = admin ? S.config.personen.find((p) => p.id === defaultPerson()) || persons[0] : persons[0]
  const mine = S.config.playlists.filter((p) => (p.status || 'aktiv') === 'aktiv' && (admin || persons.some((x) => x.id === p.person)))
  const pl = (p) => (p ? `#/playlist/${encodeURIComponent(p.id)}` : null)
  return {
    admin,
    choosePerson: persons.length > 1,
    profile: me ? `#/person/${me.id}` : null,
    playlist: pl(mine.find((p) => (p.person || defaultPerson()) === me?.id) || mine[0]),
    mix: pl(mine.find((p) => p.type === 'mix' && !p.review)),
  }
}

const noProfile = () => ({ go: '#/willkommen', title: t('First a profile'), text: t('The welcome assistant briefly asks what you like to listen to. After that, suggestions and mixes fit you.') })

export const GUIDES = translated(() => [
  {
    id: 'aktualisieren', icon: 'refresh', who: 'admin', href: '#/',
    title: t('Bring everything up to date'),
    short: [t('Open the home page'), t('Tap “Update everything”'), t('Follow the progress below')],
    keys: t('scan navidrome apply write deezer lyrics opus aac analysis automatic folder'),
    steps: () => [
      { go: '#/', sel: ['[data-guide=update]'], title: t('One click for everything'), text: t('Convert music, fetch lyrics and missing covers, understand the sound, write playlists, scan Navidrome and set stars – one after another. “Apply playlists only” writes just the playlists.') },
      { go: '#/einstellungen/ablaeufe', sel: ['[data-guide=schritte]'], title: t('Which steps are included'), text: t('Here you decide what “Update everything” does.') },
      { sel: ['[data-guide=watch]'], title: t('New music on its own'), text: t('With “Folder watch”, Tuttiphon starts the needed steps on its own as soon as new music arrives.') },
    ],
  },
  {
    id: 'playlist', icon: 'plus', href: '#/neu',   // i18n-ignore: route
    title: t('Put together your own playlist'),
    short: [t('Tap a music world'), t('Choose a vibe'), t('Look at the preview and create')],
    keys: t('new create make assistant music world vibe mood'),
    steps: (c) => [
      { go: '#/neu', reset: true, sel: ['.stepper'], title: c.choosePerson ? t('Four short steps') : t('Three short steps'),   // i18n-ignore: route
        text: c.choosePerson ? t('For whom, which music, which mood and finally the finishing touches. At the top you see where you are.')
          : t('Which music, which mood and finally the finishing touches. At the top you see where you are.') },
      c.choosePerson
        ? { sel: ['.pick'], title: t('For whom?'), text: t('The person decides which Navidrome account the playlist goes to and whose stars count. Then you choose the music world.') }
        : { sel: ['.pick'], title: t('Choose music'), text: t('Tap one or more music worlds. “All” takes the whole library.') },
      { sel: ['.wiz-foot'], title: t('On to the mood'), text: t('Then you choose the mood, such as Party or Calm. In the last step you see right away which songs would be in it, and create the playlist.') },
    ],
  },
  {
    id: 'mix', icon: 'smartphone', href: '#/entdecken',
    title: t('Mix for your phone'),
    short: [t('Create a mix'), t('Download it once in Symfonium'), t('New songs arrive on their own')],
    keys: t('offline download on the go auto daily weekly reshuffle symfonium'),
    steps: (c) => [
      { go: '#/entdecken', sel: ['[data-guide=anlegen]', '[data-guide=vorschlag]'], title: t('Ready-made mixes'), text: t('Here are mixes and playlists that match your taste. “Create” adds one of them right away.') },
      c.mix
        ? { go: c.mix, sel: ['[data-guide=pl-actions]'], title: t('Your mix'), text: t('A mix renews itself daily, weekly or monthly. “Reshuffle” puts together a different selection right away.') }
        : { go: '#/neu?type=mix', reset: true, sel: ['.stepper'], title: t('Or put it together yourself'), text: t('In the assistant you choose music and mood and, in the last step, “Mix”.') },   // i18n-ignore: route
      { title: t('Download in Symfonium'), text: t('Open the mix in Symfonium under Playlists and download it once. When it renews, Symfonium fetches the new songs on its own at the next sync.') },
    ],
  },
  {
    id: 'welt', icon: 'globe', who: 'admin', href: '#/welten',
    title: t('Adjust music worlds'),
    short: [t('Open music worlds'), t('Tap a world: add or remove bands'), t('Your own world with “New music world”')],
    keys: t('scene genre bands classify catalog automatic delete'),
    steps: () => [
      { go: '#/welten', sel: ['.g-welt .wcard'], title: t('Music worlds form on their own'), text: t('Tuttiphon recognizes from your library which worlds there are, and classifies new bands on its own. Tapping shows all bands of a world – there you remove bands or add some.') },
      { sel: ['[data-guide=welt-neu]'], title: t('Your own music world'), text: t('For your own selection: quickest from the scene catalog, then matching bands are added here on their own too.') },   // i18n-ignore: selector
    ],
  },
  {
    id: 'familie', icon: 'users', who: 'admin', href: '#/einstellungen/navidrome',
    title: t('Set up the family'),
    short: [t('Enter the passwords of the accounts'), t('Set roles'), t('Create one person per account')],
    keys: t('user account password role rights sign in person access'),
    steps: () => [
      { go: '#/einstellungen/navidrome', sel: ['[data-guide=passwoerter]'], title: t('Accounts & passwords'), text: t('With an account’s password, Tuttiphon creates playlists there and sees what is played.') },
      { go: '#/einstellungen/benutzer', sel: ['[data-guide=rechte]'], title: t('Who may do what?'), text: t('Everyone signs in with their own Navidrome account. Here you choose administrator, user or no access for each account.') },
      { go: '#/personen', sel: ['[data-guide=person-neu]'], title: t('People'), text: t('One person per account: suggestions and mixes are made for them with their favorites and dislikes.') },   // i18n-ignore: selector
    ],
  },
  {
    id: 'geschmack', icon: 'heart', href: '#/profil',
    title: t('Make suggestions better'),
    short: [t('Open my profile'), t('Add what was recognized with “+”'), t('Add favorites and dislikes')],
    keys: t('profile preferences favorites favorite bands favorite worlds recommendations taste listening'),
    steps: (c) => !c.profile ? [noProfile()] : [
      { go: c.profile, sel: ['[data-guide=taste]'], optional: true, title: c.admin ? t('From listening') : t('From your listening'),
        text: c.admin ? t('Tuttiphon recognizes from what is played in Symfonium which music people like. “+” turns it into a favorite.')
          : t('Tuttiphon recognizes from what you play in Symfonium which music you like. “+” turns it into a favorite.') },
      { go: c.profile, sel: ['[data-guide=likes]'], title: c.admin ? t('Preferences') : t('What you like to hear'),
        text: t('Favorite worlds bring matching suggestions, favorite bands show up more often in the mixes.') },
      { sel: ['[data-guide=dislikes]'], title: t('Dislikes'), text: t('Bands and genres here never go into the playlists – whatever the music world or mood.') },
    ],
  },
  {
    id: 'suche', icon: 'search', focus: true,
    title: t('Find music by mood'),
    short: [t('Type into the search field at the top'), t('For example “calm children’s songs”'), t('Tap “Create as mix”')],
    keys: t('search searching find mood band song combination'),
    steps: () => [
      { sel: ['[data-tour=search]'], title: t('Just type'), text: t('A band, a song or a mood, such as “calm children’s songs”, “Christmas kids” or “for falling asleep”.') },
      { sel: ['[data-tour=search]'], title: t('Straight to a mix'), text: t('If a mood matches your music, “Create as mix” is right at the top. A tap shows the mix with a preview in the assistant – “Create playlist” creates it, and it renews every week.') },
    ],
  },
  {
    id: 'nie', icon: 'ban', href: '#/profil',
    title: t('Stop hearing something'),
    short: [t('Band or genre under “Dislikes”'), t('Rate the song 1 star in Symfonium'), t('What you skip comes less often')],
    keys: t('hide block ban never dislike star skip annoying'),
    steps: (c) => [
      ...(c.profile ? [{ go: c.profile, sel: ['[data-guide=dislikes]'], title: t('Dislikes'), text: t('Bands and genres here never end up in the playlists – whatever the music world or mood.') }] : [noProfile()]),
      { title: t('Single songs'), text: t('Rate a song 1 star in Symfonium. Then it no longer comes into your mixes. What you often skip in the mix comes less often on its own.') },
    ],
  },
  {
    id: 'aendern', icon: 'edit', href: '#/playlists',
    title: t('Change or share a playlist'),
    short: [t('Tap a playlist'), t('Choose “Edit”, or “…” for the cover and more'), t('Set sharing in the profile')],
    keys: t('edit rename name cover picture pause delete trash share family visible copy'),
    steps: (c) => [
      { go: '#/playlists', sel: ['.g-pl .pcard'], title: t('Open a playlist'), text: c.playlist ? t('Tap a playlist to open it.') : t('All playlists show up here as soon as there is a first one.') },
      ...(c.playlist ? [{ go: c.playlist, sel: ['[data-guide=pl-actions]'], title: t('Everything at a glance'), text: t('“Edit” changes music and name. Under “…” you design the cover, pause the playlist – it then leaves Symfonium for a while and stays kept here – or move it to the trash.') }] : []),
      ...(c.profile ? [{ go: c.profile, sel: ['[data-guide=sichtbar]'], title: t('Share with the family'),
        text: c.admin ? t('With “visible to everyone”, all accounts see this person’s playlists in Navidrome and Symfonium.') : t('Here you set whether only you see your playlists or the whole family. Only you can change them.') }] : []),
    ],
  },
  {
    id: 'kinderschutz', icon: 'shield-check', href: '#/profil',
    title: t('Turn on kid-safe mode'),
    short: [t('Open the profile'), t('“Leave out songs with explicit lyrics”'), t('Applies to all playlists and mixes')],
    keys: t('kids rude swear words explicit parental clean lyrics'),
    steps: (c) => !c.profile ? [noProfile()] : [
      { go: c.profile, sel: ['[data-guide=kinderschutz]'], title: t('Kid-safe mode'),
        text: c.admin ? t('Turn it on per person – for example for the person whose playlists the kids listen to. Detected from the lyrics.')
          : t('Turn it on, and songs with explicit lyrics stay out of all your playlists and mixes. Detected from the lyrics.') },
      ...(c.admin ? [{ go: '#/einstellungen/lyrics', sel: ['[data-guide=kinderschutz-liste]'], title: t('Detected songs'),
        text: t('Here are the songs detected by their lyrics, sorted by band and searchable, with the words found – what you allow stays in even with kid-safe mode. Songs tagged as explicit in the file stay out as well.') }] : []),
    ],
  },
  {
    id: 'push', icon: 'bell', href: (admin) => (admin ? '#/einstellungen/benachrichtigungen' : '#/profil'),
    show: (admin) => admin || !!S.config.settings.notify?.enabled,
    title: t('Notifications on your phone'),
    short: [t('Open Tuttiphon on the phone'), t('Turn on for this device'), t('Allow notifications')],
    keys: t('ntfy push message phone notification app device'),
    steps: (c) => c.admin ? [
      { go: '#/einstellungen/benachrichtigungen', sel: ['[data-guide=notify]'], title: t('Turn on'), text: t('Turn on notifications and tap “Turn on for this device” on the phone. Alternatively it also works via ntfy.') },
      { title: t('For everyone'), text: t('Each person turns on their devices in the profile under “To your phone” and gets news from their favorite bands, what is new for them each Monday and their monthly recap there.') },
    ] : !c.profile ? [noProfile()] : [
      { go: c.profile, sel: ['[data-guide=push]'], title: t('On this device'), text: t('Open Tuttiphon on the phone, tap “Turn on for this device” and allow notifications.') },
      { title: t('Done'), text: t('Then news from your favorite bands, what is new for you each Monday and your monthly recap come to your phone. If you prefer the ntfy app, open “Or via the ntfy app” below and enter a topic.') },
    ],
  },
  {
    id: 'statistik', icon: 'chart', who: 'user', href: '#/einstellungen/konto',
    title: t('Turn on statistics and learning'),
    short: [t('Open settings'), t('Turn on “Statistics & stars”'), t('From then on Tuttiphon learns along')],
    keys: t('password recap week year played learn stars'),
    steps: () => [
      { go: '#/einstellungen/konto', sel: ['[data-guide=statistik]'], title: t('Statistics & stars'), text: t('Turn it on once with your Navidrome password. Then Tuttiphon sees what you listen to: for statistics, recap, your mixes and matching suggestions.') },
      { go: '#/statistik', title: t('Your statistics'), text: t('Most played bands, songs and albums. At the top you switch between Overall, This week, 30 days and the year.') },
    ],
  },
])

/** Guides for the signed-in role */
export const guidesFor = (admin) => GUIDES.filter((g) => (!g.who || g.who === (admin ? 'admin' : 'user')) && (!g.show || g.show(admin)))
export const guideById = (id) => GUIDES.find((g) => g.id === id)
/** Steps of a guide for the current account */
export const guideSteps = (g) => g.steps(context())
/** Where “Jump right in” leads for the signed-in role */
export const guideHref = (g) => (typeof g.href === 'function' ? g.href(isAdmin()) : g.href)
