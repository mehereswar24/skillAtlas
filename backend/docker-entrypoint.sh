#!/bin/sh
# Bring the database up to date, then hand off to the server.
#
# `exec` at the end matters: it replaces this shell with gunicorn so gunicorn
# becomes PID 1 and receives SIGTERM directly. Without it the shell holds PID 1,
# ignores the signal, and every deploy waits out the orchestrator's kill timeout
# before dying hard mid-request.
set -eu

echo "[entrypoint] environment=${ENVIRONMENT:-unset}"

# ---------------------------------------------------------------- wait for db
# Postgres accepts TCP connections before it is ready to answer queries, so
# poll with a real query rather than a port check.
if [ "${DATABASE_URL#postgres}" != "${DATABASE_URL:-}" ]; then
  echo "[entrypoint] waiting for postgres..."
  attempts=0
  until python -c "
import os, sys
from sqlalchemy import create_engine, text
try:
    create_engine(os.environ['DATABASE_URL'], pool_pre_ping=True).connect().execute(text('SELECT 1'))
except Exception as exc:
    print(f'  not ready: {type(exc).__name__}', file=sys.stderr)
    sys.exit(1)
" 2>/dev/null; do
    attempts=$((attempts + 1))
    if [ "$attempts" -ge 60 ]; then
      echo "[entrypoint] postgres did not become ready after 60 attempts" >&2
      exit 1
    fi
    sleep 2
  done
  echo "[entrypoint] postgres is ready"
fi

# ---------------------------------------------------------------- migrations
# Run on boot so a deploy cannot serve traffic against an older schema.
#
# Safe with several replicas starting at once: alembic takes a lock on its
# version table, so the losers block and then find nothing to do. It is *not*
# safe for a migration that rewrites a large table — do those deliberately,
# with RUN_MIGRATIONS=false and a one-off task.
if [ "${RUN_MIGRATIONS:-true}" = "true" ]; then
  echo "[entrypoint] running migrations"
  python -m alembic upgrade head
fi

# ---------------------------------------------------------------- seed content
# Off by default: seeding is idempotent but rewrites every concept, which is
# minutes of work and not something a routine restart should do. Turn it on for
# a first boot or after a content change.
if [ "${SEED_ON_START:-false}" = "true" ]; then
  echo "[entrypoint] seeding content"
  python -m app.seed.loader
fi

# Default workers to something sane; the usual (2 x cores) + 1 is for
# CPU-bound sync work, and these are async workers doing mostly I/O.
if [ -z "${WEB_CONCURRENCY:-}" ]; then
  WEB_CONCURRENCY=$(python -c "import os; print(max(2, (os.cpu_count() or 2)))")
  export WEB_CONCURRENCY
fi
echo "[entrypoint] starting with ${WEB_CONCURRENCY} workers"

exec "$@" --workers "${WEB_CONCURRENCY}"
