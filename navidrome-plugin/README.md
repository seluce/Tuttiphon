# Tuttiphon plugin for Navidrome

Passes Navidrome's questions for similar songs and artists to Tuttiphon, which answers from the sound of the music
files (its AI sound analysis): Instant Mix, song and artist radio, related artists (`getSimilarSongs2`,
`getArtistInfo2`) and the OpenSubsonic extension `sonicSimilarity` (`getSonicSimilarTracks`, `findSonicPath`).
The plugin itself only asks `GET <Tuttiphon>/api/sonic/<similar|artist|album|artists|path>` with the key from its
settings (`Authorization: Bearer …`) and hands the answer back – the answers are made in `app/sonic.py`.

- Setting it up: Tuttiphon's Settings → Navidrome → "Navidrome plugin", and [docs/08-operations.md](../docs/08-operations.md#navidrome-plugin).
- Building: `tools/build-plugin.sh` (Go and TinyGo) → `dist/tuttiphon.ndp` (a zip of `manifest.json` with Tuttiphon's
  version and `plugin.wasm`).
- Checking end to end: `tools/plugin-check.sh` – a throwaway Navidrome with the plugin and a throwaway Tuttiphon.
- Plugin development kit: `github.com/navidrome/navidrome/plugins/pdk/go`, pinned to the commit of Navidrome 0.64.2
  (`go.mod`); when Navidrome changes its plugin interface, update it there and run the check again.

License: AGPL-3.0, like Tuttiphon (see `../THIRD-PARTY-NOTICES.md` for the parts it contains).
