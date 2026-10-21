// Same keys as ../de/settings-opus.js
export default {
  'At least one format':
    'Minstens één formaat',
  'Delete originals?':
    'Originelen verwijderen?',
  'The lossless originals are deleted after converting instead of archived. This cannot be undone.':
    'De lossless originelen worden na het converteren verwijderd in plaats van gearchiveerd. Dit kan niet ongedaan worden gemaakt.',
  'Yes, delete':
    'Ja, verwijderen',
  'Please enter as UID:GID, e.g. 1000:1000':
    'Voer in als UID:GID, bijv. 1000:1000',
  'Convert lossless files':
    'Lossless bestanden converteren',
  'Converted music sounds like the original but takes only about a fifth of the space – ideal for phones. Every new file is fully checked before Tuttiphon touches the original; tags and cover are kept.':
    'Geconverteerde muziek klinkt als het origineel, maar neemt maar ongeveer een vijfde van de ruimte in – ideaal voor telefoons. Elk nieuw bestand wordt volledig gecontroleerd voordat Tuttiphon het origineel aanraakt; tags en cover blijven behouden.',
  'ffmpeg/ffprobe are missing on this computer – please install them. The Docker image includes them.':
    'ffmpeg/ffprobe ontbreken op deze computer – installeer ze. Het Docker-image bevat ze.',
  'For AAC, this computer lacks a package that carries the tags over. The Docker image includes everything.':
    'Voor AAC mist deze computer een pakket dat de tags overneemt. Het Docker-image bevat alles.',
  'Files to convert: {n}':
    'Te converteren bestanden: {n}',
  'Nothing to convert':
    'Niets te converteren',
  'count again':
    'opnieuw tellen',
  'Music: {music} · Archive: {archive}':
    'Muziek: {music} · Archief: {archive}',
  'Conversion on':
    'Conversie aan',
  'Target format':
    'Doelformaat',
  'Opus is the smallest and ideal for Android. iPhone, iPad and Mac play AAC everywhere. Applies to new conversions; finished files stay as they are.':
    'Opus is het kleinst en ideaal voor Android. iPhone, iPad en Mac spelen AAC overal af. Geldt voor nieuwe conversies; al geconverteerde bestanden blijven zoals ze zijn.',
  'Which formats?':
    'Welke formaten?',
  'Lossless only – .m4a only if it contains ALAC.':
    'Alleen lossless – .m4a alleen als het ALAC bevat.',
  'Quality':
    'Kwaliteit',
  'kbit/s. AAC needs a little more than Opus for the same sound. 224 is the default, 256 for purists.':
    'kbit/s. AAC heeft voor dezelfde klank iets meer nodig dan Opus. 224 is de standaard, 256 voor puristen.',
  'kbit/s. 128 is enough for phones, 160 is the default, 256 for purists.':
    'kbit/s. 128 is genoeg voor telefoons, 160 is de standaard, 256 voor puristen.',
  'Original afterwards':
    'Origineel daarna',
  'Only once the new file is fully checked.':
    'Pas als het nieuwe bestand volledig is gecontroleerd.',
  'to the archive':
    'naar het archief',
  'keep':
    'behouden',
  'delete':
    'verwijderen',
  'Archive folder':
    'Archiefmap',
  'The folder structure is kept.':
    'De mapstructuur blijft behouden.',
  'Storage locations':
    'Opslaglocaties',
  'Waiting time':
    'Wachttijd',
  'Leave freshly imported files alone for this many minutes in case Lidarr is still writing.':
    'Vers geïmporteerde bestanden zoveel minuten met rust laten, voor het geval Lidarr nog schrijft.',
  'Advanced':
    'Geavanceerd',
  'Simultaneous conversions':
    'Gelijktijdige conversies',
  'More = faster, but more load on the computer/NAS.':
    'Meer = sneller, maar meer belasting voor de computer/NAS.',
  'Owner of new files':
    'Eigenaar van nieuwe bestanden',
  'Empty = the user Tuttiphon runs as (user: in docker-compose.yaml). Otherwise UID:GID as in Lidarr – only works with sufficient rights.':
    'Leeg = de gebruiker waaronder Tuttiphon draait (user: in docker-compose.yaml). Anders UID:GID zoals in Lidarr – werkt alleen met voldoende rechten.',
  'Even out loudness':
    'Volume gelijktrekken',
  'At night Tuttiphon measures how loud each song is and writes ReplayGain values into the files without re-encoding them. Turn on ReplayGain in Symfonium and all songs play equally loud, even in a mix from a children\'s song to metal.':
    '’s Nachts meet Tuttiphon hoe luid elk nummer is en schrijft ReplayGain-waarden in de bestanden zonder ze opnieuw te coderen. Zet ReplayGain aan in Symfonium en alle nummers spelen even luid, zelfs in een mix van een kinderliedje tot metal.',
  'Leveling on':
    'Gelijktrekken aan',
  'Writes once into every music file. Each file is copied and checked first, only then replaced. Values that already came from elsewhere stay.':
    'Schrijft één keer in elk muziekbestand. Elk bestand wordt eerst gekopieerd en gecontroleerd, pas daarna vervangen. Waarden die al van elders kwamen, blijven.',
  'Album values too':
    'Ook albumwaarden',
  'For albums you listen to in one go: quiet and loud songs of an album keep their balance.':
    'Voor albums die je in één keer beluistert: zachte en harde nummers van een album houden hun verhouding.',
  'Not possible here: {why}. The Docker container on the NAS includes everything.':
    'Hier niet mogelijk: {why}. De Docker-container op de NAS bevat alles.',
  '{measured} of {songs} songs measured · {written} with values written':
    '{measured} van {songs} nummers gemeten · {written} met geschreven waarden',
  ' · {n} already had their own':
    ' · {n} hadden al eigen waarden',
  'Run now':
    'Nu uitvoeren',
  'Convert now':
    'Nu converteren',
  'Dry run':
    'Proefrun',
}
