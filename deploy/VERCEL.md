# Deploying SkillAtlas to Vercel

One Vercel project, two services, one domain. `vercel.json` at the repository
root defines them:

| service | root | public? |
|---|---|---|
| `web` | `frontend/` | yes — every path routes here |
| `api` | `backend/` | **no** — reachable only from `web`, over a service binding |

The API has no top-level rewrite, so Vercel never routes public traffic to it.
`web` declares a binding to `api`, which grants internal access and injects the
URL as `API_BASE_URL`. This matches the design the app already had — the browser
talks to the Next.js BFF and never to FastAPI — and now enforces it at the
platform level rather than by convention.

Two consequences of that binding, both already handled in code, worth knowing
before you change anything:

- **Bindings resolve at runtime, not at build.** `frontend/src/lib/api.ts`
  exposes `apiBaseUrl()` as a function for exactly this reason. Turning it back
  into a module-level constant will break `next build`, because the variable
  does not exist yet at that point.
- **Proxy/middleware cannot call a bound service.** `frontend/src/proxy.ts`
  only reads cookies, so this costs nothing today. Do not add a network call
  there.

---

## 1. Database

SQLite will not work: a serverless function has no durable disk, so every write
would disappear with the instance. You need Postgres.

Add one from the Vercel dashboard — **Storage → Create → Neon** — and attach it
to the project. It injects connection-string variables automatically.

**Use the pooled connection string.** Neon exposes two hosts, and the pooled one
has `-pooler` in it:

```
postgresql://USER:PASSWORD@ep-xxxx-pooler.REGION.aws.neon.tech/DB?sslmode=require
```

Serverless scales out to many instances, each holding its own SQLAlchemy pool.
The unpooled host sees `instances × pool_size` connections and exhausts the
free-tier limit under quite ordinary traffic; the pooled host puts PgBouncer in
front. `app/database.py` already keeps its own pool small (2 + 3 overflow) for
the same reason.

Set `DATABASE_URL` to that pooled string in the project's environment variables.

---

## 2. Environment variables

Set these on the **api** service (Project → Settings → Environment Variables):

| variable | value | why |
|---|---|---|
| `DATABASE_URL` | pooled Neon string | see above |
| `SECRET_KEY` | `python -c "import secrets; print(secrets.token_urlsafe(48))"` | signs JWTs; the app **refuses to start** in production with the placeholder or anything under 32 characters |
| `ENVIRONMENT` | `production` | turns on the production guards and disables `/docs` |
| `DEBUG` | `false` | tracebacks must not reach clients |
| `CORS_ORIGINS` | your deployment origin, e.g. `https://skillatlas.vercel.app` | must be https and must not be `*`; the app refuses to start otherwise |
| `OPENROUTER_API_KEY` | your key | the hosted tutor |
| `OPENROUTER_MODEL` | `nvidia/nemotron-3-super-120b-a12b:free` | the default; override to change model without a code change |

`API_BASE_URL` is **not** set by hand — the binding provides it. Setting it
manually would override the binding and point the frontend somewhere else.

`config.py` refuses to construct in production with a placeholder secret, a
short secret, `DEBUG=true`, or wildcard/plaintext CORS. That is deliberate: a
warning at boot is invisible in a platform that restarts you silently, and each
of those is exploitable rather than untidy. A failed deploy is the point.

---

## 3. Migrate and seed — from your machine, once

There is no boot step on Vercel, so nothing runs `alembic upgrade head` for you.
Run it against Neon yourself, before the first deploy and after any migration:

```powershell
cd backend
$env:DATABASE_URL = "postgresql://...-pooler...neon.tech/db?sslmode=require"
.\venv\Scripts\python.exe -m alembic upgrade head
.\venv\Scripts\python.exe -m app.seed.loader
Remove-Item Env:\DATABASE_URL
```

Seeding loads 92 tracks, 2,782 concepts and ~21,400 resources. It is idempotent
— safe to re-run when content changes.

> **Migrations are only tested once they run on Postgres.** SQLite accepted a
> drop-order bug in `3a725c2a4a4e` for months; the first Postgres boot
> crash-looped on `DependentObjectsStillExist`. Watch this step rather than
> assuming it.

Embeddings (`-m app.seed.loader --embed`) need Ollama and are optional: the
hosted tutor cannot embed a query anyway, so retrieval uses BM25 in production.
Skip it unless you are also running Ollama.

---

## 4. Deploy

Push the branch, or:

```bash
npx vercel deploy
```

`.vercelignore` keeps the 161MB venv, the 50MB SQLite file and the roadmap.sh
prose backup out of the upload. `excludeFiles` in `vercel.json` additionally
keeps tests, scripts and 9.2MB of seed YAML out of the *function bundle* — the
seed data is only read by offline tooling, never at request time.

---

## 5. After it works

**Rotate `OPENROUTER_API_KEY`.** Any key that has been pasted into a chat, a
terminal transcript or a screenshot should be treated as public.

---

## Known limits of this deployment

Not defects to fix before launch — things that will surprise you later if you
do not know them now.

- **The tutor is capped.** Free OpenRouter models allow 20 requests a minute
  and 50 a day on an account with no credits, *site-wide*. Past the cap
  `chat.py` falls back to `RetrievalOnlyProvider`, so the tutor answers from
  retrieved text instead of failing. Buying $10 of credits raises the cap to
  1000/day.
- **No vector search.** OpenRouter brokers chat, not embeddings, so
  `rag.retrieve` falls back to BM25 keyword search. The 7,427 stored vectors
  are untouched and return the moment an embedding-capable provider is set.
- **Every page is dynamic.** The nonce-based CSP in `proxy.ts` requires dynamic
  rendering, so nothing is statically cached and every page view is a function
  invocation. This is the cost of not allowing `'unsafe-inline'` scripts.
- **Rate limiting is per-instance.** `middleware/ratelimit.py` holds its token
  buckets in process memory. Fluid compute reuses instances so it is not
  useless, but it is not a global limit either: the effective ceiling is
  roughly `instances × limit`. A shared store (Upstash Redis, also on the
  Vercel marketplace) is the fix if this starts to matter.
- **`retrieve()` reads every embedding row.** It pulls all 7,427 rows to build
  its matrix. Harmless against local SQLite, meaningfully slow against a
  network database — and currently moot, since BM25 is doing the work. Worth
  fixing (pgvector) before vector search is turned back on.
