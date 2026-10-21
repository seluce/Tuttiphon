// Same keys as ../de/settings-opus.js
export default {
  'At least one format':
    'Pelo menos um formato',
  'Delete originals?':
    'Eliminar os originais?',
  'The lossless originals are deleted after converting instead of archived. This cannot be undone.':
    'Os originais sem perdas são eliminados após a conversão em vez de arquivados. Isto não pode ser anulado.',
  'Yes, delete':
    'Sim, eliminar',
  'Please enter as UID:GID, e.g. 1000:1000':
    'Introduza no formato UID:GID, p. ex. 1000:1000',
  'Convert lossless files':
    'Converter ficheiros sem perdas',
  'Converted music sounds like the original but takes only about a fifth of the space – ideal for phones. Every new file is fully checked before Tuttiphon touches the original; tags and cover are kept.':
    'A música convertida soa como o original, mas ocupa apenas cerca de um quinto do espaço – ideal para telemóveis. Cada ficheiro novo é verificado por completo antes de o Tuttiphon mexer no original; as etiquetas e a capa mantêm-se.',
  'ffmpeg/ffprobe are missing on this computer – please install them. The Docker image includes them.':
    'O ffmpeg/ffprobe não existem neste computador – instale-os. A imagem Docker já os inclui.',
  'For AAC, this computer lacks a package that carries the tags over. The Docker image includes everything.':
    'Para AAC, falta neste computador um pacote que transfere as etiquetas. A imagem Docker inclui tudo.',
  'Files to convert: {n}':
    'Ficheiros a converter: {n}',
  'Nothing to convert':
    'Nada a converter',
  'count again':
    'contar de novo',
  'Music: {music} · Archive: {archive}':
    'Música: {music} · Arquivo: {archive}',
  'Conversion on':
    'Conversão ativa',
  'Target format':
    'Formato de destino',
  'Opus is the smallest and ideal for Android. iPhone, iPad and Mac play AAC everywhere. Applies to new conversions; finished files stay as they are.':
    'O Opus é o mais pequeno e ideal para Android. O iPhone, o iPad e o Mac reproduzem AAC em todo o lado. Aplica-se às novas conversões; os ficheiros já convertidos ficam como estão.',
  'Which formats?':
    'Que formatos?',
  'Lossless only – .m4a only if it contains ALAC.':
    'Só sem perdas – .m4a só se contiver ALAC.',
  'Quality':
    'Qualidade',
  'kbit/s. AAC needs a little more than Opus for the same sound. 224 is the default, 256 for purists.':
    'kbit/s. O AAC precisa de um pouco mais do que o Opus para o mesmo som. 224 é a predefinição, 256 para puristas.',
  'kbit/s. 128 is enough for phones, 160 is the default, 256 for purists.':
    'kbit/s. 128 chega para telemóveis, 160 é a predefinição, 256 para puristas.',
  'Original afterwards':
    'Original depois',
  'Only once the new file is fully checked.':
    'Só quando o ficheiro novo estiver totalmente verificado.',
  'to the archive':
    'para o arquivo',
  'keep':
    'manter',
  'delete':
    'eliminar',
  'Archive folder':
    'Pasta de arquivo',
  'The folder structure is kept.':
    'A estrutura de pastas mantém-se.',
  'Storage locations':
    'Locais de armazenamento',
  'Waiting time':
    'Tempo de espera',
  'Leave freshly imported files alone for this many minutes in case Lidarr is still writing.':
    'Não tocar em ficheiros acabados de importar durante este número de minutos, caso o Lidarr ainda esteja a escrever.',
  'Advanced':
    'Avançado',
  'Simultaneous conversions':
    'Conversões em simultâneo',
  'More = faster, but more load on the computer/NAS.':
    'Mais = mais rápido, mas com mais carga no computador/NAS.',
  'Owner of new files':
    'Proprietário dos ficheiros novos',
  'Empty = the user Tuttiphon runs as (user: in docker-compose.yaml). Otherwise UID:GID as in Lidarr – only works with sufficient rights.':
    'Vazio = o utilizador com que o Tuttiphon corre (user: no docker-compose.yaml). Caso contrário, UID:GID como no Lidarr – só funciona com permissões suficientes.',
  'Even out loudness':
    'Equilibrar o volume',
  'At night Tuttiphon measures how loud each song is and writes ReplayGain values into the files without re-encoding them. Turn on ReplayGain in Symfonium and all songs play equally loud, even in a mix from a children\'s song to metal.':
    'À noite, o Tuttiphon mede o volume de cada música e escreve valores ReplayGain nos ficheiros sem os recodificar. Ative o ReplayGain no Symfonium e todas as músicas tocam com o mesmo volume, mesmo num mix que vai de uma canção infantil ao metal.',
  'Leveling on':
    'Nivelamento ativo',
  'Writes once into every music file. Each file is copied and checked first, only then replaced. Values that already came from elsewhere stay.':
    'Escreve uma vez em cada ficheiro de música. Cada ficheiro é primeiro copiado e verificado e só depois substituído. Os valores que já vieram de outro lado mantêm-se.',
  'Album values too':
    'Também valores de álbum',
  'For albums you listen to in one go: quiet and loud songs of an album keep their balance.':
    'Para álbuns que ouve de seguida: as músicas calmas e as fortes de um álbum mantêm o seu equilíbrio.',
  'Not possible here: {why}. The Docker container on the NAS includes everything.':
    'Não é possível aqui: {why}. O contentor Docker no NAS inclui tudo.',
  '{measured} of {songs} songs measured · {written} with values written':
    '{measured} de {songs} músicas medidas · {written} com valores escritos',
  ' · {n} already had their own':
    ' · {n} já tinham os seus próprios',
  'Run now':
    'Executar agora',
  'Convert now':
    'Converter agora',
  'Dry run':
    'Simulação',
}
