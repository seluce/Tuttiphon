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
    { id: 'plugin', icon: 'puzzle', title: t('Navidrome plugin: Instant Mix by sound'), body: plugin },
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
  <p>{@html t('The home page shows at a glance what’s going on: the big <b>“Update everything”</b> button, your mixes, <b>“To review”</b> with what needs you – such as new bands or missing passwords – and what was played and added. You arrange the sections under <a class="link" href="#/einstellungen/start">Settings → Home page</a>.')}</p>
  <p>{@html t('<b>“Update everything”</b> runs all steps in order – convert, lyrics, covers, sound analysis, playlists, scan, Deezer stars. Which steps take part you set under <a class="link" href="#/einstellungen/ablaeufe">Settings → Automation</a>; the log is under <a class="link" href="#/verlauf">History</a>.')}</p>
{/snippet}

{#snippet neu()}
  <p>{@html t('The easiest way is the assistant under <a class="link" href="#/neu">New playlist</a>. It asks step by step – “For whom?” only when there are several people:')}</p>
  <Steps>
    <li><span>{@html t('<b>For whom?</b> – a person’s playlist is only theirs, and the stars of their account count; a family playlist is for everyone.')}</span></li>
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
    </CompareCard>
  </div>
  <p>{t('Rule of thumb: for streaming and “everything by …” lists, the smart playlist. For kids’ and family music and everything that should go offline onto the phone, the mix – e.g. “Kids · Seasons” as a weekly mix.')}</p>
  <p>{@html t('<b>Mixes from listening</b> – under <a class="link" href="#/entdecken">Discover</a>, for every person:')}</p>
  <Bullets>
    <li>{@html t('<b>Discovered for you</b> and <b>Album of the week</b> – every Monday songs or a whole album the account has never played, by its taste.')}</li>
    <li>{@html t('<b>Next episode</b> – for accounts that listen to audio plays: the next episode of every series, new every day.')}</li>
    <li>{@html t('<b>New from your favorite bands</b> and <b>Your October</b> – what is new from the favorite bands, the most played songs of the month.')}</li>
    <li>{@html t('<b>Good night</b>, <b>Good morning</b> and <b>Car ride</b> – a fixed length instead of a number of songs; good morning only for accounts that often listen in the morning.')}</li>
    <li>{@html t('<b>What everyone likes</b> – a family playlist in which the taste of every person counts equally; what someone dislikes stays out.')}</li>
  </Bullets>
  <p>{@html t('Mixes renew themselves at the time of the daily refresh (<a class="link" href="#/einstellungen/ablaeufe">Settings → Automation</a>) – daily, on Mondays or on the 1st.')}</p>
  <p>{@html t('<b>Mixes learn:</b> what was skipped comes up less often, songs someone rates 1 star never – with the Navidrome plugin for every account, otherwise for accounts whose password Tuttiphon knows. Switch: “Mixes that learn” under <a class="link" href="#/einstellungen/playlists">Settings → Playlists</a>.')}</p>
  <p>{@html t('<b>The family’s mixes</b> heard on a person’s own account are recognized by their order (three songs in a row): what is played or skipped there teaches the family, not the person’s taste and mixes – with the Navidrome plugin.')}</p>
{/snippet}

{#snippet playlists()}
  <p>{t('A playlist’s page shows a preview, its bands and in plain words how it is made; a click on a song plays it.')}</p>
  <Bullets>
    <li>{@render withUi(t('{edit} – everything can be changed; the name and ID in Navidrome stay, Symfonium keeps the playlist.'), { edit: ['edit', t('Edit')] })}</li>
  </Bullets>
  <p>{@render withUi(t('The other actions are in the {more} menu next to it:'), { more: ['more', ''] })}</p>
  <Bullets>
    <li>{@render withUi(t('{pause} – disappears from Navidrome but stays here with all its settings. Simply activate it again later.'), { pause: ['pause', t('Pause playlist')] })}</li>
    <li>{@render withUi(t('{trash} – filed under “Trash”, deleted for good after 30 days.'), { trash: ['trash', t('Move to trash')] })}</li>
    <li>{@render withUi(t('{keep} – the current selection as a fixed playlist that never changes again.'), { keep: ['pin', t('Keep this mix')] })}</li>
    <li>{@render withUi(t('{cover} – your own picture for Navidrome and Symfonium.'), { cover: ['image', t('Cover')] })}</li>
  </Bullets>
  <p>{@render withUi(t('<b>Keeping things tidy:</b> seasonal playlists such as Christmas are only in Navidrome during their season. “To review” reports playlists nobody listens to, with {pause}, and playlists with the same selection.'), { pause: ['pause', t('Pause playlist')] })}</p>
  <p>{@html t('Almost everything can be taken back right away with <b>“Undo”</b> in the message at the bottom.')}</p>
{/snippet}

{#snippet cover()}
  <p>{@html t('On the playlist page, “…” → “Cover”: a <b>mosaic</b> of album covers, a <b>band photo</b>, a <b>gradient</b> or the <b>album cover</b> – or <b>your own picture</b>.')}</p>
  <p>{t('Designed covers renew themselves when the playlist changes; formats such as discovered or album of the week bring a cover of their own. A picture set in Navidrome itself stays, “Navidrome default” removes the cover.')}</p>
{/snippet}

{#snippet entdecken()}
  <p>{@html t('Under <a class="link" href="#/entdecken">Discover</a> the tool suggests ready-made playlists – matching your preferences, music worlds and existing playlists, mixes included. One click creates them, “Customize” opens them in the editor first, and the ✕ hides a suggestion for half a year. After that it comes back if it still fits.')}</p>
{/snippet}

{#snippet suche()}
  <p>{t('The search field at the top finds bands, songs, playlists, music worlds and people – and understands moods:')}</p>
  <Bullets>
    <li>{@html t('<b>Combined:</b> “calm kids’ songs” or “party medieval” – <b>Create as mix</b> appears at the top.')}</li>
    <li>{@html t('<b>By sound:</b> “for falling asleep”, “without vocals” or “calm piano music”.')}</li>
    <li>{@html t('<b>In the lyrics:</b> one line is enough, such as “hands up in the air”.')}</li>
  </Bullets>
  <p>{@html t('On a computer, the <b>/</b> key jumps straight to the search field.')}</p>
{/snippet}

{#snippet welten()}
  <p>{@html t('A music world groups bands, such as “Medieval” with Saltatio Mortis and In Extremo. <b>Music worlds appear on their own:</b> from genres, Last.fm, AI and language Tuttiphon recognizes what your library offers – and puts new bands into their world.')}</p>
  <Bullets>
    <li>{@render withUi(t('Worlds Tuttiphon created carry the {auto} badge; rename or delete them – a deleted one won’t come back.'), { auto: ['sparkles', t('created by Tuttiphon')] })}</li>
    <li>{@html t('Kids and audio dramas become <b>separate worlds</b>: they are left out of playlists made from “All”.')}</li>
    <li>{@render withUi(t('{new} creates a world of your own; {rebuild} puts a changed world together from its scene again.'), { new: ['plus', t('New music world'), true], rebuild: ['wand', t('Rebuild')] })}</li>
    <li>{@html t('You can turn this off under <a class="link" href="#/einstellungen/intel">Settings → Intelligence</a>.')}</li>
  </Bullets>
  <Steps>
    <li><span>{@html t('Open a music world under <a class="link" href="#/welten">Music worlds</a>.')}</span></li>
    <li><span>{@html t('Under <b>“Might fit too”</b>, tap bands to add them; <b>×</b> takes one out.')}</span></li>
    <li><span>{@render withUi(t('The home page reports new bands in your library that don’t belong to any world yet. {assign} opens the band window, where you choose the world.'), { assign: ['', t('Assign music world …')] })}</span></li>
  </Steps>
  <p>{t('All playlists of this world adjust automatically.')}</p>
{/snippet}

{#snippet richtungen()}
  <p>{@html t('Vibes describe <b>what</b> is playing: a mood such as Party or Calm, an occasion such as Christmas or Good night, a time such as 80s or Newly added, or special cases such as Favorite songs. Seasonal vibes switch on and off automatically – Christmas songs only come from late November to 6 January.')}</p>
  <p>{@html t('Under <a class="link" href="#/richtungen">Vibes</a> you can adjust them and create your own, e.g. “Acoustic covers”. <a class="link" href="#/entdecken">Discover</a> → “All combinations as a table” shows how many songs each combination of music world and vibe gives.')}</p>
{/snippet}

{#snippet personen()}
  <p>{@html t('Each person has a Navidrome account of their own, and their playlists are only theirs. <b>Preferences</b> steer their suggestions and mixes, <b>Dislikes</b> never appear in their playlists.')}</p>
  <Steps>
    <li><span>{@html t('Under <a class="link" href="#/personen">People</a>, “Add person”.')}</span></li>
    <li><span>{t('Choose the Navidrome account – it must already exist in Navidrome under “Users”.')}</span></li>
    <li><span>{@html t('Store the account’s password under <a class="link" href="#/einstellungen/navidrome">Settings → Navidrome</a> – or the person signs in and chooses “Turn on statistics & stars”.')}</span></li>
  </Steps>
  <Bullets>
    <li>{@render withUi(t('<b>From listening:</b> the person’s page shows what Tuttiphon has recognized from plays, favorites and stars; {all} turns it into preferences.'), { all: ['plus', t('Add all')] })}</li>
    <li>{@html t('<b>Not part of the taste:</b> children’s music on a parent’s account – switched on in their profile, it no longer shapes their mixes.')}</li>
    <li>{@html t('<b>Kid-safe mode:</b> “Leave out songs with explicit lyrics” in the profile; songs detected wrongly can be allowed under <a class="link" href="#/einstellungen/lyrics">Settings → Lyrics</a>.')}</li>
    <li>{@html t('<b>Child profile:</b> for a child with an account of their own – children’s music belongs to their whole library, and kid-safe mode stays on.')}</li>
    <li>{@html t('<b>To the phone:</b> with notifications on, every person turns on their devices in their profile.')}</li>
    <li>{@html t('<b>The family</b> (optional): “Set up the family” creates a Navidrome account of its own for it – or takes one Navidrome already has, such as the car’s. Its playlists are for everyone – shared devices such as the car or the kitchen tablet use it in Symfonium.')}</li>
  </Bullets>
  <p>{@html t('With their own sign-in, everyone maintains their own profile – more under <a class="link" href="#/hilfe/konten">Users & sign-in</a>.')}</p>
{/snippet}

{#snippet statistik()}
  <p>{@html t('<a class="link" href="#/statistik">Statistics</a> shows per person the most played bands, songs and albums, the listening time – and <b>forgotten favorites</b>, as a playlist with one click. At the top you switch between week, 30 days and year; every recap can be kept as a fixed playlist.')}</p>
  <p>{t('In December the year waits on the start page as a story – for every person and for the family, with a picture to share. Under year, “Watch as a story” opens it any time.')}</p>
  <p>{t('It is based on the plays Symfonium reports, so leave “Scrobbling” on in Symfonium. Tuttiphon counts them for accounts with a stored password or through the Navidrome plugin – the recap grows from the first day.')}</p>
{/snippet}

{#snippet aktualisieren()}
  <p>{@html t('For “Only the hits” and the order of top songs in Symfonium, Tuttiphon gives stars by popularity on Deezer – day to day only for new songs. A match only counts if band and title fit.')}</p>
  <p>{@html t('Under <a class="link" href="#/einstellungen/deezer">Settings → Deezer stars</a> you set how many stars each popularity rank gets – the chart shows the distribution right away.')}</p>
  <Bullets>
    <li>{@html t('<b>Who gets stars?</b> – stars in Navidrome are per account; here you choose the accounts.')}</li>
    <li>{@html t('<b>Highlight top tracks per band</b> – if many songs of a band share the top star count, the most popular get one more.')}</li>
    <li>{@html t('<b>Refresh every night</b>, <b>Retry not found</b> and <b>Check everything again</b> keep the stars up to date.')}</li>
    <li>{t('Stars given by hand always stay, unless you explicitly allow overwriting them.')}</li>
  </Bullets>
{/snippet}

{#snippet lyrics()}
  <p>{t('Tuttiphon finds missing lyrics and puts them next to the songs – synced ones scroll along in Symfonium. Navidrome reads them at the next scan.')}</p>
  <Bullets>
    <li>{@html t('<b>Providers:</b> LRCLIB and, if you like, NetEase – in an order you choose. Synced lyrics win.')}</li>
    <li>{@html t('<b>Fast:</b> each run searches a few minutes at most, new songs first; the rest follows.')}</li>
    <li>{@html t('Everything can be set under <a class="link" href="#/einstellungen/lyrics">Settings → Lyrics</a> – including a dry run.')}</li>
  </Bullets>
  <p>{@html t('<b>Lyrics search & kid-safe mode:</b> all lyrics go into a search index – so the search finds songs by a line, and kid-safe mode detects explicit lyrics.')}</p>
{/snippet}

{#snippet intel()}
  <p>{@html t('Tuttiphon gets to know your music – locally and free of charge. Set it up under <a class="link" href="#/einstellungen/intel">Settings → Intelligence</a>.')}</p>
  <Bullets>
    <li>{@html t('<b>Sound analysis:</b> measures tempo, energy and mood of every song. This gives sound vibes such as “Falling asleep” or “Danceable” – as mixes, because Navidrome doesn’t know the sound.')}</li>
    <li>{@html t('<b>AI sound analysis:</b> also recognizes music style, vocals, instruments, key and themes such as Christmas or film music. The search then finds, for example, “calm piano music”. Only in the Docker image.')}</li>
    <li>{@html t('<b>Sounds alike:</b> similar songs and bands for “More like this”, the radio, smooth transitions in mixes and the Navidrome plugin.')}</li>
    <li>{@html t('<b>Taste from the sound:</b> what a person likes to hear shapes their mixes – also with bands they don’t know yet.')}</li>
    <li>{@html t('<b>Classify new bands:</b> Tuttiphon suggests the matching music world and files confident matches itself – under “To review” with “Undo”.')}</li>
    <li>{@html t('<b>Same recording twice:</b> an audio fingerprint finds it, also in another format; the result is under <a class="link" href="#/einstellungen/bibliothek">Settings → Check library</a>.')}</li>
    <li>{@html t('<b>Radio and gaps:</b> “Start radio” in the band window plays the band with similar bands; Discover shows similar bands you are still missing.')}</li>
  </Bullets>
  <p>{@html t('The analysis works through what is open at night. The AI’s first pass takes several nights on a NAS; after that only new songs are added. Last.fm needs a free key. Details are in the <a class="link" href="https://github.com/seluce/tuttiphon/blob/main/docs/06-intelligence.md" target="_blank" rel="noopener">handbook</a>.')}</p>
{/snippet}

{#snippet watch()}
  <p>{@html t('If you like, Tuttiphon watches the music folder (<a class="link" href="#/einstellungen/ablaeufe">Settings → Automation → Folder watch</a>). New music – e.g. from Lidarr – is then processed on its own: converted, lyrics, scan, sound, Deezer stars.')}</p>
  <p>{t('It looks every 5–60 minutes and waits until freshly copied files are complete.')}</p>
{/snippet}

{#snippet docker()}
  <p>{@html t('Under <a class="link" href="#/einstellungen/speicher">Settings → Storage locations</a> you see where music, playlists and the archive are; in Docker you set them in docker-compose.yaml.')}</p>
  <p>{@html t('The AI sound analysis needs extra memory while it runs; how many processor cores it may use you set under <a class="link" href="#/einstellungen/intel">Settings → Intelligence</a>.')}</p>
  <p>{@html t('Setup and updates are described in the <a class="link" href="https://github.com/seluce/tuttiphon#readme" target="_blank" rel="noopener">README on GitHub</a>.')}</p>
{/snippet}

{#snippet opus()}
  <p>{@html t('Tuttiphon converts new lossless files such as FLAC to <b>Opus</b> or <b>AAC</b> – sounds the same with about a fifth of the space. Opus suits Android, AAC iPhone and Mac.')}</p>
  <Bullets>
    <li>{t('The original only goes to the archive once the new file has been checked; nothing there is ever overwritten.')}</li>
    <li>{t('Tags such as MusicBrainz IDs and ISRC, lyrics and the cover move along.')}</li>
  </Bullets>
  <p>{@html t('Target format, quality, formats and waiting time: <a class="link" href="#/einstellungen/opus">Settings → Conversion</a>; the archive folder is set under <a class="link" href="#/einstellungen/speicher">Settings → Storage locations</a>.')}</p>
  <p>{@html t('<b>Even out loudness:</b> if you like, Tuttiphon writes ReplayGain values into the files at night – with ReplayGain on in Symfonium, all songs play equally loud.')}</p>
{/snippet}

{#snippet bibliothek()}
  <p>{@html t('Under <a class="link" href="#/einstellungen/bibliothek">Settings → Check library</a> Tuttiphon shows what helps with tidying up. Nothing is changed there – tapping a band opens it.')}</p>
  <Bullets>
    <li>{@html t('<b>Duplicates</b> – the same song twice in an album, on several albums or as the same recording in another format.')}</li>
    <li>{@html t('<b>Gaps and oddities</b> – albums with gaps in the track numbers, very short files, songs without a genre, MP3 below 128 kbit/s.')}</li>
  </Bullets>
  <p>{@html t('<b>Missing covers:</b> for albums without any picture, Tuttiphon fetches one (Cover Art Archive or Deezer) and saves it as cover.jpg next to the music. Existing pictures stay untouched.')}</p>
{/snippet}

{#snippet plugin()}
  <p>{t('With the Tuttiphon plugin (Navidrome 0.64 or later), Instant Mix, song radio and the smart queue in Symfonium follow the sound of your own files – and Navidrome passes every play on.')}</p>
  <Steps>
    <li><span>{@html t('Under <a class="link" href="#/einstellungen/navidrome">Settings → Navidrome</a>, create a key in the card “Navidrome plugin” and download the plugin.')}</span></li>
    <li><span>{@html t('Put the file – not unpacked and named exactly <b>tuttiphon.ndp</b> – into Navidrome’s plugins folder, put <code>tuttiphon</code> first in Navidrome’s list of agents (navidrome.toml: <code>Agents = "tuttiphon,deezer,lastfm,listenbrainz"</code>, docker-compose: <code>ND_AGENTS=…</code>) and restart Navidrome.')}</span></li>
    <li><span>{t('In Navidrome under Settings → Plugins, turn on “Tuttiphon”, enter Tuttiphon’s address in the home network and the key, and allow it all users.')}</span></li>
    <li><span>{t('In Symfonium, turn on “Use similar tracks for Radio Mix” for the Navidrome server (Manage media providers → the server) and choose “Sonic Analysis” for the smart queue in the player.')}</span></li>
  </Steps>
  <p>{t('Navidrome does not say who is asking; Tuttiphon sees it from the plays and answers for the person listening – otherwise for the family, or for everyone if there is none. Songs with explicit lyrics stay out as soon as a person has kid-safe mode or is a child profile. The card shows for whom it last answered.')}</p>
  <p>{t('Skips steer the smart queue at once: after two in a row it turns to another sound. Every few songs one the account has never played comes in – how often is set per person in the profile (“New songs in the queue”).')}</p>
{/snippet}

{#snippet benachrichtigungen()}
  <p>{@html t('Turn on notifications under <a class="link" href="#/einstellungen/benachrichtigungen">Settings → Notifications</a> and tap “Turn on for this device” on the phone – this needs the https address, on the iPhone the home screen. Each person turns on their devices in their profile.')}</p>
  <p>{@html t('Alternatively via the <b>ntfy</b> app:')}</p>
  <Steps>
    <li><span>{@html t('Install the <b>ntfy</b> app on your phone.')}</span></li>
    <li><span>{@render withUi(t('Under “Via ntfy”, enter your own topic and {test}.'), { test: ['', t('Send test')] })}</span></li>
    <li><span>{t('Subscribe to the same topic in the ntfy app.')}</span></li>
  </Steps>
  <p>{t('You get failed runs, new music and newly classified bands – which of them is set under “What to notify about?”. Each person gets news from their favorite bands, Monday’s news and the monthly recap. Anyone who knows an ntfy topic can read along – on your own ntfy server, NTFY_TOKEN protects it.')}</p>
{/snippet}

{#snippet einstellungen()}
  <p>{@html t('<a class="link" href="#/einstellungen">Settings</a> are divided into sections; each says in its subtitle what it holds. Credentials stay in Tuttiphon’s data folder on your NAS; whatever docker-compose.yaml sets appears grayed out and is changed there.')}</p>
{/snippet}

{#snippet einrichtung()}
  <p>{@html t('The setup assistant goes through the most important settings step by step. On a new installation it opens by itself; later you start it under <a class="link" href="#/einstellungen/allgemein">Settings → General</a>.')}</p>
  <p>{@html t('Only the connection is saved right away, everything else with <b>“Finish”</b>; <b>“Skip setup”</b> leaves the rest as it is.')}</p>
{/snippet}

{#snippet allgemein()}
  <p>{@html t('Under <a class="link" href="#/einstellungen/allgemein">Settings → General</a> you choose the language and light or dark. “Automatic” and “System” follow your phone or computer. The choice applies to this device.')}</p>
  <p>{@html t('The <b>language of the server</b> applies to logs, the administrators’ ntfy topic and the names Tuttiphon gives playlists and music worlds. Notifications on phones and in the browser follow the language of the device.')}</p>
{/snippet}

{#snippet sicherung()}
  <p>{@html t('Every day Tuttiphon backs up everything that cannot be restored on its own – settings, playlists, credentials, Deezer, sound analysis and the listening history – as a ZIP file. Under <a class="link" href="#/einstellungen/sicherung">Settings → Backup</a> you back up right away, download backups and set how many are kept.')}</p>
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
    <li>{@html t('<b>User</b> – own home page, playlists and profile; listens to the family playlists and changes them unless only administrators may.')}</li>
    <li>{@html t('<b>No access</b> – cannot sign in to Tuttiphon; Navidrome and Symfonium keep working.')}</li>
  </Bullets>
  <p>{@html t('Under <a class="link" href="#/einstellungen/benutzer">Settings → Users & permissions</a> you set the roles and who may change the family playlists; new users are guided through their profile by a short assistant.')}</p>
  <Steps>
    <li><span>{@html t('At the first start you set the password of the <b>local administrator</b> in the browser – with the setup code from the container log. It turns on sign-in; you change it later under Settings → Users & permissions.')}</span></li>
    <li><span>{t('From then on Tuttiphon asks everyone for their username and password.')}</span></li>
    <li><span>{t('Make it reachable via https through a reverse proxy such as nginx – then Tuttiphon can also be installed as an app.')}</span></li>
  </Steps>
  <p>{t('The local administrator signs in under “Local administrator” on the sign-in page – also when Navidrome is not reachable.')}</p>
{/snippet}

{#snippet app()}
  <p>{@html t('Tuttiphon can be put on the home screen like an app – with its own icon. iPhone: in Safari <b>Share → Add to Home Screen</b>. Android: Chrome menu <b>⋮ → Add to Home screen</b> or “Install app”.')}</p>
  <p>{@html t('As a “real” app with its own window, this only works via https, e.g. with a reverse proxy on the NAS. Via the normal http address you get a shortcut that works just as well. More under <a class="link" href="#/einstellungen/allgemein">Settings → General</a>.')}</p>
{/snippet}

{#snippet alt()}
  <p>{@html t('Playlists that were already in the <code>00_SmartPlaylists</code> folder don’t disappear. The home page offers to <b>take them over</b>: then Tuttiphon keeps maintaining them, their rules stay unchanged, and the original file is backed up first.')}</p>
  <p>{t('Regular playlists you create by hand in Navidrome or Symfonium are never touched by the tool.')}</p>
{/snippet}
