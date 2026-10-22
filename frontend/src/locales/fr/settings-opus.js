// Same keys as ../de/settings-opus.js
export default {
  'At least one format':
    'Au moins un format',
  'Delete originals?':
    'Supprimer les originaux ?',
  'The lossless originals are deleted after converting instead of archived. This cannot be undone.':
    'Les originaux sans perte seront supprimés après la conversion au lieu d’être archivés. Cette action est irréversible.',
  'Yes, delete':
    'Oui, supprimer',
  'Please enter as UID:GID, e.g. 1000:1000':
    'Veuillez saisir au format UID:GID, par ex. 1000:1000',
  'Convert lossless files':
    'Convertir les fichiers sans perte',
  'Converted music sounds like the original but takes only about a fifth of the space – ideal for phones. Every new file is fully checked before Tuttiphon touches the original; tags and cover are kept.':
    'La musique convertie sonne comme l’original mais n’occupe qu’environ un cinquième de la place – idéal pour les téléphones. Chaque nouveau fichier est entièrement vérifié avant que Tuttiphon ne touche à l’original ; les tags et la pochette sont conservés.',
  'ffmpeg/ffprobe are missing on this computer – please install them. The Docker image includes them.':
    'ffmpeg/ffprobe sont absents de cet ordinateur – veuillez les installer. L’image Docker les inclut.',
  'For AAC, this computer lacks a package that carries the tags over. The Docker image includes everything.':
    'Pour l’AAC, il manque sur cet ordinateur un paquet qui reprend les tags. L’image Docker inclut tout.',
  'Files to convert: {n}':
    'Fichiers à convertir : {n}',
  'Nothing to convert':
    'Rien à convertir',
  'count again':
    'recompter',
  'Music: {music} · Archive: {archive}':
    'Musique : {music} · Archive : {archive}',
  'Conversion on':
    'Conversion activée',
  'Target format':
    'Format cible',
  'Opus is the smallest and ideal for Android. iPhone, iPad and Mac play AAC everywhere. Applies to new conversions; finished files stay as they are.':
    'Opus est le plus compact et idéal pour Android. iPhone, iPad et Mac lisent l’AAC partout. S’applique aux nouvelles conversions ; les fichiers terminés restent tels quels.',
  'Which formats?':
    'Quels formats ?',
  'Lossless only – .m4a only if it contains ALAC.':
    'Sans perte uniquement – .m4a seulement s’il contient de l’ALAC.',
  'Quality':
    'Qualité',
  'kbit/s. AAC needs a little more than Opus for the same sound. 224 is the default, 256 for purists.':
    'kbit/s. L’AAC a besoin d’un peu plus que l’Opus pour le même son. 224 par défaut, 256 pour les puristes.',
  'kbit/s. 128 is enough for phones, 160 is the default, 256 for purists.':
    'kbit/s. 128 suffit pour les téléphones, 160 par défaut, 256 pour les puristes.',
  'Original afterwards':
    'Original ensuite',
  'Only once the new file is fully checked.':
    'Seulement une fois le nouveau fichier entièrement vérifié.',
  'to the archive':
    'vers l’archive',
  'keep':
    'garder',
  'delete':
    'supprimer',
  'Archive folder':
    'Dossier d’archive',
  'The folder structure is kept.':
    'L’arborescence des dossiers est conservée.',
  'Storage locations':
    'Emplacements de stockage',
  'Waiting time':
    'Délai d’attente',
  'Leave freshly imported files alone for this many minutes in case Lidarr is still writing.':
    'Laisser les fichiers fraîchement importés tranquilles pendant ce nombre de minutes, au cas où Lidarr écrirait encore.',
  'Advanced':
    'Avancé',
  'Simultaneous conversions':
    'Conversions simultanées',
  'More = faster, but more load on the computer/NAS.':
    'Plus = plus rapide, mais davantage de charge pour l’ordinateur/le NAS.',
  'Owner of new files':
    'Propriétaire des nouveaux fichiers',
  'Empty = the user Tuttiphon runs as (user: in docker-compose.yaml). Otherwise UID:GID as in Lidarr – only works with sufficient rights.':
    'Vide = l’utilisateur sous lequel tourne Tuttiphon (user: dans docker-compose.yaml). Sinon UID:GID comme dans Lidarr – ne fonctionne qu’avec des droits suffisants.',
  'Even out loudness':
    'Égaliser le volume',
  'At night Tuttiphon measures how loud each song is and writes ReplayGain values into the files without re-encoding them. Turn on ReplayGain in Symfonium and all songs play equally loud, even in a mix from a children\'s song to metal.':
    'La nuit, Tuttiphon mesure le volume de chaque titre et écrit des valeurs ReplayGain dans les fichiers sans les réencoder. Activez ReplayGain dans Symfonium et tous les titres sont joués au même volume, même dans un mix allant d’une chanson pour enfants au metal.',
  'Leveling on':
    'Égalisation activée',
  'Writes once into every music file. Each file is copied and checked first, only then replaced. Values that already came from elsewhere stay.':
    'Écrit une fois dans chaque fichier musical. Chaque fichier est d’abord copié et vérifié, puis seulement remplacé. Les valeurs déjà venues d’ailleurs restent.',
  'Album values too':
    'Valeurs d’album aussi',
  'For albums you listen to in one go: quiet and loud songs of an album keep their balance.':
    'Pour les albums que vous écoutez d’une traite : les titres calmes et forts d’un album gardent leur équilibre.',
  'Not possible here: {why}. The Docker container on the NAS includes everything.':
    'Pas possible ici : {why}. Le conteneur Docker sur le NAS inclut tout.',
  '{measured} of {songs} songs measured · {written} with values written':
    '{measured} titres mesurés sur {songs} · {written} avec valeurs écrites',
  ' · {n} already had their own':
    ' · {n} avaient déjà les leurs',
  'Run now':
    'Lancer maintenant',
  'Convert now':
    'Convertir maintenant',
  'Dry run':
    'Simulation',
}
