# SkillAtlas

Choose a domain, choose a pace, and get a route built from a real prerequisite
graph. Every step comes with sources to learn from, points for finishing it, and
a project you build and run **inside the app** — no local toolchain. A companies
section then shows what specific employers actually test, with every question
traceable to its source.

- **Frontend** — Next.js 16 (App Router) + React 19 + Tailwind v4 + shadcn/Base UI
- **Backend** — FastAPI + SQLAlchemy 2.0 + Alembic
- **Database** — SQLite by default (zero setup); Postgres by changing one env var
- **AI tutor** — local Ollama (`qwen2.5:7b` + `nomic-embed-text`) with RAG over the
  concept content, and a deterministic retrieval fallback when Ollama is off
- **Build environment** — Pyodide, sql.js and a sandboxed iframe, all served from
  `public/` so projects run in the browser with no network and no setup

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

## Design

Light mode is parchment and ink; dark mode is deep survey-blue. One accent — a
burnt amber taken from contour lines on a map — so anything amber is always an
action. Fraunces for headings, Inter for UI, and a `.contour` backdrop that
approximates map hachure in pure CSS. The theme is applied by a blocking inline
script in `<head>` (`src/components/theme-toggle.tsx`) so there is no flash of
the wrong theme before hydration.

## How it works

**The graph.** `concepts` are nodes, `concept_prerequisites` are edges. A track
lists its concepts; roadmap generation takes the transitive closure of their
prerequisites. Since the roadmap.sh import each track owns its own concepts and
every chain is linear, so a closure stays inside one track — the machinery still
handles a shared, branching graph, there just is not one in the current content.

**Roadmap generation.** Closure → subtract what the learner says they already
know → Kahn topological sort (deterministic, quickest-wins first) → pack into
weeks of `daily_hours × 7`, never splitting a concept across a week boundary.
Because order is preserved, a prerequisite always lands in the same week or an
earlier one. The result is persisted, so progress means something.

**Progress and points.** Quizzes are graded server-side (the API never sends
which option is correct until you submit). A failed attempt records nothing and
returns explanations. Passing awards points scaled by effort × score, advances
the level and streak, evaluates badges, and unlocks dependent concepts. Every
award is written to a `points_events` ledger, so the dashboard can show *what*
paid out rather than a total that moves on its own — and a test asserts the
ledger sums to the profile.

**Projects.** Each concept ends in something you build. Projects carry starter
files and automated tests, and run in the learner's browser: Python under
Pyodide in a terminable Web Worker, SQL under sql.js, and HTML/CSS/JS in an
iframe sandboxed with `allow-scripts` and no `allow-same-origin`. The worker is
the point — a learner *will* write an infinite loop, and terminating a worker is
the only reliable way back.

Because execution is client-side, the pass/fail signal is **reported by the
client**. The server records every submission in full, rejects a green run that
does not use the API the brief required (`must_contain`), and pays out at most
once per project — but it cannot re-run the code, and the UI says so rather than
implying an authority it does not have.

