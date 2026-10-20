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
  <p>{@html t('When you open Tuttiphon, you land on <a class="link" href="#/">For you</a>. From top to bottom:')}</p>
  <Bullets>
    <li>{@html t('<b>Your mixes</b> – playlists that renew themselves daily, weekly or monthly. Under Discover there’s also a mix with your sound: every day songs that match your taste.')}</li>
    <li>{@render rich(t('<b>Discovered for you</b> – ready-made ideas that match what you listen to. <Ui icon="plus" primary>Create</Ui> adds them, <Ui icon="x">✕</Ui> hides them.'))}</li>
    <li>{@html t('<b>Your week</b> – what you listened to most in the last 7 days.')}</li>
    <li>{@html t('<b>Your playlists</b> and <b>Shared by the family</b> – what belongs to you and what others have shared with everyone.')}</li>
    <li>{@html t('<b>New in your library</b> – the latest albums added. Tap one to see the band.')}</li>
  </Bullets>
  <p>{@render rich(t('On your phone, the navigation is at the bottom. Under <Ui icon="more">More</Ui> you’ll find New playlist, Statistics, Profile, Settings and Help.'))}</p>
{/snippet}

{#snippet personen()}
  <p>{@html t('<a class="link" href="#/profil">My profile</a> shows what Tuttiphon knows about your taste. All suggestions and mixes are based on it:')}</p>
  <Bullets>
    <li>{@render rich(t('<b>From your listening</b> – Tuttiphon learns which music worlds and bands you like from what you play in Symfonium, mark as a favorite and rate yourself. <Ui icon="plus">Remember</Ui> or <Ui icon="plus">Add all</Ui> turns it into a favorite.'))}</li>
    <li>{@html t('<b>Favorite music worlds</b> – you get playlist ideas for these.')}</li>
    <li>{@html t('<b>Favorite bands</b> – come up more often in your mixes.')}</li>
    <li>{@html t('<b>Favorite vibes</b> – kinds of music and decades you like, such as Rock & Punk or 80s – you get playlist ideas for these too.')}</li>
    <li>{@html t('<b>Dislikes</b> – bands or genres that <b>never</b> end up in your playlists.')}</li>
    <li>{@html t('<b>Who can see your playlists?</b> – “Only me” or “The whole family”. Either way, only you can change them.')}</li>
    <li>{@html t('<b>Prefix</b> – goes in front of every playlist name, such as “Mia · ”, so you spot your playlists in Symfonium right away.')}</li>
    <li>{@html t('<b>Kid-safe mode</b> – songs with explicit lyrics stay out of all your playlists and mixes. Tuttiphon detects them from the lyrics.')}</li>
    <li>{@html t('<b>To your phone</b> – tap “Turn on for this device” on your phone to get news from your favorite bands and your monthly recap as notifications. If you’d rather use the ntfy app, enter a topic under “Or via the ntfy app”. This is available if the administrator has turned on notifications.')}</li>
  </Bullets>
  <p>{t('Changes apply right away – your playlists adjust by themselves. The more you listen, the better Tuttiphon knows your taste, even without you entering anything.')}</p>
{/snippet}

{#snippet entdecken()}
  <p>{@html t('<a class="link" href="#/entdecken">Discover</a> has ready-made playlists for you – matching your taste and the season. “From listening” or “Played often” on a suggestion shows that it comes from your listening.')}</p>
  <Steps>
    <li><span>{@render rich(t('<Ui icon="plus" primary>Create</Ui> – the playlist is there right away and reaches Navidrome in a few seconds.'))}</span></li>
    <li><span>{@render rich(t('<Ui>Customize</Ui> – change the name, type or selection first.'))}</span></li>
    <li><span>{@render rich(t('<Ui icon="x">✕</Ui> – not interested: the suggestion disappears for half a year. At the bottom of the page you can bring hidden ones back at any time.'))}</span></li>
  </Steps>
  <p>{t('A few suggestions are put together entirely from your listening:')}</p>
  <Bullets>
    <li>{@render rich(t('<b>New from your favorite bands</b> – what has been added in the last two months by the bands you like or listen to most. Newest first. On “For you”, such albums carry the badge <Ui icon="heart">Favorite band</Ui>.'))}</li>
    <li>{@html t('<b>Your October</b> – your most played songs of the last month. On the first of the month it turns into the new month; it always stays one playlist.')}</li>
    <li>{@html t('<b>Discovered for you</b> – every Monday 30 songs from the library that you have never played, picked to fit your taste. With more than 90 % of a typical library never played, there is a lot to find.')}</li>
    <li>{@html t('<b>Album of the week</b> – every Monday one whole album you have never played, by a favorite band or in your sound, to listen to from start to finish.')}</li>
    <li>{@html t('<b>Good night</b> – half an hour every evening that gets calmer and calmer and fades out, ideally without vocals.')}</li>
    <li>{@html t('<b>Good morning</b> – comes up when you often listen in the morning: as long as your usual morning round, starts calm, gets livelier and sounds like what you play in the morning.')}</li>
    <li>{@html t('<b>Car ride</b> – an hour every day for the road that the whole family likes, with children’s songs and no songs to fall asleep to.')}</li>
    <li>{@html t('<b>What everyone likes</b> – a mix of what everyone in the family enjoys. Good for car rides.')}</li>
  </Bullets>
  <p>{t('On “Discover” these come first; further ideas such as music world × vibe are behind “more ideas”.')}</p>
  <p>{t('At the very bottom, “You might also like” shows bands that are similar to your favorites but not in your library yet – to have a listen. If you like something, let the administrator know.')}</p>
{/snippet}

{#snippet suche()}
  <p>{t('The search field at the top finds bands, songs, playlists and music worlds – and understands moods:')}</p>
  <Bullets>
    <li>{@html t('<b>“calm kids’ songs”</b>, <b>“Christmas kids”</b> or <b>“medieval party”</b> – if something matches, <b>Create as mix</b> appears at the very top. A tap shows the mix with a preview in the assistant; only “Create playlist” creates it.')}</li>
    <li>{@html t('<b>“to fall asleep”</b>, <b>“happy”</b> or <b>“no vocals”</b> – shows how many songs sound like that and opens a new playlist from them.')}</li>
    <li>{@html t('<b>Sounds like</b> – styles Tuttiphon has recognized from the sound, with the matching bands.')}</li>
    <li>{@html t('<b>“piano”</b>, <b>“calm piano music”</b> or <b>“film music”</b> – finds songs by the instruments and themes Tuttiphon has heard in the sound.')}</li>
    <li>{@html t('<b>In the lyrics</b> – you only know one line? Type it in, such as “hands up in the air”. Tuttiphon finds the song by its lyrics.')}</li>
  </Bullets>
  <p>{@html t('On a computer, press the <b>/</b> key to jump straight into the search field.')}</p>
{/snippet}

{#snippet neu()}
  <p>{@html t('With <a class="link" href="#/neu">New playlist</a> you put one together yourself – in three short steps:')}</p>
  <Steps>
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
    </CompareCard>
  </div>
  <p>{t('Rule of thumb: the mix for on the go and for children’s and family music, the smart playlist for browsing at home.')}</p>
{/snippet}

{#snippet playlists()}
  <p>{@html t('<a class="link" href="#/playlists">My playlists</a> lists all your playlists. Tap one to open it: preview, which bands are in it and how it is made. Tapping a song plays it right here, “…” shows the lyrics and “More like this”. At the top you’ll find:')}</p>
  <Bullets>
    <li>{@render rich(t('<Ui icon="edit">Edit</Ui> – change music, name and type; Symfonium keeps the playlist.'))}</li>
    <li>{@render rich(t('<Ui icon="dice">Reshuffle</Ui> – mixes only: a different selection right away.'))}</li>
  </Bullets>
  <p>{@render rich(t('Everything else is in the <Ui icon="more"></Ui> menu next to it:'))}</p>
  <Bullets>
    <li>{@render rich(t('<Ui icon="image">Cover</Ui> – a picture from band photos and album covers, or a photo of your own.'))}</li>
    <li>{@render rich(t('<Ui icon="pause">Pause playlist</Ui> – disappears from Navidrome but stays saved here.'))}</li>
    <li>{@render rich(t('<Ui icon="pin">Keep this mix</Ui> – save the current selection as a fixed playlist that never changes again. For a smart playlist it is called <Ui icon="pin">Save as fixed playlist</Ui>.'))}</li>
    <li>{@render rich(t('<Ui icon="copy">Duplicate</Ui> – a copy of the playlist that you adjust first and then create.'))}</li>
    <li>{@render rich(t('<Ui icon="external">Open in Navidrome</Ui> – opens the playlist on Navidrome’s web page.'))}</li>
    <li>{@render rich(t('<Ui icon="trash">Move to trash</Ui> – it can be restored from there for 30 days, after that it is deleted automatically. Under “My playlists”, <Ui icon="trash">Empty trash</Ui> empties it all at once.'))}</li>
  </Bullets>
  <p>{@html t('<b>Seasonal playlists</b> such as Christmas are only in Symfonium during their season and come back by themselves when it starts – until then the playlist shows “resting until its season”. Playlists nobody has listened to in three months show up under “Next steps”.')}</p>
  <p>{@render rich(t('<b>Shared playlists:</b> you can view playlists that others have shared with everyone and listen to them in Symfonium. With <Ui icon="copy">Copy for me</Ui> you get your own version that you can adjust.'))}</p>
  <p>{@render rich(t('Almost everything can be taken back right away with <Ui icon="undo">Undo</Ui> in the message at the bottom.'))}</p>
{/snippet}

{#snippet symfonium()}
  <p>{@html t('Everything you create here, Tuttiphon writes to <b>your Navidrome account</b>. Symfonium shows it under “Playlists” – after the next sync. If you don’t want to wait: refresh the media source in Symfonium.')}</p>
  <Bullets>
    <li>{@html t('<b>Offline:</b> download a mix in Symfonium once – when it renews itself, Symfonium downloads the new songs by itself.')}</li>
    <li>{@html t('<b>Private or family:</b> only your account sees private playlists. Everyone sees family playlists.')}</li>
    <li>{@html t('<b>Listening counts:</b> Tuttiphon uses what you listen to in Symfonium for your statistics, your taste and your mixes. Symfonium reports this to the server by itself.')}</li>
    <li>{@html t('<b>1 star:</b> rate a song you no longer want to hear with 1 star in Symfonium – then it no longer goes into your mixes.')}</li>
  </Bullets>
{/snippet}

{#snippet welten()}
  <p>{@render rich(t('A <b>music world</b> groups similar bands, such as “Medieval” with Saltatio Mortis, In Extremo and Feuerschwanz. Tuttiphon detects them itself from your library – such as 80s hits, Eurodance or German rap. Under <a class="link" href="#/welten">Music worlds</a>, the worlds you listen to are at the very front, with the badge <Ui icon="headphones">you listen to it often</Ui>.'))}</p>
  <Bullets>
    <li>{@html t('<b>Your favorites here</b> – which bands of this world you listen to most.')}</li>
    <li>{@render rich(t('<Ui icon="dice">Daily Mix</Ui> – a mix from this world with one tap, new every day.'))}</li>
    <li>{@render rich(t('<Ui icon="heart">Like</Ui> – saves the world as a favorite world in your profile.'))}</li>
    <li>{@render rich(t('<b>Tap a band</b> – albums, similar bands, “Favorite” or “never” and <Ui icon="radio">Start radio</Ui>: a mix with this band and similar ones, new every week.'))}</li>
  </Bullets>
  <p>{t('If a band is missing or in the wrong world, let the administrator know – they look after the music worlds for everyone.')}</p>
{/snippet}

{#snippet statistik()}
  <p>{@html t('<a class="link" href="#/statistik">My statistics</a> shows your most played bands, songs and albums, your listening time – and <b>forgotten favorites</b>: favorites that haven’t played in a long time. You get them as a playlist with one tap.')}</p>
  <p>{@render rich(t('Switch at the top to <a class="link" href="#/statistik/woche">This week</a>, <a class="link" href="#/statistik/monat">30 days</a> or <a class="link" href="#/statistik/jahr">the year</a>. With <Ui icon="pin">Keep as playlist</Ui> the recap becomes a fixed playlist that never changes again.'))}</p>
  <p>{@html t('<b>Your month:</b> under Discover there’s a playlist with your most played songs of the last month. It switches by itself on the first of the month – there is only ever one.')}</p>
  <p>{@html t('For this, Tuttiphon needs your Navidrome password once – leave “Turn on statistics & stars” checked when you sign in, or do it later under <a class="link" href="#/einstellungen/konto">Settings → My account</a>. The recap grows from the day Tuttiphon first starts counting.')}</p>
{/snippet}

{#snippet konten()}
  <p>{@html t('You sign in with your <b>Navidrome account</b> – with the same name and password as in Symfonium. You stay signed in for 90 days.')}</p>
  <Bullets>
    <li>{@html t('<b>Change password:</b> in Navidrome, click your name at the top right → Profile. Then sign out and sign in again with “Turn on statistics & stars” checked – or under <a class="link" href="#/einstellungen/konto">My account</a> tap “Turn off” and turn it on again with the new password. The card there says when the stored password no longer works.')}</li>
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
