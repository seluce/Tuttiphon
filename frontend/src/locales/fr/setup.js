// Same keys as ../de/setup.js
export default {
  'Set up Tuttiphon':
    'Configurer Tuttiphon',
  'Setup assistant':
    'Assistant de configuration',
  'A few questions about what Tuttiphon should do – each with a sensible default. Apart from the connection, nothing changes until you tap “Finish”.':
    'Quelques questions sur ce que Tuttiphon doit faire – chacune avec une valeur par défaut raisonnable. À part la connexion, rien ne change tant que vous n’appuyez pas sur « Terminer ».',
  'Skip setup':
    'Passer la configuration',
  'Summary':
    'Récapitulatif',
  'Finish':
    'Terminer',
  'Finish and start':
    'Terminer et démarrer',
  'Skip the setup?':
    'Passer la configuration ?',
  'Tuttiphon keeps its current settings. You find everything under Settings – and this assistant under Settings → General.':
    'Tuttiphon garde ses réglages actuels. Vous trouvez tout sous Paramètres – et cet assistant sous Paramètres → Général.',
  'Everything is under Settings whenever you need it.':
    'Tout se trouve sous Paramètres, dès que vous en avez besoin.',
  'Setup saved – the first run is starting.':
    'Configuration enregistrée – la première exécution démarre.',
  'Setup saved ✓':
    'Configuration enregistrée ✓',
  'Connect to Navidrome':
    'Se connecter à Navidrome',
  'Tuttiphon reads your library from Navidrome and writes the playlists back there. For that it needs the address of Navidrome and an admin account – in the background, for scans, playlists and their owners.':
    'Tuttiphon lit votre bibliothèque depuis Navidrome et y écrit les playlists. Pour cela, il a besoin de l’adresse de Navidrome et d’un compte administrateur – en arrière-plan, pour les scans, les playlists et leurs propriétaires.',
  'Connected – Navidrome {version}':
    'Connecté – Navidrome {version}',
  'Tuttiphon cannot reach Navidrome yet: {error}':
    'Tuttiphon ne parvient pas encore à joindre Navidrome : {error}',
  'Tuttiphon cannot reach Navidrome yet.':
    'Tuttiphon ne parvient pas encore à joindre Navidrome.',
  'The connection is set in docker-compose.yaml – it can only be changed there.':
    'La connexion est définie dans docker-compose.yaml – elle ne peut être modifiée que là.',
  'Change connection':
    'Modifier la connexion',
  'Without a working connection Tuttiphon can neither read your library nor write playlists – so the next steps only make sense once it works. Can’t get it to work right now? Skip the setup and connect later under Settings → Navidrome.':
    'Sans connexion fonctionnelle, Tuttiphon ne peut ni lire votre bibliothèque ni écrire de playlists – les étapes suivantes n’ont donc de sens qu’une fois qu’elle fonctionne. Vous n’y arrivez pas pour l’instant ? Passez la configuration et connectez-vous plus tard sous Paramètres → Navidrome.',
  'Convert lossless files?':
    'Convertir les fichiers sans perte ?',
  'Lossless files such as FLAC are large. Converted, they sound the same to the ear but take only about a fifth of the space – ideal for phones and for listening offline.':
    'Les fichiers sans perte comme le FLAC sont volumineux. Convertis, ils sonnent pareil à l’oreille mais n’occupent qu’environ un cinquième de la place – idéal pour les téléphones et l’écoute hors ligne.',
  'Your files stay exactly as they are.':
    'Vos fichiers restent exactement tels qu’ils sont.',
  'Smallest files, ideal for Android · {n} kbit/s':
    'Fichiers les plus petits, idéal pour Android · {n} kbit/s',
  'For iPhone, iPad and Mac · {n} kbit/s':
    'Pour iPhone, iPad et Mac · {n} kbit/s',
  'Converted are the lossless files in the music folder – FLAC, more formats under Settings → Conversion. The first run takes everything that is there, after that only new files. Files fresh from Lidarr get a few minutes of rest first.':
    'Sont convertis les fichiers sans perte du dossier de musique – FLAC, d’autres formats sous Paramètres → Conversion. La première exécution prend tout ce qui s’y trouve, ensuite seulement les nouveaux fichiers. Les fichiers fraîchement arrivés de Lidarr ont d’abord quelques minutes de repos.',
  'Every new file is checked first: only when it is just as long as the original, to the second, does Tuttiphon touch the original. Tags and cover are kept.':
    'Chaque nouveau fichier est d’abord vérifié : Tuttiphon ne touche à l’original que s’il a exactement la même durée, à la seconde près. Les tags et la pochette sont conservés.',
  'And the original?':
    'Et l’original ?',
  'Move to the archive':
    'Déplacer vers l’archive',
  'The original goes to the archive folder, in the same folder structure. The safest choice – you can always get it back.':
    'L’original va dans le dossier d’archive, avec la même arborescence. Le choix le plus sûr – vous pouvez toujours le récupérer.',
  'The original stays next to the new file. Both are then in your library, and it needs the most space.':
    'L’original reste à côté du nouveau fichier. Les deux sont alors dans votre bibliothèque, et cela prend le plus de place.',
  'The original is gone for good. Only if you have a backup of your music.':
    'L’original disparaît définitivement. Seulement si vous avez une sauvegarde de votre musique.',
  'The folder does not exist yet – Tuttiphon creates it with the first conversion if it may write there. You can choose another folder under Settings → Storage locations.':
    'Le dossier n’existe pas encore – Tuttiphon le crée lors de la première conversion s’il a le droit d’y écrire. Vous pouvez choisir un autre dossier sous Paramètres → Emplacements de stockage.',
  'Tuttiphon may not write to this folder, so the originals cannot be moved there. Fix the permissions or choose another folder under Settings → Storage locations.':
    'Tuttiphon n’a pas le droit d’écrire dans ce dossier, les originaux ne peuvent donc pas y être déplacés. Corrigez les droits ou choisissez un autre dossier sous Paramètres → Emplacements de stockage.',
  'Deleted originals cannot be restored – the backup of Tuttiphon contains only its own data, not your music.':
    'Les originaux supprimés ne peuvent pas être restaurés – la sauvegarde de Tuttiphon ne contient que ses propres données, pas votre musique.',
  'Tuttiphon looks up missing lyrics and saves them as files next to the songs: synced lyrics as .lrc, plain text as .txt. Navidrome reads them at the next scan, and many players show them – Symfonium even line by line while the song plays.':
    'Tuttiphon cherche les paroles manquantes et les enregistre en fichiers à côté des titres : paroles synchronisées en .lrc, texte simple en .txt. Navidrome les lit au prochain scan, et de nombreux lecteurs les affichent – Symfonium même ligne par ligne pendant la lecture.',
  'Only adds files next to the songs – the music files stay untouched.':
    'Ajoute seulement des fichiers à côté des titres – les fichiers musicaux restent intacts.',
  'At least one provider must stay on.':
    'Au moins une source doit rester activée.',
  'Tuttiphon listens to every song – completely locally, without a cloud and without costs. From that come sound vibes such as “Falling asleep”, mixes with smooth transitions and the classification of new bands. It works gently: mostly at night, during the day only a few minutes per run.':
    'Tuttiphon écoute chaque titre – entièrement en local, sans cloud et sans frais. Il en découle des ambiances sonores comme « Pour s’endormir », des mix aux transitions douces et la classification des nouveaux groupes. Il travaille en douceur : surtout la nuit, le jour seulement quelques minutes par exécution.',
  'Measures tempo, energy, danceability and timbre of every song.':
    'Mesure le tempo, l’énergie, la dansabilité et le timbre de chaque titre.',
  'Also recognizes mood, vocals or instrumental, instruments, themes, key and music style.':
    'Reconnaît aussi l’humeur, la voix ou l’instrumental, les instruments, les thèmes, la tonalité et le style musical.',
  'The AI sound analysis is not installed here – it is part of the Docker image. The measurement works without it.':
    'L’analyse sonore par IA n’est pas installée ici – elle fait partie de l’image Docker. La mesure fonctionne sans elle.',
  'AI sound analysis: {reason} The measurement works without it.':
    'Analyse sonore par IA : {reason} La mesure fonctionne sans elle.',
  'Finds the same recording stored twice – also as another format, in another folder or on another album. About 3 KB per song.':
    'Trouve le même enregistrement stocké en double – aussi dans un autre format, dans un autre dossier ou sur un autre album. Environ 3 Ko par titre.',
  'At night Tuttiphon works through whatever is still open, without a time limit. On a NAS the first pass of a large library takes several nights – after that only new songs are left. The nightly Deezer refresh and the weekly cover search also run in this window.':
    'La nuit, Tuttiphon traite tout ce qui reste à faire, sans limite de temps. Sur un NAS, le premier passage d’une grande bibliothèque prend plusieurs nuits – ensuite, il ne reste que les nouveaux titres. L’actualisation Deezer nocturne et la recherche hebdomadaire de pochettes ont aussi lieu dans cette plage.',
  'Start and end must not be the same.':
    'Le début et la fin ne doivent pas être identiques.',
  'Star ratings from Deezer':
    'Notes en étoiles de Deezer',
  'Deezer knows how popular almost every song is. Tuttiphon turns that into stars in Navidrome: apps like Symfonium then sort the top tracks of every band correctly, and the “Only the hits” playlists know which songs are the hits. No Deezer account needed.':
    'Deezer sait à quel point presque chaque titre est populaire. Tuttiphon en fait des étoiles dans Navidrome : des apps comme Symfonium trient alors correctement les titres phares de chaque groupe, et les playlists « Seulement les tubes » savent quels titres sont les tubes. Aucun compte Deezer nécessaire.',
  'Set stars from Deezer':
    'Attribuer les étoiles depuis Deezer',
  'New songs are rated during “Update everything”; in the time window of the night analysis a portion is checked again every night.':
    'Les nouveaux titres sont notés pendant « Tout mettre à jour » ; dans la plage horaire de l’analyse nocturne, une partie est revérifiée chaque nuit.',
  'Songs rated by hand':
    'Titres notés à la main',
  'Keep their stars':
    'Garder leurs étoiles',
  'Stars someone gave by hand stay – Deezer only rates the other songs.':
    'Les étoiles données à la main restent – Deezer note seulement les autres titres.',
  'Overwrite':
    'Écraser',
  'The Deezer rating replaces stars given by hand too.':
    'La notation Deezer remplace aussi les étoiles données à la main.',
  'Stars given by hand are lost with the next rating – they cannot be restored.':
    'Les étoiles données à la main sont perdues à la prochaine notation – elles ne peuvent pas être restaurées.',
  'What should run by itself?':
    'Que doit-il se passer tout seul ?',
  'Tuttiphon can keep everything up to date by itself every day – and pick up new music as soon as it lands in the music folder. Both run as long as Tuttiphon is running, ideally in the Docker container on the NAS.':
    'Tuttiphon peut tout tenir à jour de lui-même chaque jour – et prendre en compte la nouvelle musique dès qu’elle arrive dans le dossier de musique. Les deux fonctionnent tant que Tuttiphon tourne, idéalement dans le conteneur Docker sur le NAS.',
  '“Playlists” rebuilds the mixes that are due and switches seasons. “Everything” also runs the steps of “Update everything” – conversion, lyrics, covers, understanding music and Deezer, as far as they are on.':
    '« Playlists » reconstruit les mix arrivés à échéance et change de saison. « Tout » exécute aussi les étapes de « Tout mettre à jour » – conversion, paroles, pochettes, compréhension de la musique et Deezer, dans la mesure où elles sont activées.',
  'Anything missed is caught up at the next start.':
    'Ce qui a été manqué est rattrapé au prochain démarrage.',
  'All set?':
    'Tout est prêt ?',
  'This is what Tuttiphon will do. Everything can be changed later under Settings – and this assistant is under Settings → General.':
    'Voici ce que Tuttiphon va faire. Tout peut être modifié plus tard sous Paramètres – et cet assistant se trouve sous Paramètres → Général.',
  'Not connected':
    'Non connecté',
  'Off – files stay as they are':
    'Désactivé – les fichiers restent tels quels',
  'originals to the archive':
    'originaux vers l’archive',
  'originals are kept':
    'les originaux sont conservés',
  'originals are deleted':
    'les originaux sont supprimés',
  'search with {providers}':
    'recherche avec {providers}',
  'no search':
    'pas de recherche',
  'also text only':
    'aussi texte seul',
  '“text only” is replaced by synced lyrics later':
    'le « texte seul » est remplacé plus tard par des paroles synchronisées',
  'duplicate lyrics files are deleted':
    'les fichiers de paroles en double sont supprimés',
  'measurement and AI · {depth}':
    'mesure et IA · {depth}',
  'measurement · {depth}':
    'mesure · {depth}',
  'no sound analysis':
    'pas d’analyse sonore',
  'audio fingerprints':
    'empreintes audio',
  'at night {from}–{to}':
    'la nuit {from}–{to}',
  'no night analysis':
    'pas d’analyse nocturne',
  'for {accounts}':
    'pour {accounts}',
  'no accounts yet':
    'pas encore de comptes',
  'overwrites stars given by hand':
    'écrase les étoiles données à la main',
  'stars given by hand stay':
    'les étoiles données à la main restent',
  'no daily refresh':
    'pas d’actualisation quotidienne',
  'every day at {time}: {what}':
    'chaque jour à {time} : {what}',
  'everything':
    'tout',
  'folder watch every {n} min':
    'surveillance des dossiers toutes les {n} min',
  'no folder watch':
    'pas de surveillance des dossiers',
  'Start the first run now':
    'Lancer la première exécution maintenant',
  'Runs “Update everything” once after “Finish”: {steps}. With a large library the first run takes a while – you can follow it on the home page and stop it at any time.':
    'Exécute une fois « Tout mettre à jour » après « Terminer » : {steps}. Avec une grande bibliothèque, la première exécution prend un moment – vous pouvez la suivre sur la page d’accueil et l’arrêter à tout moment.',
  'Only possible with a working connection to Navidrome.':
    'Possible seulement avec une connexion fonctionnelle à Navidrome.',
  'Run the setup assistant again':
    'Relancer l’assistant de configuration',
  'Goes through the most important settings once more: connection, conversion, lyrics, understanding music, Deezer stars and what runs by itself. Apart from the connection, nothing changes until you tap “Finish”.':
    'Reparcourt les réglages les plus importants : connexion, conversion, paroles, comprendre la musique, étoiles Deezer et ce qui tourne tout seul. À part la connexion, rien ne change tant que vous n’appuyez pas sur « Terminer ».',
}
