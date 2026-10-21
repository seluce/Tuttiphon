#!/usr/bin/env bash
# End-to-end check of the Navidrome plugin against a throwaway Navidrome and Tuttiphon (maintainers only) – builds
# the plugin and runs tools/plugin_check.py. Never touches the real Navidrome or the real data.
#
#   tools/plugin-check.sh [--keep]
#
# Needs Go and TinyGo (see tools/build-plugin.sh), ffmpeg and a Navidrome binary: TUTTIPHON_NAVIDROME (dev.local.env),
# otherwise "navidrome" in PATH or $TUTTIPHON_GO_TOOLS/navidrome/navidrome. Ports 4599 (Navidrome) and 8799 (Tuttiphon).
set -euo pipefail
cd "$(dirname "$0")/.."
if [ -f dev.local.env ]; then set -a; . ./dev.local.env; set +a; fi
nd="${TUTTIPHON_NAVIDROME:-$(command -v navidrome || true)}"
[ -z "$nd" ] && [ -n "${TUTTIPHON_GO_TOOLS:-}" ] && nd="$TUTTIPHON_GO_TOOLS/navidrome/navidrome"
[ -x "$nd" ] || { echo "✕ No Navidrome binary – set TUTTIPHON_NAVIDROME in dev.local.env"; exit 1; }
[ -d web ] || npm run build
tools/build-plugin.sh
exec python3 tools/plugin_check.py --navidrome "$nd" --plugin navidrome-plugin/dist/tuttiphon.ndp "$@"
