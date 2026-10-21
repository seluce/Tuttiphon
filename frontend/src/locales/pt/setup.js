// Same keys as ../de/setup.js
export default {
  'Set up Tuttiphon':
    'Configurar o Tuttiphon',
  'Setup assistant':
    'Assistente de configuração',
  'A few questions about what Tuttiphon should do – each with a sensible default. Apart from the connection, nothing changes until you tap “Finish”.':
    'Algumas perguntas sobre o que o Tuttiphon deve fazer – cada uma com uma predefinição sensata. Além da ligação, nada muda até tocar em «Concluir».',
  'Skip setup':
    'Saltar a configuração',
  'Summary':
    'Resumo',
  'Finish':
    'Concluir',
  'Finish and start':
    'Concluir e iniciar',
  'Skip the setup?':
    'Saltar a configuração?',
  'Tuttiphon keeps its current settings. You find everything under Settings – and this assistant under Settings → General.':
    'O Tuttiphon mantém as definições atuais. Encontra tudo em Definições – e este assistente em Definições → Geral.',
  'Everything is under Settings whenever you need it.':
    'Está tudo em Definições sempre que precisar.',
  'Setup saved – the first run is starting.':
    'Configuração guardada – a primeira execução está a começar.',
  'Setup saved ✓':
    'Configuração guardada ✓',
  'Connect to Navidrome':
    'Ligar ao Navidrome',
  'Tuttiphon reads your library from Navidrome and writes the playlists back there. For that it needs the address of Navidrome and an admin account – in the background, for scans, playlists and their owners.':
    'O Tuttiphon lê a sua biblioteca a partir do Navidrome e escreve lá as playlists. Para isso precisa do endereço do Navidrome e de uma conta de administrador – em segundo plano, para verificações, playlists e os seus proprietários.',
  'Connected – Navidrome {version}':
    'Ligado – Navidrome {version}',
  'Tuttiphon cannot reach Navidrome yet: {error}':
    'O Tuttiphon ainda não consegue aceder ao Navidrome: {error}',
  'Tuttiphon cannot reach Navidrome yet.':
    'O Tuttiphon ainda não consegue aceder ao Navidrome.',
  'The connection is set in docker-compose.yaml – it can only be changed there.':
    'A ligação está definida no docker-compose.yaml – só pode ser alterada lá.',
  'Change connection':
    'Alterar ligação',
  'Without a working connection Tuttiphon can neither read your library nor write playlists – so the next steps only make sense once it works. Can’t get it to work right now? Skip the setup and connect later under Settings → Navidrome.':
    'Sem uma ligação a funcionar, o Tuttiphon não consegue ler a sua biblioteca nem escrever playlists – por isso, os passos seguintes só fazem sentido quando funcionar. Não consegue pô-la a funcionar agora? Salte a configuração e ligue mais tarde em Definições → Navidrome.',
  'Convert lossless files?':
    'Converter ficheiros sem perdas?',
  'Lossless files such as FLAC are large. Converted, they sound the same to the ear but take only about a fifth of the space – ideal for phones and for listening offline.':
    'Os ficheiros sem perdas, como FLAC, são grandes. Convertidos, soam iguais ao ouvido, mas ocupam apenas cerca de um quinto do espaço – ideal para telemóveis e para ouvir offline.',
  'Your files stay exactly as they are.':
    'Os seus ficheiros ficam exatamente como estão.',
  'Smallest files, ideal for Android · {n} kbit/s':
    'Ficheiros mais pequenos, ideal para Android · {n} kbit/s',
  'For iPhone, iPad and Mac · {n} kbit/s':
    'Para iPhone, iPad e Mac · {n} kbit/s',
  'Converted are the lossless files in the music folder – FLAC, more formats under Settings → Conversion. The first run takes everything that is there, after that only new files. Files fresh from Lidarr get a few minutes of rest first.':
    'São convertidos os ficheiros sem perdas da pasta de música – FLAC, mais formatos em Definições → Conversão. A primeira execução trata de tudo o que lá está; depois, apenas de ficheiros novos. Os ficheiros acabados de chegar do Lidarr ficam primeiro uns minutos em repouso.',
  'Every new file is checked first: only when it is just as long as the original, to the second, does Tuttiphon touch the original. Tags and cover are kept.':
    'Cada ficheiro novo é verificado primeiro: só quando tem exatamente a mesma duração que o original, ao segundo, é que o Tuttiphon mexe no original. As etiquetas e a capa mantêm-se.',
  'And the original?':
    'E o original?',
  'Move to the archive':
    'Mover para o arquivo',
  'The original goes to the archive folder, in the same folder structure. The safest choice – you can always get it back.':
    'O original vai para a pasta de arquivo, com a mesma estrutura de pastas. A opção mais segura – pode sempre recuperá-lo.',
  'The original stays next to the new file. Both are then in your library, and it needs the most space.':
    'O original fica ao lado do ficheiro novo. Ficam ambos na sua biblioteca, e é o que ocupa mais espaço.',
  'The original is gone for good. Only if you have a backup of your music.':
    'O original desaparece para sempre. Só se tiver uma cópia de segurança da sua música.',
  'The folder does not exist yet – Tuttiphon creates it with the first conversion if it may write there. You can choose another folder under Settings → Storage locations.':
    'A pasta ainda não existe – o Tuttiphon cria-a na primeira conversão, se puder escrever lá. Pode escolher outra pasta em Definições → Locais de armazenamento.',
  'Tuttiphon may not write to this folder, so the originals cannot be moved there. Fix the permissions or choose another folder under Settings → Storage locations.':
    'O Tuttiphon não pode escrever nesta pasta, por isso os originais não podem ser movidos para lá. Corrija as permissões ou escolha outra pasta em Definições → Locais de armazenamento.',
  'Deleted originals cannot be restored – the backup of Tuttiphon contains only its own data, not your music.':
    'Os originais eliminados não podem ser restaurados – a cópia de segurança do Tuttiphon contém apenas os seus próprios dados, não a sua música.',
  'Tuttiphon looks up missing lyrics and saves them as files next to the songs: synced lyrics as .lrc, plain text as .txt. Navidrome reads them at the next scan, and many players show them – Symfonium even line by line while the song plays.':
    'O Tuttiphon procura as letras em falta e guarda-as como ficheiros ao lado das músicas: letras sincronizadas como .lrc, texto simples como .txt. O Navidrome lê-as na verificação seguinte e muitos leitores mostram-nas – o Symfonium até verso a verso enquanto a música toca.',
  'Only adds files next to the songs – the music files stay untouched.':
    'Só adiciona ficheiros ao lado das músicas – os ficheiros de música ficam intactos.',
  'At least one provider must stay on.':
    'Pelo menos um fornecedor tem de ficar ativo.',
  'Tuttiphon listens to every song – completely locally, without a cloud and without costs. From that come sound vibes such as “Falling asleep”, mixes with smooth transitions and the classification of new bands. It works gently: mostly at night, during the day only a few minutes per run.':
    'O Tuttiphon ouve cada música – totalmente em local, sem nuvem e sem custos. Daí nascem ambientes sonoros como «Para adormecer», mixes com transições suaves e a classificação de bandas novas. Trabalha com cuidado: sobretudo à noite; durante o dia, só alguns minutos por execução.',
  'Measures tempo, energy, danceability and timbre of every song.':
    'Mede o andamento, a energia, a dançabilidade e o timbre de cada música.',
  'Also recognizes mood, vocals or instrumental, instruments, themes, key and music style.':
    'Reconhece também o estado de espírito, voz ou instrumental, instrumentos, temas, tonalidade e estilo musical.',
  'The AI sound analysis is not installed here – it is part of the Docker image. The measurement works without it.':
    'A análise de som com IA não está instalada aqui – faz parte da imagem Docker. A medição funciona sem ela.',
  'AI sound analysis: {reason} The measurement works without it.':
    'Análise de som com IA: {reason} A medição funciona sem ela.',
  'Finds the same recording stored twice – also as another format, in another folder or on another album. About 3 KB per song.':
    'Encontra a mesma gravação guardada duas vezes – também noutro formato, noutra pasta ou noutro álbum. Cerca de 3 KB por música.',
  'At night Tuttiphon works through whatever is still open, without a time limit. On a NAS the first pass of a large library takes several nights – after that only new songs are left. The nightly Deezer refresh and the weekly cover search also run in this window.':
    'À noite, o Tuttiphon trata de tudo o que ainda está pendente, sem limite de tempo. Num NAS, a primeira passagem de uma biblioteca grande demora várias noites – depois só restam as músicas novas. A atualização noturna do Deezer e a procura semanal de capas também correm neste intervalo.',
  'Start and end must not be the same.':
    'O início e o fim não podem ser iguais.',
  'Star ratings from Deezer':
    'Classificações por estrelas do Deezer',
  'Deezer knows how popular almost every song is. Tuttiphon turns that into stars in Navidrome: apps like Symfonium then sort the top tracks of every band correctly, and the “Only the hits” playlists know which songs are the hits. No Deezer account needed.':
    'O Deezer sabe quão popular é quase cada música. O Tuttiphon transforma isso em estrelas no Navidrome: apps como o Symfonium ordenam então corretamente as melhores faixas de cada banda, e as playlists «Só os êxitos» sabem quais são os êxitos. Não é preciso conta Deezer.',
  'Set stars from Deezer':
    'Atribuir estrelas do Deezer',
  'New songs are rated during “Update everything”; in the time window of the night analysis a portion is checked again every night.':
    'As músicas novas são classificadas durante «Atualizar tudo»; no intervalo da análise noturna, uma parte é verificada de novo todas as noites.',
  'Songs rated by hand':
    'Músicas classificadas à mão',
  'Keep their stars':
    'Manter as estrelas',
  'Stars someone gave by hand stay – Deezer only rates the other songs.':
    'As estrelas dadas à mão ficam – o Deezer só classifica as outras músicas.',
  'Overwrite':
    'Substituir',
  'The Deezer rating replaces stars given by hand too.':
    'A classificação do Deezer substitui também as estrelas dadas à mão.',
  'Stars given by hand are lost with the next rating – they cannot be restored.':
    'As estrelas dadas à mão perdem-se na classificação seguinte – não podem ser restauradas.',
  'What should run by itself?':
    'O que deve correr sozinho?',
  'Tuttiphon can keep everything up to date by itself every day – and pick up new music as soon as it lands in the music folder. Both run as long as Tuttiphon is running, ideally in the Docker container on the NAS.':
    'O Tuttiphon pode manter tudo atualizado sozinho todos os dias – e apanhar música nova assim que chega à pasta de música. Ambos funcionam enquanto o Tuttiphon estiver a correr, idealmente no contentor Docker do NAS.',
  '“Playlists” rebuilds the mixes that are due and switches seasons. “Everything” also runs the steps of “Update everything” – conversion, lyrics, covers, understanding music and Deezer, as far as they are on.':
    '«Playlists» reconstrói os mixes pendentes e muda as épocas. «Tudo» corre também os passos de «Atualizar tudo» – conversão, letras, capas, compreender a música e Deezer, desde que estejam ativos.',
  'Anything missed is caught up at the next start.':
    'O que ficar por fazer é recuperado no arranque seguinte.',
  'All set?':
    'Tudo pronto?',
  'This is what Tuttiphon will do. Everything can be changed later under Settings – and this assistant is under Settings → General.':
    'É isto que o Tuttiphon vai fazer. Tudo pode ser alterado mais tarde em Definições – e este assistente está em Definições → Geral.',
  'Not connected':
    'Não ligado',
  'Off – files stay as they are':
    'Desativado – os ficheiros ficam como estão',
  'originals to the archive':
    'originais para o arquivo',
  'originals are kept':
    'os originais são mantidos',
  'originals are deleted':
    'os originais são eliminados',
  'search with {providers}':
    'procurar com {providers}',
  'no search':
    'sem procura',
  'also text only':
    'também só texto',
  '“text only” is replaced by synced lyrics later':
    '«só texto» é substituído mais tarde por letras sincronizadas',
  'duplicate lyrics files are deleted':
    'os ficheiros de letras duplicados são eliminados',
  'measurement and AI · {depth}':
    'medição e IA · {depth}',
  'measurement · {depth}':
    'medição · {depth}',
  'no sound analysis':
    'sem análise de som',
  'audio fingerprints':
    'impressões digitais de áudio',
  'at night {from}–{to}':
    'à noite, {from}–{to}',
  'no night analysis':
    'sem análise noturna',
  'for {accounts}':
    'para {accounts}',
  'no accounts yet':
    'ainda sem contas',
  'overwrites stars given by hand':
    'substitui as estrelas dadas à mão',
  'stars given by hand stay':
    'as estrelas dadas à mão ficam',
  'no daily refresh':
    'sem atualização diária',
  'every day at {time}: {what}':
    'todos os dias às {time}: {what}',
  'everything':
    'tudo',
  'folder watch every {n} min':
    'vigilância de pastas a cada {n} min',
  'no folder watch':
    'sem vigilância de pastas',
  'Start the first run now':
    'Iniciar já a primeira execução',
  'Runs “Update everything” once after “Finish”: {steps}. With a large library the first run takes a while – you can follow it on the home page and stop it at any time.':
    'Executa «Atualizar tudo» uma vez após «Concluir»: {steps}. Com uma biblioteca grande, a primeira execução demora algum tempo – pode acompanhá-la na página inicial e pará-la a qualquer momento.',
  'Only possible with a working connection to Navidrome.':
    'Só é possível com uma ligação ao Navidrome a funcionar.',
  'Run the setup assistant again':
    'Executar de novo o assistente de configuração',
  'Goes through the most important settings once more: connection, conversion, lyrics, understanding music, Deezer stars and what runs by itself. Apart from the connection, nothing changes until you tap “Finish”.':
    'Percorre de novo as definições mais importantes: ligação, conversão, letras, compreender a música, estrelas do Deezer e o que corre sozinho. Além da ligação, nada muda até tocar em «Concluir».',
}
