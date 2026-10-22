// Same keys as ../de/settings-a.js
export default {
  'testing …':
    'testowanie …',
  'minutes':
    'min',
  'Test':
    'Testuj',
  'Password':
    'Hasło',
  'Run now':
    'Uruchom teraz',
  'Dry run':
    'Próbny przebieg',
  'Accounts & passwords':
    'Konta i hasła',
  'Statistics & stars':
    'Statystyki i gwiazdki',
  'Turn on':
    'Włącz',
  'Notifications on your phone':
    'Powiadomienia na telefonie',
  '✓ Last.fm responds, e.g. Nightwish: {tags}':
    '✓ Last.fm odpowiada, np. Nightwish: {tags}',
  'Please enter the key':
    'Wpisz klucz',
  'Last.fm key saved ✓':
    'Zapisano klucz Last.fm ✓',
  'Sound analysis':
    'Analiza brzmienia',
  'Tuttiphon listens to every song – completely locally, with no cloud and no costs. This gives sound vibes such as “Falling asleep” or “Running wild”, mixes that wind down calmly and the classification of new bands. A pass has two stages:':
    'Tuttiphon słucha każdej piosenki – całkowicie lokalnie, bez chmury i bez kosztów. Dzięki temu powstają klimaty brzmieniowe, takie jak „Do zasypiania” czy „Do szaleństwa”, mixy, które spokojnie się wyciszają, oraz klasyfikacja nowych zespołów. Przebieg ma dwa etapy:',
  'Measure':
    'Pomiar',
  '– tempo, energy, danceability, timbre':
    '– tempo, energia, taneczność, barwa dźwięku',
  '{done} of {total} songs · {pct}%':
    '{done} z {total} piosenek · {pct}%',
  'AI':
    'AI',
  '– mood, vocals or instrumental, acoustic, music style':
    '– nastrój, wokal lub instrumentalnie, akustyczność, styl muzyczny',
  'Not available.':
    'Niedostępne.',
  ' · most common: {styles}':
    ' · najczęstsze: {styles}',
  'The AI takes each song right after its measurement, and only songs already measured. In the first pass this means it really gets going once the measurement is almost done. The night analysis does both at night – the first pass takes several nights on the NAS, after that only new songs are left.':
    'AI bierze każdą piosenkę zaraz po jej pomiarze i tylko piosenki już zmierzone. W pierwszym przebiegu oznacza to, że naprawdę rusza, gdy pomiar jest prawie gotowy. Analiza nocna robi oba etapy nocą – pierwszy przebieg zajmuje na NAS kilka nocy, potem zostają już tylko nowe piosenki.',
  ' Last measurement: {when}.':
    ' Ostatni pomiar: {when}.',
  ' AI last run: {when}.':
    ' Ostatni przebieg AI: {when}.',
  'With the current AI version (key, tempo, instruments, how easy to listen to): {done} of {total} songs · {pct}%':
    'Z bieżącą wersją AI (tonacja, tempo, instrumenty, łatwość odbioru): {done} z {total} piosenek · {pct}%',
  'Sound vectors for similar bands and smooth transitions: {n} songs':
    'Wektory brzmienia dla podobnych zespołów i płynnych przejść: piosenki: {n}',
  'Most common instruments: {list}':
    'Najczęstsze instrumenty: {list}',
  'Most common themes: {list}':
    'Najczęstsze tematy: {list}',
  'After an update the AI listens to the library once more – new songs first, the rest over the next nights. Until then the earlier results keep working.':
    'Po aktualizacji AI jeszcze raz przesłuchuje bibliotekę – najpierw nowe piosenki, resztę przez kolejne noce. Do tego czasu wcześniejsze wyniki nadal działają.',
  'Same recording twice':
    'To samo nagranie dwa razy',
  'Audio fingerprints find songs stored more than once – also as another format, in another folder or on another album, for example a FLAC file next to its converted Opus file. Live versions, re-recordings and karaoke stay apart. They are made during “Understand music” and at night, new songs first.':
    'Odciski audio znajdują piosenki zapisane więcej niż raz – także w innym formacie, w innym folderze lub na innym albumie, np. plik FLAC obok swojego skonwertowanego pliku Opus. Wersje live, ponowne nagrania i karaoke pozostają osobno. Powstają podczas „Zrozum muzykę” i nocą, najpierw dla nowych piosenek.',
  'fpcalc is {why} – it is included in the Docker image.':
    'fpcalc: {why} – jest zawarty w obrazie Docker.',
  'not installed':
    'niezainstalowany',
  '{n} song still open':
    '{n} piosenka jeszcze czeka',
  '{n} songs still open': { few: '{n} piosenki jeszcze czekają', many: '{n} piosenek jeszcze czeka' },
  '{n} not readable':
    'nieczytelne: {n}',
  '{n} recording is there more than once':
    '{n} nagranie występuje więcej niż raz',
  '{n} recordings are there more than once': { few: '{n} nagrania występują więcej niż raz', many: '{n} nagrań występuje więcej niż raz' },
  'No recording is there twice':
    'Żadne nagranie nie występuje dwa razy',
  '{n} extra file · compared {when}':
    '{n} zbędny plik · porównano {when}',
  '{n} extra files · compared {when}': { few: '{n} zbędne pliki · porównano {when}', many: '{n} zbędnych plików · porównano {when}' },
  'compared {when}':
    'porównano {when}',
  'Make audio fingerprints':
    'Twórz odciski audio',
  'Independent of the AI sound analysis. About 3 KB per song – not part of the backup, they renew themselves.':
    'Niezależne od analizy brzmienia AI. Ok. 3 KB na piosenkę – nie wchodzą do kopii zapasowej, odnawiają się same.',
  '{label}: {n} songs':
    '{label} – piosenki: {n}',
  'Tempo: mostly between {low} and {high} BPM, median {median}.':
    'Tempo: głównie między {low} a {high} BPM, mediana {median}.',
  'Turn on sound analysis':
    'Włącz analizę brzmienia',
  'Add AI':
    'Dodaj AI',
  'Stage 2. Without AI, only the measurement runs.':
    'Etap 2. Bez AI działa tylko pomiar.',
  'Night analysis':
    'Analiza nocna',
  'At night Tuttiphon works through everything still open with no time limit – first the measurement, then the AI. Ends at the latest at the end of the time window and before the daily refresh. New music arriving during this time is processed afterwards. The nightly Deezer refresh and the weekly cover search also run in this window.':
    'Nocą Tuttiphon przerabia bez limitu czasu wszystko, co jeszcze czeka – najpierw pomiar, potem AI. Kończy najpóźniej z końcem okna czasowego i przed codziennym odświeżeniem. Nowa muzyka, która pojawi się w tym czasie, zostanie przetworzona później. W tym oknie działają też nocne odświeżanie Deezer i cotygodniowe wyszukiwanie okładek.',
  'Time window':
    'Okno czasowe',
  'Night analysis from':
    'Analiza nocna od',
  'to':
    'do',
  'Night analysis until':
    'Analiza nocna do',
  'Daytime and performance':
    'Dzień i wydajność',
  'Applies to runs outside the night – new music and “Update everything”: new songs first, the rest comes later. 0 = no limit.':
    'Dotyczy przebiegów poza nocą – nowej muzyki i „Zaktualizuj wszystko”: najpierw nowe piosenki, reszta później. 0 = bez limitu.',
  'Time limit for measuring':
    'Limit czasu pomiaru',
  'Time limit for AI':
    'Limit czasu AI',
  'Simultaneous measurements':
    'Równoczesne pomiary',
  '0 = automatic: half as many as processor cores.':
    '0 = automatycznie: połowa liczby rdzeni procesora.',
  'Processor cores for the AI':
    'Rdzenie procesora dla AI',
  'The AI may use at most this many cores – the rest stays free for Navidrome.':
    'AI może używać najwyżej tylu rdzeni – reszta zostaje wolna dla Navidrome.',
  'Free with your own key: similar bands for radio, suggestions and “You might still be missing”, plus genre and mood tags for classifying new bands. Everything is cached for 30 days.':
    'Za darmo z własnym kluczem: podobne zespoły dla radia, propozycji i „Tego może wam jeszcze brakować”, a do tego tagi gatunku i nastroju do klasyfikacji nowych zespołów. Wszystko jest buforowane przez 30 dni.',
  'Key entered':
    'Klucz wpisany',
  'No key yet':
    'Jeszcze brak klucza',
  '{n} band loaded':
    'Wczytano {n} zespół',
  '{n} bands loaded': { few: 'Wczytano {n} zespoły', many: 'Wczytano {n} zespołów' },
  ' · last run {when}':
    ' · ostatni przebieg: {when}',
  'The key is set in docker-compose.yaml as LASTFM_API_KEY.':
    'Klucz jest ustawiony w docker-compose.yaml jako LASTFM_API_KEY.',
  'API key':
    'Klucz API',
  '•••••• entered':
    '•••••• wpisany',
  'You can get a key for free at last.fm/api/account/create. It is only stored on your NAS.':
    'Klucz dostaniesz za darmo na last.fm/api/account/create. Jest przechowywany tylko na twoim NAS.',
  'Time limit per run':
    'Limit czasu na przebieg',
  'Tuttiphon loads Last.fm data for at most this long. The first pass takes a few minutes.':
    'Tuttiphon wczytuje dane z Last.fm najwyżej tak długo. Pierwszy przebieg trwa kilka minut.',
  'Music worlds':
    'Światy muzyczne',
  'From genres, Last.fm tags, AI music style, language and decade, Tuttiphon recognizes which music worlds your library offers – such as 80s hits, Eurodance, German rap or Schlager & party – and classifies every band. New bands go into their world on their own.':
    'Na podstawie gatunków, tagów Last.fm, stylu muzycznego AI, języka i dekady Tuttiphon rozpoznaje, jakie światy muzyczne oferuje twoja biblioteka – np. hity lat 80., Eurodance, niemiecki rap albo Schlager i impreza – i klasyfikuje każdy zespół. Nowe zespoły same trafiają do swojego świata.',
  'Create music worlds automatically':
    'Twórz światy muzyczne automatycznie',
  'From 4 bands and 60 songs, or from just 2 bands if someone listens to them a lot. Deleted worlds don’t come back.':
    'Od 4 zespołów i 60 piosenek albo już od 2 zespołów, jeśli ktoś dużo ich słucha. Usunięte światy nie wracają.',
  'Classify new bands':
    'Klasyfikuj nowe zespoły',
  'For bands without a music world, Tuttiphon works out where they fit – from similar bands on Last.fm, tags, genres, the music styles of the AI sound analysis and the scene catalog. With match rate and reasoning.':
    'Dla zespołów bez świata muzycznego Tuttiphon ustala, gdzie pasują – na podstawie podobnych zespołów w Last.fm, tagów, gatunków, stylów muzycznych z analizy brzmienia AI i katalogu scen. Z poziomem dopasowania i uzasadnieniem.',
  'What happens with matches':
    'Co dzieje się z dopasowaniami',
  '“Suggest” shows them under “To review” on the home page.':
    '„Proponuj” pokazuje je w „Do przejrzenia” na stronie głównej.',
  'nothing':
    'nic',
  'suggest':
    'proponuj',
  'automatic':
    'automatycznie',
  'Classify new bands right away':
    'Klasyfikuj nowe zespoły od razu',
  'Bands that are new in the library, e.g. from Lidarr, go straight into their music world with a confident match of 75% or more. “To review” then shows what was classified, with “Undo”.':
    'Zespoły, które są nowe w bibliotece, np. z Lidarr, trafiają od razu do swojego świata muzycznego przy pewnym dopasowaniu od 75%. „Do przejrzenia” pokazuje potem, co sklasyfikowano, z opcją „Cofnij”.',
  'Automatic from':
    'Automatycznie od',
  'Only very confident matches are classified directly; the rest stays a suggestion.':
    'Bezpośrednio klasyfikowane są tylko bardzo pewne dopasowania; reszta pozostaje propozycją.',
  '{n} song · {why}':
    '{n} piosenka · {why}',
  '{n} songs · {why}': { few: '{n} piosenki · {why}', many: '{n} piosenek · {why}' },
  'add':
    'dodaj',
  'No bands without a music world right now.':
    'Na razie brak zespołów bez świata muzycznego.',
  'Vibes from Last.fm tags for bands without a genre':
    'Klimaty z tagów Last.fm dla zespołów bez gatunku',
  'assign':
    'przypisz',
  'Analyze everything without a time limit':
    'Analizuj wszystko bez limitu czasu',
  'One pass with a time limit':
    'Jeden przebieg z limitem czasu',
  'Sound analysis and AI sound analysis one after the other. The first full pass takes many hours on the NAS, the AI much longer. It can be stopped at any time – the night analysis is usually enough. After that, only new songs are left.':
    'Analiza brzmienia i analiza brzmienia AI jedna po drugiej. Pierwszy pełny przebieg zajmuje na NAS wiele godzin, AI dużo dłużej. Można go w każdej chwili zatrzymać – zwykle wystarcza analiza nocna. Potem zostają tylko nowe piosenki.',
  'Local administrator with all rights':
    'Administrator lokalny ze wszystkimi uprawnieniami',
  'Administrator – may change all settings':
    'Administrator – może zmieniać wszystkie ustawienia',
  'User – own playlists and own profile':
    'Użytkownik – własne playlisty i własny profil',
  'Please enter the password':
    'Wpisz hasło',
  'checking …':
    'sprawdzanie …',
  'Turned on ✓ – your statistics will be there in a moment':
    'Włączono ✓ – twoje statystyki pojawią się za chwilę',
  'Forget password?':
    'Zapomnieć hasło?',
  'Then there are no personal statistics and no Deezer stars of your own until you enter it again. You can still sign in.':
    'Wtedy nie będzie osobistych statystyk ani własnych gwiazdek Deezer, dopóki nie wpiszesz go ponownie. Nadal możesz się logować.',
  'Forget':
    'Zapomnij',
  'Password forgotten':
    'Hasło zapomniane',
  'Everything visible again':
    'Wszystko znów widoczne',
  'Sign-in':
    'Logowanie',
  'Sign-in is currently turned off – anyone who can open Tuttiphon is automatically an administrator. This only makes sense as long as Tuttiphon runs on this computer alone.':
    'Logowanie jest obecnie wyłączone – każdy, kto może otworzyć Tuttiphon, jest automatycznie administratorem. Ma to sens tylko, dopóki Tuttiphon działa wyłącznie na tym komputerze.',
  'Signed in':
    'Zalogowano',
  'Navidrome account “{user}” · {role}':
    'Konto Navidrome „{user}” · {role}',
  'Sign out':
    'Wyloguj się',
  'You change your password in Navidrome, in the profile at the top right. Then enter the new one here under “Statistics & stars” as well.':
    'Hasło zmieniasz w Navidrome, w profilu w prawym górnym rogu. Potem wpisz nowe także tutaj w „Statystyki i gwiazdki”.',
  'You change your password in Navidrome, in the profile at the top right.':
    'Hasło zmieniasz w Navidrome, w profilu w prawym górnym rogu.',
  'The stored password no longer works – probably it was changed in Navidrome. Enter the new one so your statistics and stars keep working.':
    'Zapisane hasło już nie działa – prawdopodobnie zostało zmienione w Navidrome. Wpisz nowe, aby statystyki i gwiazdki nadal działały.',
  'Save new password':
    'Zapisz nowe hasło',
  'The password of the local administrator is set in docker-compose.yaml (TUTTIPHON_ADMIN_PASSWORD).':
    'Hasło administratora lokalnego jest ustawione w docker-compose.yaml (TUTTIPHON_ADMIN_PASSWORD).',
  'The local administrator has no Navidrome account of its own.':
    'Administrator lokalny nie ma własnego konta Navidrome.',
  'Turned on':
    'Włączone',
  'Tuttiphon knows your plays, stars and favorites – for your statistics, your stars and more accurate suggestions.':
    'Tuttiphon zna twoje odtworzenia, gwiazdki i ulubione – dla twoich statystyk, twoich gwiazdek i trafniejszych propozycji.',
  'For Tuttiphon to show your statistics and set Deezer stars in your account, it needs your Navidrome password once – the same as in Symfonium. It stays on your NAS.':
    'Aby Tuttiphon mógł pokazywać twoje statystyki i ustawiać gwiazdki Deezer na twoim koncie, potrzebuje raz twojego hasła Navidrome – tego samego co w Symfonium. Zostaje ono na twoim NAS.',
  'your Navidrome password':
    'twoje hasło Navidrome',
  'Your profile':
    'Twój profil',
  'Playlists only for you':
    'Playlisty tylko dla ciebie',
  'Create profile':
    'Utwórz profil',
  'This is where your favorite worlds, bands and dislikes are – your suggestions come from them.':
    'Tutaj są twoje ulubione światy, zespoły i to, czego nie lubisz – z nich biorą się twoje propozycje.',
  'Introduction':
    'Wprowadzenie',
  'Tour':
    'Prezentacja',
  'Shows in a few steps where to find what.':
    'Pokazuje w kilku krokach, gdzie co znaleźć.',
  'Start tour':
    'Rozpocznij prezentację',
  'Hidden items':
    'Ukryte elementy',
  '{suggestions} suggestions · {tips} tips are hidden. Suggestions come back on their own after half a year.':
    'Ukryte propozycje: {suggestions} · ukryte wskazówki: {tips}. Propozycje wracają same po pół roku.',
  'show again':
    'pokaż ponownie',
  'Open, free lyrics database – fast, synced lyrics and plain text.':
    'Otwarta, darmowa baza tekstów – szybka, teksty zsynchronizowane i zwykły tekst.',
  'Large music platform with many synced lyrics, also for Western music. Unofficial interface, somewhat slower.':
    'Duża platforma muzyczna z wieloma zsynchronizowanymi tekstami, także dla muzyki zachodniej. Nieoficjalny interfejs, nieco wolniejszy.',
  'Find lyrics automatically':
    'Znajduj teksty automatycznie',
  'Tuttiphon looks up missing lyrics on LRCLIB, and on NetEase too if you like, and puts them next to the songs: synced lyrics as .lrc, otherwise as .txt. Navidrome reads them in at the next scan, Symfonium shows them while playing.':
    'Tuttiphon wyszukuje brakujące teksty w LRCLIB, a jeśli chcesz, także w NetEase, i zapisuje je obok piosenek: zsynchronizowane jako .lrc, inne jako .txt. Navidrome wczytuje je przy następnym skanie, Symfonium pokazuje je podczas odtwarzania.',
  'No numbers yet – they appear with the first run.':
    'Jeszcze brak liczb – pojawią się po pierwszym przebiegu.',
  'synced':
    'zsynchronizowane',
  'text only':
    'tylko tekst',
  'without lyrics':
    'bez tekstu',
  '{n} synced':
    'zsynchronizowane: {n}',
  '{n} text only':
    'tylko tekst: {n}',
  '{n} without lyrics':
    'bez tekstu: {n}',
  'last run {when}':
    'ostatni przebieg: {when}',
  'Search for missing lyrics':
    'Szukaj brakujących tekstów',
  'Providers & order':
    'Dostawcy i kolejność',
  'Asked in order; synced lyrics win – if the first finds only plain text, Tuttiphon asks the next ones for a synced version.':
    'Pytani po kolei; wygrywają teksty zsynchronizowane – jeśli pierwszy znajdzie tylko zwykły tekst, Tuttiphon pyta kolejnych o wersję zsynchronizowaną.',
  'Time limit for “Update everything”':
    'Limit czasu dla „Zaktualizuj wszystko”',
  'Tuttiphon searches at most this long per run – the rest comes next time. New songs always go first. 0 = no limit.':
    'Tuttiphon szuka najwyżej tak długo na przebieg – reszta następnym razem. Nowe piosenki zawsze idą pierwsze. 0 = bez limitu.',
  'Also save “text only”':
    'Zapisuj też „tylko tekst”',
  'If there are no synced ones.':
    'Jeśli nie ma zsynchronizowanych.',
  'Replace “text only” with synced later':
    'Zastąp później „tylko tekst” zsynchronizowanym',
  'Regularly looks for a synced version for songs with .txt.':
    'Regularnie szuka wersji zsynchronizowanej dla piosenek z .txt.',
  'Instrumental tracks':
    'Utwory instrumentalne',
  'Mark as “instrumental” – then Tuttiphon doesn’t keep searching there.':
    'Oznacz jako „instrumentalne” – wtedy Tuttiphon przestaje tam szukać.',
  'mark':
    'oznacz',
  'save nothing':
    'nic nie zapisuj',
  'Retry search':
    'Ponów wyszukiwanie',
  'What wasn’t found is only searched again after this many days.':
    'To, czego nie znaleziono, będzie szukane ponownie dopiero po tylu dniach.',
  'days later':
    'dni później',
  'Simultaneous requests':
    'Równoczesne zapytania',
  'LRCLIB is a community project – better go easy.':
    'LRCLIB to projekt społeczności – lepiej go oszczędzać.',
  'Cleanup':
    'Porządki',
  'Delete duplicate lyrics':
    'Usuń zdublowane teksty',
  'If there is an .lrc next to a .txt, the .txt goes – otherwise Symfonium sometimes shows the wrong lyrics.':
    'Jeśli obok .txt jest .lrc, .txt znika – inaczej Symfonium czasem pokazuje zły tekst.',
  'Search all missing now':
    'Szukaj teraz wszystkich brakujących',
  'Retry recent misses too':
    'Szukaj ponownie także niedawno nieznalezionych',
  '“Search all missing now” runs without a time limit and can be stopped at any time. For the lyrics to appear in Navidrome, a scan is needed afterwards. With “Update everything” this happens automatically.':
    '„Szukaj teraz wszystkich brakujących” działa bez limitu czasu i można go w każdej chwili zatrzymać. Aby teksty pojawiły się w Navidrome, potrzebny jest potem skan. Przy „Zaktualizuj wszystko” dzieje się to automatycznie.',
  '{band}: {songs} blocked again':
    '{band}: ponownie zablokowano {songs}',
  '{band}: {songs} allowed':
    '{band}: dopuszczono {songs}',
  'Lyrics are being read in the background':
    'Teksty są wczytywane w tle',
  'Lyrics search & kid-safe mode':
    'Wyszukiwanie w tekstach i tryb dla dzieci',
  'Tuttiphon reads in all lyrics. This lets the search find songs by a line from the lyrics, and kid-safe mode detects explicit lyrics. You turn on kid-safe mode per person in their profile.':
    'Tuttiphon wczytuje wszystkie teksty. Dzięki temu wyszukiwarka znajduje piosenki po wersie tekstu, a tryb dla dzieci wykrywa wulgarne teksty. Tryb dla dzieci włączasz dla każdej osoby w jej profilu.',
  'The status could not be loaded.':
    'Nie udało się wczytać stanu.',
  'Lyrics read in':
    'Wczytane teksty',
  'Being read in right now …':
    'Właśnie trwa wczytywanie …',
  'New ones are added on their own with every scan.':
    'Nowe są dodawane automatycznie przy każdym skanie.',
  'Read in now':
    'Wczytaj teraz',
  'Kid-safe mode on for':
    'Tryb dla dzieci włączony dla',
  'Turn it on in the profile of the person concerned.':
    'Włącz go w profilu danej osoby.',
  'no one':
    'nikogo',
  'Detected as explicit':
    'Wykryte jako wulgarne',
  'What you allow stays in, even with kid-safe mode.':
    'To, na co pozwolisz, zostaje, nawet w trybie dla dzieci.',
  'No songs with explicit lyrics detected.':
    'Nie wykryto piosenek z wulgarnymi tekstami.',
  'Search band, song or word …':
    'Szukaj zespołu, piosenki lub słowa …',
  'Search explicit songs':
    'Szukaj wulgarnych piosenek',
  'All':
    'Wszystkie',
  'Blocked':
    'Zablokowane',
  'Allowed':
    'Dozwolone',
  '{shown} of {songs} · {bands}':
    '{shown} z {songs} · {bands}',
  '{songs} by {bands} · {allowed} allowed':
    '{songs} – {bands} · dozwolone: {allowed}',
  'Nothing found.':
    'Nic nie znaleziono.',
  ' · {n} allowed':
    ' · dozwolone: {n}',
  'all allowed':
    'wszystkie dozwolone',
  'allow all':
    'zezwól na wszystkie',
  '“{word}”':
    '„{word}”',
  'allowed':
    'dozwolone',
  'allow':
    'zezwól',
  'Show {n} more band':
    'Pokaż jeszcze {n} zespół',
  'Show {n} more bands': { few: 'Pokaż jeszcze {n} zespoły', many: 'Pokaż jeszcze {n} zespołów' },
  'The levels must go up: ★ < ★★ < …':
    'Poziomy muszą rosnąć: ★ < ★★ < …',
  'Recalculate stars?':
    'Przeliczyć gwiazdki?',
  'All stars are set again from the stored ranks with the new levels – without asking Deezer again. Stars given by hand stay, unless you allow overwriting below.':
    'Wszystkie gwiazdki zostaną ustawione ponownie z zapisanych rankingów według nowych poziomów – bez ponownego pytania Deezer. Gwiazdki nadane ręcznie zostają, chyba że niżej zezwolisz na nadpisywanie.',
  'Recalculate':
    'Przelicz',
  'Check everything again?':
    'Sprawdzić wszystko ponownie?',
  'All songs are looked up on Deezer again; this takes about 45–60 minutes. You can stop at any time – next time it continues from there.':
    'Wszystkie piosenki zostaną ponownie wyszukane w Deezer; zajmie to ok. 45–60 minut. Możesz w każdej chwili przerwać – następnym razem sprawdzanie ruszy od tego miejsca.',
  'Start':
    'Start',
  'From popularity to stars':
    'Od popularności do gwiazdek',
  'Deezer knows a popularity rank from 0 to about 1 million for almost every song – the higher, the more popular. Tuttiphon turns this into stars – and “Only the hits” takes the songs with the most stars.':
    'Deezer zna dla niemal każdej piosenki ranking popularności od 0 do ok. 1 miliona – im wyższy, tym piosenka popularniejsza. Tuttiphon zamienia go na gwiazdki – a „Tylko hity” bierze piosenki z największą liczbą gwiazdek.',
  '{stars} from rank':
    '{stars} od rankingu',
  '{k} stars: {n} songs · {pct}%':
    'Gwiazdki: {k} – piosenki: {n} · {pct}%',
  'no stars':
    'bez gwiazdek',
  'This is how {n} songs with a known Deezer rank are distributed; {missing} were not found on Deezer.':
    'Tak rozkładają się piosenki ze znanym rankingiem Deezer ({n}); nie znaleziono w Deezer: {missing}.',
  'This is how {n} songs with a known Deezer rank are distributed.':
    'Tak rozkładają się piosenki ze znanym rankingiem Deezer ({n}).',
  'Defaults':
    'Domyślne',
  'Recalculate stars now':
    'Przelicz gwiazdki teraz',
  'Top tracks and refreshing':
    'Najlepsze utwory i odświeżanie',
  'Highlight top tracks per band':
    'Wyróżniaj najlepsze utwory każdego zespołu',
  'If many songs of a band share the highest star count, the most popular get one more star. This way Symfonium sorts the top tracks correctly. Takes effect on the next run.':
    'Jeśli wiele piosenek zespołu ma najwyższą liczbę gwiazdek, najpopularniejsze dostają jedną gwiazdkę więcej. Dzięki temu Symfonium poprawnie sortuje najlepsze utwory. Działa od następnego przebiegu.',
  'Refresh every night':
    'Odświeżaj co noc',
  'Checks {n} songs on Deezer again every night in the time window of the night analysis, first those rated with the older, less accurate search. After that always the ones unchecked the longest – so the stars stay up to date.':
    'Co noc w oknie czasowym analizy nocnej ponownie sprawdza w Deezer kolejne piosenki ({n}) – najpierw te ocenione starszym, mniej dokładnym wyszukiwaniem. Potem zawsze te najdłużej niesprawdzane – tak gwiazdki pozostają aktualne.',
  'Checked with the accurate search: {done} of {total} songs · {top} top tracks highlighted.':
    'Sprawdzone dokładnym wyszukiwaniem: {done} z {total} piosenek · wyróżnione najlepsze utwory: {top}.',
  'Checked with the accurate search: {done} of {total} songs.':
    'Sprawdzone dokładnym wyszukiwaniem: {done} z {total} piosenek.',
  'Who gets stars?':
    'Kto dostaje gwiazdki?',
  'No accounts yet – create them under People first.':
    'Jeszcze brak kont – najpierw utwórz je w „Osoby”.',
  'In Navidrome, stars are per account. Accounts without a password are skipped.':
    'W Navidrome gwiazdki są osobne dla każdego konta. Konta bez hasła są pomijane.',
  'Overwrite stars given by hand':
    'Nadpisuj gwiazdki nadane ręcznie',
  'Normally your own stars stay untouched.':
    'Normalnie twoje własne gwiazdki pozostają nietknięte.',
  'In the full run':
    'W pełnym przebiegu',
  '“Update everything” rates …':
    '„Zaktualizuj wszystko” ocenia …',
  'new songs only':
    'tylko nowe piosenki',
  'new + not found':
    'nowe + nieznalezione',
  'Requests per second':
    'Zapytania na sekundę',
  'Deezer allows at most 10. Fewer = slower, but gentler.':
    'Deezer pozwala najwyżej na 10. Mniej = wolniej, ale łagodniej.',
  'Rate new ones now':
    'Oceń teraz nowe',
  'Retry not found':
    'Szukaj ponownie nieznalezionych',
  'Check everything again':
    'Sprawdź wszystko ponownie',
  'also overwrite stars given by hand':
    'nadpisz też gwiazdki nadane ręcznie',
  'Only for “Check everything again”: stars given by hand are replaced by the Deezer rating too and are lost.':
    'Tylko dla „Sprawdź wszystko ponownie”: gwiazdki nadane ręcznie również zostaną zastąpione oceną z Deezer i przepadną.',
  '✓ Connected – Navidrome {version}':
    '✓ Połączono – Navidrome {version}',
  'Save anyway?':
    'Zapisać mimo to?',
  'The connection does not work with these details right now.':
    'Połączenie z tymi danymi teraz nie działa.',
  'Connection saved ✓':
    'Połączenie zapisane ✓',
  'Connection':
    'Połączenie',
  'Server address for Tuttiphon':
    'Adres serwera dla Tuttiphon',
  'Address in the browser for “Open in Navidrome” links':
    'Adres w przeglądarce dla linków „Otwórz w Navidrome”',
  'empty = same as server address':
    'puste = taki sam jak adres serwera',
  'Admin user':
    'Użytkownik admin',
  'Admin password':
    'Hasło admina',
  '•••••• leave unchanged':
    '•••••• pozostaw bez zmian',
  'Gray = set in docker-compose.yaml or as an environment variable and only changeable there: {vars}.':
    'Szare = ustawione w docker-compose.yaml albo jako zmienna środowiskowa i zmienialne tylko tam: {vars}.',
  'Test connection':
    'Testuj połączenie',
  'Tuttiphon needs the admin account in the background for scans, playlists and their owners. Credentials are only stored on your NAS.':
    'Tuttiphon potrzebuje w tle konta admina do skanów, playlist i ich właścicieli. Dane logowania są przechowywane tylko na twoim NAS.',
  'Password stored':
    'Hasło zapisane',
  'The stored password no longer works – probably it was changed in Navidrome.':
    'Zapisane hasło już nie działa – prawdopodobnie zostało zmienione w Navidrome.',
  'Password missing – stars, accurate preview and statistics won’t work then':
    'Brak hasła – gwiazdki, dokładny podgląd i statystyki wtedy nie działają',
  'Change':
    'Zmień',
  'Enter':
    'Wpisz',
  'The list comes from the Navidrome accounts of your <a class="link" href="#/personen">people</a>. Anyone who signs in and leaves the “Turn on statistics & stars” box checked enters it themselves. Roles: <a class="link" href="#/einstellungen/benutzer">Users & permissions</a>.':
    'Lista pochodzi z kont Navidrome twoich <a class="link" href="#/personen">osób</a>. Kto się loguje i zostawi zaznaczone pole „Włącz statystyki i gwiazdki”, wpisuje je samodzielnie. Role: <a class="link" href="#/einstellungen/benutzer">Użytkownicy i uprawnienia</a>.',
  'Scan':
    'Skan',
  'Type of scan':
    'Rodzaj skanu',
  '“Quick” reads in only what changed and takes seconds. “Full” checks every file – only needed if Navidrome missed something.':
    '„Szybki” wczytuje tylko to, co się zmieniło, i trwa sekundy. „Pełny” sprawdza każdy plik – potrzebny tylko, jeśli Navidrome coś przeoczył.',
  'Quick':
    'Szybki',
  'Full':
    'Pełny',
  'A run failed':
    'Przebieg się nie powiódł',
  'To the administrators’ devices and your topic.':
    'Na urządzenia administratorów i do twojego tematu.',
  'New music has been processed':
    'Nowa muzyka została przetworzona',
  'After the folder watch, to the administrators’ devices and your topic.':
    'Po obserwowaniu folderu – na urządzenia administratorów i do twojego tematu.',
  'New bands were classified':
    'Sklasyfikowano nowe zespoły',
  'Which band went into which music world, to the administrators’ devices and your topic.':
    'Który zespół trafił do którego świata muzycznego – na urządzenia administratorów i do twojego tematu.',
  'News from favorite bands':
    'Nowości od ulubionych zespołów',
  'To the person concerned, on their devices and their topic from the profile.':
    'Do danej osoby, na jej urządzenia i jej temat z profilu.',
  'The monthly recap is here':
    'Jest miesięczne podsumowanie',
  'On the first of the month to the person, if they have “Your month”.':
    'Pierwszego dnia miesiąca do osoby, jeśli ma „Twój miesiąc”.',
  'Test message sent':
    'Wysłano wiadomość testową',
  'Tuttiphon notifies you directly through the app, on every device where you turn it on. Each person turns on their devices in their profile. Optionally it also works via ntfy.':
    'Tuttiphon powiadamia cię bezpośrednio przez aplikację, na każdym urządzeniu, na którym to włączysz. Każda osoba włącza swoje urządzenia w swoim profilu. Opcjonalnie działa to też przez ntfy.',
  'Notifications':
    'Powiadomienia',
  'Turns everything on or off.':
    'Włącza lub wyłącza wszystko.',
  'This device':
    'To urządzenie',
  'Gets the notifications for administrators and those of your people.':
    'Dostaje powiadomienia dla administratorów i te od twoich osób.',
  'Via ntfy':
    'Przez ntfy',
  'Instead of or in addition to the app: short messages via ntfy, free via ntfy.sh or your own ntfy server. Install the ntfy app on your phone and subscribe to the topic. Each person can enter their own topic in their profile.':
    'Zamiast aplikacji albo dodatkowo: krótkie wiadomości przez ntfy, za darmo przez ntfy.sh albo własny serwer ntfy. Zainstaluj aplikację ntfy na telefonie i zasubskrybuj temat. Każda osoba może wpisać własny temat w swoim profilu.',
  'ntfy server':
    'Serwer ntfy',
  'Without your own server, just leave https://ntfy.sh.':
    'Bez własnego serwera po prostu zostaw https://ntfy.sh.',
  'Your topic':
    'Twój temat',
  'For notifications to you. Only letters, digits, - and _. Anyone who knows the topic can read along.':
    'Dla powiadomień do ciebie. Tylko litery, cyfry, - i _. Każdy, kto zna temat, może czytać.',
  'Send test':
    'Wyślij test',
  'Tuttiphon address':
    'Adres Tuttiphon',
  'Tapping a message opens Tuttiphon – e.g. the address via the reverse proxy.':
    'Dotknięcie wiadomości otwiera Tuttiphon – np. adres przez reverse proxy.',
  'Own topic in the profile':
    'Własny temat w profilu',
  'People with their own topic get their notifications directly.':
    'Osoby z własnym tematem dostają swoje powiadomienia bezpośrednio.',
  'nobody yet':
    'jeszcze nikt',
  'Protected topics on your own server: enter an access token as NTFY_TOKEN in the .env or in docker-compose.':
    'Chronione tematy na własnym serwerze: wpisz token dostępu jako NTFY_TOKEN w .env albo w docker-compose.',
  ' A token is stored.':
    ' Token jest zapisany.',
  'What to notify about?':
    'O czym powiadamiać?',
  'Once the local administrator has a password (<a class="link" href="#/einstellungen/benutzer">Settings → Users & permissions</a>), everyone signs in with their own Navidrome account and gets their own view. <a class="link" href="#/hilfe/konten">How it works →</a>':
    'Gdy administrator lokalny ma hasło (<a class="link" href="#/einstellungen/benutzer">Ustawienia → Użytkownicy i uprawnienia</a>), każdy loguje się własnym kontem Navidrome i dostaje własny widok. <a class="link" href="#/hilfe/konten">Jak to działa →</a>',
  'You change the password of the local administrator under Settings → Users & permissions.':
    'Hasło administratora lokalnego zmieniasz w Ustawienia → Użytkownicy i uprawnienia.',
  'New for you this week':
    'Nowe dla ciebie w tym tygodniu',
  'On Mondays to the person, if they have “Discovered for you” or “Album of the week”.':
    'W poniedziałki do osoby, jeśli ma „Odkryte dla ciebie” albo „Album tygodnia”.',
  'Navidrome plugin':
    'Wtyczka Navidrome',
  'With the plugin, Navidrome asks Tuttiphon for similar songs and passes every play on: Instant Mix, song and artist radio and the smart queue in Symfonium then follow the sound of your own music files – also for bands that other services hardly know. Needs Navidrome 0.64 or later.':
    'Dzięki wtyczce Navidrome pyta Tuttiphon o podobne piosenki i przekazuje każde odtworzenie: Instant Mix, radio piosenki i wykonawcy oraz inteligentna kolejka w Symfonium podążają wtedy za brzmieniem twoich własnych plików muzycznych – także dla zespołów, których inne serwisy prawie nie znają. Wymaga Navidrome 0.64 lub nowszego.',
  'Songs with a sound vector':
    'Piosenki z wektorem brzmienia',
  'No sound vectors yet – the AI sound analysis of the Docker image adds them night by night. Until then the plugin answers with similar bands from Last.fm and the genres.':
    'Jeszcze brak wektorów brzmienia – analiza brzmienia AI w obrazie Docker dodaje je noc po nocy. Do tego czasu wtyczka odpowiada podobnymi zespołami z Last.fm i gatunkami.',
  'Key':
    'Klucz',
  'Created {when}':
    'Utworzono {when}',
  'Navidrome signs in to Tuttiphon with it.':
    'Navidrome loguje się nim do Tuttiphon.',
  'New key':
    'Nowy klucz',
  'Create key':
    'Utwórz klucz',
  'Your key – shown only now:':
    'Twój klucz – widoczny tylko teraz:',
  'Copy':
    'Kopiuj',
  'Copied':
    'Skopiowano',
  'Select the text and copy it':
    'Zaznacz tekst i skopiuj go',
  'Last request from Navidrome':
    'Ostatnie zapytanie od Navidrome',
  '{n} since Tuttiphon started':
    '{n} od uruchomienia Tuttiphon',
  'Setting it up':
    'Konfiguracja',
  'Download the plugin':
    'Pobierz wtyczkę',
  'Download <b>tuttiphon.ndp</b> from the release on <a class="link" href="https://github.com/seluce/tuttiphon/releases" target="_blank" rel="noopener">GitHub</a>.':
    'Pobierz <b>tuttiphon.ndp</b> z wydania na <a class="link" href="https://github.com/seluce/tuttiphon/releases" target="_blank" rel="noopener">GitHub</a>.',
  'Put the file as it is – not unpacked and named exactly <b>tuttiphon.ndp</b>, Navidrome takes the name for its list of agents – into Navidrome’s plugins folder (in the Navidrome container <code>/data/plugins</code>) and put “tuttiphon” first in that list, in navidrome.toml or in docker-compose:':
    'Umieść plik bez zmian – nierozpakowany i nazwany dokładnie <b>tuttiphon.ndp</b>, bo Navidrome bierze tę nazwę do swojej listy agentów – w folderze wtyczek Navidrome (w kontenerze Navidrome <code>/data/plugins</code>) i ustaw „tuttiphon” na początku tej listy, w navidrome.toml albo w docker-compose:',
  'If there is a list already, put “tuttiphon,” in front of it – without one these are Navidrome’s defaults. The docker-compose line wins over navidrome.toml. Restart Navidrome afterwards; where Tuttiphon has no answer, Navidrome asks the next ones.':
    'Jeśli lista już istnieje, wstaw przed nią „tuttiphon,” – bez niej to są domyślne wartości Navidrome. Wiersz w docker-compose ma pierwszeństwo przed navidrome.toml. Potem uruchom ponownie Navidrome; gdzie Tuttiphon nie ma odpowiedzi, Navidrome pyta kolejnych.',
  'In Navidrome under <b>Settings → Plugins</b> turn on “Tuttiphon”, enter the address and the key and allow it <b>all users</b> (for the plays). Ideally the address in the home network, e.g. <code>http://&lt;NAS&gt;:8765</code> – not an https address through a reverse proxy, which may turn Navidrome away. This browser reaches Tuttiphon at <code>{address}</code>.':
    'W Navidrome w <b>Settings → Plugins</b> włącz „Tuttiphon”, wpisz adres i klucz i zezwól na <b>all users</b> – wszystkich użytkowników (dla odtworzeń). Najlepiej adres w sieci domowej, np. <code>http://&lt;NAS&gt;:8765</code> – nie adres https przez reverse proxy, który może odrzucić Navidrome. Ta przeglądarka łączy się z Tuttiphon pod <code>{address}</code>.',
  'In Symfonium, turn on <b>“Use similar tracks for Radio Mix”</b> for the Navidrome server (Manage media providers → the server) and choose <b>“Sonic Analysis”</b> for the smart queue in the player.':
    'W Symfonium włącz dla serwera Navidrome <b>„Use similar tracks for Radio Mix”</b> („Manage media providers” → serwer) i wybierz <b>„Sonic Analysis”</b> dla inteligentnej kolejki w odtwarzaczu.',
  'Navidrome does not say who is asking. If the song is playing on exactly one account – or only one account is playing – the answer is for that person: without their dislikes, without what they just heard or rated 1 star, what they often skip comes later, and after two songs of a band other bands come first. Otherwise for the family – without a family for everyone. Children’s music only for children’s songs, and without songs with explicit lyrics as soon as a person has kid-safe mode or is a child profile.':
    'Navidrome nie mówi, kto pyta. Jeśli piosenka gra właśnie na dokładnie jednym koncie – albo odtwarza tylko jedno konto – odpowiedź jest dla tej osoby: bez tego, czego nie lubi, bez tego, czego właśnie słuchała lub co oceniła na 1 gwiazdkę; to, co często pomija, pojawia się później, a po dwóch piosenkach jednego zespołu najpierw pojawiają się inne zespoły. W przeciwnym razie dla rodziny – bez rodziny dla wszystkich. Muzyka dziecięca tylko do piosenek dla dzieci i bez piosenek z wulgarnymi tekstami, gdy tylko jakaś osoba ma włączony tryb dla dzieci albo ma profil dziecka.',
  'Create a new key?':
    'Utworzyć nowy klucz?',
  'The old key stops working – enter the new one in Navidrome afterwards.':
    'Stary klucz przestanie działać – potem wpisz nowy w Navidrome.',
  'Remove the key?':
    'Usunąć klucz?',
  'Navidrome then gets no more answers from Tuttiphon and uses its other sources again – turn the plugin off in Navidrome as well.':
    'Navidrome nie dostanie wtedy więcej odpowiedzi od Tuttiphon i znów użyje innych źródeł – wyłącz też wtyczkę w Navidrome.',
  'Plays from Navidrome':
    'Odtworzenia z Navidrome',
  'Every play as it happens – exact listening times and real skips; for accounts without a stored password also the recap.':
    'Każde odtworzenie na bieżąco – dokładne czasy słuchania i prawdziwe pominięcia; dla kont bez zapisanego hasła także podsumowanie.',
  '{when} · {accounts}':
    '{when} · {accounts}',
  'none since Tuttiphon started':
    'brak od uruchomienia Tuttiphon',
  'Nothing yet? Put the new plugin file into Navidrome, restart it and allow the plugin all users.':
    'Jeszcze nic? Umieść nowy plik wtyczki w Navidrome, uruchom go ponownie i zezwól wtyczce na wszystkich użytkowników.',
  '{when} · for {name}':
    '{when} · dla osoby {name}',
  '{when} · for everyone':
    '{when} · dla wszystkich',
  '{when} · probably for {name}':
    '{when} · prawdopodobnie dla osoby {name}',
  'Last answer with similar songs':
    'Ostatnia odpowiedź z podobnymi piosenkami',
  'Copy {what}':
    'Kopiuj: {what}',
}
