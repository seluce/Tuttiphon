// Same keys as ../de/setup.js
export default {
  'Set up Tuttiphon':
    'Configura Tuttiphon',
  'Setup assistant':
    'Configurazione guidata',
  'A few questions about what Tuttiphon should do – each with a sensible default. Apart from the connection, nothing changes until you tap “Finish”.':
    'Qualche domanda su cosa deve fare Tuttiphon – ognuna con un\'impostazione predefinita sensata. A parte la connessione, non cambia nulla finché non tocchi «Fine».',
  'Skip setup':
    'Salta la configurazione',
  'Summary':
    'Riepilogo',
  'Finish':
    'Fine',
  'Finish and start':
    'Fine e avvia',
  'Skip the setup?':
    'Saltare la configurazione?',
  'Tuttiphon keeps its current settings. You find everything under Settings – and this assistant under Settings → General.':
    'Tuttiphon mantiene le impostazioni attuali. Trovi tutto in Impostazioni – e questa configurazione guidata in Impostazioni → Generali.',
  'Everything is under Settings whenever you need it.':
    'Trovi tutto in Impostazioni, quando ti serve.',
  'Setup saved – the first run is starting.':
    'Configurazione salvata – la prima esecuzione sta partendo.',
  'Setup saved ✓':
    'Configurazione salvata ✓',
  'Connect to Navidrome':
    'Connetti a Navidrome',
  'Tuttiphon reads your library from Navidrome and writes the playlists back there. For that it needs the address of Navidrome and an admin account – in the background, for scans, playlists and their owners.':
    'Tuttiphon legge la tua libreria da Navidrome e vi riscrive le playlist. Per questo ha bisogno dell\'indirizzo di Navidrome e di un account amministratore – in background, per scansioni, playlist e i loro proprietari.',
  'Connected – Navidrome {version}':
    'Connesso – Navidrome {version}',
  'Tuttiphon cannot reach Navidrome yet: {error}':
    'Tuttiphon non riesce ancora a raggiungere Navidrome: {error}',
  'Tuttiphon cannot reach Navidrome yet.':
    'Tuttiphon non riesce ancora a raggiungere Navidrome.',
  'The connection is set in docker-compose.yaml – it can only be changed there.':
    'La connessione è impostata in docker-compose.yaml – si può cambiare solo lì.',
  'Change connection':
    'Cambia connessione',
  'Without a working connection Tuttiphon can neither read your library nor write playlists – so the next steps only make sense once it works. Can’t get it to work right now? Skip the setup and connect later under Settings → Navidrome.':
    'Senza una connessione funzionante Tuttiphon non può né leggere la tua libreria né scrivere playlist – quindi i passaggi successivi hanno senso solo quando funziona. Non riesci a farla funzionare adesso? Salta la configurazione e connettiti più tardi in Impostazioni → Navidrome.',
  'Convert lossless files?':
    'Convertire i file lossless?',
  'Lossless files such as FLAC are large. Converted, they sound the same to the ear but take only about a fifth of the space – ideal for phones and for listening offline.':
    'I file lossless come FLAC sono grandi. Convertiti suonano uguali all\'orecchio ma occupano solo circa un quinto dello spazio – ideale per i telefoni e per l\'ascolto offline.',
  'Your files stay exactly as they are.':
    'I tuoi file restano esattamente come sono.',
  'Smallest files, ideal for Android · {n} kbit/s':
    'File più piccoli, ideale per Android · {n} kbit/s',
  'For iPhone, iPad and Mac · {n} kbit/s':
    'Per iPhone, iPad e Mac · {n} kbit/s',
  'Converted are the lossless files in the music folder – FLAC, more formats under Settings → Conversion. The first run takes everything that is there, after that only new files. Files fresh from Lidarr get a few minutes of rest first.':
    'Vengono convertiti i file lossless nella cartella della musica – FLAC, altri formati in Impostazioni → Conversione. La prima esecuzione prende tutto ciò che c\'è, poi solo i nuovi file. I file appena arrivati da Lidarr hanno prima qualche minuto di tregua.',
  'Every new file is checked first: only when it is just as long as the original, to the second, does Tuttiphon touch the original. Tags and cover are kept.':
    'Ogni nuovo file viene prima verificato: solo se dura esattamente quanto l\'originale, al secondo, Tuttiphon tocca l\'originale. Tag e copertina vengono mantenuti.',
  'And the original?':
    'E l\'originale?',
  'Move to the archive':
    'Sposta nell\'archivio',
  'The original goes to the archive folder, in the same folder structure. The safest choice – you can always get it back.':
    'L\'originale va nella cartella dell\'archivio, con la stessa struttura di cartelle. La scelta più sicura – puoi sempre recuperarlo.',
  'The original stays next to the new file. Both are then in your library, and it needs the most space.':
    'L\'originale resta accanto al nuovo file. Così entrambi sono nella tua libreria, e serve più spazio.',
  'The original is gone for good. Only if you have a backup of your music.':
    'L\'originale sparisce per sempre. Solo se hai un backup della tua musica.',
  'The folder does not exist yet – Tuttiphon creates it with the first conversion if it may write there. You can choose another folder under Settings → Storage locations.':
    'La cartella non esiste ancora – Tuttiphon la crea alla prima conversione, se può scrivere lì. Puoi scegliere un\'altra cartella in Impostazioni → Percorsi.',
  'Tuttiphon may not write to this folder, so the originals cannot be moved there. Fix the permissions or choose another folder under Settings → Storage locations.':
    'Tuttiphon non può scrivere in questa cartella, quindi gli originali non possono essere spostati lì. Correggi i permessi o scegli un\'altra cartella in Impostazioni → Percorsi.',
  'Deleted originals cannot be restored – the backup of Tuttiphon contains only its own data, not your music.':
    'Gli originali eliminati non si possono ripristinare – il backup di Tuttiphon contiene solo i suoi dati, non la tua musica.',
  'Tuttiphon looks up missing lyrics and saves them as files next to the songs: synced lyrics as .lrc, plain text as .txt. Navidrome reads them at the next scan, and many players show them – Symfonium even line by line while the song plays.':
    'Tuttiphon cerca i testi mancanti e li salva come file accanto ai brani: i testi sincronizzati come .lrc, il testo semplice come .txt. Navidrome li legge alla scansione successiva e molti player li mostrano – Symfonium addirittura riga per riga mentre il brano suona.',
  'Only adds files next to the songs – the music files stay untouched.':
    'Aggiunge solo file accanto ai brani – i file musicali restano intatti.',
  'At least one provider must stay on.':
    'Almeno un fornitore deve restare attivo.',
  'Tuttiphon listens to every song – completely locally, without a cloud and without costs. From that come sound vibes such as “Falling asleep”, mixes with smooth transitions and the classification of new bands. It works gently: mostly at night, during the day only a few minutes per run.':
    'Tuttiphon ascolta ogni brano – completamente in locale, senza cloud e senza costi. Ne nascono atmosfere sonore come «Per addormentarsi», mix con transizioni morbide e la classificazione delle nuove band. Lavora con delicatezza: soprattutto di notte, di giorno solo pochi minuti per esecuzione.',
  'Measures tempo, energy, danceability and timbre of every song.':
    'Misura tempo, energia, ballabilità e timbro di ogni brano.',
  'Also recognizes mood, vocals or instrumental, instruments, themes, key and music style.':
    'Riconosce anche mood, voce o strumentale, strumenti, temi, tonalità e stile musicale.',
  'The AI sound analysis is not installed here – it is part of the Docker image. The measurement works without it.':
    'Qui l\'analisi del suono con IA non è installata – fa parte dell\'immagine Docker. La misurazione funziona anche senza.',
  'AI sound analysis: {reason} The measurement works without it.':
    'Analisi del suono con IA: {reason} La misurazione funziona anche senza.',
  'Finds the same recording stored twice – also as another format, in another folder or on another album. About 3 KB per song.':
    'Trova la stessa registrazione salvata due volte – anche in un altro formato, in un\'altra cartella o in un altro album. Circa 3 KB per brano.',
  'At night Tuttiphon works through whatever is still open, without a time limit. On a NAS the first pass of a large library takes several nights – after that only new songs are left. The nightly Deezer refresh and the weekly cover search also run in this window.':
    'Di notte Tuttiphon elabora, senza limite di tempo, ciò che resta da fare. Su un NAS il primo passaggio di una grande libreria richiede diverse notti – poi restano solo i nuovi brani. In questa fascia oraria si svolgono anche l\'aggiornamento notturno di Deezer e la ricerca settimanale delle copertine.',
  'Start and end must not be the same.':
    'Inizio e fine non possono coincidere.',
  'Star ratings from Deezer':
    'Stelle da Deezer',
  'Deezer knows how popular almost every song is. Tuttiphon turns that into stars in Navidrome: apps like Symfonium then sort the top tracks of every band correctly, and the “Only the hits” playlists know which songs are the hits. No Deezer account needed.':
    'Deezer sa quanto è popolare quasi ogni brano. Tuttiphon lo trasforma in stelle in Navidrome: app come Symfonium ordinano così correttamente i brani top di ogni band, e le playlist «Solo le hit» sanno quali brani sono le hit. Non serve un account Deezer.',
  'Set stars from Deezer':
    'Assegna stelle da Deezer',
  'New songs are rated during “Update everything”; in the time window of the night analysis a portion is checked again every night.':
    'I nuovi brani vengono valutati durante «Aggiorna tutto»; nella fascia oraria dell\'analisi notturna una parte viene ricontrollata ogni notte.',
  'Songs rated by hand':
    'Brani valutati a mano',
  'Keep their stars':
    'Mantieni le loro stelle',
  'Stars someone gave by hand stay – Deezer only rates the other songs.':
    'Le stelle date a mano da qualcuno restano – Deezer valuta solo gli altri brani.',
  'Overwrite':
    'Sovrascrivi',
  'The Deezer rating replaces stars given by hand too.':
    'La valutazione Deezer sostituisce anche le stelle date a mano.',
  'Stars given by hand are lost with the next rating – they cannot be restored.':
    'Le stelle date a mano vanno perse con la valutazione successiva – non si possono ripristinare.',
  'What should run by itself?':
    'Cosa deve funzionare da solo?',
  'Tuttiphon can keep everything up to date by itself every day – and pick up new music as soon as it lands in the music folder. Both run as long as Tuttiphon is running, ideally in the Docker container on the NAS.':
    'Tuttiphon può tenere tutto aggiornato da solo ogni giorno – e prendere la nuova musica appena arriva nella cartella della musica. Entrambi funzionano finché Tuttiphon è in esecuzione, meglio nel container Docker sul NAS.',
  '“Playlists” rebuilds the mixes that are due and switches seasons. “Everything” also runs the steps of “Update everything” – conversion, lyrics, covers, understanding music and Deezer, as far as they are on.':
    '«Playlist» ricompone i mix in scadenza e cambia le stagioni. «Tutto» esegue anche i passaggi di «Aggiorna tutto» – conversione, testi, copertine, capire la musica e Deezer, per quanto attivi.',
  'Anything missed is caught up at the next start.':
    'Ciò che è stato saltato viene recuperato al prossimo avvio.',
  'All set?':
    'Tutto pronto?',
  'This is what Tuttiphon will do. Everything can be changed later under Settings – and this assistant is under Settings → General.':
    'Ecco cosa farà Tuttiphon. Tutto si può cambiare più tardi in Impostazioni – e questa configurazione guidata è in Impostazioni → Generali.',
  'Not connected':
    'Non connesso',
  'Off – files stay as they are':
    'Disattivata – i file restano come sono',
  'originals to the archive':
    'originali nell\'archivio',
  'originals are kept':
    'gli originali restano',
  'originals are deleted':
    'gli originali vengono eliminati',
  'search with {providers}':
    'ricerca su {providers}',
  'no search':
    'nessuna ricerca',
  'also text only':
    'anche solo testo',
  '“text only” is replaced by synced lyrics later':
    '«solo testo» viene sostituito più tardi da testi sincronizzati',
  'duplicate lyrics files are deleted':
    'i file di testo doppi vengono eliminati',
  'measurement and AI · {depth}':
    'misurazione e IA · {depth}',
  'measurement · {depth}':
    'misurazione · {depth}',
  'no sound analysis':
    'nessuna analisi del suono',
  'audio fingerprints':
    'impronte audio',
  'at night {from}–{to}':
    'di notte {from}–{to}',
  'no night analysis':
    'nessuna analisi notturna',
  'for {accounts}':
    'per {accounts}',
  'no accounts yet':
    'ancora nessun account',
  'overwrites stars given by hand':
    'sovrascrive le stelle date a mano',
  'stars given by hand stay':
    'le stelle date a mano restano',
  'no daily refresh':
    'nessun aggiornamento giornaliero',
  'every day at {time}: {what}':
    'ogni giorno alle {time}: {what}',
  'everything':
    'tutto',
  'folder watch every {n} min':
    'monitoraggio cartelle ogni {n} min',
  'no folder watch':
    'nessun monitoraggio cartelle',
  'Start the first run now':
    'Avvia ora la prima esecuzione',
  'Runs “Update everything” once after “Finish”: {steps}. With a large library the first run takes a while – you can follow it on the home page and stop it at any time.':
    'Dopo «Fine» esegue una volta «Aggiorna tutto»: {steps}. Con una grande libreria la prima esecuzione richiede un po\' di tempo – puoi seguirla nella pagina iniziale e fermarla in qualsiasi momento.',
  'Only possible with a working connection to Navidrome.':
    'Possibile solo con una connessione funzionante a Navidrome.',
  'Run the setup assistant again':
    'Riavvia la configurazione guidata',
  'Goes through the most important settings once more: connection, conversion, lyrics, understanding music, Deezer stars and what runs by itself. Apart from the connection, nothing changes until you tap “Finish”.':
    'Ripercorre le impostazioni più importanti: connessione, conversione, testi, capire la musica, stelle Deezer e cosa funziona da solo. A parte la connessione, non cambia nulla finché non tocchi «Fine».',
}
