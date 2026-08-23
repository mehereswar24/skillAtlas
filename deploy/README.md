# Deploying SkillAtlas

Three containers: Postgres, the FastAPI API, and the Next.js BFF. The browser
only ever talks to the BFF, which proxies to the API over the private compose
network — so the API is never published to the host.

```
internet ──▶ your TLS terminator ──▶ web :3000 ──▶ api :8000 ──▶ db :5432
             (Caddy/nginx/ALB)        (public)      (internal)    (internal)
```

## First deploy

```bash
cp deploy/.env.production.example deploy/.env
# Fill in SECRET_KEY, POSTGRES_PASSWORD and CORS_ORIGINS. The API refuses to
# start without them — see backend/app/config.py.

docker compose -f deploy/compose.prod.yml --env-file deploy/.env up -d --build

# Load the content corpus. Once, on first boot — it rewrites every concept and
# takes several minutes, so it is not part of a routine restart.
docker compose -f deploy/compose.prod.yml --env-file deploy/.env \
  run --rm -e SEED_ON_START=true api true
```

Put TLS in front of `web`. Cookies are issued `Secure`, so over plain HTTP
nobody can stay logged in — and the API refuses to boot with a plaintext origin
in `CORS_ORIGINS` for exactly that reason.

Set `TRUST_PROXY_HEADERS=true` only when a proxy you control sets
`X-Forwarded-For`. It is already on for the API in compose, because there its
only caller is the `web` container. If you expose the API directly, turn it off:
a client that can set its own forwarded address can pick its own rate-limit
bucket, which makes every limit decorative.

## Verifying a deploy

`deploy/wsl-smoke.sh` brings the whole stack up from nothing and asserts that it
actually serves — migrations applied against Postgres, content seeded, docs
closed, headers present, rate limiting live. Run it after any change to the
images or the compose file:

    wsl -d Ubuntu -- bash /mnt/c/Users/Mehereswar/Desktop/skillatlas/deploy/wsl-smoke.sh

It starts with `docker compose down -v`, which **destroys the database volume**.
That is deliberate — a smoke test should prove a *fresh* deploy works, and a
half-applied migration leaves a state no real deploy is ever in. Never point it
at anything you care about.

Last run: 14/14 passed. Images are 436MB (api) and 320MB (web).

## Routine operations

```bash
# Deploy a new version
docker compose -f deploy/compose.prod.yml --env-file deploy/.env up -d --build

# Logs (JSON lines in production; every line carries request_id)
docker compose -f deploy/compose.prod.yml logs -f api

# Trace one user's report through every service
docker compose -f deploy/compose.prod.yml logs api | grep '"request_id":"<id>"'

# Back up
docker compose -f deploy/compose.prod.yml exec db \
  pg_dump -U skillatlas skillatlas | gzip > backup-$(date +%F).sql.gz
```

Migrations run automatically on API start. For a migration that rewrites a
large table, set `RUN_MIGRATIONS=false` and run it as a one-off task instead, so
a rolling deploy is not blocked behind it.

## What is enforced, and where

| Control | Where |
|---|---|
| Refuses to boot with a placeholder/short `SECRET_KEY`, `DEBUG=true`, wildcard or plaintext CORS | `backend/app/config.py` |
| Rate limiting per client and route class (auth, tutor, upload, default) | `backend/app/middleware/ratelimit.py` |
| Security headers, HSTS on HTTPS in production | `backend/app/middleware/security.py` |
| CSP, `X-Frame-Options`, `Referrer-Policy` for rendered pages | `frontend/next.config.ts` |
| Request id, JSON logging, unhandled errors never leak a traceback | `backend/app/middleware/logging.py` |
| Liveness vs readiness split | `backend/app/main.py` |
| Non-root container users, no build toolchain in runtime images | `deploy/Dockerfile.*` |
| Secrets, `venv/`, `node_modules/`, `.next/` and the pre-strip corpus kept out of images | `backend/.dockerignore`, `frontend/.dockerignore` |

The entrypoint lives at `backend/docker-entrypoint.sh`, not in `deploy/`: the
build context is `backend/`, and `COPY` cannot reach outside it. Widening the
context to the repository root would pull the frontend's `node_modules` into
every backend build.

Build on Windows through WSL with `deploy/wsl-sync-and-build.sh`, which rsyncs
the tree to `~/skillatlas` first. Building directly from `/mnt/c` works but is
several times slower — Docker reads the entire context across the filesystem
bridge.

## Content licensing

`scripts/strip_imported_prose.py` has removed roadmap.sh's prose from every
imported track. What remains in those tracks is a syllabus (topic names),
figures our own importer synthesised (hour estimates, difficulty,
prerequisites) and links — none of which is theirs. The seven hand-written
tracks are ours outright.

So all 92 tracks are publishable. The API reports `depth` on every concept
(`written` or `outline`) so the UI can say which is which rather than letting a
learner find out by opening one, and `tests/test_production.py` fails if an
imported concept ever carries prose again — which is what would happen if
someone re-ran the importer and skipped the strip.

`PUBLISH_AUTHORED_ONLY=true` hides the outline tracks entirely. That is a
product choice about what users should see, not a legal one.

## Scaling notes, stated honestly

- **Rate limit state is per process.** Two API replicas enforce twice the
  configured limit. Fine for one container; for more, move the counter to Redis
  — `_Bucket` in `ratelimit.py` is deliberately small enough to swap.
- **Uploads are not shared.** Résumé uploads live on the API container's
  filesystem, so more than one replica needs object storage first.
- **The tutor needs Ollama.** If `OLLAMA_BASE_URL` is unreachable the tutor
  degrades to deterministic retrieval over the corpus rather than failing — a
  supported configuration, not an outage.
