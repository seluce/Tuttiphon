// Same keys as ../de/setup.js
export default {
  'Set up Tuttiphon':
    'Configurar Tuttiphon',
  'Setup assistant':
    'Asistente de configuración',
  'A few questions about what Tuttiphon should do – each with a sensible default. Apart from the connection, nothing changes until you tap “Finish”.':
    'Unas preguntas sobre lo que debe hacer Tuttiphon – cada una con un valor razonable por defecto. Aparte de la conexión, nada cambia hasta que toques «Finalizar».',
  'Skip setup':
    'Saltar la configuración',
  'Summary':
    'Resumen',
  'Finish':
    'Finalizar',
  'Finish and start':
    'Finalizar e iniciar',
  'Skip the setup?':
    '¿Saltar la configuración?',
  'Tuttiphon keeps its current settings. You find everything under Settings – and this assistant under Settings → General.':
    'Tuttiphon mantiene sus ajustes actuales. Todo está en Ajustes – y este asistente, en Ajustes → General.',
  'Everything is under Settings whenever you need it.':
    'Todo está en Ajustes cuando lo necesites.',
  'Setup saved – the first run is starting.':
    'Configuración guardada – se inicia la primera ejecución.',
  'Setup saved ✓':
    'Configuración guardada ✓',
  'Connect to Navidrome':
    'Conectar con Navidrome',
  'Tuttiphon reads your library from Navidrome and writes the playlists back there. For that it needs the address of Navidrome and an admin account – in the background, for scans, playlists and their owners.':
    'Tuttiphon lee tu biblioteca de Navidrome y escribe allí las playlists. Para ello necesita la dirección de Navidrome y una cuenta de administrador – en segundo plano, para escaneos, playlists y sus propietarios.',
  'Connected – Navidrome {version}':
    'Conectado – Navidrome {version}',
  'Tuttiphon cannot reach Navidrome yet: {error}':
    'Tuttiphon aún no puede conectar con Navidrome: {error}',
  'Tuttiphon cannot reach Navidrome yet.':
    'Tuttiphon aún no puede conectar con Navidrome.',
  'The connection is set in docker-compose.yaml – it can only be changed there.':
    'La conexión está definida en docker-compose.yaml – solo se puede cambiar allí.',
  'Change connection':
    'Cambiar conexión',
  'Without a working connection Tuttiphon can neither read your library nor write playlists – so the next steps only make sense once it works. Can’t get it to work right now? Skip the setup and connect later under Settings → Navidrome.':
    'Sin una conexión que funcione, Tuttiphon no puede leer tu biblioteca ni escribir playlists – así que los siguientes pasos solo tienen sentido cuando funcione. ¿No lo consigues ahora? Salta la configuración y conecta más tarde en Ajustes → Navidrome.',
  'Convert lossless files?':
    '¿Convertir archivos sin pérdida?',
  'Lossless files such as FLAC are large. Converted, they sound the same to the ear but take only about a fifth of the space – ideal for phones and for listening offline.':
    'Los archivos sin pérdida como FLAC son grandes. Convertidos suenan igual al oído, pero ocupan solo una quinta parte del espacio – ideal para el teléfono y para escuchar sin conexión.',
  'Your files stay exactly as they are.':
    'Tus archivos se quedan exactamente como están.',
  'Smallest files, ideal for Android · {n} kbit/s':
    'Archivos más pequeños, ideal para Android · {n} kbit/s',
  'For iPhone, iPad and Mac · {n} kbit/s':
    'Para iPhone, iPad y Mac · {n} kbit/s',
  'Converted are the lossless files in the music folder – FLAC, more formats under Settings → Conversion. The first run takes everything that is there, after that only new files. Files fresh from Lidarr get a few minutes of rest first.':
    'Se convierten los archivos sin pérdida de la carpeta de música – FLAC; más formatos en Ajustes → Conversión. La primera ejecución toma todo lo que hay; después, solo los archivos nuevos. Los archivos recién llegados de Lidarr esperan antes unos minutos.',
  'Every new file is checked first: only when it is just as long as the original, to the second, does Tuttiphon touch the original. Tags and cover are kept.':
    'Cada archivo nuevo se comprueba primero: solo si dura exactamente lo mismo que el original, al segundo, Tuttiphon toca el original. Las etiquetas y la portada se conservan.',
  'And the original?':
    '¿Y el original?',
  'Move to the archive':
    'Archivar',
  'The original goes to the archive folder, in the same folder structure. The safest choice – you can always get it back.':
    'El original va a la carpeta de archivo, con la misma estructura de carpetas. La opción más segura – siempre puedes recuperarlo.',
  'The original stays next to the new file. Both are then in your library, and it needs the most space.':
    'El original se queda junto al archivo nuevo. Así ambos están en tu biblioteca, y es lo que más espacio ocupa.',
  'The original is gone for good. Only if you have a backup of your music.':
    'El original desaparece para siempre. Solo si tienes una copia de seguridad de tu música.',
  'The folder does not exist yet – Tuttiphon creates it with the first conversion if it may write there. You can choose another folder under Settings → Storage locations.':
    'La carpeta aún no existe – Tuttiphon la crea en la primera conversión si tiene permiso de escritura. Puedes elegir otra carpeta en Ajustes → Ubicaciones.',
  'Tuttiphon may not write to this folder, so the originals cannot be moved there. Fix the permissions or choose another folder under Settings → Storage locations.':
    'Tuttiphon no tiene permiso para escribir en esta carpeta, así que los originales no se pueden mover allí. Corrige los permisos o elige otra carpeta en Ajustes → Ubicaciones.',
  'Deleted originals cannot be restored – the backup of Tuttiphon contains only its own data, not your music.':
    'Los originales eliminados no se pueden recuperar – la copia de seguridad de Tuttiphon solo contiene sus propios datos, no tu música.',
  'Tuttiphon looks up missing lyrics and saves them as files next to the songs: synced lyrics as .lrc, plain text as .txt. Navidrome reads them at the next scan, and many players show them – Symfonium even line by line while the song plays.':
    'Tuttiphon busca las letras que faltan y las guarda como archivos junto a las canciones: las sincronizadas como .lrc, el texto simple como .txt. Navidrome las lee en el próximo escaneo y muchos reproductores las muestran – Symfonium incluso verso a verso mientras suena la canción.',
  'Only adds files next to the songs – the music files stay untouched.':
    'Solo añade archivos junto a las canciones – los archivos de música no se tocan.',
  'At least one provider must stay on.':
    'Al menos un proveedor debe seguir activo.',
  'Tuttiphon listens to every song – completely locally, without a cloud and without costs. From that come sound vibes such as “Falling asleep”, mixes with smooth transitions and the classification of new bands. It works gently: mostly at night, during the day only a few minutes per run.':
    'Tuttiphon escucha cada canción – en local, sin nube y sin costes. De ahí salen ambientes de sonido como «Para dormir», mixes con transiciones suaves y la clasificación de bandas nuevas. Trabaja con calma: sobre todo de noche; de día, solo unos minutos por ejecución.',
  'Measures tempo, energy, danceability and timbre of every song.':
    'Mide el tempo, la energía, la bailabilidad y el timbre de cada canción.',
  'Also recognizes mood, vocals or instrumental, instruments, themes, key and music style.':
    'Además reconoce estado de ánimo, voz o instrumental, instrumentos, temas, tonalidad y estilo musical.',
  'The AI sound analysis is not installed here – it is part of the Docker image. The measurement works without it.':
    'El análisis de sonido con IA no está instalado aquí – forma parte de la imagen Docker. La medición funciona sin él.',
  'AI sound analysis: {reason} The measurement works without it.':
    'Análisis de sonido con IA: {reason} La medición funciona sin él.',
  'Finds the same recording stored twice – also as another format, in another folder or on another album. About 3 KB per song.':
    'Encuentra la misma grabación guardada dos veces – también en otro formato, en otra carpeta o en otro álbum. Unos 3 KB por canción.',
  'At night Tuttiphon works through whatever is still open, without a time limit. On a NAS the first pass of a large library takes several nights – after that only new songs are left. The nightly Deezer refresh and the weekly cover search also run in this window.':
    'De noche, Tuttiphon procesa lo pendiente sin límite de tiempo. En un NAS, la primera pasada de una biblioteca grande lleva varias noches – después solo quedan las canciones nuevas. En esta franja también se ejecutan la actualización nocturna de Deezer y la búsqueda semanal de portadas.',
  'Start and end must not be the same.':
    'El inicio y el fin no pueden ser iguales.',
  'Star ratings from Deezer':
    'Estrellas de Deezer',
  'Deezer knows how popular almost every song is. Tuttiphon turns that into stars in Navidrome: apps like Symfonium then sort the top tracks of every band correctly, and the “Only the hits” playlists know which songs are the hits. No Deezer account needed.':
    'Deezer sabe lo popular que es casi cada canción. Tuttiphon lo convierte en estrellas en Navidrome: así, apps como Symfonium ordenan bien las canciones top de cada banda, y las playlists «Solo los éxitos» saben qué canciones son los éxitos. No necesitas cuenta de Deezer.',
  'Set stars from Deezer':
    'Poner estrellas de Deezer',
  'New songs are rated during “Update everything”; in the time window of the night analysis a portion is checked again every night.':
    'Las canciones nuevas se valoran durante «Actualizar todo»; en la franja del análisis nocturno se vuelve a comprobar una parte cada noche.',
  'Songs rated by hand':
    'Canciones valoradas a mano',
  'Keep their stars':
    'Conservar sus estrellas',
  'Stars someone gave by hand stay – Deezer only rates the other songs.':
    'Las estrellas puestas a mano se quedan – Deezer solo valora las demás canciones.',
  'Overwrite':
    'Sobrescribir',
  'The Deezer rating replaces stars given by hand too.':
    'La valoración de Deezer también sustituye las estrellas puestas a mano.',
  'Stars given by hand are lost with the next rating – they cannot be restored.':
    'Las estrellas puestas a mano se pierden con la siguiente valoración – no se pueden recuperar.',
  'What should run by itself?':
    '¿Qué debe funcionar automáticamente?',
  'Tuttiphon can keep everything up to date by itself every day – and pick up new music as soon as it lands in the music folder. Both run as long as Tuttiphon is running, ideally in the Docker container on the NAS.':
    'Tuttiphon puede mantenerlo todo al día cada día por sí solo – y procesar la música nueva en cuanto llega a la carpeta de música. Ambas cosas funcionan mientras Tuttiphon esté en marcha, idealmente en el contenedor Docker del NAS.',
  '“Playlists” rebuilds the mixes that are due and switches seasons. “Everything” also runs the steps of “Update everything” – conversion, lyrics, covers, understanding music and Deezer, as far as they are on.':
    '«Playlists» rehace los mixes pendientes y cambia de temporada. «Todo» ejecuta además los pasos de «Actualizar todo» – conversión, letras, portadas, entender la música y Deezer, si están activados.',
  'Anything missed is caught up at the next start.':
    'Lo que se haya perdido se recupera en el próximo inicio.',
  'All set?':
    '¿Todo listo?',
  'This is what Tuttiphon will do. Everything can be changed later under Settings – and this assistant is under Settings → General.':
    'Esto es lo que hará Tuttiphon. Todo se puede cambiar más tarde en Ajustes – y este asistente está en Ajustes → General.',
  'Not connected':
    'Sin conexión',
  'Off – files stay as they are':
    'Desactivado – los archivos se quedan como están',
  'originals to the archive':
    'originales archivados',
  'originals are kept':
    'los originales se conservan',
  'originals are deleted':
    'los originales se eliminan',
  'search with {providers}':
    'búsqueda en {providers}',
  'no search':
    'sin búsqueda',
  'also text only':
    'también solo texto',
  '“text only” is replaced by synced lyrics later':
    '«solo texto» se sustituye más tarde por letras sincronizadas',
  'duplicate lyrics files are deleted':
    'los archivos de letras duplicados se eliminan',
  'measurement and AI · {depth}':
    'medición e IA · {depth}',
  'measurement · {depth}':
    'medición · {depth}',
  'no sound analysis':
    'sin análisis de sonido',
  'audio fingerprints':
    'huellas de audio',
  'at night {from}–{to}':
    'de noche {from}–{to}',
  'no night analysis':
    'sin análisis nocturno',
  'for {accounts}':
    'para {accounts}',
  'no accounts yet':
    'aún no hay cuentas',
  'overwrites stars given by hand':
    'sobrescribe las estrellas puestas a mano',
  'stars given by hand stay':
    'las estrellas puestas a mano se quedan',
  'no daily refresh':
    'sin actualización diaria',
  'every day at {time}: {what}':
    'cada día a las {time}: {what}',
  'everything':
    'todo',
  'folder watch every {n} min':
    'vigilancia de carpetas cada {n} min',
  'no folder watch':
    'sin vigilancia de carpetas',
  'Start the first run now':
    'Iniciar ahora la primera ejecución',
  'Runs “Update everything” once after “Finish”: {steps}. With a large library the first run takes a while – you can follow it on the home page and stop it at any time.':
    'Tras «Finalizar», ejecuta una vez «Actualizar todo»: {steps}. Con una biblioteca grande, la primera ejecución tarda un rato – puedes seguirla en la página de inicio y detenerla cuando quieras.',
  'Only possible with a working connection to Navidrome.':
    'Solo es posible con una conexión a Navidrome que funcione.',
  'Run the setup assistant again':
    'Volver a ejecutar el asistente de configuración',
  'Goes through the most important settings once more: connection, conversion, lyrics, understanding music, Deezer stars and what runs by itself. Apart from the connection, nothing changes until you tap “Finish”.':
    'Repasa de nuevo los ajustes más importantes: conexión, conversión, letras, entender la música, estrellas de Deezer y lo que funciona automáticamente. Aparte de la conexión, nada cambia hasta que toques «Finalizar».',
}
