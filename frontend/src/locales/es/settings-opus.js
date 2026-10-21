// Same keys as ../de/settings-opus.js
export default {
  'At least one format':
    'Al menos un formato',
  'Delete originals?':
    '¿Eliminar los originales?',
  'The lossless originals are deleted after converting instead of archived. This cannot be undone.':
    'Los originales sin pérdida se eliminan tras la conversión en lugar de archivarse. No se puede deshacer.',
  'Yes, delete':
    'Sí, eliminar',
  'Please enter as UID:GID, e.g. 1000:1000':
    'Indícalo como UID:GID, p. ej. 1000:1000',
  'Convert lossless files':
    'Convertir archivos sin pérdida',
  'Converted music sounds like the original but takes only about a fifth of the space – ideal for phones. Every new file is fully checked before Tuttiphon touches the original; tags and cover are kept.':
    'La música convertida suena como el original, pero ocupa solo una quinta parte del espacio – ideal para el teléfono. Cada archivo nuevo se comprueba por completo antes de que Tuttiphon toque el original; las etiquetas y la portada se conservan.',
  'ffmpeg/ffprobe are missing on this computer – please install them. The Docker image includes them.':
    'Faltan ffmpeg/ffprobe en este equipo – instálalos. La imagen Docker los incluye.',
  'For AAC, this computer lacks a package that carries the tags over. The Docker image includes everything.':
    'Para AAC, a este equipo le falta un paquete que traslade las etiquetas. La imagen Docker lo incluye todo.',
  'Files to convert: {n}':
    'Archivos por convertir: {n}',
  'Nothing to convert':
    'Nada que convertir',
  'count again':
    'volver a contar',
  'Music: {music} · Archive: {archive}':
    'Música: {music} · Archivo: {archive}',
  'Conversion on':
    'Conversión activa',
  'Target format':
    'Formato de destino',
  'Opus is the smallest and ideal for Android. iPhone, iPad and Mac play AAC everywhere. Applies to new conversions; finished files stay as they are.':
    'Opus es el más pequeño e ideal para Android. iPhone, iPad y Mac reproducen AAC en todas partes. Se aplica a las conversiones nuevas; los archivos ya convertidos se quedan como están.',
  'Which formats?':
    '¿Qué formatos?',
  'Lossless only – .m4a only if it contains ALAC.':
    'Solo sin pérdida – .m4a solo si contiene ALAC.',
  'Quality':
    'Calidad',
  'kbit/s. AAC needs a little more than Opus for the same sound. 224 is the default, 256 for purists.':
    'kbit/s. AAC necesita algo más que Opus para el mismo sonido. 224 es el estándar, 256 para puristas.',
  'kbit/s. 128 is enough for phones, 160 is the default, 256 for purists.':
    'kbit/s. 128 basta para el teléfono, 160 es el estándar, 256 para puristas.',
  'Original afterwards':
    'El original después',
  'Only once the new file is fully checked.':
    'Solo cuando el archivo nuevo se ha comprobado por completo.',
  'to the archive':
    'archivar',
  'keep':
    'conservar',
  'delete':
    'eliminar',
  'Archive folder':
    'Carpeta de archivo',
  'The folder structure is kept.':
    'La estructura de carpetas se conserva.',
  'Storage locations':
    'Ubicaciones',
  'Waiting time':
    'Tiempo de espera',
  'Leave freshly imported files alone for this many minutes in case Lidarr is still writing.':
    'Dejar tranquilos durante estos minutos los archivos recién importados, por si Lidarr sigue escribiendo.',
  'Advanced':
    'Avanzado',
  'Simultaneous conversions':
    'Conversiones simultáneas',
  'More = faster, but more load on the computer/NAS.':
    'Más = más rápido, pero más carga para el equipo o el NAS.',
  'Owner of new files':
    'Propietario de los archivos nuevos',
  'Empty = the user Tuttiphon runs as (user: in docker-compose.yaml). Otherwise UID:GID as in Lidarr – only works with sufficient rights.':
    'Vacío = el usuario con el que se ejecuta Tuttiphon (user: en docker-compose.yaml). Si no, UID:GID como en Lidarr – solo funciona con permisos suficientes.',
  'Even out loudness':
    'Igualar el volumen',
  'At night Tuttiphon measures how loud each song is and writes ReplayGain values into the files without re-encoding them. Turn on ReplayGain in Symfonium and all songs play equally loud, even in a mix from a children\'s song to metal.':
    'De noche, Tuttiphon mide lo fuerte que suena cada canción y escribe valores ReplayGain en los archivos sin volver a codificarlos. Activa ReplayGain en Symfonium y todas las canciones sonarán igual de fuerte, incluso en un mix que va de una canción infantil al metal.',
  'Leveling on':
    'Igualación activa',
  'Writes once into every music file. Each file is copied and checked first, only then replaced. Values that already came from elsewhere stay.':
    'Escribe una vez en cada archivo de música. Cada archivo se copia y se comprueba antes, y solo entonces se sustituye. Los valores que ya venían de otro sitio se quedan.',
  'Album values too':
    'También valores de álbum',
  'For albums you listen to in one go: quiet and loud songs of an album keep their balance.':
    'Para álbumes que se escuchan de principio a fin: las canciones suaves y fuertes de un álbum mantienen su equilibrio.',
  'Not possible here: {why}. The Docker container on the NAS includes everything.':
    'Aquí no es posible: {why}. El contenedor Docker del NAS lo incluye todo.',
  '{measured} of {songs} songs measured · {written} with values written':
    '{measured} de {songs} canciones medidas · {written} con valores escritos',
  ' · {n} already had their own':
    ' · {n} ya tenían los suyos',
  'Run now':
    'Ejecutar ahora',
  'Convert now':
    'Convertir ahora',
  'Dry run':
    'Simulación',
}
