#!/usr/bin/env bash
# Builds the Navidrome plugin: navidrome-plugin/dist/tuttiphon.ndp (a zip of manifest.json with Tuttiphon's version,
# plugin.wasm compiled with TinyGo for WebAssembly (wasip1), and the licenses LICENSES.txt and GPL-3.0.txt).
#
#   tools/build-plugin.sh
#
# Needs Go and TinyGo – in PATH, or in the folder TUTTIPHON_GO_TOOLS (dev.local.env) with go/ and tinygo/ in it.
# The Docker image takes the built file along (Dockerfile: COPY navidrome-plugin/dis[t]); GitHub Actions builds it
# for every release (.github/workflows/docker.yaml).
set -euo pipefail
cd "$(dirname "$0")/.."
if [ -f dev.local.env ]; then set -a; . ./dev.local.env; set +a; fi
if [ -n "${TUTTIPHON_GO_TOOLS:-}" ]; then
  PATH="$TUTTIPHON_GO_TOOLS/go/bin:$TUTTIPHON_GO_TOOLS/tinygo/bin:$PATH"
fi
export GOTELEMETRY=off GOFLAGS=-modcacherw
command -v go >/dev/null || { echo "✕ Go not found – install Go or set TUTTIPHON_GO_TOOLS in dev.local.env"; exit 1; }
command -v tinygo >/dev/null || { echo "✕ TinyGo not found – install TinyGo or set TUTTIPHON_GO_TOOLS in dev.local.env"; exit 1; }

VERSION=$(sed -n 's/^VERSION = "\(.*\)"/\1/p' app/version.py)
[ -n "$VERSION" ] || { echo "✕ No version in app/version.py"; exit 1; }
tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT
(cd navidrome-plugin && tinygo build -o "$tmp/plugin.wasm" -target wasip1 -buildmode=c-shared -no-debug .)
mkdir -p navidrome-plugin/dist
rm -f navidrome-plugin/dist/*.part   # a run cut off before
python3 - "$VERSION" "$tmp/plugin.wasm" navidrome-plugin/manifest.json navidrome-plugin/dist/tuttiphon.ndp <<'PY'
import json, sys, zipfile
version, wasm, manifest, out = sys.argv[1:]
m = json.load(open(manifest, encoding="utf-8"))
m["version"] = version
with zipfile.ZipFile(out + ".part", "w", zipfile.ZIP_DEFLATED) as z:
    z.writestr("manifest.json", json.dumps(m, ensure_ascii=False, indent=2) + "\n")
    z.write(wasm, "plugin.wasm")
    for name in ("LICENSES.txt", "GPL-3.0.txt"):   # the licenses of what plugin.wasm contains go along
        z.write("navidrome-plugin/" + name, name)
import os
os.replace(out + ".part", out)
PY
echo "✓ navidrome-plugin/dist/tuttiphon.ndp – Tuttiphon plugin $VERSION ($(( $(wc -c < navidrome-plugin/dist/tuttiphon.ndp) / 1024 )) KB)"
