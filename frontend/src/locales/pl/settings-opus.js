// Same keys as ../de/settings-opus.js (tools/translate.py)
export default {
  'At least one format':
    'Co najmniej jeden format',
  'Delete originals?':
    'Usunąć oryginały?',
  'The lossless originals are deleted after converting instead of archived. This cannot be undone.':
    'Bezstratne oryginały zostaną po konwersji usunięte zamiast zarchiwizowane. Tego nie można cofnąć.',
  'Yes, delete':
    'Tak, usuń',
  'Please enter as UID:GID, e.g. 1000:1000':
    'Wpisz jako UID:GID, np. 1000:1000',
  'Convert lossless files':
    'Konwertuj pliki bezstratne',
  'Converted music sounds like the original but takes only about a fifth of the space – ideal for phones. Every new file is fully checked before Tuttiphon touches the original; tags and cover are kept.':
    'Skonwertowana muzyka brzmi jak oryginał, ale zajmuje tylko ok. jednej piątej miejsca – idealne dla telefonów. Każdy nowy plik jest w pełni sprawdzany, zanim Tuttiphon dotknie oryginału; tagi i okładka zostają zachowane.',
  'ffmpeg/ffprobe are missing on this computer – please install them. The Docker image includes them.':
    'Na tym komputerze brakuje ffmpeg/ffprobe – zainstaluj je. Obraz Docker je zawiera.',
  'For AAC, this computer lacks a package that carries the tags over. The Docker image includes everything.':
    'Dla AAC na tym komputerze brakuje pakietu, który przenosi tagi. Obraz Docker zawiera wszystko.',
  'Files to convert: {n}':
    'Pliki do konwersji: {n}',
  'Nothing to convert':
    'Nic do konwersji',
  'count again':
    'policz ponownie',
  'Music: {music} · Archive: {archive}':
    'Muzyka: {music} · Archiwum: {archive}',
  'Conversion on':
    'Konwersja włączona',
  'Target format':
    'Format docelowy',
  'Opus is the smallest and ideal for Android. iPhone, iPad and Mac play AAC everywhere. Applies to new conversions; finished files stay as they are.':
    'Opus jest najmniejszy i idealny dla Androida. iPhone, iPad i Mac odtwarzają AAC wszędzie. Dotyczy nowych konwersji; gotowe pliki pozostają bez zmian.',
  'Which formats?':
    'Które formaty?',
  'Lossless only – .m4a only if it contains ALAC.':
    'Tylko bezstratne – .m4a tylko, jeśli zawiera ALAC.',
  'Quality':
    'Jakość',
  'kbit/s. AAC needs a little more than Opus for the same sound. 224 is the default, 256 for purists.':
    'kbit/s. AAC potrzebuje trochę więcej niż Opus dla tego samego brzmienia. 224 to wartość domyślna, 256 dla purystów.',
  'kbit/s. 128 is enough for phones, 160 is the default, 256 for purists.':
    'kbit/s. 128 wystarcza dla telefonów, 160 to wartość domyślna, 256 dla purystów.',
  'Original afterwards':
    'Oryginał potem',
  'Only once the new file is fully checked.':
    'Dopiero gdy nowy plik zostanie w pełni sprawdzony.',
  'to the archive':
    'do archiwum',
  'keep':
    'zachowaj',
  'delete':
    'usuń',
  'Archive folder':
    'Folder archiwum',
  'The folder structure is kept.':
    'Struktura folderów zostaje zachowana.',
  'Storage locations':
    'Lokalizacje',
  'Waiting time':
    'Czas oczekiwania',
  'Leave freshly imported files alone for this many minutes in case Lidarr is still writing.':
    'Nie ruszaj świeżo zaimportowanych plików przez tyle minut, na wypadek gdyby Lidarr jeszcze zapisywał.',
  'Advanced':
    'Zaawansowane',
  'Simultaneous conversions':
    'Równoczesne konwersje',
  'More = faster, but more load on the computer/NAS.':
    'Więcej = szybciej, ale większe obciążenie komputera/NAS.',
  'Owner of new files':
    'Właściciel nowych plików',
  'Empty = the user Tuttiphon runs as (user: in docker-compose.yaml). Otherwise UID:GID as in Lidarr – only works with sufficient rights.':
    'Puste = użytkownik, jako który działa Tuttiphon (user: w docker-compose.yaml). W przeciwnym razie UID:GID jak w Lidarr – działa tylko przy wystarczających uprawnieniach.',
  'Even out loudness':
    'Wyrównaj głośność',
  'At night Tuttiphon measures how loud each song is and writes ReplayGain values into the files without re-encoding them. Turn on ReplayGain in Symfonium and all songs play equally loud, even in a mix from a children\'s song to metal.':
    'Nocą Tuttiphon mierzy, jak głośna jest każda piosenka, i zapisuje wartości ReplayGain w plikach bez ponownego kodowania. Włącz ReplayGain w Symfonium, a wszystkie piosenki zagrają równie głośno, nawet w mixie od piosenki dla dzieci po metal.',
  'Leveling on':
    'Wyrównywanie włączone',
  'Writes once into every music file. Each file is copied and checked first, only then replaced. Values that already came from elsewhere stay.':
    'Zapisuje jednorazowo w każdym pliku muzycznym. Każdy plik jest najpierw kopiowany i sprawdzany, dopiero potem zastępowany. Wartości, które pochodziły już skądinąd, zostają.',
  'Album values too':
    'Także wartości albumowe',
  'For albums you listen to in one go: quiet and loud songs of an album keep their balance.':
    'Dla albumów słuchanych w całości: ciche i głośne piosenki albumu zachowują swoje proporcje.',
  'Not possible here: {why}. The Docker container on the NAS includes everything.':
    'Tutaj niemożliwe: {why}. Kontener Docker na NAS zawiera wszystko.',
  '{measured} of {songs} songs measured · {written} with values written':
    'Zmierzono {measured} z {songs} piosenek · z zapisanymi wartościami: {written}',
  ' · {n} already had their own':
    ' · własne miały już: {n}',
  'Run now':
    'Uruchom teraz',
  'Convert now':
    'Konwertuj teraz',
  'Dry run':
    'Próbny przebieg',
}
