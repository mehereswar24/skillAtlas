#!/usr/bin/env bash
#
# Install Docker Engine inside WSL2 Ubuntu.
#
# Run it from Windows:
#     wsl -d Ubuntu -- bash /mnt/c/Users/Mehereswar/Desktop/skillatlas/deploy/install-docker-wsl.sh
# or from inside a WSL shell:
#     bash ~/…/skillatlas/deploy/install-docker-wsl.sh
#
# You will be asked for your WSL password once, for sudo.
#
# ---------------------------------------------------------------------------
# Why Docker Engine and not Docker Desktop
# ---------------------------------------------------------------------------
# Two reasons, and the second one matters commercially.
#
# 1. Docker Desktop needs Windows administrator rights to install. This account
#    does not have them.
#
# 2. Docker Desktop is not free for a company this size. Its subscription terms
#    require a paid plan for organisations above 250 employees or $10M annual
#    revenue, and this machine is signed in as @granulesindia.com. Docker
#    *Engine* — what this script installs — is Apache-2.0 licensed and free for
#    any use, commercial included. It runs the same containers from the same
#    Dockerfiles.
#
# What you give up: the Docker Desktop GUI and its Kubernetes toggle. The CLI,
# compose, buildx and the daemon are all here.
# ---------------------------------------------------------------------------

set -euo pipefail

log() { printf '\n\033[1;36m==> %s\033[0m\n' "$*"; }
warn() { printf '\033[1;33m!!  %s\033[0m\n' "$*"; }

# --- sanity checks ---------------------------------------------------------

if ! grep -qi microsoft /proc/version 2>/dev/null; then
  warn "This does not look like WSL. The script still works on plain Ubuntu."
fi

. /etc/os-release
log "Ubuntu ${VERSION_ID} (${VERSION_CODENAME}), $(uname -m)"

# Docker's repository is published per codename. Verified present for
# 'resolute' at the time of writing; if a future codename is missing, the
# nearest older LTS ('noble') is a working fallback.
CODENAME="${VERSION_CODENAME}"
if ! curl -fsSL --head "https://download.docker.com/linux/ubuntu/dists/${CODENAME}/Release" >/dev/null 2>&1; then
  warn "Docker publishes nothing for '${CODENAME}'. Falling back to 'noble'."
  CODENAME="noble"
fi

# systemd must be PID 1, or `systemctl start docker` has nothing to talk to.
# WSL only runs it when /etc/wsl.conf asks for it.
if [ "$(ps -p 1 -o comm=)" != "systemd" ]; then
  warn "systemd is not PID 1. Add this to /etc/wsl.conf and run 'wsl --shutdown':"
  warn "    [boot]"
  warn "    systemd=true"
  exit 1
fi

log "Asking for sudo once, up front"
sudo -v

# --- remove the distro's unofficial packages -------------------------------
# Ubuntu ships docker.io / podman-docker, which conflict with Docker's own
# packages. Removing them is the documented first step.

log "Removing conflicting packages, if any"
for pkg in docker.io docker-doc docker-compose docker-compose-v2 podman-docker containerd runc; do
  sudo apt-get remove -y "$pkg" >/dev/null 2>&1 || true
done

# --- repository ------------------------------------------------------------

log "Installing prerequisites"
sudo apt-get update -qq
sudo apt-get install -y -qq ca-certificates curl gnupg

log "Adding Docker's signing key"
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg \
  -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc

log "Adding the Docker repository for ${CODENAME}"
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] \
https://download.docker.com/linux/ubuntu ${CODENAME} stable" \
  | sudo tee /etc/apt/sources.list.d/docker.list >/dev/null

# --- install ---------------------------------------------------------------

log "Installing Docker Engine, CLI, containerd, buildx and compose"
sudo apt-get update -qq
sudo apt-get install -y \
  docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

log "Enabling the daemon"
sudo systemctl enable --now docker
sudo systemctl enable --now containerd

# --- run as yourself, not root ---------------------------------------------
# Membership of the 'docker' group is equivalent to root on this machine: the
# daemon runs as root and will happily bind-mount /. That is the accepted
# trade-off for a single-user development box; on a shared host, use rootless
# mode instead.

log "Adding ${USER} to the docker group"
sudo groupadd -f docker
sudo usermod -aG docker "${USER}"

# --- verify ----------------------------------------------------------------

log "Verifying (as root, since your new group membership is not active yet)"
sudo docker run --rm hello-world

log "Versions"
sudo docker --version
sudo docker compose version

cat <<'DONE'

============================================================================
Docker Engine is installed and running.

One more step: your shell does not have the new 'docker' group yet, so
`docker` without sudo will say "permission denied" until you reload it.

From Windows, restart WSL:

    wsl --shutdown

Then reopen your shell and check it works without sudo:

    docker run --rm hello-world

To build and run SkillAtlas (from the repo root, inside WSL):

    cp deploy/.env.production.example deploy/.env
    # fill in SECRET_KEY, POSTGRES_PASSWORD, CORS_ORIGINS
    docker compose -f deploy/compose.prod.yml --env-file deploy/.env up -d --build

Note: build from a path inside WSL (e.g. ~/skillatlas), not /mnt/c/... .
Docker builds over the Windows filesystem bridge are many times slower.
============================================================================

DONE
