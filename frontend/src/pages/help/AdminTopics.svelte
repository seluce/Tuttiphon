<!--
  Help for administrators: all topics. Each topic is a snippet; ADMIN_TOPICS provides the id (anchor #h-<id>,
  #/hilfe/<id>), icon, title, body and matching "show me" guides (guides, lib/guides.js) for Help.svelte and the help
  sheet behind the (?). Interface buttons appear as <Ui> in the text – inside a sentence through withUi.
-->
<script module>
  import Steps from './Steps.svelte'
  import Bullets from './Bullets.svelte'
  import CompareCard from './CompareCard.svelte'
  import Ui from './Ui.svelte'
  import { t, translated } from '../../lib/i18n.svelte.js'

  export const ADMIN_TOPICS = translated(() => [
    { id: 'start', icon: 'home', title: t('The home page'), body: start, guides: ['aktualisieren'] },
    { id: 'neu', icon: 'plus', title: t('Create a new playlist'), body: neu, guides: ['playlist'] },  // i18n-ignore: topic id
    { id: 'mix', icon: 'dice', title: t('Smart playlist or mix?'), body: mix, guides: ['mix'] },
    { id: 'playlists', icon: 'playlists', title: t('Change, pause, delete playlists'), body: playlists, guides: ['aendern'] },
    { id: 'cover', icon: 'image', title: t('Design covers'), body: cover, guides: ['aendern'] },
    { id: 'entdecken', icon: 'compass', title: t('Suggestions & Discover'), body: entdecken, guides: ['mix', 'geschmack'] },
    { id: 'suche', icon: 'search', title: t('Search & moods'), body: suche, guides: ['suche'] },
    { id: 'welten', icon: 'globe', title: t('Maintain music worlds'), body: welten, guides: ['welt'] },
    { id: 'richtungen', icon: 'sliders', title: t('Vibes'), body: richtungen },
    { id: 'personen', icon: 'users', title: t('People & preferences'), body: personen, guides: ['geschmack', 'nie', 'kinderschutz'] },
    { id: 'statistik', icon: 'chart', title: t('Statistics'), body: statistik },
    { id: 'aktualisieren', icon: 'star', title: t('Deezer stars'), body: aktualisieren, guides: ['aktualisieren'] },
    { id: 'lyrics', icon: 'music', title: t('Lyrics, lyrics search & kid-safe mode'), body: lyrics, guides: ['kinderschutz'] },
    { id: 'intel', icon: 'brain', title: t('Intelligence: sound, radio, classification'), body: intel },
    { id: 'watch', icon: 'folder-search', title: t('Process new music automatically'), body: watch, guides: ['aktualisieren'] },
    { id: 'docker', icon: 'server', title: t('Storage locations & Docker'), body: docker },
    { id: 'opus', icon: 'disc', title: t('Conversion: FLAC → Opus or AAC'), body: opus },
    { id: 'bibliothek', icon: 'eraser', title: t('Check library'), body: bibliothek },
    { id: 'benachrichtigungen', icon: 'bell', title: t('Notifications on your phone'), body: benachrichtigungen, guides: ['push'] },
    { id: 'einstellungen', icon: 'settings', title: t('Settings'), body: einstellungen },
    { id: 'einrichtung', icon: 'wand', title: t('Setup assistant'), body: einrichtung },
    { id: 'allgemein', icon: 'palette', title: t('Language & theme'), body: allgemein },
    { id: 'sicherung', icon: 'archive', title: t('Backup'), body: sicherung },
    { id: 'konten', icon: 'users', title: t('Users & sign-in'), body: konten, guides: ['familie'] },
    { id: 'app', icon: 'plus', title: t('As an app on your phone'), body: app },
    { id: 'alt', icon: 'folder', title: t('Old & handmade playlists'), body: alt },
  ])

  // Splits a help text at {name} placeholders: even parts are HTML, odd parts name an interface button.
  const parts = (text) => text.split(/\{(\w+)\}/)
</script>

<!-- A help text with interface buttons inside: {name} in the text becomes the button ui[name] = [icon, label, primary],
     so a translation can put the button anywhere in the sentence. -->
{#snippet withUi(text, ui)}{#each parts(text) as part, i (i)}{#if i % 2}<Ui icon={ui[part][0]} primary={ui[part][2]}>{ui[part][1]}</Ui>{:else}{@html part}{/if}{/each}{/snippet}

{#snippet start()}
  <p>{@html t('The home page shows at a glance what’s going on: at the top the big <b>“Update everything”</b> button, below it <b>“Today for you”</b> with your mixes, <b>“To review”</b>, <b>“Played this week”</b>, <b>“New in your library”</b>, <b>“Family playlists”</b>, the Deezer status and the history. “To review” lists, for example, missing passwords, new bands or playlists for which Navidrome shows a different number of songs than expected.')}</p>
  <p>{@html t('You choose which sections appear and in which order under <a class="link" href="#/einstellungen/start">Settings → Home page</a>. The “Customize start page” link at the very bottom of the home page also leads there.')}</p>
  <p>{@html t('One click on “Update everything” does, in order: convert music → find & clean up lyrics → fetch missing covers → understand the music with sound, AI & Last.fm → write playlists → have Navidrome scan and recount → rate new songs on Deezer. You set which steps are included under <a class="link" href="#/einstellungen/ablaeufe">Settings → Automation</a>. “Apply playlists only” does just playlists + scan. The bar at the bottom shows the progress; the log is under <a class="link" href="#/verlauf">History</a>.')}</p>
{/snippet}

{#snippet neu()}
  <p>{@html t('The easiest way is the assistant under <a class="link" href="#/neu">New playlist</a>. It asks step by step – “For whom?” only when there are several people:')}</p>
  <Steps>
    <li><span>{@html t('<b>For whom?</b> – the person decides which Navidrome account the playlist goes to and whose stars count.')}</span></li>
    <li><span>{@html t('<b>Music world</b> – who’s playing: e.g. “Kids’ rock”, “Medieval” or several together. “All” takes the whole library.')}</span></li>
    <li><span>{@html t('<b>Vibe</b> – what’s on: e.g. “Party”, “Calm”, “Christmas”. The numbers show how many songs fit.')}</span></li>
    <li><span>{@html t('<b>Finishing touches</b> – name, <b>smart playlist or mix</b>, hits only or everything, add or remove single bands. On the right you see right away what comes out.')}</span></li>
  </Steps>
  <p>{t('After “Create playlist” it shows up in Navidrome automatically within a few seconds, and in Symfonium at the next sync.')}</p>
{/snippet}

{#snippet mix()}
  <div class="grid grid-cols-2 gap-3.5 max-mobile:grid-cols-1">
    <CompareCard icon="shuffle" title={t('Smart playlist')}>
      <li>{@html t('<b>Dynamic, by rules:</b> Navidrome reshuffles all matching songs <b>every time it’s loaded</b>.')}</li>
      <li>{t('New songs are included right away.')}</li>
      <li>{t('The same band can come up several times in a row.')}</li>
      <li>{t('Not suitable for offline downloads in Symfonium – the list changes every time it’s loaded.')}</li>
    </CompareCard>
    <CompareCard icon="dice" title={t('Mix')}>
      <li>{@html t('<b>Fixed, but renews itself:</b> Tuttiphon puts together a new selection <b>daily, weekly or monthly</b> – in between it stays the same.')}</li>
      <li>{@html t('<b>At most 3 songs per band</b>, never the same band twice in a row. The maximum is adjustable or “any”.')}</li>
      <li>{@html t('<b>Ideal for offline:</b> save the playlist offline in Symfonium once – after each renewal, Symfonium downloads the new songs automatically at the next sync.')}</li>
      <li>{t('Choose the blend: balanced, more hits or more lesser-known songs; recently played songs come up less often.')}</li>
      <li>{@render withUi(t('Don’t like today’s selection? {reshuffle} on the playlist page.'), { reshuffle: ['dice', t('Reshuffle')] })}</li>
      <li>{@html t('<b>Learns as you listen:</b> songs skipped in the mix come up less often for a while; songs someone rates 1 star themselves – e.g. in Symfonium – no longer appear in their mixes.')}</li>
    </CompareCard>
  </div>
  <p>{t('Rule of thumb: for streaming and “everything by …” lists, the smart playlist. For kids’ and family music and everything that should go offline onto the phone, the mix – e.g. “Kids · Seasons” as a weekly mix.')}</p>
  <p>{@html t('<b>Special mixes from listening</b> – all under <a class="link" href="#/entdecken">Discover</a>:')}</p>
  <Bullets>
    <li>{@html t('<b>New from your favorite bands</b> – a smart playlist with what was added in the last two months by the bands someone likes or listens to most. Newest first.')}</li>
    <li>{@html t('<b>What everyone likes</b> – a mix for the shared person: the taste of every account with enough listening counts equally; everyone’s dislikes and 1-star songs stay out.')}</li>
    <li>{@html t('<b>Good night</b> – a fixed length instead of a number of songs, about 30 minutes. Gets calmer and calmer and ends without vocals where possible. The length can be set for any mix under “Length”.')}</li>
    <li>{@html t('<b>Good morning</b> – only for accounts that listen in the morning on at least 6 days in 6 weeks: as long as their usual morning round, starts calm, gets livelier and sounds like their mornings. Profiles without a stored password get “Good morning · world” as before. <b>Car ride</b> – an hour every day from the family’s worlds, with kids’ songs, without sleepy songs.')}</li>
    <li>{@html t('<b>Your October</b> and <b>Your year</b> – the most-played songs. Changes on the first of the month; it always stays one playlist.')}</li>
    <li>{@html t('<b>Discovered for you</b> – like Spotify’s Discover Weekly inside your own library: every Monday 30 songs the account has never played, by its taste, at most one per album. For every account with a stored password and enough unheard songs.')}</li>
    <li>{@html t('<b>Album of the week</b> – every Monday one whole album the account has never played (at least 6 songs, one band, no compilation), by its taste, favorite bands first, in album order. It stays the same all week.')}</li>
    <li>{@html t('<b>Core set first:</b> per person, “Discover” shows the formats with a fixed rhythm first – discovered, album of the week, own sound, new from favorite bands, rediscover, your month, good morning and the Daily Mixes of the two most played worlds. Everything else is behind “more ideas”.')}</li>
  </Bullets>
  <p>{@html t('The change happens at the time set under <a class="link" href="#/einstellungen/ablaeufe">Settings → Automation → Daily refresh</a> – every day, on Mondays or on the 1st, depending on the mix. If Tuttiphon isn’t running at that time, it catches up at the next start – in the Docker container on the NAS it always runs.')}</p>
  <p>{@html t('<b>Mixes learn:</b> Tuttiphon recognizes what was skipped from the plays Symfonium reports to Navidrome – so, as with statistics and recap, only for accounts whose password Tuttiphon knows. What it learns takes effect from the next new mix. You can turn it off under <a class="link" href="#/einstellungen/playlists">Settings → Playlists</a> with “Mixes that learn”.')}</p>
{/snippet}

{#snippet playlists()}
  <p>{t('Clicking a playlist opens its page: a preview, which bands are in it and, in plain words, how it is made. Clicking a song plays it in the browser; “…” shows the lyrics and “More like this”. At the top you find the actions:')}</p>
  <Bullets>
    <li>{@render withUi(t('{edit} – everything can be changed; the name and ID in Navidrome stay, Symfonium keeps the playlist.'), { edit: ['edit', t('Edit')] })}</li>
  </Bullets>
  <p>{@render withUi(t('The other actions are in the {more} menu next to it:'), { more: ['more', ''] })}</p>
  <Bullets>
    <li>{@render withUi(t('{pause} – disappears from Navidrome but stays here with all its settings. Simply activate it again later.'), { pause: ['pause', t('Pause playlist')] })}</li>
    <li>{@render withUi(t('{trash} – like pausing, but filed under “Trash”. Only “Delete permanently” removes it from the tool; {empty} under “Playlists” removes all of them at once. After 30 days in the trash this happens on its own.'), { trash: ['trash', t('Move to trash')], empty: ['trash', t('Empty trash')] })}</li>
    <li>{@render withUi(t('{keep} – saves the current selection as a fixed playlist that never changes again, e.g. “Kids’ rock – Oct 2026”. For a smart playlist it is called {fixed}.'), { keep: ['pin', t('Keep this mix')], fixed: ['pin', t('Save as fixed playlist')] })}</li>
    <li>{@render withUi(t('{cover} – your own picture for Navidrome and Symfonium.'), { cover: ['image', t('Cover')] })}</li>
  </Bullets>
  <p>{@render withUi(t('<b>Keeping things tidy:</b> seasonal playlists such as Christmas, Halloween or summer are only in Navidrome and Symfonium during their season – otherwise “resting until its season”; single ones can be shown all year in the edit window, turn this off under <a class="link" href="#/einstellungen/playlists">Settings → Playlists</a>. “To review” reports playlists from which no song has played on any account for three months, mixes of which not a single song played in their last editions (at least 12 days), each with {pause}, and playlists with exactly the same selection. On the page of a mix, “Is it listened to?” shows how much of its last editions was played.'), { pause: ['pause', t('Pause playlist')] })}</p>
  <p>{@html t('Almost everything can be taken back right away with <b>“Undo”</b> in the message at the bottom.')}</p>
{/snippet}

{#snippet cover()}
  <p>{@html t('On the playlist page, tap “…” and then “Cover”. You can choose a <b>mosaic</b> of four album covers, a <b>band photo</b>, a <b>gradient</b> with round band photos or the <b>album cover</b> – each with a preview. Or upload <b>your own picture</b>; large phone photos are scaled down automatically.')}</p>
  <p>{t('Tuttiphon renews designed covers on its own when the playlist changes – for mixes, with every new selection. Your own pictures stay as they are. “Navidrome default” removes the cover again.')}</p>
  <p>{@html t('<b>Formats bring their own cover:</b> discovered, album of the week, good morning, your sound and the other formats get a cover of their own by themselves – the same look every week, so they are easy to spot in Symfonium. A picture set in Navidrome stays; after “Navidrome default” it does not come back.')}</p>
{/snippet}

{#snippet entdecken()}
  <p>{@html t('Under <a class="link" href="#/entdecken">Discover</a> the tool suggests ready-made playlists – matching your preferences, music worlds and existing playlists, mixes included. One click creates them, “Customize” opens them in the editor first, and the ✕ hides a suggestion for half a year. After that it comes back if it still fits.')}</p>
{/snippet}

{#snippet suche()}
  <p>{t('The search field at the top finds bands, songs, playlists, music worlds and people – and understands moods:')}</p>
  <Bullets>
    <li>{@html t('<b>Combined search:</b> “calm kids’ songs”, “Christmas kids” or “party medieval” recognizes music world, mood and vibe and suggests <b>Create as mix</b> at the very top – with the number of matching songs.')}</li>
    <li>{@html t('<b>Mood:</b> “for falling asleep”, “happy” or “without vocals” shows how many songs sound like that according to the sound analysis, and opens the assistant from there.')}</li>
    <li>{@html t('<b>Sounds like:</b> music styles from the AI sound analysis with the matching bands.')}</li>
    <li>{@html t('<b>In the lyrics:</b> one line of the lyrics is enough, such as “hands up in the air” – Tuttiphon searches all lyrics in the library.')}</li>
  </Bullets>
  <p>{@html t('On a computer, the <b>/</b> key jumps straight to the search field.')}</p>
{/snippet}

{#snippet welten()}
  <p>{@html t('A music world groups bands together, e.g. “Medieval” with Saltatio Mortis, In Extremo, Feuerschwanz … <b>Music worlds appear on their own:</b> from genres, Last.fm tags, AI music style, language and decade, Tuttiphon recognizes which worlds your library offers – such as 80s hits, Eurodance & 90s, German rap, Schlager & party or audio dramas – and creates them as soon as there are enough bands or someone listens to them a lot. New bands, e.g. from Lidarr, go into their world on their own.')}</p>
  <Bullets>
    <li>{@render withUi(t('Worlds created by Tuttiphon carry the {auto} badge and are listed under “To review”. Name and icon can be changed.'), { auto: ['sparkles', t('created by Tuttiphon')] })}</li>
    <li>{t('If a world doesn’t fit, just delete it – it won’t come back.')}</li>
    <li>{@render withUi(t('If a world is linked to a scene and was changed by hand, {rebuild} puts it together entirely from the scene again, with its name and icon. Beforehand, Tuttiphon shows which bands drop out and whether playlists get a different name. Bands that become free can get their own music world.'), { rebuild: ['wand', t('Rebuild')] })}</li>
    <li>{@html t('Kids and audio dramas become <b>separate worlds</b>: they are left out of playlists made from “All”.')}</li>
    <li>{@render withUi(t('You create your own worlds with {new}. If one is linked to a scene, matching bands are added there on their own as well.'), { new: ['plus', t('New music world'), true] })}</li>
    <li>{@html t('You can turn this off under <a class="link" href="#/einstellungen/intel">Settings → Intelligence</a>.')}</li>
  </Bullets>
  <Steps>
    <li><span>{@html t('Open a music world under <a class="link" href="#/welten">Music worlds</a>.')}</span></li>
    <li><span>{@html t('Under <b>“Might fit too”</b>, tap similar bands to add them. If a band doesn’t fit, tap <b>×</b> next to it to take it out – <b>↺</b> brings it back in.')}</span></li>
    <li><span>{@render withUi(t('The home page reports new bands in your library that don’t belong to any world yet. {assign} opens the band window, where you choose the world.'), { assign: ['', t('Assign music world …')] })}</span></li>
  </Steps>
  <p>{t('All playlists of this world adjust automatically.')}</p>
{/snippet}

{#snippet richtungen()}
  <p>{@html t('Vibes describe <b>what</b> is playing: a mood such as Party or Calm, an occasion such as Christmas or Good night, a time such as 80s or Newly added, or special cases such as Favorite songs. Seasonal vibes switch on and off automatically – Christmas songs only come from late November to 6 January.')}</p>
  <p>{@html t('Under <a class="link" href="#/richtungen">Vibes</a> you can adjust them and create your own, e.g. “Acoustic covers”. <a class="link" href="#/entdecken">Discover</a> → “All combinations as a table” shows how many songs each combination of music world and vibe gives.')}</p>
{/snippet}

{#snippet personen()}
  <p>{@html t('Each person has a Navidrome account; several people may share one, e.g. “Family”. On top of that come <b>preferences</b>: favorite worlds and favorite bands get matching suggestions, <b>dislikes</b> never appear in their playlists.')}</p>
  <Steps>
    <li><span>{@html t('Under <a class="link" href="#/personen">People</a>, “Add person”.')}</span></li>
    <li><span>{t('Choose the Navidrome account – it must already exist in Navidrome under “Users”.')}</span></li>
    <li><span>{@html t('Enter this account’s password under <a class="link" href="#/einstellungen/navidrome">Settings → Navidrome</a> so stars, favorites and statistics are right – or the person signs in themselves and chooses “Turn on statistics & stars”.')}</span></li>
  </Steps>
  <p>{@render withUi(t('<b>From listening:</b> once the password is stored, the person’s page shows which music worlds, bands and moods Tuttiphon has recognized from plays, favorites and stars they gave themselves – {all} turns them into preferences. Suggestions and mixes use the taste even without adding.'), { all: ['plus', t('Add all')] })}</p>
  <p>{@html t('<b>Not part of the taste:</b> if children’s music plays on a parent’s account, switch it on in their profile under “Not part of … taste”. Then their discoveries, album of the week and mixes follow their own music; the family person on the same account keeps it. “To review” points it out when a lot of it is played.')}</p>
  <p>{@html t('<b>Kid-safe mode:</b> in a person’s profile you can turn on “Leave out songs with explicit lyrics”. This applies to all their playlists and mixes – it leaves out songs detected from the lyrics and songs tagged as explicit in the file; songs found by their lyrics can be allowed under <a class="link" href="#/einstellungen/lyrics">Settings → Lyrics</a>, where the list of detected songs is.')}</p>
  <p>{@html t('<b>To your phone:</b> when notifications are on, each person turns on their devices in their profile and gets news from their favorite bands and the monthly recap, directly through the app. Alternatively, it works through their own ntfy topic.')}</p>
  <p>{@html t('With their own sign-in, everyone maintains their own profile – more under <a class="link" href="#/hilfe/konten">Users & sign-in</a>.')}</p>
{/snippet}

{#snippet statistik()}
  <p>{@html t('<a class="link" href="#/statistik">Statistics</a> shows, per person, the most-played bands, songs and albums, listening time, music worlds and decades – and <b>forgotten favorites</b>: favorites that haven’t played for a long time. One click turns them into a playlist.')}</p>
  <p>{@html t('<b>Keep as playlist:</b> every recap can be saved as a fixed playlist in the person’s account. <b>Your month</b> and <b>Your year</b> are also available as suggestions: a playlist with the most-played songs that changes on the first of the month – it always stays one.')}</p>
  <p>{@html t('<b>Recap:</b> at the top, switch to <a class="link" href="#/statistik/woche">This week</a>, <a class="link" href="#/statistik/monat">30 days</a> or <a class="link" href="#/statistik/jahr">the year</a> – with the history day by day, the top bands and songs, new discoveries and the band of the year.')}</p>
  <p>{t('It is based on the plays Symfonium reports to Navidrome, so leave “Scrobbling” turned on in Symfonium. Every day Tuttiphon notes the counters from Navidrome for each account whose password it knows, so the recap grows from the day Tuttiphon first ran.')}</p>
{/snippet}

{#snippet aktualisieren()}
  <p>{@html t('For “Only the hits” and the right order of top songs in Symfonium, the tool needs stars. It gets them from Deezer: the more popular a song is there, the more stars. Day to day it asks <b>only for new songs</b>, which is quick. A match only counts if band and title fit. If the search finds nothing, Tuttiphon looks the song up precisely by its MusicBrainz ID.')}</p>
  <p>{@html t('Under <a class="link" href="#/einstellungen/deezer">Settings → Deezer stars</a> you decide from which popularity rank there are how many stars – the chart shows right away how your songs are then distributed. <b>“Recalculate stars now”</b> then resets all stars without asking Deezer again.')}</p>
  <Bullets>
    <li>{@html t('<b>Who gets stars?</b> – stars in Navidrome are per account; here you choose the accounts.')}</li>
    <li>{@html t('<b>Retry not found</b> – songs Deezer didn’t know last time.')}</li>
    <li>{@html t('<b>Check everything again</b> – look up all songs on Deezer again. This takes a long time but can be stopped and continued later.')}</li>
    <li>{@html t('<b>Highlight top tracks per band</b> – if many songs of a band share the highest star count, the most popular get one more star. That way “Barbie Girl” comes out on top for Aqua, for example.')}</li>
    <li>{@html t('<b>Refresh every night</b> – in the time window of the night analysis, Tuttiphon rechecks a batch of songs so the stars stay up to date.')}</li>
    <li>{t('Stars given by hand always stay, unless you explicitly allow overwriting them.')}</li>
  </Bullets>
  <p>{@html t('Every run is listed in the <a class="link" href="#/verlauf">history</a> with a full log.')}</p>
{/snippet}

{#snippet lyrics()}
  <p>{@html t('Tuttiphon looks for missing lyrics automatically and puts them next to the songs: synced ones as <code>.lrc</code>, which scroll along in Symfonium, otherwise as <code>.txt</code>. Navidrome reads them at the next scan, and Symfonium shows them during playback.')}</p>
  <Bullets>
    <li>{@html t('<b>Providers:</b> LRCLIB and, if you like, NetEase – in an order you choose. Synced lyrics win.')}</li>
    <li>{@html t('<b>Fast:</b> during “Update everything”, Tuttiphon searches for a few minutes at most, new songs first – the rest follows in the next run. After that, only new songs are left. The search time is adjustable.')}</li>
    <li>{t('Songs without results are only searched again after an adjustable number of days; “text only” is later replaced by synced lyrics as soon as there are any.')}</li>
    <li>{t('If there is a .txt next to a .lrc, Tuttiphon cleans up the duplicate file so Symfonium shows the right lyrics.')}</li>
    <li>{@html t('Everything can be set under <a class="link" href="#/einstellungen/lyrics">Settings → Lyrics</a> – including a dry run.')}</li>
  </Bullets>
  <p>{@html t('<b>Lyrics search & kid-safe mode:</b> Tuttiphon reads all lyrics into a search index – the first time in the background, after that only new ones at each scan. This lets the search find songs by a line of their lyrics, and kid-safe mode detects explicit lyrics with a word list: one strong swear word is enough, milder ones take two. If new explicit lyrics are detected during a scan and someone has kid-safe mode on, Tuttiphon rewrites their playlists right away.')}</p>
{/snippet}

{#snippet intel()}
  <p>{t('All local and free of charge – Tuttiphon “understands” your music in several ways:')}</p>
  <Bullets>
    <li>{@html t('<b>Sound analysis:</b> every song is listened to – from 30 seconds up to the whole song, depending on the depth you set. This yields tempo in BPM, energy, danceability and mood. With that there are sound vibes such as <b>“Falling asleep”</b>, <b>“Running wild”</b>, <b>“Good mood”</b> or <b>“Danceable”</b> – independent of genre tags. “Falling asleep” gets calmer and calmer toward the end. Because Navidrome doesn’t know the sound, sound vibes only exist as mixes.')}</li>
    <li>{@html t('<b>AI sound analysis:</b> pre-trained Essentia models from Universitat Pompeu Fabra also pick out mood, danceability, vocals or instrumental, acoustic or electronic, and the music style. As moods they recognize happy, sad, relaxed, aggressive and party. This makes moods and sound vibes more accurate, adds the moods <b>“without vocals”</b> and <b>“acoustic”</b>, the band window shows “Sounds like: …”, and even bands Last.fm doesn’t know can be classified. The AI is included in the Docker container, usually not on a PC. It runs gently on a few processor cores and only listens to songs the sound analysis already knows.')}</li>
    <li>{@html t('<b>Instruments, key and tempo:</b> the AI also hears which instruments play – piano, guitar, strings, brass … –, the key and the tempo. Sound vibes can ask for instruments, the search finds “piano” or “calm piano music”, and the song window shows key and tempo.')}</li>
    <li>{@html t('<b>Themes:</b> the AI also hears themes – Christmas, film music, epic, dark, love songs, romantic, ballads, summer, space. Sound vibes can ask for them, the search finds “film music” or “epic”, and the song window shows them. In the search a music world or vibe of the same name comes first.')}</li>
    <li>{@html t('<b>Easy to listen to, for close listening:</b> the AI also rates how easy a song is to listen to and how much it invites close listening. The sound vibes <b>“In the background”</b> and <b>“For listening closely”</b> are based on this, and every sound vibe can ask for it.')}</li>
    <li>{@html t('<b>Sounds alike:</b> from the sound of every song the AI recognizes similar songs and bands – for “More like this”, the radio, “Sounds like these bands” in the band window and when classifying new bands. Mixes get smooth transitions: neighboring songs fit in sound, tempo, key and energy – the switch is under <a class="link" href="#/einstellungen/playlists">Settings → Playlists</a>.')}</li>
    <li>{@html t('<b>Taste from the sound:</b> from the songs a person plays and likes – and those they skip or rate low – Tuttiphon learns which sound they like. Their mixes and suggestions use it, even for bands they haven’t listened to yet.')}</li>
    <li>{@html t('<b>Audio fingerprints:</b> a fingerprint of every recording, about 3 KB per song, finds the same recording stored twice – also as another format, in another folder or on another album; the result is under <a class="link" href="#/einstellungen/bibliothek">Settings → Check library</a>. Needs fpcalc, which is included in the Docker image.')}</li>
    <li>{@html t('<b>Night analysis:</b> at night, by default from 1 to 5 a.m., Tuttiphon works through whatever is still open without a time limit – first the sound analysis, then the AI – and stops in time before the daily refresh. The AI’s first pass takes several nights on the NAS. New music arriving during that time is processed afterwards. The nightly Deezer refresh and the weekly cover search also run in this window.')}</li>
    <li>{@html t('<b>Radio:</b> “Start radio” in the band window – a playlist with the band and similar bands from your library, new every week. Precise with Last.fm, via similar genres without it; with the AI, songs that sound like the band come up more often.')}</li>
    <li>{@html t('<b>Classify new bands:</b> for bands without a music world, Tuttiphon works out where they fit from similar bands, Last.fm tags, genres, AI music styles and scenes. Bands with a confident match of 75 % or more go straight into their world (listed under “To review” with “Undo”); the rest stays a suggestion with a match rate under “To review”.')}</li>
    <li>{@html t('<b>You might still be missing:</b> under Discover, bands that are similar to your favorites but not yet in the library.')}</li>
  </Bullets>
  <p>{@html t('Set it up under <a class="link" href="#/einstellungen/intel">Settings → Intelligence</a>. There you also choose how closely it listens: Fast, Standard, Thorough or Deep. The first full pass of the sound analysis takes half an hour to several hours, depending on depth and computer. It can be stopped, each run has a time limit, and the night analysis does the rest; after that, only new songs are left. The AI listens as much as the sound analysis, at most “Thorough”. Last.fm needs a free key.')}</p>
{/snippet}

{#snippet watch()}
  <p>{@html t('If you like, Tuttiphon watches the music folder – turn it on under <a class="link" href="#/einstellungen/ablaeufe">Settings → Automation → Folder watch</a>. When new music lands there – e.g. from Lidarr – everything happens on its own: convert to Opus or AAC, find lyrics, have Navidrome scan, analyze the sound, rate on Deezer. Smart playlists then include the new songs right away.')}</p>
  <p>{t('Tuttiphon checks at an adjustable interval of every 5–60 minutes and gives freshly copied files two minutes of rest. While another run is working – such as the night analysis – the folder watch waits and processes the new music afterwards. Best in the Docker container on the NAS, which always runs.')}</p>
{/snippet}

{#snippet docker()}
  <p>{@html t('Under <a class="link" href="#/einstellungen/speicher">Settings → Storage locations</a> you see where music, playlists and the archive are. In the Docker container, e.g. on a NAS, you set them in docker-compose.yaml – the template mounts the music at <code>/music</code>, the archive at <code>/archive</code>, the backups at <code>/backup</code> and settings & credentials at <code>/config</code>.')}</p>
  <p>{@html t('The image includes the AI sound analysis, which makes it about 700 MB larger. While it runs it needs about 850 MB of extra memory – afterwards that is free again. You set how many processor cores it may use under <a class="link" href="#/einstellungen/intel">Settings → Intelligence</a>.')}</p>
  <p>{@html t('Setup and updates are described in the <a class="link" href="https://github.com/seluce/tuttiphon#readme" target="_blank" rel="noopener">README on GitHub</a>.')}</p>
{/snippet}

{#snippet opus()}
  <p>{@html t('Tuttiphon converts new lossless files – FLAC, and if you like also WAV, AIFF, ALAC … – to <b>Opus</b> or <b>AAC</b>: sounds the same but takes only about a fifth of the space. Opus is the smallest and ideal for Android; iPhone, iPad and Mac play AAC everywhere. The rules:')}</p>
  <Bullets>
    <li>{t('Freshly imported files, e.g. from Lidarr, are left alone for a few minutes.')}</li>
    <li>{t('The new file is checked for the same length; only then does the original go to the archive – or is kept or deleted, as you choose.')}</li>
    <li>{t('Tags such as MusicBrainz IDs and ISRC, lyrics and the cover move along.')}</li>
    <li>{t('Nothing in the archive is ever overwritten.')}</li>
  </Bullets>
  <p>{@html t('Target format, quality, formats and waiting time: <a class="link" href="#/einstellungen/opus">Settings → Conversion</a>; the archive folder is set under <a class="link" href="#/einstellungen/speicher">Settings → Storage locations</a>.')}</p>
  <p>{@html t('<b>Even out loudness:</b> if you like, Tuttiphon measures at night how loud each song is and writes ReplayGain values into the files without re-encoding them. Turn on ReplayGain in Symfonium and all songs play equally loud. Each file is copied and checked first, only then replaced.')}</p>
{/snippet}

{#snippet bibliothek()}
  <p>{@html t('Under <a class="link" href="#/einstellungen/bibliothek">Settings → Check library</a> Tuttiphon shows what helps with tidying up. Nothing is changed there – tapping a band opens it.')}</p>
  <Bullets>
    <li>{@html t('<b>Duplicates in the same album</b> – the same title twice with the same length, often an old FLAC file next to the converted Opus file.')}</li>
    <li>{@html t('<b>Same song on several albums</b> – e.g. as a single and on the album. Usually intended.')}</li>
    <li>{@html t('<b>Same recording twice</b> – found by audio fingerprints: the same recording in different formats, folders or albums, e.g. a FLAC file next to its Opus version or a song on the album and on a best-of. Live and karaoke versions are kept apart.')}</li>
    <li>{@html t('<b>Albums without a cover</b> – Tuttiphon fetches them itself, see below. <b>Albums with gaps</b> in the track numbers, <b>very short files</b> under 20 seconds, <b>songs without a genre</b> and <b>MP3 below 128 kbit/s</b>.')}</li>
  </Bullets>
  <p>{@html t('<b>Missing covers:</b> for albums with no picture at all – no image file in the folder, none in the files – Tuttiphon fetches a cover from the Cover Art Archive via the MusicBrainz ID, otherwise from Deezer, and saves it as cover.jpg next to the music. This happens during “Update everything” and once a week in the time window of the night analysis. Existing pictures stay untouched, and new albums get two days so Lidarr can save its own cover; if Lidarr saves one later, Lidarr’s counts. Turn it off under <a class="link" href="#/einstellungen/bibliothek">Settings → Check library</a>.')}</p>
{/snippet}

{#snippet benachrichtigungen()}
  <p>{@html t('Tuttiphon notifies you directly through the app: turn on notifications under <a class="link" href="#/einstellungen/benachrichtigungen">Settings → Notifications</a> and tap “Turn on for this device” on the phone (needs the https address; on the iPhone only from the home screen). Each person turns on their devices in their profile under “To your phone”. Optionally it also works via ntfy:')}</p>
  <Steps>
    <li><span>{@html t('Install the <b>ntfy</b> app on your phone.')}</span></li>
    <li><span>{@render withUi(t('Under “Via ntfy”, enter your own topic and {test}.'), { test: ['', t('Send test')] })}</span></li>
    <li><span>{t('Subscribe to the same topic in the ntfy app. With Tuttiphon’s address set, tapping the message opens the matching page right away.')}</span></li>
  </Steps>
  <p>{t('On Mondays, “New for you this week” tells each person what is new in their discoveries and their album of the week.')}</p>
  <p>{t('You get failed runs, processed new music and newly classified bands; which of them is set under “What to notify about?”. Each person gets news from their favorite bands and the monthly recap – on their devices or via their own ntfy topic from the profile. Anyone who knows an ntfy topic can read along – on your own server an access token protects it, as NTFY_TOKEN in the .env or in docker-compose.')}</p>
{/snippet}

{#snippet einstellungen()}
  <p>{@html t('<a class="link" href="#/einstellungen">Settings</a> are divided into sections:')}</p>
  <Bullets>
    <li>{@html t('<b>General</b> – theme, language of the interface and of the server, install as an app, setup assistant, About Tuttiphon.')}</li>
    <li>{@html t('<b>My account</b> – signed in as, statistics & stars, restart the tour, sign out.')}</li>
    <li>{@html t('<b>Users & permissions</b> – who is an administrator, who is a user, who has no access.')}</li>
    <li>{@html t('<b>Home page</b> – which sections, in which order.')}</li>
    <li>{@html t('<b>Notifications</b> – to your phone via the app or ntfy, and about what.')}</li>
    <li>{@html t('<b>Navidrome</b> – server address and admin with connection test, account passwords, type of scan.')}</li>
    <li>{@html t('<b>Playlists</b> – apply automatically, mixes that learn, basic rules such as minimum length, live recordings, “the hits” …')}</li>
    <li>{@html t('<b>Storage locations</b> – where music, playlists and the archive are.')}</li>
    <li>{@html t('<b>Deezer stars, Lyrics, Conversion, Intelligence</b> – see the sections above.')}</li>
    <li>{@html t('<b>Check library</b> – duplicates, missing covers, gaps in albums.')}</li>
    <li>{@html t('<b>Automation</b> – what “Update everything” does and the time of the daily refresh.')}</li>
    <li>{@html t('<b>Backup</b> – the daily backup, download and restore.')}</li>
  </Bullets>
  <p>{t('Credentials stay in Tuttiphon’s data folder on your NAS. Whatever is set in docker-compose.yaml appears grayed out and is changed there.')}</p>
{/snippet}

{#snippet einrichtung()}
  <p>{@html t('The setup assistant goes through the most important settings step by step: the connection to Navidrome, conversion, lyrics, understanding music, Deezer stars and what runs by itself. On a new installation it opens by itself after the first administrator signs in; later you start it again under <a class="link" href="#/einstellungen/allgemein">Settings → General</a> with “Run the setup assistant again”.')}</p>
  <p>{@html t('Every step starts with the current values. The connection is saved right away, everything else only with <b>“Finish”</b>: the last step shows a summary with “Change” for each step and can start the first run of “Update everything” right away. <b>“Skip setup”</b> keeps the other settings as they are.')}</p>
{/snippet}

{#snippet allgemein()}
  <p>{@html t('Under <a class="link" href="#/einstellungen/allgemein">Settings → General</a> you choose the language and light or dark. “Automatic” and “System” follow your phone or computer. The choice applies to this device.')}</p>
  <p>{@html t('The <b>language of the server</b> applies to run logs, notifications and the names Tuttiphon gives playlists and music worlds by itself; delivered vibes that still have their original name are renamed too. There you also find “Install as app”, the setup assistant and, under “About Tuttiphon”, the version.')}</p>
{/snippet}

{#snippet sicherung()}
  <p>{t('Once a day, at the time of the daily refresh, Tuttiphon backs up everything that cannot be restored on its own – settings, people, music worlds and playlists, credentials, Deezer status, sound analysis and the listening history for the recap – as a ZIP file. Not included are images, logs and your music itself.')}</p>
  <p>{@html t('Under <a class="link" href="#/einstellungen/sicherung">Settings → Backup</a> you make one right away with “Back up now”, download backups and set how many are kept – 14 by default. They are stored in the Docker container in the folder mounted as <code>/backup</code>, otherwise in the data folder; best on a different disk than the settings.')}</p>
  <p>{@html t('<b>Restoring</b> works by hand:')}</p>
  <Steps>
    <li><span>{t('Quit Tuttiphon or stop the Docker container.')}</span></li>
    <li><span>{@html t('Unpack the chosen ZIP backup into the data folder – in the container, that is the folder mounted as <code>/config</code>. Overwrite existing files.')}</span></li>
    <li><span>{t('Start Tuttiphon again. After that, everyone signs in once more.')}</span></li>
  </Steps>
  <p>{t('The backup contains credentials – keep it in safe places only.')}</p>
{/snippet}

{#snippet konten()}
  <p>{@html t('Everyone in the family can sign in with their own <b>Navidrome account</b> – with the same name and password as in Symfonium. Tuttiphon checks the password directly with Navidrome; there are no separate passwords.')}</p>
  <Bullets>
    <li>{@html t('<b>Administrator</b> – sees and changes everything. Default for Navidrome admins such as root.')}</li>
    <li>{@html t('<b>User</b> – own “For you” home page, own playlists, own profile with taste. Other people’s playlists are only visible if they are shared with everyone – for listening and copying, not for changing. Music worlds, vibes, Deezer, lyrics and settings remain with the administrator.')}</li>
    <li>{@html t('<b>No access</b> – cannot sign in to Tuttiphon; Navidrome and Symfonium keep working.')}</li>
  </Bullets>
  <p>{@html t('You change the roles under <a class="link" href="#/einstellungen/benutzer">Settings → Users & permissions</a>. Anyone signing in as a user for the first time is guided by a short assistant: profile, favorite worlds, favorite bands, dislikes and the first playlists.')}</p>
  <Steps>
    <li><span>{@html t('At the first start you set the password of the <b>local administrator</b> in the browser – with the setup code from the container log. It turns on sign-in; you change it later under Settings → Users & permissions.')}</span></li>
    <li><span>{t('From then on Tuttiphon asks everyone for their username and password.')}</span></li>
    <li><span>{t('Make it reachable via https through a reverse proxy such as nginx – then Tuttiphon can also be installed as an app.')}</span></li>
  </Steps>
  <p>{t('The local administrator signs in on the sign-in page under “Local administrator”. It works even when Navidrome can’t be reached and has full permissions. You stay signed in for 90 days; “Sign out” is in the menu under your own name.')}</p>
{/snippet}

{#snippet app()}
  <p>{@html t('Tuttiphon can be put on the home screen like an app – with its own icon. iPhone: in Safari <b>Share → Add to Home Screen</b>. Android: Chrome menu <b>⋮ → Add to Home screen</b> or “Install app”.')}</p>
  <p>{@html t('As a “real” app with its own window, this only works via https, e.g. with a reverse proxy on the NAS. Via the normal http address you get a shortcut that works just as well. More under <a class="link" href="#/einstellungen/allgemein">Settings → General</a>.')}</p>
{/snippet}

{#snippet alt()}
  <p>{@html t('Playlists that were already in the <code>00_SmartPlaylists</code> folder don’t disappear. The home page offers to <b>take them over</b>: then Tuttiphon keeps maintaining them, their rules stay unchanged, and the original file is backed up first.')}</p>
  <p>{t('Regular playlists you create by hand in Navidrome or Symfonium are never touched by the tool.')}</p>
{/snippet}
