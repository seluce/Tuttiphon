<!--
  Help for users: simple guides addressed as "you", only about what they can do themselves.
  USER_TOPICS provides id (anchor #h-<id>, #/hilfe/<id>), icon, title, content (snippet) and matching
  "Show me" guides (guides, lib/guides.js) for Help.svelte and the help window behind the (?).
  Interface buttons appear as <Ui> in the text – so they are recognizable on every device.
-->
<script module>
  import Steps from './Steps.svelte'
  import Bullets from './Bullets.svelte'
  import CompareCard from './CompareCard.svelte'
  import Ui from './Ui.svelte'
  import { t, translated } from '../../lib/i18n.svelte.js'
  import { S, creatablePersons, familyPerson } from '../../lib/state.svelte.js'

  export const USER_TOPICS = translated(() => [
    { id: 'start', icon: 'home', title: t('“For you” – your home page'), body: start, guides: ['mix', 'geschmack'] },
    { id: 'personen', icon: 'user', title: t('Your profile & taste'), body: personen, guides: ['geschmack', 'nie', 'kinderschutz', 'push'] },
    { id: 'entdecken', icon: 'compass', title: t('Accepting suggestions'), body: entdecken, guides: ['mix', 'geschmack'] },
    { id: 'suche', icon: 'search', title: t('Search & moods'), body: suche, guides: ['suche'] },
    { id: 'neu', icon: 'plus', title: t('Build your own playlist'), body: neu, guides: ['playlist'] },   // i18n-ignore: topic id
    { id: 'mix', icon: 'dice', title: t('Playlist or mix?'), body: mix, guides: ['mix'] },
    { id: 'playlists', icon: 'playlists', title: t('Your playlists'), body: playlists, guides: ['aendern'] },
    { id: 'symfonium', icon: 'smartphone', title: t('Listening in Symfonium'), body: symfonium, guides: ['mix', 'nie'] },
    { id: 'welten', icon: 'globe', title: t('Music worlds & bands'), body: welten, guides: ['playlist'] },
    { id: 'statistik', icon: 'chart', title: t('Your statistics & your month'), body: statistik, guides: ['statistik'] },
    { id: 'konten', icon: 'key', title: t('Signing in & your account'), body: konten, guides: ['statistik'] },
    { id: 'allgemein', icon: 'palette', title: t('Language & theme'), body: allgemein },
    { id: 'app', icon: 'smartphone', title: t('As an app on your phone'), body: app },
  ])

  // A help text is one translated string. Interface buttons inside it are written as
  // <Ui icon="…" primary>Label</Ui> and drawn by the Ui component; everything around them is fixed HTML.
  const UI_TAG = /<Ui(?: icon="([\w-]+)")?( primary)?>(.*?)<\/Ui>/g
  function pieces(text) {
    const out = []
    let last = 0
    for (const m of text.matchAll(UI_TAG)) {
      out.push({ html: text.slice(last, m.index) })
      out.push({ icon: m[1] ?? '', primary: !!m[2], label: m[3] })
      last = m.index + m[0].length
    }
    out.push({ html: text.slice(last) })
    return out
  }
</script>

{#snippet rich(text)}{#each pieces(text) as p}{#if p.label != null}<Ui icon={p.icon} primary={p.primary}>{p.label}</Ui>{:else}{@html p.html}{/if}{/each}{/snippet}

{#snippet start()}
  <p>{@html t('When you open Tuttiphon, you land on <a class="link" href="#/">For you</a>:')}</p>
  <Bullets>
    <li>{@html t('<b>Your mixes</b> – playlists that renew themselves daily, weekly or monthly.')}</li>
    <li>{@render rich(t('<b>Discovered for you</b> – ideas that match what you listen to. <Ui icon="plus" primary>Create</Ui> adds one, <Ui icon="x">✕</Ui> hides it.'))}</li>
    <li>{@html t('<b>Your week</b>, <b>your playlists</b>, the family playlists and the latest albums.')}</li>
  </Bullets>
  <p>{@render rich(t('On your phone, <Ui icon="more">More</Ui> at the bottom leads to all other pages.'))}</p>
{/snippet}

{#snippet personen()}
  <p>{@html t('Under <a class="link" href="#/profil">My profile</a> you see what Tuttiphon knows about your taste. Your mixes and suggestions build on it.')}</p>
  <Bullets>
    <li>{@render rich(t('<b>From your listening:</b> what you play in Symfonium, mark as a favorite or rate, Tuttiphon learns by itself. <Ui icon="plus">Remember</Ui> turns it into a favorite.'))}</li>
    <li>{@html t('<b>Favorite music worlds, bands and vibes:</b> come up more often in your mixes, and you get matching playlist ideas.')}</li>
    <li>{@html t('<b>Dislikes:</b> bands or genres that <b>never</b> end up in your playlists.')}</li>
    <li>{@html t('<b>Not part of your taste:</b> music that plays on your account for someone else, such as children’s music.')}</li>
    <li>{@html t('<b>Kid-safe mode:</b> songs with explicit lyrics stay out of all your playlists.')}</li>
    <li>{@html t('<b>To your phone:</b> “Turn on for this device” – then news from your favorite bands, what is new for you on Mondays and your monthly recap come as notifications.')}</li>
  </Bullets>
  <p>{t('Changes apply right away.')}</p>
{/snippet}

{#snippet entdecken()}
  <p>{@html t('<a class="link" href="#/entdecken">Discover</a> has ready-made playlists for you – matching your taste and the season.')}</p>
  <Steps>
    <li><span>{@render rich(t('<Ui icon="plus" primary>Create</Ui> – the playlist is there right away.'))}</span></li>
    <li><span>{@render rich(t('<Ui>Customize</Ui> – change the name, type or selection first.'))}</span></li>
    <li><span>{@render rich(t('<Ui icon="x">✕</Ui> – hides the suggestion for half a year; you can bring it back at the bottom of the page.'))}</span></li>
  </Steps>
  <p>{t('Some suggestions come entirely from your listening:')}</p>
  <Bullets>
    <li>{@html t('<b>New from your favorite bands</b> – what they released in the last two months.')}</li>
    <li>{@html t('<b>Your October</b> – your most played songs of the last month.')}</li>
    <li>{@html t('<b>Discovered for you</b> – every Monday 30 songs you have never played, picked to fit your taste.')}</li>
    <li>{@html t('<b>Album of the week</b> – every Monday a whole album you don’t know yet.')}</li>
    <li>{@html t('<b>Next episode</b> – for every audio play series you listen to, the episode that comes next.')}</li>
    <li>{@html t('<b>Good night</b> and <b>Good morning</b> – calming down in the evening, waking up gently in the morning.')}</li>
    <li>{@html t('<b>Car ride</b> and <b>What everyone likes</b> – for the family: music everyone enjoys.')}</li>
  </Bullets>
  <p>{t('At the very bottom, “You might also like” shows bands that are not in the library yet – if you like one, let the administrator know.')}</p>
{/snippet}

{#snippet suche()}
  <p>{t('The search field at the top finds bands, songs, playlists and music worlds – and understands moods:')}</p>
  <Bullets>
    <li>{@html t('<b>“calm kids’ songs”</b> or <b>“medieval party”</b> – if something matches, <b>Create as mix</b> appears at the top.')}</li>
    <li>{@html t('<b>“to fall asleep”</b>, <b>“no vocals”</b> or <b>“calm piano music”</b> – finds songs by their sound.')}</li>
    <li>{@html t('<b>A line of the lyrics</b>, such as “hands up in the air” – finds the song by its words.')}</li>
  </Bullets>
  <p>{@html t('On a computer, press the <b>/</b> key to jump straight into the search field.')}</p>
{/snippet}

{#snippet neu()}
  {#if creatablePersons().length > 1}
    <p>{@html t('With <a class="link" href="#/neu">New playlist</a> you put one together yourself – in four short steps:')}</p>
  {:else}
    <p>{@html t('With <a class="link" href="#/neu">New playlist</a> you put one together yourself – in three short steps:')}</p>
  {/if}
  <Steps>
    {#if creatablePersons().length > 1}
      <li><span>{@html t('<b>For whom?</b> – just for you, or for the whole family: everyone sees family playlists in Navidrome and Symfonium.')}</span></li>
    {/if}
    <li><span>{@html t('<b>Music world</b> – which music? For example “Kids’ rock”. You can pick several; “All” takes the whole library.')}</span></li>
    <li><span>{@html t('<b>Vibe</b> – which mood or occasion? Such as “Party”, “Calm” or “Christmas”. The number shows how many songs match.')}</span></li>
    <li><span>{@html t('<b>Finishing touches</b> – name, <b>playlist or mix</b>, only the hits or everything. Right next to it you see which songs would be in it.')}</span></li>
  </Steps>
  <p>{@render rich(t('After <Ui icon="check" primary>Create playlist</Ui> it is in Navidrome within a few seconds, and in Symfonium after the next sync.'))}</p>
{/snippet}

{#snippet mix()}
  <div class="grid grid-cols-2 gap-3.5 max-mobile:grid-cols-1">
    <CompareCard icon="shuffle" title={t('Smart playlist')}>
      <li>{@html t('Navidrome reshuffles it <b>every time you open it</b> from all matching songs.')}</li>
      <li>{t('New songs are included right away.')}</li>
      <li>{t('Good for streaming – not suited for downloading, because it changes all the time.')}</li>
    </CompareCard>
    <CompareCard icon="dice" title={t('Mix')}>
      <li>{@html t('Puts itself together anew <b>daily, weekly or monthly</b> and stays the same in between.')}</li>
      <li>{t('Only a few songs per band, never the same band twice in a row.')}</li>
      <li>{@html t('<b>Ideal for downloading:</b> save it offline in Symfonium once – new songs arrive by themselves at the next sync.')}</li>
      <li>{@render rich(t('Don’t like the selection? <Ui icon="dice">Reshuffle</Ui> on the playlist page.'))}</li>
      <li>{@html t('<b>Learns as you go:</b> what you skip in a mix comes up less often. Songs you rate with 1 star yourself no longer go into your mixes.')}</li>
      <li>{@html t('<b>The family’s mixes too:</b> if you play one on your own account, Tuttiphon recognizes it by its order – then the family learns from it, not your own taste.')}</li>
    </CompareCard>
  </div>
  <p>{t('Rule of thumb: the mix for on the go and for children’s and family music, the smart playlist for browsing at home.')}</p>
{/snippet}

{#snippet playlists()}
  <p>{@html t('<a class="link" href="#/playlists">My playlists</a> lists all your playlists. Tap one to see its songs and bands – a tap on a song plays it.')}</p>
  <Bullets>
    <li>{@render rich(t('<Ui icon="edit">Edit</Ui> – change music, name and type; Symfonium keeps the playlist.'))}</li>
    <li>{@render rich(t('<Ui icon="dice">Reshuffle</Ui> – mixes only: a different selection right away.'))}</li>
  </Bullets>
  <p>{@render rich(t('Everything else is in the <Ui icon="more"></Ui> menu next to it:'))}</p>
  <Bullets>
    <li>{@render rich(t('<Ui icon="image">Cover</Ui> – a picture from band photos and album covers, or a photo of your own.'))}</li>
    <li>{@render rich(t('<Ui icon="pause">Pause playlist</Ui> – disappears from Navidrome but stays saved here.'))}</li>
    <li>{@render rich(t('<Ui icon="pin">Keep this mix</Ui> – the current selection as a fixed playlist that never changes.'))}</li>
    <li>{@render rich(t('<Ui icon="copy">Duplicate</Ui> – a copy of the playlist that you adjust first and then create.'))}</li>
    <li>{@render rich(t('<Ui icon="trash">Move to trash</Ui> – can be restored for 30 days.'))}</li>
  </Bullets>
  <p>{@html t('<b>Seasonal playlists</b> such as Christmas are only in Symfonium during their season and come back by themselves.')}</p>
  <p>{@render rich(t('<b>Your playlists</b> are only yours, <b>family playlists</b> are for everyone. If you may not change one, <Ui icon="copy">Copy for me</Ui> gives you your own version.'))}</p>
  <p>{@render rich(t('Almost everything can be taken back right away with <Ui icon="undo">Undo</Ui> in the message at the bottom.'))}</p>
{/snippet}

{#snippet symfonium()}
  <p>{t('Everything you create here appears in Symfonium after the next sync – or right away if you refresh the media source there.')}</p>
  <Bullets>
    <li>{@html t('<b>Offline:</b> download a mix in Symfonium once – when it renews itself, Symfonium downloads the new songs by itself.')}</li>
    <li>{@html t('<b>Listening counts:</b> what you play in Symfonium shapes your statistics, taste and mixes.')}</li>
    <li>{@html t('<b>1 star:</b> rate a song you no longer want to hear with 1 star in Symfonium – then it no longer goes into your mixes.')}</li>
    {#if familyPerson()}
      <li>{@html t('<b>Shared devices</b> such as the car or a kitchen tablet can use the family account in Symfonium – the administrator sets it up.')}</li>
    {/if}
    {#if S.status?.plugin}
      <li>{@html t('<b>Radio and smart queue by sound:</b> in Symfonium, turn on “Use similar tracks for Radio Mix” for the server (Manage media providers) and choose “Sonic Analysis” for the smart queue in the player. The next songs then come from Tuttiphon – picked for you and with variety between bands.')}</li>
      <li>{@html t('<b>The queue learns along:</b> skip twice and it turns to another sound at once. Every few songs one you have never played comes in – how often, you set in <a class="link" href="#/profil">your profile</a>.')}</li>
    {/if}
  </Bullets>
{/snippet}

{#snippet welten()}
  <p>{@html t('A <b>music world</b> groups similar bands, such as “Medieval” with Saltatio Mortis and In Extremo. Under <a class="link" href="#/welten">Music worlds</a>, the ones you listen to come first.')}</p>
  <Bullets>
    <li>{@render rich(t('<Ui icon="dice">Daily Mix</Ui> – a mix from this world with one tap, new every day.'))}</li>
    <li>{@render rich(t('<Ui icon="heart">Like</Ui> – saves the world as a favorite world in your profile.'))}</li>
    <li>{@render rich(t('<b>Tap a band</b> – albums, similar bands and <Ui icon="radio">Start radio</Ui>.'))}</li>
  </Bullets>
  <p>{t('If a band is missing or in the wrong world, let the administrator know – they look after the music worlds for everyone.')}</p>
{/snippet}

{#snippet statistik()}
  <p>{@html t('<a class="link" href="#/statistik">My statistics</a> shows your most played bands, songs and albums – and <b>forgotten favorites</b> you haven’t heard in a long time, as a playlist with one tap.')}</p>
  <p>{@render rich(t('At the top you switch between week, 30 days and year; <Ui icon="pin">Keep as playlist</Ui> saves the recap as a fixed playlist.'))}</p>
  <p>{@render rich(t('<b>Your year as a story:</b> under year, <Ui icon="play">Watch as a story</Ui> shows it slide by slide – listening time, band of the year, discoveries and when you listen – and shares it as a picture. In December it waits for you on the start page and comes as a notification.'))}</p>
  <p>{@html t('For this, Tuttiphon needs your Navidrome password once – leave “Turn on statistics & stars” checked when you sign in, or turn it on under <a class="link" href="#/einstellungen/konto">Settings → My account</a>.')}</p>
{/snippet}

{#snippet konten()}
  <p>{@html t('You sign in with your <b>Navidrome account</b> – with the same name and password as in Symfonium. You stay signed in for 90 days.')}</p>
  <Bullets>
    <li>{@html t('<b>Changed your password in Navidrome?</b> Under <a class="link" href="#/einstellungen/konto">My account</a>, turn statistics off and on again with the new one.')}</li>
    <li>{@html t('<b>Sign out:</b> tap your name at the bottom left → “Sign out”. On your phone, your name is at the top right.')}</li>
    <li>{@render rich(t('<b>Tour again:</b> <a class="link" href="#/einstellungen/konto">Settings → My account</a> → <Ui icon="play">Start tour</Ui>.'))}</li>
  </Bullets>
{/snippet}

{#snippet allgemein()}
  <p>{@html t('Under <a class="link" href="#/einstellungen/allgemein">Settings → General</a> you choose the language and light or dark. “Automatic” and “System” follow your phone or computer. The choice applies to this device.')}</p>
{/snippet}

{#snippet app()}
  <p>{t('You can put Tuttiphon on your home screen like an app – with its own icon.')}</p>
  <Bullets>
    <li>{@html t('<b>iPhone:</b> in Safari, <b>Share → Add to Home Screen</b>.')}</li>
    <li>{@html t('<b>Android:</b> in the Chrome menu, <b>⋮ → Install app</b> or “Add to Home screen”.')}</li>
  </Bullets>
{/snippet}
