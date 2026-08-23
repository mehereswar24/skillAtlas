#!/usr/bin/env bash
#
# Sync the working tree into WSL's own filesystem and build the images there.
#
#     wsl -d Ubuntu -- bash /mnt/c/Users/Mehereswar/Desktop/skillatlas/deploy/wsl-sync-and-build.sh
#
# Why sync rather than build in place: Docker reads the whole build context,
# and doing that across the /mnt/c bridge is many times slower than on ext4.
# The excludes below mirror the .dockerignore files — 3.9GB of node_modules,
# .next and venv never need to cross.
#
# Run it again after any source change; rsync only moves what differs.

set -euo pipefail

SRC="/mnt/c/Users/Mehereswar/Desktop/skillatlas"
DST="${HOME}/skillatlas"

log() { printf '\n\033[1;36m==> %s\033[0m\n' "$*"; }

log "Syncing ${SRC} -> ${DST}"
mkdir -p "${DST}"
rsync -a --delete \
  --exclude 'backend/venv/' \
  --exclude 'frontend/node_modules/' \
  --exclude 'frontend/.next/' \
  --exclude '.git/' \
  --exclude 'backend/.backup-pre*/' \
  --exclude 'backend/.frag/' \
  --exclude 'backend/.authoring/' \
  --exclude 'backend/.qa/' \
  --exclude 'backend/qa/' \
  --exclude 'frontend/.qa*/' \
  --exclude 'frontend/qa/' \
  --exclude '__pycache__/' \
  --exclude '*.db' --exclude '*.db-wal' --exclude '*.db-shm' \
  --exclude '*.log' \
  "${SRC}/" "${DST}/"

log "Synced. Context sizes Docker will actually read:"
du -sh "${DST}/backend" "${DST}/frontend"

cd "${DST}"

# A .env is required by compose for SECRET_KEY and POSTGRES_PASSWORD. Generate
# one for local verification if it is absent — these values never leave this
# machine, and a real deployment fills the file in by hand.
if [ ! -f deploy/.env ]; then
  log "No deploy/.env — generating one for a local build/run"
  {
    echo "SECRET_KEY=$(head -c 48 /dev/urandom | base64 | tr -d '/+=' | head -c 64)"
    echo "POSTGRES_PASSWORD=$(head -c 24 /dev/urandom | base64 | tr -d '/+=' | head -c 32)"
    echo "POSTGRES_USER=skillatlas"
    echo "POSTGRES_DB=skillatlas"
    # Localhost is permitted past the plaintext-origin guard precisely so a
    # production image can be smoke-tested on the machine that built it.
    echo 'CORS_ORIGINS=["http://localhost:3000"]'
    echo "WEB_PORT=3000"
    echo "SEED_ON_START=false"
  } > deploy/.env
  chmod 600 deploy/.env
fi

log "Building images"
docker compose -f deploy/compose.prod.yml --env-file deploy/.env build

log "Built. Images:"
docker images --format 'table {{.Repository}}\t{{.Tag}}\t{{.Size}}' | head -10
