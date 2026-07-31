# SkillAtlas

Pick a career or skill, get an adaptive roadmap built from a real prerequisite
graph, work through concepts with curated resources and quizzes, and watch your
readiness for actual job roles move as you go.

- **Frontend** — Next.js 16 (App Router) + React 19 + Tailwind v4 + shadcn/Base UI
- **Backend** — FastAPI + SQLAlchemy 2.0 + Alembic
- **Database** — SQLite by default (zero setup); Postgres by changing one env var
- **AI tutor** — local Ollama (`qwen2.5:7b` + `nomic-embed-text`) with RAG over the
  concept content, and a deterministic retrieval fallback when Ollama is off

No Docker, Neo4j or Redis required. The knowledge graph lives in relational
tables and is traversed in Python (`backend/app/services/graph.py`).

## Quick start

```powershell
# from the repo root — installs, migrates, seeds, then starts both servers
.\run-dev.ps1 -Setup

# subsequent runs
.\run-dev.ps1
```

Open http://localhost:3000. API docs are at http://localhost:8010/docs.

### Manual setup

```powershell
# Backend
cd backend
py -3 -m venv venv
.\venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env     # then set SECRET_KEY
.\venv\Scripts\python.exe -m alembic upgrade head
.\venv\Scripts\python.exe -m app.seed.loader
.\venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8010

# Frontend (second terminal)
cd frontend
npm install
Copy-Item .env.example .env.local
npm run dev
```

Port 8010 rather than the FastAPI-conventional 8000, which is frequently
already taken on a dev machine. Change `API_BASE_URL` in `frontend/.env.local`
if you move it.

### AI tutor (optional)

```powershell
ollama pull qwen2.5:7b
ollama pull nomic-embed-text
ollama serve

# then index the content for semantic retrieval
cd backend
.\venv\Scripts\python.exe -m app.seed.loader --embed
```

Without Ollama the tutor still answers — it retrieves the relevant concept
notes by keyword and says plainly in the UI that it is not generating.

## How it works

**The graph.** `concepts` are nodes, `concept_prerequisites` are edges. A track
lists its curated concepts; roadmap generation takes the transitive closure of
their prerequisites, so choosing *AI Engineer* pulls in `containers-docker`
even though that concept is curated under the backend track.

**Roadmap generation.** Closure → subtract what the learner says they already
know → Kahn topological sort (deterministic, quickest-wins first) → pack into
weeks of `daily_hours × 7`, never splitting a concept across a week boundary.
Because order is preserved, a prerequisite always lands in the same week or an
earlier one. The result is persisted, so progress means something.

**Progress and XP.** Quizzes are graded server-side (the API never sends which
option is correct until you submit). A failed attempt records nothing and
returns explanations. Passing awards XP scaled by effort × score, advances the
level and streak, evaluates badges, and unlocks dependent concepts.

**Readiness.** `role_skills` weights each concept per role, so readiness is
`Σ(weight of completed) / Σ(weight of all)`. "Biggest gaps" shows exactly how
many percentage points each missing concept is worth for your chosen goal.

**Auth.** FastAPI issues JWTs; the Next.js BFF (`src/app/api/`) keeps them in
`HttpOnly` cookies and proxies every call server-side, so the browser never
holds a token and there is no CORS. `src/proxy.ts` (Next 16's renamed
middleware) does an optimistic cookie check; the API authorises for real.

## Content

Learning content is authored as YAML in `backend/app/seed/tracks/`. Two tracks
are written to full depth today:

| Track | Concepts | Hours |
|---|---|---|
| Become a Backend Developer | 15 | ~435 |
| Become an AI Engineer | 15 | ~695 |

That is 29 distinct concepts (one is shared by both tracks), 117 curated
resource links, 87 quiz questions and 36 interview questions.

All 27 domains are seeded, but a domain only advertises itself as available if
it actually has a track — the rest show "Coming soon" on Explore rather than
linking into an empty page. **Adding a track is content work, not code**: drop a
new YAML file into `app/seed/tracks/`, re-run the seeder, and it appears
everywhere. A track file may reference a concept defined in another file by
slug alone, which is how tracks share nodes.

```powershell
.\venv\Scripts\python.exe -m app.seed.loader     # idempotent; safe to re-run
```

The loader validates as it goes: unknown domains and prerequisites, duplicate
concept definitions, quiz questions without exactly one correct answer, and
prerequisite cycles all fail the seed rather than corrupting the graph.

## Tests

```powershell
cd backend
.\venv\Scripts\python.exe -m pytest tests        # 84 tests
.\venv\Scripts\python.exe scripts\smoke.py       # end-to-end, needs both servers up

cd ..\frontend
npx tsc --noEmit
npm run build
```

`scripts/smoke.py` walks the product the way a person does — signup → roadmap
→ locked concept → study → complete → dashboard → tutor → community — through
the frontend BFF with real cookies.

## Using Postgres instead of SQLite

```powershell
docker compose --profile postgres up -d
# backend/.env
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/skillatlas
.\venv\Scripts\python.exe -m pip install psycopg2-binary
.\venv\Scripts\python.exe -m alembic upgrade head
.\venv\Scripts\python.exe -m app.seed.loader
```

No application code changes; the models avoid SQLite-only SQL.

## Layout

```
backend/
  app/
    main.py config.py database.py security.py deps.py
    models/      identity, knowledge graph, progress, community
    schemas/     Pydantic request/response DTOs
    routers/     auth content roadmaps progress dashboard chat community
    services/    graph roadmap gamification readiness rag llm/
    seed/        tracks/*.yaml domains.yaml roles.yaml + loader
  alembic/       migrations
  tests/         pytest suite
  scripts/       smoke.py
frontend/
  src/
    app/         pages + BFF route handlers under app/api
    proxy.ts     route guard (Next 16's renamed middleware)
    components/  UI
    lib/         api client, session, DAL, types
```
