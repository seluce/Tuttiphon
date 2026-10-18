#!/usr/bin/env bash
# Start Tuttiphon and open it in the browser. If one is already running, only the browser is opened.
#   ./tuttiphon.sh                  interface (builds it first if needed: npm run build)
#   ./tuttiphon.sh run              update everything (without the interface, e.g. for cron)
#   ./tuttiphon.sh install-launcher add a "Tuttiphon" entry to the application menu
cd "$(dirname "$(readlink -f "$0")")" || exit 1
PORT=8765
# Personal settings (not in Git), e.g. TUTTIPHON_BASE=/path/to/the/Navidrome/folder – see dev.local.env in the README
if [ -f dev.local.env ]; then set -a; . ./dev.local.env; set +a; fi
# Data (configuration, credentials, state, logs) lives in data/ – never put it into Git.
export TUTTIPHON_DATA="${TUTTIPHON_DATA:-$PWD/data}"
# Navidrome folder with Music/ (and Archiv/): without TUTTIPHON_BASE the folder above the project is used
[ -n "${TUTTIPHON_BASE:-}" ] && export TUTTIPHON_BASE

case "${1:-}" in
  install-launcher)
    target="$HOME/.local/share/applications/tuttiphon.desktop"
    mkdir -p "$(dirname "$target")"
    cat >"$target" <<EOF
[Desktop Entry]
Type=Application
Name=Tuttiphon
Comment=Smart playlists and maintenance for Navidrome
Exec=$(pwd)/tuttiphon.sh
Icon=multimedia-player
Terminal=false
Categories=AudioVideo;Audio;
EOF
    rm -f "$HOME/.local/share/applications/navitool.desktop"   # entry from the time when Tuttiphon was called NaviTool
    echo "Menu entry created: $target"
    exit 0 ;;
  "") ;;
  *) exec python3 tuttiphon.py "$@" ;;
esac

# Build the interface if it is missing or the sources are newer (needs Node.js; without Node an existing build is kept)
build_ui() {
  if [ -f web/index.html ] && [ -z "$(find frontend package.json package-lock.json vite.config.js -newer web/index.html -print -quit 2>/dev/null)" ]; then
    return 0
  fi
  if ! command -v npm >/dev/null 2>&1; then
    [ -f web/index.html ] && return 0
    echo "Tuttiphon: the interface needs Node.js (npm run build)." >&2
    exit 1
  fi
  if [ ! -d node_modules ] || [ package-lock.json -nt node_modules/.package-lock.json ]; then
    npm ci --no-audit --no-fund || exit 1
  fi
  npm run build || exit 1
}

if curl -s -o /dev/null "http://127.0.0.1:$PORT/api/config" 2>/dev/null; then
  xdg-open "http://127.0.0.1:$PORT/" >/dev/null 2>&1 &
  exit 0
fi
build_ui
exec python3 tuttiphon.py serve --port "$PORT"
