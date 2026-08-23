#!/usr/bin/env bash
# Diagnostic: `npm ci` exit code and the TAIL of its output (the error lives at
# the end, after the peer-dependency warnings).
set -euo pipefail
cd /home/mehereswar/skillatlas/frontend

cat > /tmp/case.Dockerfile <<'EOF'
FROM node:22-alpine
WORKDIR /app
COPY package.json package-lock.json ./
RUN set +e; npm ci >/tmp/out.txt 2>&1; echo "EXITCODE=$?"; \
    echo "=== last 30 lines ==="; tail -30 /tmp/out.txt; exit 0
EOF

docker build -f /tmp/case.Dockerfile --progress=plain --no-cache -t casediag . 2>&1 \
  | grep -aE "^#[0-9]+ [0-9.]+ " | sed 's/^#[0-9]* [0-9.]* //' | tail -35

docker image rm -f casediag >/dev/null 2>&1 || true
