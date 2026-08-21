# SkillAtlas → one-stop career platform

Draft plan, 2026-08-21. Nothing here is built yet except where marked **done**.

---

## Where you actually are

Worth being blunt about the starting position, because it changes what to build next.

**Strong:** 91 routes / 2,739 concepts with 21,809 sourced links; a real prerequisite
graph with a weekly scheduler; projects that run in the browser (Pyodide, sql.js) and
are verified to be passable; a company section with sourced interview questions; an
Ollama tutor with RAG over the corpus; points, badges, streaks, readiness-against-role.

**Weak, and it matters for "one-stop":**

| Gap | Why it blocks the goal |
|---|---|
| **Zero quizzes / interview questions on concepts** | roadmap.sh ships none. "Every step ends in a check" is currently false. |
| **Content is licence-encumbered** | roadmap.sh forbids redistribution. You cannot launch publicly on it. This is the single biggest constraint on the whole plan. |
| **Every route is a strict linear chain** | roadmap.sh has no dependency data, so concept N+1 is locked behind N. Real careers are not a line. |
| **Concepts are duplicated per roadmap** | Docker exists separately in devops, backend and kubernetes. Progress does not carry across routes. |
| **Projects cover 2 of 91 routes** | The "build it" half of the promise is missing for 89 routes. |
| **No résumé, no applications, no jobs, no mock interviews** | These are the parts of "career" that are not "learning". |

**Already fixed this session:** auth was disabled in committed code (all three layers);
Explore was a dead end with no way to start a route; multiple concurrent routes now work.

**Status at 2026-08-21 evening — the table above is the starting position, not the
current one.** Four of its six rows have moved: quizzes now exist for 111 concepts
(462 quiz + 304 interview questions), so "every step ends in a check" is true for the
authored routes; the licence exit is real for the seven authored tracks; those tracks
have hand-written prerequisite graphs rather than chains; and projects are up to 55.
The résumé, applications, mock-interview and portfolio surfaces of Phase 2 exist in
code. The corpus is 92 tracks / 2,782 concepts, and `pytest tests` is green at 281
tests.

---

## The strategic decision you have to make first

Everything downstream depends on this, so decide it before building.

**Decided 2026-08-21: the product goes public, and the content becomes ours.**

roadmap.sh's licence permits personal use and forbids republishing, so going public
means the corpus has to be replaced — not relicensed, not attributed, replaced.

**How, precisely.** Paraphrasing their prose would still be a derivative work and would
buy nothing. What works is writing *independently about the same subject*: facts are
not copyrightable, a particular expression of them is. So each track is rewritten from
primary sources (MDN, RFCs, official docs) by someone who is not looking at theirs —
and the syllabus is re-curated rather than mirrored, because a renamed copy of their
structure is still recognisably their product.

**The mechanism.** `app/seed/tracks/authored-<slug>.yaml` is ours: tracked in git,
publishable, and `scripts/import_roadmapsh.py` now **skips** any roadmap that has one.
Coverage grows one track at a time; when every track is authored the importer is dead
code and roadmap.sh is out of the product entirely.

**Order of work.** The 20 core routes are 581 concepts of the 2,757; the full corpus is
~796,000 words, which is several books and not the target. Author the routes people
actually take, and leave the long tail imported (and unpublished) until it matters.

Worth doing anyway: email roadmap.sh and ask. Costs one message.

---

## Phase 1 — Make what exists trustworthy (2-3 weeks)

Nothing new. This phase is about the platform being *correct*, because every later
phase compounds on it.

1. **Quizzes and interview questions per concept.** Generate with the local Ollama
   model against each concept's own `content_md`, then gate on a verification pass —
   a question whose answer is not supported by the body gets rejected. Store
   `generated_by` and `verified_at` so the UI can be honest about provenance. Target
   the ~200 concepts that appear in real routes first, not all 2,739.
