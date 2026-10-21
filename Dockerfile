# Tuttiphon as a container – e.g. on a NAS (UGREEN, Synology, Unraid …) or with Portainer.
# Ready-made image: ghcr.io/seluce/tuttiphon (built by .github/workflows/docker.yaml for every release).
# The program lives in the image; data lives in volumes (see docker-compose.yaml):
#   /config   configuration, credentials (.env), state, logs
#   /music    the music folder Navidrome reads (MUSIC_DIR) · /archive the archive (ARCHIVE_DIR) · /backup (BACKUP_DIR)
# Update: "docker compose pull && docker compose up -d" – or, when building yourself, "docker compose up -d --build".

# 1. Build the interface (Svelte + Vite) – Node is only needed here, not in the final image
FROM node:22-slim AS ui
WORKDIR /src
COPY package.json package-lock.json vite.config.js ./
RUN npm ci --no-audit --no-fund
COPY frontend ./frontend
RUN npm run build

# 2. The actual image: Python + ffmpeg + AI sound analysis
FROM python:3.12-slim

# ffmpeg: FLAC→Opus, reading tags, sound analysis, loudness · fonts-dejavu-core + Pillow: designed playlist covers · curl: health check
# mutagen: write ReplayGain values into the music files (volume levelling)
# cryptography: notifications through the app (Web Push, encrypted)
# essentia-tensorflow: AI sound analysis (about 700 MB – runs only as a separate process during the analysis)
# libchromaprint-tools: fpcalc – audio fingerprints that find the same recording stored twice (Check library)
RUN apt-get update \
 && apt-get install -y --no-install-recommends ffmpeg curl tzdata fonts-dejavu-core libchromaprint-tools \
 && rm -rf /var/lib/apt/lists/* \
 && pip install --no-cache-dir "pillow==11.3.0" "mutagen==1.47.0" "cryptography==44.0.3" "numpy==2.5.4" "essentia-tensorflow==2.1b6.dev1389"

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    TUTTIPHON_DOCKER=1 \
    TUTTIPHON_DATA=/config \
    TUTTIPHON_BASE=/nas \
    TUTTIPHON_MODELS=/app/models \
    HOME=/tmp \
    TZ=Europe/Berlin

WORKDIR /app
# AI models (30 MB, with checksums) – their own layer so updates do not download them again. If the download
# fails, a build of your own still finishes; the AI sound analysis then reports that the models are missing.
# MODELS_REQUIRED=1 (the published image, .github/workflows/docker.yaml) stops the build instead.
ARG MODELS_REQUIRED=0
COPY app/ml_worker.py ./app/ml_worker.py
RUN python3 app/ml_worker.py --download /app/models \
 || if [ "$MODELS_REQUIRED" = "1" ]; then echo "✕ AI models could not be downloaded (MODELS_REQUIRED=1)"; exit 1; \
    else echo "⚠ AI models not loaded – the AI sound analysis stays off."; fi
COPY tuttiphon.py CHANGELOG.md LICENSE THIRD-PARTY-NOTICES.md ./
COPY app ./app
COPY --from=ui /src/web ./web
# the Navidrome plugin to download in Settings → Navidrome (tools/build-plugin.sh – built by the release and by
# GitHub Actions; a folder without it gives an image without it). LICENSE: so that the copy never comes up empty
COPY LICENSE navidrome-plugin/dis[t] ./plugin/
# Set permissions in the image itself: files copied to the NAS via a share often arrive readable only by their owner –
# but the container runs as the "user:" from docker-compose.yaml (e.g. 1000:1000) and must be able to read everything
RUN chmod -R a+rX /app \
 && mkdir -p /config /music /archive /backup && chmod 777 /config
# not as root – docker-compose.yaml sets the owner of the music files with "user:" (this is only the default)
USER 1000:1000

EXPOSE 8765
VOLUME ["/config"]

HEALTHCHECK --interval=60s --timeout=5s --start-period=60s \
  CMD curl -fs -o /dev/null http://127.0.0.1:8765/login.html || exit 1

# at the end, so a new version number does not invalidate the cached layers above
ARG VERSION=dev
LABEL org.opencontainers.image.title="Tuttiphon" \
      org.opencontainers.image.description="Smart playlists, mixes, lyrics, Opus/AAC and sound analysis for Navidrome" \
      org.opencontainers.image.source="https://github.com/seluce/tuttiphon" \
      org.opencontainers.image.licenses="AGPL-3.0-or-later" \
      org.opencontainers.image.version="$VERSION"

CMD ["python3", "tuttiphon.py", "serve", "--host", "0.0.0.0", "--port", "8765", "--no-browser"]
