#!/usr/bin/env bash
#
# Builds the release/ folder – exactly the files needed to build Tuttiphon yourself on a server (instead of the
# ready-made image from GitHub): copy it into the folder of the Docker project, there "docker compose up -d --build".
#
#   npm run release             program and docker-compose.example.yaml (set to build)
#   npm run release:with-data   additionally first-install/config/ from data/ (only for moving an existing installation,
#                               e.g. from the PC to the NAS; same as: npm run release -- --with-data)
#
# Version: app/version.py. What changes: CHANGELOG.md – the section for the current version must exist and goes
# into README.txt (which also says when docker-compose.yaml has to be replaced). Between releases the version ends in
# "+dev" and the section is "## Unreleased" – such a folder is marked as not released.
#
# Why a list of what MAY go in (and not "everything except …"): data/ contains credentials. With an exclusion
# list one forgotten entry is enough for them to end up in the program part. At the end the script also checks
# that none of it lies outside first-install/. frontend/ holds only sources and goes in as a whole (without
# node_modules) – like "COPY frontend" in the Dockerfile, so a new build file there (e.g. svelte.config.js) is not
# forgotten.
#
# Checked first: Python compiles, Python tests pass, the interface builds without errors. The interface is built
# again on the NAS (Node stage in the Dockerfile) – this run only makes sure an error does not show up there first.
set -euo pipefail
cd "$(dirname "$0")/.."

TARGET="release"
WITH_DATA=0
for arg in "$@"; do
  case "$arg" in
    --with-data|--mit-daten) WITH_DATA=1 ;;
    *) echo "Unknown option: $arg" >&2; exit 2 ;;
  esac
done

VERSION=$(sed -n 's/^VERSION = "\(.*\)"/\1/p' app/version.py)
[ -n "$VERSION" ] || { echo "✕ No version in app/version.py"; exit 1; }
case "$VERSION" in
  *+dev) SECTION="Unreleased"; LABEL=" (not released yet)" ;;
  *) SECTION="$VERSION"; LABEL="" ;;
