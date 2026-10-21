// Same keys as ../de/setup.js (tools/translate.py)
export default {
  'Set up Tuttiphon':
    'Skonfiguruj Tuttiphon',
  'Setup assistant':
    'Kreator konfiguracji',
  'A few questions about what Tuttiphon should do – each with a sensible default. Apart from the connection, nothing changes until you tap “Finish”.':
    'Kilka pytań o to, co Tuttiphon ma robić – każde z rozsądną wartością domyślną. Poza połączeniem nic się nie zmieni, dopóki nie dotkniesz „Zakończ”.',
  'Skip setup':
    'Pomiń konfigurację',
  'Summary':
    'Podsumowanie',
  'Finish':
    'Zakończ',
  'Finish and start':
    'Zakończ i uruchom',
  'Skip the setup?':
    'Pominąć konfigurację?',
  'Tuttiphon keeps its current settings. You find everything under Settings – and this assistant under Settings → General.':
    'Tuttiphon zachowa obecne ustawienia. Wszystko znajdziesz w Ustawieniach – a ten kreator w Ustawienia → Ogólne.',
  'Everything is under Settings whenever you need it.':
    'Wszystko jest w Ustawieniach, kiedy tylko będzie potrzebne.',
  'Setup saved – the first run is starting.':
    'Konfiguracja zapisana – rusza pierwszy przebieg.',
  'Setup saved ✓':
    'Konfiguracja zapisana ✓',
  'Connect to Navidrome':
    'Połącz z Navidrome',
  'Tuttiphon reads your library from Navidrome and writes the playlists back there. For that it needs the address of Navidrome and an admin account – in the background, for scans, playlists and their owners.':
    'Tuttiphon czyta twoją bibliotekę z Navidrome i zapisuje tam z powrotem playlisty. Potrzebuje do tego adresu Navidrome i konta admina – w tle, do skanów, playlist i ich właścicieli.',
  'Connected – Navidrome {version}':
    'Połączono – Navidrome {version}',
  'Tuttiphon cannot reach Navidrome yet: {error}':
    'Tuttiphon nie może jeszcze połączyć się z Navidrome: {error}',
  'Tuttiphon cannot reach Navidrome yet.':
    'Tuttiphon nie może jeszcze połączyć się z Navidrome.',
  'The connection is set in docker-compose.yaml – it can only be changed there.':
    'Połączenie jest ustawione w docker-compose.yaml – można je zmienić tylko tam.',
  'Change connection':
    'Zmień połączenie',
  'Without a working connection Tuttiphon can neither read your library nor write playlists – so the next steps only make sense once it works. Can’t get it to work right now? Skip the setup and connect later under Settings → Navidrome.':
    'Bez działającego połączenia Tuttiphon nie może ani czytać twojej biblioteki, ani zapisywać playlist – dlatego kolejne kroki mają sens dopiero, gdy ono działa. Teraz się nie udaje? Pomiń konfigurację i połącz później w Ustawienia → Navidrome.',
  'Convert lossless files?':
    'Konwertować pliki bezstratne?',
  'Lossless files such as FLAC are large. Converted, they sound the same to the ear but take only about a fifth of the space – ideal for phones and for listening offline.':
    'Pliki bezstratne, np. FLAC, są duże. Po konwersji brzmią dla ucha tak samo, ale zajmują tylko ok. jednej piątej miejsca – idealne dla telefonów i do słuchania offline.',
  'Your files stay exactly as they are.':
    'Twoje pliki pozostają dokładnie takie, jakie są.',
  'Smallest files, ideal for Android · {n} kbit/s':
    'Najmniejsze pliki, idealne dla Androida · {n} kbit/s',
  'For iPhone, iPad and Mac · {n} kbit/s':
    'Dla iPhone’a, iPada i Maca · {n} kbit/s',
  'Converted are the lossless files in the music folder – FLAC, more formats under Settings → Conversion. The first run takes everything that is there, after that only new files. Files fresh from Lidarr get a few minutes of rest first.':
    'Konwertowane są pliki bezstratne w folderze muzyki – FLAC, więcej formatów w Ustawienia → Konwersja. Pierwszy przebieg bierze wszystko, co tam jest, potem tylko nowe pliki. Pliki świeżo z Lidarr najpierw dostają kilka minut spokoju.',
  'Every new file is checked first: only when it is just as long as the original, to the second, does Tuttiphon touch the original. Tags and cover are kept.':
    'Każdy nowy plik jest najpierw sprawdzany: dopiero gdy jest co do sekundy tak samo długi jak oryginał, Tuttiphon dotyka oryginału. Tagi i okładka zostają zachowane.',
  'And the original?':
    'A oryginał?',
  'Move to the archive':
    'Przenieś do archiwum',
  'The original goes to the archive folder, in the same folder structure. The safest choice – you can always get it back.':
    'Oryginał trafia do folderu archiwum, w tej samej strukturze folderów. Najbezpieczniejszy wybór – zawsze możesz go odzyskać.',
  'The original stays next to the new file. Both are then in your library, and it needs the most space.':
    'Oryginał zostaje obok nowego pliku. Oba są wtedy w twojej bibliotece, a to zajmuje najwięcej miejsca.',
  'The original is gone for good. Only if you have a backup of your music.':
    'Oryginał znika na dobre. Tylko jeśli masz kopię zapasową swojej muzyki.',
  'The folder does not exist yet – Tuttiphon creates it with the first conversion if it may write there. You can choose another folder under Settings → Storage locations.':
    'Folder jeszcze nie istnieje – Tuttiphon utworzy go przy pierwszej konwersji, jeśli może tam zapisywać. Inny folder wybierzesz w Ustawienia → Lokalizacje.',
  'Tuttiphon may not write to this folder, so the originals cannot be moved there. Fix the permissions or choose another folder under Settings → Storage locations.':
    'Tuttiphon nie może zapisywać w tym folderze, więc oryginałów nie da się tam przenieść. Popraw uprawnienia albo wybierz inny folder w Ustawienia → Lokalizacje.',
  'Deleted originals cannot be restored – the backup of Tuttiphon contains only its own data, not your music.':
    'Usuniętych oryginałów nie da się przywrócić – kopia zapasowa Tuttiphon zawiera tylko jego własne dane, nie twoją muzykę.',
  'Tuttiphon looks up missing lyrics and saves them as files next to the songs: synced lyrics as .lrc, plain text as .txt. Navidrome reads them at the next scan, and many players show them – Symfonium even line by line while the song plays.':
    'Tuttiphon wyszukuje brakujące teksty i zapisuje je jako pliki obok piosenek: zsynchronizowane jako .lrc, zwykły tekst jako .txt. Navidrome wczytuje je przy następnym skanie, a wiele odtwarzaczy je pokazuje – Symfonium nawet wers po wersie podczas odtwarzania.',
  'Only adds files next to the songs – the music files stay untouched.':
    'Tylko dodaje pliki obok piosenek – pliki muzyczne pozostają nietknięte.',
  'At least one provider must stay on.':
    'Co najmniej jeden dostawca musi pozostać włączony.',
  'Tuttiphon listens to every song – completely locally, without a cloud and without costs. From that come sound vibes such as “Falling asleep”, mixes with smooth transitions and the classification of new bands. It works gently: mostly at night, during the day only a few minutes per run.':
    'Tuttiphon słucha każdej piosenki – całkowicie lokalnie, bez chmury i bez kosztów. Dzięki temu powstają klimaty brzmieniowe, takie jak „Do zasypiania”, mixy z płynnymi przejściami i klasyfikacja nowych zespołów. Działa oszczędnie: głównie nocą, w ciągu dnia tylko kilka minut na przebieg.',
  'Measures tempo, energy, danceability and timbre of every song.':
    'Mierzy tempo, energię, taneczność i barwę dźwięku każdej piosenki.',
  'Also recognizes mood, vocals or instrumental, instruments, themes, key and music style.':
    'Rozpoznaje też nastrój, wokal lub instrumentalność, instrumenty, tematy, tonację i styl muzyczny.',
  'The AI sound analysis is not installed here – it is part of the Docker image. The measurement works without it.':
    'Analiza brzmienia AI nie jest tu zainstalowana – jest częścią obrazu Docker. Pomiar działa bez niej.',
  'AI sound analysis: {reason} The measurement works without it.':
    'Analiza brzmienia AI: {reason} Pomiar działa bez niej.',
  'Finds the same recording stored twice – also as another format, in another folder or on another album. About 3 KB per song.':
    'Znajduje to samo nagranie zapisane dwa razy – także w innym formacie, w innym folderze lub na innym albumie. Ok. 3 KB na piosenkę.',
  'At night Tuttiphon works through whatever is still open, without a time limit. On a NAS the first pass of a large library takes several nights – after that only new songs are left. The nightly Deezer refresh and the weekly cover search also run in this window.':
    'Nocą Tuttiphon przerabia bez limitu czasu wszystko, co jeszcze czeka. Na NAS pierwszy przebieg dużej biblioteki trwa kilka nocy – potem zostają tylko nowe piosenki. W tym oknie działają też nocne odświeżanie Deezer i cotygodniowe wyszukiwanie okładek.',
  'Start and end must not be the same.':
    'Początek i koniec nie mogą być takie same.',
  'Star ratings from Deezer':
    'Oceny gwiazdkowe z Deezer',
  'Deezer knows how popular almost every song is. Tuttiphon turns that into stars in Navidrome: apps like Symfonium then sort the top tracks of every band correctly, and the “Only the hits” playlists know which songs are the hits. No Deezer account needed.':
    'Deezer wie, jak popularna jest niemal każda piosenka. Tuttiphon zamienia to na gwiazdki w Navidrome: aplikacje takie jak Symfonium poprawnie sortują wtedy najlepsze utwory każdego zespołu, a playlisty „Tylko hity” wiedzą, które piosenki są hitami. Konto Deezer nie jest potrzebne.',
  'Set stars from Deezer':
    'Ustawiaj gwiazdki z Deezer',
  'New songs are rated during “Update everything”; in the time window of the night analysis a portion is checked again every night.':
    'Nowe piosenki są oceniane podczas „Zaktualizuj wszystko”; w oknie czasowym analizy nocnej co noc część jest sprawdzana ponownie.',
  'Songs rated by hand':
    'Piosenki oceniane ręcznie',
  'Keep their stars':
    'Zachowaj ich gwiazdki',
  'Stars someone gave by hand stay – Deezer only rates the other songs.':
    'Gwiazdki nadane przez kogoś ręcznie zostają – Deezer ocenia tylko pozostałe piosenki.',
  'Overwrite':
    'Nadpisz',
  'The Deezer rating replaces stars given by hand too.':
    'Ocena z Deezer zastępuje także gwiazdki nadane ręcznie.',
  'Stars given by hand are lost with the next rating – they cannot be restored.':
    'Gwiazdki nadane ręcznie przepadną przy następnej ocenie – nie da się ich przywrócić.',
  'What should run by itself?':
    'Co ma działać samo?',
  'Tuttiphon can keep everything up to date by itself every day – and pick up new music as soon as it lands in the music folder. Both run as long as Tuttiphon is running, ideally in the Docker container on the NAS.':
    'Tuttiphon może codziennie sam utrzymywać wszystko na bieżąco – i przejmować nową muzykę, gdy tylko trafi do folderu muzyki. Oba działają, dopóki działa Tuttiphon, najlepiej w kontenerze Docker na NAS.',
  '“Playlists” rebuilds the mixes that are due and switches seasons. “Everything” also runs the steps of “Update everything” – conversion, lyrics, covers, understanding music and Deezer, as far as they are on.':
    '„Playlisty” przebudowuje należne mixy i przełącza sezony. „Wszystko” uruchamia też kroki „Zaktualizuj wszystko” – konwersję, teksty, okładki, zrozumienie muzyki i Deezer, o ile są włączone.',
  'Anything missed is caught up at the next start.':
    'To, co zostało pominięte, jest nadrabiane przy następnym starcie.',
  'All set?':
    'Wszystko gotowe?',
  'This is what Tuttiphon will do. Everything can be changed later under Settings – and this assistant is under Settings → General.':
    'Oto co zrobi Tuttiphon. Wszystko można później zmienić w Ustawieniach – a ten kreator jest w Ustawienia → Ogólne.',
  'Not connected':
    'Niepołączony',
  'Off – files stay as they are':
    'Wyłączone – pliki pozostają bez zmian',
  'originals to the archive':
    'oryginały do archiwum',
  'originals are kept':
    'oryginały są zachowywane',
  'originals are deleted':
    'oryginały są usuwane',
  'search with {providers}':
    'wyszukiwanie przez {providers}',
  'no search':
    'bez wyszukiwania',
  'also text only':
    'także tylko tekst',
  '“text only” is replaced by synced lyrics later':
    '„tylko tekst” zostanie później zastąpiony zsynchronizowanym',
  'duplicate lyrics files are deleted':
    'zdublowane pliki tekstów są usuwane',
  'measurement and AI · {depth}':
    'pomiar i AI · {depth}',
  'measurement · {depth}':
    'pomiar · {depth}',
  'no sound analysis':
    'bez analizy brzmienia',
  'audio fingerprints':
    'odciski audio',
  'at night {from}–{to}':
    'nocą {from}–{to}',
  'no night analysis':
    'bez analizy nocnej',
  'for {accounts}':
    'dla: {accounts}',
  'no accounts yet':
    'jeszcze brak kont',
  'overwrites stars given by hand':
    'nadpisuje gwiazdki nadane ręcznie',
  'stars given by hand stay':
    'gwiazdki nadane ręcznie zostają',
  'no daily refresh':
    'bez codziennego odświeżania',
  'every day at {time}: {what}':
    'codziennie o {time}: {what}',
  'everything':
    'wszystko',
  'folder watch every {n} min':
    'obserwowanie folderu co {n} min',
  'no folder watch':
    'bez obserwowania folderu',
  'Start the first run now':
    'Uruchom teraz pierwszy przebieg',
  'Runs “Update everything” once after “Finish”: {steps}. With a large library the first run takes a while – you can follow it on the home page and stop it at any time.':
    'Po „Zakończ” uruchamia raz „Zaktualizuj wszystko”: {steps}. Przy dużej bibliotece pierwszy przebieg chwilę trwa – możesz go śledzić na stronie głównej i w każdej chwili zatrzymać.',
  'Only possible with a working connection to Navidrome.':
    'Możliwe tylko z działającym połączeniem z Navidrome.',
  'Run the setup assistant again':
    'Uruchom ponownie kreator konfiguracji',
  'Goes through the most important settings once more: connection, conversion, lyrics, understanding music, Deezer stars and what runs by itself. Apart from the connection, nothing changes until you tap “Finish”.':
    'Przechodzi jeszcze raz przez najważniejsze ustawienia: połączenie, konwersję, teksty, zrozumienie muzyki, gwiazdki Deezer i to, co działa samo. Poza połączeniem nic się nie zmieni, dopóki nie dotkniesz „Zakończ”.',
}