2. **Relax the linear chain.** Keep roadmap.sh's *order* (already in
   `TrackConcept.sort_order`) but stop treating it as a hard prerequisite. Options:
   soft gating (warn, don't lock) or derive real prerequisites from concept-name
   overlap across roadmaps. Right now a learner cannot read "Caching" without
   finishing seven unrelated concepts.
   *(Solved for the authored tracks as a side effect of item 4 — prerequisites there
   are written by hand, so system-design is 43 concepts joined by 65 edges rather
   than a 42-link chain. Still outstanding for the 85 imported tracks, which is the
   argument for soft gating rather than a per-track fix.)*
3. **Deduplicate concepts across routes.** One `Docker` node that many tracks point
   at, restoring the shared graph the original design had. Progress then carries
   across routes — currently finishing Docker in devops does nothing for backend.
4. **Own the high-traffic tracks.** *(First wave done, 2026-08-21 — see the decision
   above.)* Rewrite the core routes as `authored-*.yaml`: our curation, our prose,
   primary sources. First wave shipped: backend (35 concepts), api-design (21),
   frontend (47), computer-science (37), devops (33), system-design (43), plus the
   hand-authored dsa-interview-prep (18) — 234 concepts, 2,098 estimated hours,
   337 hand-written prerequisite edges and 1,579 cited sources, every one written
   independently from primary documentation.
   Constraint that matters — existing concept slugs must survive, because projects,
   company focus areas and role skills point at them by slug. Verified: no slug from
   any imported track was dropped.
   Two mechanisms make this the licence exit. `scripts/import_roadmapsh.py` refuses to
   regenerate a roadmap that has an `authored-<slug>.yaml`; and `loader.track_files()`
   now drops the imported `<slug>.yaml` whenever the authored file exists, so a tree
   that still carries the pre-authoring import seeds the authored version. Second wave
   should follow the same route: fragments in `backend/.authoring/`, concatenated into
   `app/seed/tracks/authored-<slug>.yaml`.
   Two things to expect on the next authoring pass, both learned the hard way here.
   First, seeding breaks until the imported twin is superseded — `track_files()` is
   that fix and it needs no per-track work, but the failure is a `SeedError` about a
   concept "defined in more than one track file", which does not obviously say so.
   Second, ~15 tests fail purely because concepts were renamed and prerequisite edges
   rewritten. Those assertions have been changed to pin *slugs*, not display names,
   so the next pass should be quieter.
   The real bug hiding in that noise: `resume.build_lexicon` indexed concepts by
   **name**, so once a concept became "Git as a Directed Graph" a résumé saying "Git"
   matched a beginner track's copy instead and every role scored 0 — no career
   options, no company matches, no learn-next. It now also indexes the slug's topic
   half, arbitrated by the same rank rule. **Anything that matches user text to a
   concept must key on the slug**; the name is prose and will be rewritten.
   Citations are checked with `backend/.frag/check_urls.py <track.yaml>`. Note that
   403s from w3.org, dev.mysql.com, leetcode and dl.acm.org, 418s from freedesktop and
   429s from github are user-agent blocks rather than dead links, and nist.gov starts
   answering 404 to everything once it has rate-limited you — so trust the first
   observation of a host, not the fifth.
5. **Fix the build.** *(Done, 2026-08-21.)* `npx tsc --noEmit` is clean. The last of
   the 16 errors was the worker's dynamic import of `/pyodide/pyodide.mjs`, a URL
   served from `public/` that TypeScript can never resolve; it is declared in
   `src/components/workspace/pyodide-asset.d.ts`, as a wildcard pattern because an
   exact declaration with a leading slash is read as a path and never consulted.
   The vendored `lightswind` dropdown now carries `aria-haspopup`/`aria-expanded`
   on the trigger, `role="menu"`/`role="menuitem"` on the surface and arrow-key
   navigation, so it opens from the keyboard as well as the mouse.

**Exit test:** you can deploy publicly without a licence problem for the top 10 routes,
every concept in them has a verified quiz, and progress carries across routes.

---

## Phase 2 — Close the "career" gap (4-6 weeks)

This is what turns a learning site into a career site. Ordered by value per unit of work.

### 2a. Résumé (highest value, lowest risk)
You already have the hard part: structured evidence of what someone has done —
completed concepts, shipped projects, points, role readiness.

- Generate a résumé from actual progress, not self-report.
- Tailor to a target role or a specific job description: diff the JD against the
  learner's completed concepts, surface the gaps, and offer to add them to a route.
- Export to PDF/DOCX. **You have already solved exact-format PDF/LaTeX generation in
  the Natively project** — reuse it rather than rebuilding.
- ATS check: parse the generated PDF back out and show what a parser actually sees.

### 2b. Mock interviews
The tutor already does RAG over the corpus and the company section already holds
sourced questions per role.

- Voice or text mock interview against a chosen company + role, drawing questions
  from the existing company question bank.
- Grade against the rubric the company section already documents.
- Feed weak areas back into the route as concepts to add — this is the loop that makes
  the whole product cohere.

### 2c. Job tracker
- Applications board (saved → applied → screen → onsite → offer/rejected).
- Per-application prep: which company profile, which role, which focus areas, and
  what the learner is still missing for it.
- **Do not scrape job boards.** Use official APIs where they exist and let the learner
  paste a JD otherwise. Scraping is the same class of problem as the roadmap.sh
  licence, and worse legally.

### 2d. Portfolio
- Public profile page from completed projects and concepts, at a shareable URL.
- The projects already run in-browser — embed live demos rather than screenshots.
  This is a genuine differentiator; almost nothing else does it.

---

## Phase 3 — Depth where you are already differentiated (4-6 weeks)

1. **Projects for the other 89 routes.** Currently 21 projects across 2 routes. This is
   the hardest content to fake and the most valuable to have. Generate candidates, but
   keep the existing hard gate: `verify_projects.py` runs the reference solution *and*
   proves the starter files fail. Prioritise the 10 most-started routes.
2. **DSA prep as a first-class surface.** Striver-style progression, company-tagged
   problem sets, spaced repetition over problems you got wrong. *(A Striver-based DSA
   track is being drafted now.)*
3. **Spaced repetition across the whole corpus.** You have quizzes (after Phase 1),
   completion timestamps and a graph. Review scheduling is a small addition with a
   large retention effect.
4. **System design practice.** Rubric-graded, like the mock interviews.

---

## Phase 4 — Only if the earlier phases land (open-ended)

- Cohorts / accountability partners (you have a `community` module already stubbed).
- Mentor marketplace.
- Employer side: post a role, see candidates with *verified* project evidence. This is
  the actual business model, and it only works if Phase 2d is real.
- Referral network.

---

## What I would explicitly not build

- **A job board.** You cannot out-index LinkedIn/Indeed, and scraping them is a legal
  problem you do not need.
- **Video courses.** Enormous production cost; the sourced-links model already works.
- **A mobile app.** The projects depend on Pyodide/sql.js in browser workers. PWA first.
- **More roadmap.sh imports.** You have 91 routes and projects for 2 of them. Depth,
  not breadth, is the gap.

---

## Sequencing, honestly

The temptation is to jump to Phase 2 because résumé/jobs/mock-interviews are the
exciting part and are what "one-stop" means. Resist it for about three weeks. Phase 1
is unglamorous, but every Phase 2 feature reads from the same data: the résumé is only
as credible as the progress behind it, and the mock interview is only as useful as the
concepts it can send you back to. Building 2 on top of a corpus you cannot publish,
with no quizzes and progress that does not carry across routes, means building it twice.

**Suggested order:** 1 → 2a → 2b → 3.1 → 2c → 2d → 3.2-3.4 → 4.

---

## Open questions for you

1. Public product, or personal tool? Everything above assumes public. If it is personal,
   skip the licence work entirely and go straight to Phase 2.
2. Who is this for — Indian campus placements (the company set says yes: Infosys, TCS,
   Zoho, Wipro, Cognizant), or a global audience? It changes what Phase 2c and the
   company section should prioritise.
3. Is there a business model, or is this a portfolio project? It changes whether Phase 4
   is worth designing towards now.
