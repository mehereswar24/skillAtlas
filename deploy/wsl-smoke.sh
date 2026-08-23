#!/usr/bin/env bash
# Bring the production stack up and prove it actually serves.
#
#     wsl -d Ubuntu -- bash /mnt/c/.../deploy/wsl-smoke.sh
#
# Building an image says the Dockerfile is syntactically valid. This says the
# thing runs: migrations applied against Postgres, content seeded and served,
# security headers present, rate limiting live, docs closed.
set -uo pipefail

cd /home/mehereswar/skillatlas
COMPOSE="docker compose -f deploy/compose.prod.yml --env-file deploy/.env"

log() { printf '\n\033[1;36m==> %s\033[0m\n' "$*"; }

pass=0
fail=0
check() {
  local name="$1" got="$2" want="$3"
  if [ "$got" = "$want" ]; then
    printf '  PASS  %-50s %s\n' "$name" "$got"
    pass=$((pass + 1))
  else
    printf '  FAIL  %-50s got=[%s] want=[%s]\n' "$name" "$got" "$want"
    fail=$((fail + 1))
  fi
}

# Run a snippet of Python inside the api container. Written to a file and piped
# in on stdin rather than passed as `python -c "..."`: the quoting survives
# three layers of shell that way, and nothing has to be escaped.
api_py() {
  $COMPOSE exec -T api python - 2>/dev/null
}

# A smoke test proves a *fresh* deploy works, so it starts from nothing. `-v`
# drops the Postgres volume too: a failed migration leaves the schema half
# applied, and re-running against that tests a state no real deploy is ever in.
# Destructive by design — never point this at anything you care about.
log "Tearing down any previous stack (including its data)"
$COMPOSE down -v --remove-orphans 2>&1 | tail -3

log "Starting stack"
$COMPOSE up -d 2>&1 | tail -6

log "Waiting for every service to report healthy"
for i in $(seq 1 60); do
  states=$($COMPOSE ps --format '{{.Service}}={{.Health}}' 2>/dev/null | tr '\n' ' ')
  printf '  [%02d] %s\n' "$i" "$states"
  # `web` has no dependants, so compose does not wait on it for us.
  case "$states" in
    *api=healthy*web=healthy* | *web=healthy*api=healthy*) break ;;
  esac
  sleep 5
done

log "Container states"
$COMPOSE ps --format 'table {{.Service}}\t{{.Status}}'

log "Seeding content"
$COMPOSE exec -T api python -m app.seed.loader 2>&1 | tail -3

log "API checks (from inside the container)"

check "liveness" "$(api_py <<'PY'
import json, urllib.request
print(json.load(urllib.request.urlopen("http://127.0.0.1:8000/health"))["status"])
PY
)" "ok"

check "readiness (database reachable)" "$(api_py <<'PY'
import json, urllib.request
print(json.load(urllib.request.urlopen("http://127.0.0.1:8000/health/ready"))["status"])
PY
)" "ready"

check "interactive docs are closed" "$(api_py <<'PY'
import urllib.error, urllib.request
try:
    urllib.request.urlopen("http://127.0.0.1:8000/docs")
    print(200)
except urllib.error.HTTPError as exc:
    print(exc.code)
PY
)" "404"

check "running on postgres, not sqlite" "$(api_py <<'PY'
from app.config import settings
print(settings.database_url.split("://")[0])
PY
)" "postgresql+psycopg2"

check "production guard is active" "$(api_py <<'PY'
from app.config import settings
print(settings.is_production and not settings.debug and not settings.docs_enabled)
PY
)" "True"

check "tracks seeded" "$(api_py <<'PY'
from sqlalchemy import func, select
from app.database import SessionLocal
from app.models.content import Track
with SessionLocal() as db:
    print(db.scalar(select(func.count()).select_from(Track)))
PY
)" "92"

check "no third-party prose in the database" "$(api_py <<'PY'
from sqlalchemy import select
from app.database import SessionLocal
from app.models.content import Concept, Track
from app.services.publishing import (
    AUTHORED_TRACK_SLUGS, DEPTH_OUTLINE, concept_depth,
)
with SessionLocal() as db:
    authored = {
        tc.concept_id
        for t in db.scalars(select(Track).where(Track.slug.in_(AUTHORED_TRACK_SLUGS)))
        for tc in t.track_concepts
    }
    bad = [
        c.slug for c in db.scalars(select(Concept))
        if c.id not in authored and concept_depth(c.content_md) != DEPTH_OUTLINE
    ]
print(len(bad))
PY
)" "0"

log "Web tier (published on the host)"

check "homepage" \
  "$(curl -s -o /dev/null -w '%{http_code}' --max-time 30 http://127.0.0.1:3000/)" "200"

curl -sI --max-time 30 http://127.0.0.1:3000/ 2>/dev/null | tr -d '\r' > /tmp/hdrs.txt
check "sends X-Frame-Options"         "$(grep -ci '^x-frame-options:' /tmp/hdrs.txt)" "1"
check "sends Content-Security-Policy" "$(grep -ci '^content-security-policy:' /tmp/hdrs.txt)" "1"
check "sends X-Content-Type-Options"  "$(grep -ci '^x-content-type-options:' /tmp/hdrs.txt)" "1"
check "hides its framework version"   "$(grep -ci '^x-powered-by:' /tmp/hdrs.txt)" "0"

check "a real content page renders" \
  "$(curl -s -o /dev/null -w '%{http_code}' --max-time 30 http://127.0.0.1:3000/explore)" "200"

log "Rate limiting is live (auth limit is 10/min per client)"
codes=""
for i in $(seq 1 15); do
  codes="$codes$(curl -s -o /dev/null -w '%{http_code} ' --max-time 15 \
    -X POST http://127.0.0.1:3000/api/auth/login \
    -H 'content-type: application/json' \
    -d '{"email":"smoke@example.com","password":"wrong-on-purpose"}')"
done
echo "  codes: $codes"
throttled=$(echo "$codes" | tr ' ' '\n' | grep -c '^429$')
check "burst of 15 logins hits a 429" "$([ "$throttled" -gt 0 ] && echo yes || echo no)" "yes"

log "Result: ${pass} passed, ${fail} failed"
[ "$fail" -eq 0 ]