esac
NOTES=$(awk -v v="$SECTION" 'index($0, "## " v) == 1 && (length($0) == length(v) + 3 || substr($0, length(v) + 4, 1) == " ") {on=1; print; next} /^## / {on=0} on' CHANGELOG.md)
[ -n "$NOTES" ] || { echo "✕ CHANGELOG.md has no section \"## $SECTION\""; exit 1; }
echo "▶ Checking … (version $VERSION)"
LOGS=$(mktemp -d "${TMPDIR:-/tmp}/tuttiphon-release.XXXXXX")
python3 -m py_compile app/*.py tuttiphon.py
{ node tools/i18n-check.mjs && python3 tools/i18n_check.py; } >"$LOGS/i18n.log" 2>&1 \
  || { echo "✕ Translations incomplete – see $LOGS/i18n.log"; exit 1; }
python3 -m unittest discover -s tests/python -t . >"$LOGS/tests.log" 2>&1 \
  || { echo "✕ Python tests fail – see $LOGS/tests.log"; exit 1; }
npm run -s build >"$LOGS/build.log" 2>&1 \
  || { echo "✕ Interface does not build – see $LOGS/build.log"; exit 1; }
if grep -qiE "warn|vite-plugin-svelte|a11y|\(!\)" "$LOGS/build.log"; then   # Svelte's own warnings say no "warn"
  echo "✕ Interface builds with warnings – see $LOGS/build.log"; exit 1
fi
PLUGIN=1
if ! tools/build-plugin.sh >"$LOGS/plugin.log" 2>&1; then
  if grep -q "not found" "$LOGS/plugin.log"; then   # no Go/TinyGo here: a release without the plugin file
    PLUGIN=0
    echo "⚠ Navidrome plugin not built (Go/TinyGo missing) – see $LOGS/plugin.log. When updating a NAS, delete"
    echo "  navidrome-plugin/dist/ there, otherwise the image takes the old plugin file along."
  else
    echo "✕ The Navidrome plugin does not build – see $LOGS/plugin.log"; exit 1
  fi
fi

rm -rf "$TARGET"
mkdir -p "$TARGET"

# ---- Program (allowlist)
cp Dockerfile .dockerignore tuttiphon.py CHANGELOG.md LICENSE THIRD-PARTY-NOTICES.md package.json package-lock.json \
   vite.config.js "$TARGET/"
# docker-compose.example.yaml: the template, but built from this folder instead of pulling the ready-made image.
# Deliberately not "docker-compose.yaml": copied by mistake next to an existing docker-compose.yml, Docker Compose
# would prefer it and start with the example paths.
python3 - docker-compose.yaml "$TARGET/docker-compose.example.yaml" <<'PY'
import sys
src = open(sys.argv[1], encoding="utf-8").read()
start = src.index("    image: ghcr.io/seluce/tuttiphon:latest\n")
end = src.index("    container_name:", start)
build = ("    build: .                       # built from this folder (ready-made image instead: "
         "image: ghcr.io/seluce/tuttiphon:latest)\n    image: tuttiphon:local\n    pull_policy: build\n")
open(sys.argv[2], "w", encoding="utf-8").write(src[:start] + build + src[end:])
PY
mkdir -p "$TARGET/app" "$TARGET/frontend"
cp app/*.py app/*.json "$TARGET/app/"
cp -r app/locales "$TARGET/app/"   # translations of the server texts – without them the server would speak English only
cp -r frontend/. "$TARGET/frontend/"   # sources, svelte.config.js (runes) and README.md
if [ "$PLUGIN" = 1 ]; then   # the built Navidrome plugin – the Dockerfile takes it into the image
  mkdir -p "$TARGET/navidrome-plugin/dist" && cp navidrome-plugin/dist/tuttiphon.ndp "$TARGET/navidrome-plugin/dist/"
fi
find "$TARGET" \( -name "__pycache__" -o -name "node_modules" \) -prune -exec rm -rf {} +

# ---- Data for the very first move (same selection as a backup: without cache, sign-ins, locks)
if [ "$WITH_DATA" = 1 ]; then
  if ss -ltn 2>/dev/null | grep -q ":8765 "; then
    echo "⚠ A Tuttiphon server is still running on the PC (port 8765). The data is the state as of now – change nothing"
    echo "  on the PC afterwards and stop it before the move (otherwise: stop Tuttiphon on the PC and run this script again)."
  fi
  TUTTIPHON_DATA="$PWD/data" python3 - "$TARGET/first-install/config" <<'PY'
import os, shutil, sys
from pathlib import Path
from app import backup
target = Path(sys.argv[1])
n = 0
for path, arc in backup._files():
    if Path(arc).name in ("instances.json", "secret"):
        continue   # old PC state or session key – the container creates both anew
    dst = target / arc
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(path, dst)
    n += 1
os.chmod(target / ".env", 0o600) if (target / ".env").exists() else None
print(f"  first-install/config: {n} files")
PY
fi

# ---- Safety net: no data or credentials in the program part
leak=$(find "$TARGET" -path "$TARGET/first-install" -prune -o \( -name ".env" -o -name "config.json" -o -name "secret" \
       -o -name "sessions.json" -o -path "*/state/*" -o -name "node_modules" \) -print)
if [ -n "$leak" ]; then
  echo "✕ The program part contains something that does not belong there:"; echo "$leak"; rm -rf "$TARGET"; exit 1
fi

# ---- README.txt
stamp=$(date "+%Y-%m-%d %H:%M")
if git rev-parse --verify -q HEAD >/dev/null 2>&1; then
  ref="Git commit $(git rev-parse --short HEAD)"
  [ -n "$(git status --porcelain)" ] && ref="$ref + uncommitted changes"
else
  ref="no Git commit yet"
fi
files=$(find "$TARGET" -path "$TARGET/first-install" -prune -o -type f -print | wc -l)
cat > "$TARGET/README.txt" <<TXT
Tuttiphon $VERSION$LABEL – release of $stamp ($ref)

Everything to build Tuttiphon yourself on the server (instead of the ready-made image ghcr.io/seluce/tuttiphon).
Target: the folder of your Docker project, e.g. /volume1/docker/tuttiphon – the settings live there in the
subfolder config/ (in the container /config).

FIRST SETUP
 1. Copy everything from this folder EXCEPT first-install/ into the project folder.
    Include the hidden file: .dockerignore
 2. Rename docker-compose.example.yaml to docker-compose.yaml and adjust the lines marked CHANGE: user: (owner of the music files – "ls -n" in the music
    folder shows the numbers), music folder, archive, TZ (time zone), Navidrome address.
 3. Create the folders before the first start and give them to the user from "user:" – otherwise Docker creates
    them for root, Tuttiphon cannot write there and the container keeps restarting. In the project folder, e.g.:
      mkdir -p config backups /path/to/music-archive
      chown 1000:1000 config backups /path/to/music-archive
 4. Only when moving an existing installation (e.g. from a PC): stop it and do not start it there again. Copy
    first-install/config/ as config/ into the project folder (include the hidden file .env) and give it to the user
    from "user:" as in step 3. Permissions of config/: read/write for that user only – not "for everyone" (the
    passwords are in there). (first-install/ comes from "npm run release:with-data" on the PC.)
 5. Create and start the project in the Docker app of the NAS (or "docker compose up -d --build") – 10–15 minutes
    the first time.
 6. Open http://<NAS address>:8765 and set the password of the local administrator – with the setup code from
    the container log (also in config/setup-code.txt). The setup assistant then connects Navidrome; afterwards check
    Settings → Storage locations. In detail: README.md on GitHub (https://github.com/seluce/tuttiphon).

UPDATE (later versions)
 1. Copy everything from this folder EXCEPT first-install/ into the project folder and replace the existing files.
    Do NOT touch config/. Your own docker-compose.yaml (or .yml) stays as it is; docker-compose.example.yaml is
    only the template for comparing, if "NEW IN THIS VERSION" says so.
 2. Rebuild/recreate the project in the Docker app (or "docker compose up -d --build"). The data stays in config/.

NEW IN THIS VERSION
$(echo "$NOTES" | sed 's/^/ /')
 All versions: CHANGELOG.md

Contents: $files files (program, interface sources, Dockerfile, docker-compose.example.yaml, licenses)
TXT

echo "✓ $TARGET/ done – Tuttiphon $VERSION$LABEL, $files files$( [ "$WITH_DATA" = 1 ] && echo ", plus first-install/config/")."
[ "$WITH_DATA" = 1 ] || echo "  (without data – for moving an installation with first-install/config/: npm run release:with-data)"
echo "  Copy the contents into the folder of the Docker project – see $TARGET/README.txt"