`backend/scripts/verify_projects.py` runs every project against a reference
solution *and* checks that the starter files fail, so no brief can ship that is
impossible to pass or that passes on arrival.
`frontend/scripts/check-python-harness.mjs` runs the shipped harness and every
Python project against a real Pyodide under Node — which is how a bug that
scored every *passing* test as a failure (Python's `None` crosses the FFI as
JavaScript's `undefined`, not `null`) was caught without opening a browser.

**Companies.** Pick a company, see its roles, and for each role: what to focus
on, previous interview questions, and previous exam and online-assessment
questions. A role's focus areas point at concepts in the same graph, so
readiness is computed from work you actually completed and the gap can be added
to your route in one click. Every question stores the public source it was
written from, and every company stores a `fetched_on` date the UI displays, so
stale data is visible rather than silently trusted.

**Readiness.** `role_skills` weights each concept per role, so readiness is
`Σ(weight of completed) / Σ(weight of all)`. "Biggest gaps" shows exactly how
many percentage points each missing concept is worth for your chosen goal.

**Auth.** FastAPI issues JWTs; the Next.js BFF (`src/app/api/`) keeps them in
`HttpOnly` cookies and proxies every call server-side, so the browser never
holds a token and there is no CORS. `src/proxy.ts` (Next 16's renamed
middleware) does an optimistic cookie check; the API authorises for real.

## Content

Tracks and concepts are **imported from [roadmap.sh](https://roadmap.sh)**. The
hand-authored curriculum that used to live here was replaced by that import;
roles, projects and companies are still authored YAML under `backend/app/seed/`.

| | |
|---|---|
| Domains | 15 |
| Tracks | 92 — 91 imported, 1 authored (DSA) |
| Concepts | 2,757 |
| Resource links | 21,915 |
| Quiz questions | 0 — see below |
| Interview questions | 0 — see below |
| Job roles measured | 26 |
| Buildable projects | 55 (36 Python, 12 web, 7 SQL) |
| Companies | 30 (69 roles, 403 sourced questions) |

Tracks and concepts are imported; **projects, companies, roles and the DSA track
are authored** and live in the repo.

### Licence — read before publishing

roadmap.sh's content is **not** open source. Its licence allows *personal use*
and forbids redistributing the material anywhere outside its own repository.
The generated tracks are therefore **git-ignored**: this repo ships the
importer, not its output. Do not commit `backend/app/seed/tracks/*.yaml` or
publish a deployment built from them without permission from roadmap.sh.

### What the import does and does not give you

roadmap.sh publishes each roadmap as a visual canvas plus one markdown file per
node. Two fields it has no equivalent for are synthesised by the importer, and
two features have no source at all:

* **`est_hours` is estimated** from how much material a topic carries — there
  is no time data in the source. The weekly scheduler needs *some* number.
* **Prerequisites are the roadmap's own reading order.** The canvas has no
  dependency edges; order is spatial, so each concept requires the previous one.
* **No quizzes and no interview questions.** Completing a concept is therefore
  ungated (`routers/progress.py` treats zero questions as a pass).
* **Concepts are no longer shared between tracks.** Each roadmap is a
  self-contained canvas, so the importer namespaces concepts per roadmap and
  the same subject is duplicated across tracks. Progress does not carry over.

Regenerate the content with:

```powershell
# a checkout or tarball of github.com/nilbuild/developer-roadmap
.\venv\Scripts\python.exe scripts\import_roadmapsh.py --repo <path>
```

`scripts/remap_concept_refs.py` re-points authored `concept:` references at the
imported concepts after a re-import.

Projects cover the **backend** and **frontend** tracks. **Adding a project or a
company is content work, not code**: drop a YAML file into
`app/seed/projects/` or `app/seed/companies/`, re-run the seeder.

```powershell
.env\Scripts\python.exe -m app.seed.loader     # idempotent; safe to re-run
```

The loader validates as it goes: unknown domains and prerequisites, duplicate
concept definitions, quiz questions without exactly one correct answer,
prerequisite cycles, projects with no tests or no entry file, a test whose kind
does not match its runtime, a focus area pointing at a concept that does not
exist, and **any company question without a source URL** all fail the seed
rather than corrupting the content.

## Tests

```powershell
cd backend
.\venv\Scripts\python.exe -m pytest tests              # 111 tests
.\venv\Scripts\python.exe scripts\verify_projects.py   # every project is passable
.\venv\Scripts\python.exe scripts\smoke.py             # end-to-end, needs both servers up

cd ..\frontend
npx tsc --noEmit
node scripts/check-python-harness.mjs             # the harness, under real Pyodide
node scripts/check-web-projects.mjs               # web projects, under jsdom
npm run check:explore                             # /explore in a real browser
npm run check:routes                              # several routes at once
npm run check:companies                           # all 30 companies + the DSA track
npm run check:build                               # all 55 projects
npm run build
```

The four `check:*` scripts drive the app end to end in Chromium. They need both
servers up and `npx playwright install chromium` once.

- **`check:explore`** — browse a domain's routes, start one, land on a real
  weekly plan; plus search, the category filter and the signed-out redirect.
- **`check:routes`** — run three routes at once, switch focus, rebuild one in
  place, drop one.
- **`check:companies`** — walks all 30 companies and 69 roles, asserts every
  question is source-cited, and starts the DSA route.
- **`check:build`** — walks all 55 projects, asserts each ships an entry file
  and tests, and opens one workspace.

`scripts/smoke.py` walks the product the way a person does — signup → roadmap →
locked concept → study → complete → **build a project** → **points ledger** →
**companies** → dashboard → tutor → community — through the frontend BFF with
real cookies.

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
    models/      identity, knowledge graph, progress, projects, companies
    schemas/     Pydantic request/response DTOs
    routers/     auth content roadmaps progress projects companies dashboard chat community
    services/    graph roadmap gamification readiness rag llm/
    seed/        tracks/ projects/ companies/ + domains.yaml roles.yaml + loader
  alembic/       migrations
  tests/         pytest suite
  scripts/       smoke.py, verify_projects.py
frontend/
  public/        pyodide/ and sqljs/ runtimes, copied from node_modules
  scripts/       copy-wasm-assets.mjs, check-python-harness.mjs
  src/
    app/         pages + BFF route handlers under app/api
    proxy.ts     route guard (Next 16's renamed middleware)
    components/  UI, plus workspace/ — the in-browser build environment
    lib/         api client, session, DAL, types
```
