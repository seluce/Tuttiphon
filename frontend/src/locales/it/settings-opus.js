// Same keys as ../de/settings-opus.js
export default {
  'At least one format':
    'Almeno un formato',
  'Delete originals?':
    'Eliminare gli originali?',
  'The lossless originals are deleted after converting instead of archived. This cannot be undone.':
    'Gli originali lossless vengono eliminati dopo la conversione invece di essere archiviati. Non si può annullare.',
  'Yes, delete':
    'Sì, elimina',
  'Please enter as UID:GID, e.g. 1000:1000':
    'Inserisci come UID:GID, ad es. 1000:1000',
  'Convert lossless files':
    'Converti i file lossless',
  'Converted music sounds like the original but takes only about a fifth of the space – ideal for phones. Every new file is fully checked before Tuttiphon touches the original; tags and cover are kept.':
    'La musica convertita suona come l\'originale ma occupa solo circa un quinto dello spazio – ideale per i telefoni. Ogni nuovo file viene verificato completamente prima che Tuttiphon tocchi l\'originale; tag e copertina vengono mantenuti.',
  'ffmpeg/ffprobe are missing on this computer – please install them. The Docker image includes them.':
    'Su questo computer mancano ffmpeg/ffprobe – installali. L\'immagine Docker li include.',
  'For AAC, this computer lacks a package that carries the tags over. The Docker image includes everything.':
    'Per AAC, su questo computer manca un pacchetto che trasferisce i tag. L\'immagine Docker include tutto.',
  'Files to convert: {n}':
    'File da convertire: {n}',
  'Nothing to convert':
    'Niente da convertire',
  'count again':
    'ricalcola',
  'Music: {music} · Archive: {archive}':
    'Musica: {music} · Archivio: {archive}',
  'Conversion on':
    'Conversione attiva',
  'Target format':
    'Formato di destinazione',
  'Opus is the smallest and ideal for Android. iPhone, iPad and Mac play AAC everywhere. Applies to new conversions; finished files stay as they are.':
    'Opus è il più piccolo e ideale per Android. iPhone, iPad e Mac riproducono AAC ovunque. Vale per le nuove conversioni; i file già convertiti restano come sono.',
  'Which formats?':
    'Quali formati?',
  'Lossless only – .m4a only if it contains ALAC.':
    'Solo lossless – .m4a solo se contiene ALAC.',
  'Quality':
    'Qualità',
  'kbit/s. AAC needs a little more than Opus for the same sound. 224 is the default, 256 for purists.':
    'kbit/s. AAC richiede un po\' più di Opus per lo stesso suono. 224 è il valore predefinito, 256 per i puristi.',
  'kbit/s. 128 is enough for phones, 160 is the default, 256 for purists.':
    'kbit/s. 128 basta per i telefoni, 160 è il valore predefinito, 256 per i puristi.',
  'Original afterwards':
    'Poi l\'originale',
  'Only once the new file is fully checked.':
    'Solo quando il nuovo file è stato verificato completamente.',
  'to the archive':
    'nell\'archivio',
  'keep':
    'mantieni',
  'delete':
    'elimina',
  'Archive folder':
    'Cartella dell\'archivio',
  'The folder structure is kept.':
    'La struttura delle cartelle viene mantenuta.',
  'Storage locations':
    'Percorsi',
  'Waiting time':
    'Tempo di attesa',
  'Leave freshly imported files alone for this many minutes in case Lidarr is still writing.':
    'Lascia stare i file appena importati per questo numero di minuti, nel caso Lidarr stia ancora scrivendo.',
  'Advanced':
    'Avanzate',
  'Simultaneous conversions':
    'Conversioni simultanee',
  'More = faster, but more load on the computer/NAS.':
    'Di più = più veloce, ma più carico sul computer/NAS.',
  'Owner of new files':
    'Proprietario dei nuovi file',
  'Empty = the user Tuttiphon runs as (user: in docker-compose.yaml). Otherwise UID:GID as in Lidarr – only works with sufficient rights.':
    'Vuoto = l\'utente con cui gira Tuttiphon (user: in docker-compose.yaml). Altrimenti UID:GID come in Lidarr – funziona solo con permessi sufficienti.',
  'Even out loudness':
    'Uniforma il volume',
  'At night Tuttiphon measures how loud each song is and writes ReplayGain values into the files without re-encoding them. Turn on ReplayGain in Symfonium and all songs play equally loud, even in a mix from a children\'s song to metal.':
    'Di notte Tuttiphon misura quanto è forte ogni brano e scrive i valori ReplayGain nei file senza ricodificarli. Attiva ReplayGain in Symfonium e tutti i brani suonano allo stesso volume, anche in un mix che passa da una canzone per bambini al metal.',
  'Leveling on':
    'Uniformazione attiva',
  'Writes once into every music file. Each file is copied and checked first, only then replaced. Values that already came from elsewhere stay.':
    'Scrive una volta in ogni file musicale. Ogni file viene prima copiato e verificato, solo dopo sostituito. I valori che arrivavano già da altre fonti restano.',
  'Album values too':
    'Anche i valori dell\'album',
  'For albums you listen to in one go: quiet and loud songs of an album keep their balance.':
    'Per gli album che ascolti tutti di fila: i brani piano e forte di un album mantengono il loro equilibrio.',
  'Not possible here: {why}. The Docker container on the NAS includes everything.':
    'Non possibile qui: {why}. Il container Docker sul NAS include tutto.',
  '{measured} of {songs} songs measured · {written} with values written':
    '{measured} di {songs} brani misurati · {written} con valori scritti',
  ' · {n} already had their own':
    ' · {n} avevano già i propri',
  'Run now':
    'Esegui ora',
  'Convert now':
    'Converti ora',
  'Dry run':
    'Simulazione',
}
