"""Idempotent content seeder.

    python -m app.seed.loader              # seed everything
    python -m app.seed.loader --embed      # also build RAG embeddings (needs Ollama)

Everything is keyed by slug and upserted, so re-running is safe and editing a
YAML file then re-running propagates the edit. Child collections (resources,
quiz questions, interview questions, role skills) are replaced wholesale —
they have no independent identity and no user data hangs off them.

Quizzes live apart from the concepts they belong to, in `seed/quizzes/`, and
are attached by `seed_quizzes` after the tracks are in. `seed/tracks/` is
regenerated wholesale by `scripts/import_roadmapsh.py` and is git-ignored, so
anything written there is one re-import away from being deleted. The questions
are ours, not roadmap.sh's, and they have to survive that.

Concepts are loaded across *all* track files before prerequisites are wired,
because tracks share concepts: `programming-language-python` and
`containers-docker` appear in both the backend and AI-engineer tracks, which is
exactly what makes this a graph rather than a set of lists.
"""

from __future__ import annotations

import argparse
import secrets
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models.company import (
    INTERVIEW_OUTCOMES,
    QUESTION_KINDS,
    ROUNDS,
    Company,
    CompanyFocus,
    CompanyQuestion,
    CompanyResource,
    CompanyReview,
    CompanyRole,
)
from app.models.content import (
    Concept,
    ConceptPrerequisite,
    Domain,
    InterviewQuestion,
    QuizOption,
    QuizQuestion,
    Resource,
    Role,
    RoleSkill,
    Track,
    TrackConcept,
)
from app.models.project import (
    RUNTIME_FOR_TEST_KIND,
    RUNTIMES,
    TEST_KINDS,
    Project,
    ProjectFile,
    ProjectTest,
)
from app.models.user import User
from app.security import hash_password

SEED_DIR = Path(__file__).resolve().parent
TRACKS_DIR = SEED_DIR / "tracks"
PROJECTS_DIR = SEED_DIR / "projects"
COMPANIES_DIR = SEED_DIR / "companies"
QUIZZES_DIR = SEED_DIR / "quizzes"
REVIEWS_DIR = SEED_DIR / "reviews"

# Sample reviewers get addresses in a reserved TLD (RFC 2606) that can never
# resolve, so a placeholder account cannot collide with a real signup or be
# mistaken for one.
SAMPLE_AUTHOR_DOMAIN = "samples.skillatlas.invalid"

# The default test kind for each runtime, so simple YAML can omit `kind:`.
TEST_KIND_FOR_RUNTIME = {
    runtime: kind for kind, runtime in RUNTIME_FOR_TEST_KIND.items()
}


class SeedError(Exception):
    """Raised when the YAML content is internally inconsistent."""


def _read_yaml(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


def _is_reference(raw: dict[str, Any]) -> bool:
    """True when a track lists a concept defined in another file."""
    return "name" not in raw


# --------------------------------------------------------------------------
# domains
# --------------------------------------------------------------------------


def seed_domains(db: Session) -> dict[str, Domain]:
    data = _read_yaml(SEED_DIR / "domains.yaml")
    by_slug: dict[str, Domain] = {}

    for order, raw in enumerate(data.get("domains", [])):
        slug = raw["slug"]
        domain = db.scalar(select(Domain).where(Domain.slug == slug)) or Domain(
            slug=slug
        )
        domain.name = raw["name"]
        domain.category = raw["category"]
        domain.icon = raw.get("icon", "BookOpen")
        domain.color = raw.get("color", "text-primary")
        domain.description = raw.get("description")
        domain.sort_order = order
        # Recomputed from the tracks that actually exist, below.
        domain.has_content = False
        db.add(domain)
        by_slug[slug] = domain

    db.flush()
    return by_slug


# --------------------------------------------------------------------------
# concepts
# --------------------------------------------------------------------------


def _replace_children(db: Session, concept: Concept, raw: dict[str, Any]) -> None:
    """Rewrite a concept's resources, quiz and interview questions from YAML."""
    concept.resources.clear()
    for order, res in enumerate(raw.get("resources", [])):
        concept.resources.append(
            Resource(
                kind=res["kind"],
                title=res["title"],
                url=res["url"],
                provider=res.get("provider"),
                duration_min=res.get("duration_min"),
                is_free=res.get("is_free", True),
                sort_order=order,
            )
        )

    concept.quiz_questions.clear()
    for q_order, q in enumerate(raw.get("quiz", [])):
        concept.quiz_questions.append(_build_quiz_question(concept.slug, q, q_order))

    concept.interview_questions.clear()
    for order, iq in enumerate(raw.get("interview", [])):
        concept.interview_questions.append(
            _build_interview_question(concept.slug, iq, order)
        )


def _build_quiz_question(
    concept_slug: str,
    raw: dict[str, Any],
    order: int,
    generated_by: str | None = None,
    verified_at: datetime | None = None,
) -> QuizQuestion:
    """One multiple-choice question, with the rules the grader depends on.

    ``routers/progress.py`` scores an attempt by looking up *the* correct
    option, so "exactly one" is not a style preference — two correct options
    make a question ungradeable and none makes it unpassable. Three options is
    the floor at which a guess is worth less than knowing the answer.
    """
    options = raw.get("options", [])
    correct = [o for o in options if o.get("correct")]
    if len(correct) != 1:
        raise SeedError(
            f"Quiz question on '{concept_slug}' has {len(correct)} correct "
            f"options, expected exactly 1: {raw['prompt'][:60]!r}"
        )
    if len(options) < 3:
        raise SeedError(
            f"Quiz question on '{concept_slug}' has only {len(options)} options: "
            f"{raw['prompt'][:60]!r}"
        )

    question = QuizQuestion(
        prompt=raw["prompt"],
        explanation=raw.get("explanation"),
        sort_order=order,
        generated_by=generated_by,
        verified_at=verified_at,
    )
    for o_order, opt in enumerate(options):
        question.options.append(
            QuizOption(
                text=opt["text"],
                is_correct=bool(opt.get("correct", False)),
                sort_order=o_order,
            )
        )
    return question


def _build_interview_question(
    concept_slug: str,
    raw: dict[str, Any],
    order: int,
    generated_by: str | None = None,
    verified_at: datetime | None = None,
) -> InterviewQuestion:
    if not (raw.get("answer_md") or "").strip():
        raise SeedError(
            f"Interview question on '{concept_slug}' has no answer: "
            f"{raw['question'][:60]!r}"
        )
    return InterviewQuestion(
        question=raw["question"],
        answer_md=raw["answer_md"],
        difficulty=raw.get("difficulty", "medium"),
        sort_order=order,
        generated_by=generated_by,
        verified_at=verified_at,
    )


def upsert_concept(
    db: Session, raw: dict[str, Any], domains: dict[str, Domain]
) -> Concept:
    slug = raw["slug"]
    domain_slug = raw["domain"]
    if domain_slug not in domains:
        raise SeedError(f"Concept '{slug}' references unknown domain '{domain_slug}'")

    concept = db.scalar(select(Concept).where(Concept.slug == slug)) or Concept(
        slug=slug
    )
    concept.name = raw["name"]
    concept.domain_id = domains[domain_slug].id
    concept.summary = raw.get("summary", "")
    concept.content_md = raw.get("content_md", "")
    concept.est_hours = raw.get("est_hours", 8)
    concept.difficulty = raw.get("difficulty", "beginner")
    db.add(concept)
    db.flush()

    _replace_children(db, concept, raw)
    db.flush()
    return concept


def wire_prerequisites(
    db: Session, concept_specs: dict[str, dict[str, Any]], concepts: dict[str, Concept]
) -> None:
    """Rebuild the edge set, then reject cycles before anything is committed."""
    db.query(ConceptPrerequisite).delete()
    db.flush()

    for slug, raw in concept_specs.items():
        for prereq_slug in raw.get("prerequisites", []) or []:
            if prereq_slug not in concepts:
                raise SeedError(
                    f"Concept '{slug}' lists unknown prerequisite '{prereq_slug}'"
                )
            if prereq_slug == slug:
                raise SeedError(f"Concept '{slug}' lists itself as a prerequisite")
            db.add(
                ConceptPrerequisite(
                    concept_id=concepts[slug].id,
                    prerequisite_id=concepts[prereq_slug].id,
                )
            )
    db.flush()

    _assert_acyclic(concept_specs)


def _assert_acyclic(concept_specs: dict[str, dict[str, Any]]) -> None:
    """A cycle here would make roadmap generation silently drop concepts."""
    WHITE, GREY, BLACK = 0, 1, 2
    colour = {slug: WHITE for slug in concept_specs}

    def visit(slug: str, path: list[str]) -> None:
        colour[slug] = GREY
        for prereq in concept_specs[slug].get("prerequisites", []) or []:
            if colour.get(prereq) == GREY:
                cycle = " -> ".join([*path, slug, prereq])
                raise SeedError(f"Prerequisite cycle detected: {cycle}")
            if colour.get(prereq) == WHITE:
                visit(prereq, [*path, slug])
        colour[slug] = BLACK

    for slug in concept_specs:
        if colour[slug] == WHITE:
            visit(slug, [])


# --------------------------------------------------------------------------
# tracks
# --------------------------------------------------------------------------


def track_files() -> list[Path]:
    """Track YAMLs to seed, with hand-authored files superseding imported ones.

    `authored-<slug>.yaml` is ours: written independently, tracked in git and
    publishable. `<slug>.yaml` is whatever `scripts/import_roadmapsh.py` last
    wrote, and is git-ignored. Both define the same track slug and the same
    concept slugs, so seeding them together is an error — the importer already
    refuses to regenerate a roadmap that has an authored file, and this is the
    same rule applied to a tree that still has the pre-authoring import in it.
    """
    files = sorted(TRACKS_DIR.glob("*.yaml"))
    superseded = {
        TRACKS_DIR / f"{path.name[len('authored-'):]}"
        for path in files
        if path.name.startswith("authored-")
    }
    return [path for path in files if path not in superseded]


def seed_tracks(
    db: Session, domains: dict[str, Domain]
) -> tuple[dict[str, Track], dict[str, Concept]]:
    files = track_files()
    if not files:
        raise SeedError(f"No track files found in {TRACKS_DIR}")

    concept_specs: dict[str, dict[str, Any]] = {}
    track_specs: list[dict[str, Any]] = []

    for path in files:
        data = _read_yaml(path)
        track_specs.append(
            data["track"] | {"_concepts": data.get("concepts", []), "_file": path.name}
        )
        for raw in data.get("concepts", []):
            # An entry with only a slug is a *reference* to a concept defined in
            # another track file — that is how tracks share nodes (both the
            # backend and AI tracks include `programming-language-python`)
            # without duplicating several hundred lines of content.
            if _is_reference(raw):
                continue
            existing = concept_specs.get(raw["slug"])
            if existing is not None and existing != raw:
                raise SeedError(
                    f"Concept '{raw['slug']}' is fully defined in more than one "
                    f"track file (seen again in {path.name}). Define it once and "
                    f"reference it elsewhere with just its slug."
                )
            concept_specs[raw["slug"]] = raw

    for spec in track_specs:
        for raw in spec["_concepts"]:
            if _is_reference(raw) and raw["slug"] not in concept_specs:
                raise SeedError(
                    f"Track '{spec['slug']}' ({spec['_file']}) references concept "
                    f"'{raw['slug']}', which no track file defines."
                )

    concepts = {
        slug: upsert_concept(db, raw, domains) for slug, raw in concept_specs.items()
    }
    wire_prerequisites(db, concept_specs, concepts)

    tracks: dict[str, Track] = {}
    for order, spec in enumerate(track_specs):
        slug = spec["slug"]
        domain_slug = spec["domain"]
        if domain_slug not in domains:
            raise SeedError(f"Track '{slug}' references unknown domain '{domain_slug}'")

        track = db.scalar(select(Track).where(Track.slug == slug)) or Track(slug=slug)
        track.title = spec["title"]
        track.domain_id = domains[domain_slug].id
        track.target_role = spec["target_role"]
        track.description = spec.get("description")
        track.difficulty = spec.get("difficulty", "beginner")
        track.sort_order = order
        db.add(track)
        db.flush()

        track.track_concepts.clear()
        db.flush()
        for c_order, raw in enumerate(spec["_concepts"]):
            track.track_concepts.append(
                TrackConcept(
                    concept_id=concepts[raw["slug"]].id,
                    is_core=raw.get("is_core", True),
                    sort_order=c_order,
                )
            )

        domains[domain_slug].has_content = True
        tracks[slug] = track

    db.flush()
    return tracks, concepts


# --------------------------------------------------------------------------
# roles
# --------------------------------------------------------------------------


def seed_roles(db: Session, concepts: dict[str, Concept]) -> None:
    data = _read_yaml(SEED_DIR / "roles.yaml")

    for raw in data.get("roles", []):
        slug = raw["slug"]
        role = db.scalar(select(Role).where(Role.slug == slug)) or Role(slug=slug)
        role.title = raw["title"]
        role.description = raw.get("description")
        db.add(role)
        db.flush()

        role.skills.clear()
        db.flush()
        for skill in raw.get("skills", []):
            concept_slug = skill["concept"]
            if concept_slug not in concepts:
                raise SeedError(
                    f"Role '{slug}' references unknown concept '{concept_slug}'"
                )
            role.skills.append(
                RoleSkill(
                    concept_id=concepts[concept_slug].id,
                    weight=float(skill.get("weight", 1.0)),
                )
            )
    db.flush()


# --------------------------------------------------------------------------
# projects
# --------------------------------------------------------------------------


def seed_projects(db: Session, concepts: dict[str, Concept]) -> dict[str, Project]:
    """Load every `projects/*.yaml`.

    A project belongs to exactly one concept, which is what makes it the
    project *for that step*. Files and tests are replaced wholesale on each run
    — they have no independent identity — while submissions, which are user
    data, hang off the project id and survive.
    """
    projects: dict[str, Project] = {}
    for path in sorted(PROJECTS_DIR.glob("*.yaml")) if PROJECTS_DIR.exists() else []:
        data = _read_yaml(path)
        for order, raw in enumerate(data.get("projects", [])):
            slug = raw["slug"]
            if slug in projects:
                raise SeedError(
                    f"Project '{slug}' is defined twice (seen again in {path.name})"
                )
            concept_slug = raw["concept"]
            if concept_slug not in concepts:
                raise SeedError(
                    f"Project '{slug}' references unknown concept '{concept_slug}'"
                )
            runtime = raw.get("runtime", "python")
            if runtime not in RUNTIMES:
                raise SeedError(
                    f"Project '{slug}' has unknown runtime '{runtime}' "
                    f"(expected one of {', '.join(RUNTIMES)})"
                )

            project = db.scalar(
                select(Project).where(Project.slug == slug)
            ) or Project(slug=slug)
            project.concept_id = concepts[concept_slug].id
            project.title = raw["title"]
            project.tagline = raw.get("tagline", "")
            project.brief_md = raw.get("brief_md", "")
            project.runtime = runtime
            project.difficulty = raw.get("difficulty", "beginner")
            project.est_minutes = raw.get("est_minutes", 60)
            project.xp_reward = raw.get("xp_reward", 100)
            project.solution_md = raw.get("solution_md")
            project.must_contain = "\n".join(raw.get("must_contain", []) or []) or None
            project.sort_order = raw.get("sort_order", order)
            db.add(project)
            db.flush()

            _replace_project_children(db, project, raw, runtime)
            db.flush()
            projects[slug] = project

    return projects


def _replace_project_children(
    db: Session, project: Project, raw: dict[str, Any], runtime: str
) -> None:
    files = raw.get("files", [])
    if not files:
        raise SeedError(f"Project '{project.slug}' has no starter files")
    if not any(f.get("entry") for f in files):
        raise SeedError(
            f"Project '{project.slug}' has no entry file — mark one with `entry: true`"
        )

    # Flush the delete before inserting the replacements, or the new rows hit
    # the unique index while the old ones are still in the table.
    project.files.clear()
    db.flush()
    for order, spec in enumerate(files):
        project.files.append(
            ProjectFile(
                path=spec["path"],
                content=spec.get("content", ""),
                is_readonly=bool(spec.get("readonly", False)),
                is_entry=bool(spec.get("entry", False)),
                sort_order=order,
            )
        )

    tests = raw.get("tests", [])
    if not tests:
        raise SeedError(
            f"Project '{project.slug}' has no tests — a project with no way to "
            f"pass cannot award points"
        )

    project.tests.clear()
    db.flush()
    for order, spec in enumerate(tests):
        kind = spec.get("kind", TEST_KIND_FOR_RUNTIME[runtime])
        if kind not in TEST_KINDS:
            raise SeedError(f"Project '{project.slug}' has unknown test kind '{kind}'")
        if RUNTIME_FOR_TEST_KIND[kind] != runtime:
            raise SeedError(
                f"Project '{project.slug}' runs on '{runtime}' but test "
                f"'{spec['name']}' is a '{kind}' test"
            )
        project.tests.append(
            ProjectTest(
                name=spec["name"],
                kind=kind,
                code=spec["code"],
                expected=spec.get("expected"),
                is_hidden=bool(spec.get("hidden", False)),
                sort_order=order,
            )
        )


# --------------------------------------------------------------------------
# companies
# --------------------------------------------------------------------------


def seed_companies(db: Session, concepts: dict[str, Concept]) -> dict[str, Company]:
    """Load every `companies/*.yaml`.

    Two rules are enforced here rather than left to reviewer discipline:
    a question must cite a source URL, and a focus area's `concept:` must name
    a concept that exists. Both are the difference between this section being
    useful and it being plausible-looking filler.
    """
    companies: dict[str, Company] = {}
    for path in sorted(COMPANIES_DIR.glob("*.yaml")) if COMPANIES_DIR.exists() else []:
        data = _read_yaml(path)
        raw = data.get("company")
        if raw is None:
            raise SeedError(f"{path.name} has no top-level `company:` block")

        slug = raw["slug"]
        company = db.scalar(select(Company).where(Company.slug == slug)) or Company(
            slug=slug
        )
        company.name = raw["name"]
        company.industry = raw["industry"]
        company.hq = raw.get("hq")
        company.website = raw.get("website")
        company.icon = raw.get("icon", "Building2")
        company.description = raw.get("description")
        company.hiring_process_md = raw.get("hiring_process_md")
        company.fetched_on = raw.get("fetched_on")
        company.sort_order = raw.get("sort_order", len(companies))
        db.add(company)
        db.flush()

        company.resources.clear()
        db.flush()
        for order, res in enumerate(raw.get("resources", []) or []):
            company.resources.append(
                CompanyResource(
                    kind=res.get("kind", "careers"),
                    title=res["title"],
                    url=res["url"],
                    sort_order=order,
                )
            )

        company.roles.clear()
        db.flush()
        for order, role_raw in enumerate(data.get("roles", [])):
            company.roles.append(_build_company_role(db, slug, role_raw, order, concepts))

        db.flush()
        companies[slug] = company

    return companies


def _build_company_role(
    db: Session,
    company_slug: str,
    raw: dict[str, Any],
    order: int,
    concepts: dict[str, Concept],
) -> CompanyRole:
    role = CompanyRole(
        slug=raw["slug"],
        title=raw["title"],
        level=raw.get("level", "entry"),
        description=raw.get("description"),
        focus_md=raw.get("focus_md"),
        source_url=raw.get("source_url"),
        sort_order=raw.get("sort_order", order),
    )

    generic = raw.get("maps_to_role")
    if generic:
        matched = db.scalar(select(Role).where(Role.slug == generic))
        if matched is None:
            raise SeedError(
                f"Role '{company_slug}/{raw['slug']}' maps to unknown role '{generic}'"
            )
        role.role_id = matched.id

    for f_order, focus in enumerate(raw.get("focus_areas", []) or []):
        concept_slug = focus.get("concept")
        if concept_slug and concept_slug not in concepts:
            raise SeedError(
                f"Focus area '{focus['label']}' on '{company_slug}/{raw['slug']}' "
                f"references unknown concept '{concept_slug}'"
            )
        role.focus_areas.append(
            CompanyFocus(
                concept_id=concepts[concept_slug].id if concept_slug else None,
                label=focus["label"],
                notes=focus.get("notes"),
                weight=float(focus.get("weight", 3.0)),
                sort_order=f_order,
            )
        )

    for q_order, q in enumerate(raw.get("questions", []) or []):
        kind = q.get("kind", "interview")
        if kind not in QUESTION_KINDS:
            raise SeedError(
                f"Question on '{company_slug}/{raw['slug']}' has unknown kind '{kind}'"
            )
        round_ = q.get("round", "technical")
        if round_ not in ROUNDS:
            raise SeedError(
                f"Question on '{company_slug}/{raw['slug']}' has unknown round '{round_}'"
            )
        if not q.get("source_url") or not q.get("source_name"):
            raise SeedError(
                f"Question on '{company_slug}/{raw['slug']}' has no source: "
                f"{q['question'][:60]!r}. Every question must cite where it came from."
            )
        role.questions.append(
            CompanyQuestion(
                kind=kind,
                round=round_,
                topic=q.get("topic"),
                question=q["question"],
                answer_md=q.get("answer_md"),
                difficulty=q.get("difficulty", "medium"),
                year=q.get("year"),
                source_name=q["source_name"],
                source_url=q["source_url"],
                sort_order=q_order,
            )
        )

    return role


# --------------------------------------------------------------------------
# sample reviews
# --------------------------------------------------------------------------


def _sample_author(db: Session, key: str, display_name: str) -> User:
    """Get or create the placeholder account a sample review is attributed to.

    These are not usable accounts: the address sits in a reserved, unresolvable
    TLD, ``is_active`` is False so ``deps.get_current_user`` would reject any
    token naming one, and the password is a random value that is discarded
    after hashing, so nobody holds it.

    They exist at all only because a review has an author by design. Adding a
    nullable "authorless review" path just to seed demo content would leave a
    hole that real reviews could later fall through — the honest fix is a real
    author who happens to be a placeholder, labelled as one.
    """
    email = f"{key}@{SAMPLE_AUTHOR_DOMAIN}"
    user = db.scalar(select(User).where(User.email == email))
    if user is None:
        user = User(
            email=email,
            # A real hash of a value nobody holds, rather than an empty
            # string: `verify_password` then behaves normally and simply never
            # matches, instead of every login attempt taking the malformed-hash
            # path. `is_active=False` is what actually locks the account.
            password_hash=hash_password(secrets.token_urlsafe(32)),
            is_active=False,
        )
        db.add(user)
    user.display_name = display_name
    db.flush()
    return user


def seed_reviews(db: Session, companies: dict[str, Company]) -> int:
    """Load every `reviews/*.yaml` — illustrative member reviews.

    Sample content, and it says so in three places: `is_sample` on the row, a
    display name containing "sample", and body text that opens by admitting it.
    That triple is deliberate. A demo review that reads as real testimony is
    worse than an empty section, because a learner would weigh it when deciding
    where to apply.

    Unlike `seed_companies` these rows are not authored claims about a company,
    so there is no `source_url` rule to enforce. What is enforced instead is
    that every review points at a company and a role that actually exist, and
    carries a rating and an outcome the API can serve — an unknown company slug
    is a hard error, exactly as it is for a focus area's concept.
    """
    if not REVIEWS_DIR.exists():
        return 0

    loaded = 0
    for path in sorted(REVIEWS_DIR.glob("*.yaml")):
        data = _read_yaml(path)

        authors: dict[str, User] = {}
        for raw in data.get("authors", []) or []:
            key = raw["key"]
            if key in authors:
                raise SeedError(f"{path.name} defines sample author '{key}' twice")
            authors[key] = _sample_author(db, key, raw["display_name"])

        for raw in data.get("reviews", []) or []:
            company_slug = raw["company"]
            company = companies.get(company_slug)
            if company is None:
                raise SeedError(
                    f"{path.name} has a review for unknown company '{company_slug}'"
                )

            author_key = raw["author"]
            if author_key not in authors:
                raise SeedError(
                    f"{path.name} has a review by unknown sample author "
                    f"'{author_key}' for '{company_slug}'"
                )
            author = authors[author_key]

            role_slug = raw.get("role")
            role_id = None
            if role_slug:
                role = next((r for r in company.roles if r.slug == role_slug), None)
                if role is None:
                    raise SeedError(
                        f"{path.name}: review for '{company_slug}' names unknown "
                        f"role '{role_slug}'"
                    )
                role_id = role.id

            rating = int(raw["rating"])
            if not 1 <= rating <= 5:
                raise SeedError(
                    f"{path.name}: review for '{company_slug}' has rating {rating}, "
                    f"expected 1-5"
                )

            outcome = raw.get("interview_outcome", "not-interviewed")
            if outcome not in INTERVIEW_OUTCOMES:
                raise SeedError(
                    f"{path.name}: review for '{company_slug}' has unknown outcome "
                    f"'{outcome}' (expected one of {', '.join(INTERVIEW_OUTCOMES)})"
                )

            # Keyed on (company, author) — the same pair the unique constraint
            # covers — so re-running edits the row rather than colliding.
            review = db.scalar(
                select(CompanyReview).where(
                    CompanyReview.company_id == company.id,
                    CompanyReview.user_id == author.id,
                )
            ) or CompanyReview(company_id=company.id, user_id=author.id)

            review.company_role_id = role_id
            review.rating = rating
            review.title = raw["title"]
            review.body_md = raw["body_md"]
            review.interview_outcome = outcome
            review.interview_year = raw.get("interview_year")
            review.is_anonymous = bool(raw.get("is_anonymous", False))
            # Not configurable from YAML. Anything loaded from here is a sample
            # by definition, and a file that could opt out of the label would
            # be a way to seed content that passes as genuine.
            review.is_sample = True
            review.helpful_count = review.helpful_count or 0
            review.not_helpful_count = review.not_helpful_count or 0
            db.add(review)
            loaded += 1

        db.flush()

    return loaded


# --------------------------------------------------------------------------
# quizzes
# --------------------------------------------------------------------------


def _parse_verified_at(value: Any, slug: str) -> datetime | None:
    """Accept an ISO-8601 string or the date/datetime PyYAML already parsed."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as exc:
            raise SeedError(
                f"Quiz block for '{slug}' has an unparseable verified_at "
                f"{value!r}: {exc}"
            ) from None
    raise SeedError(f"Quiz block for '{slug}' has a non-date verified_at {value!r}")


def seed_quizzes(db: Session, concepts: dict[str, Concept]) -> dict[str, int]:
    """Load every `quizzes/*.yaml` and attach the questions to their concept.

    These files are the reason the product's "every step ends in a check"
    claim can be true: roadmap.sh ships no assessment material at all, so
    without them ``routers/progress.py`` waves every concept through on its
    ``question_count == 0`` fallback.

    They live outside `tracks/` deliberately. `tracks/` is machine-generated
    and git-ignored; re-running the importer wipes it. The questions were
    written for this product and have to outlive a re-import, so they are keyed
    by concept slug and attached here instead of being folded into the concept
    body.

    Attached wholesale, like every other child collection: a concept named in
    one of these files loses whatever questions it already had. A file naming a
    concept that does not exist is an error rather than a silent skip — that is
    a typo or a slug that moved under the importer, and either way the check it
    was meant to gate has quietly stopped existing.
    """
    seen: dict[str, str] = {}
    counts = {"concepts": 0, "quiz": 0, "interview": 0}

    for path in sorted(QUIZZES_DIR.glob("*.yaml")) if QUIZZES_DIR.exists() else []:
        data = _read_yaml(path)
        for slug, raw in (data.get("concepts") or {}).items():
            if slug in seen:
                raise SeedError(
                    f"Concept '{slug}' has quizzes in both {seen[slug]} and "
                    f"{path.name}. Define them in one file."
                )
            if slug not in concepts:
                raise SeedError(
                    f"{path.name} attaches questions to unknown concept '{slug}'"
                )
            seen[slug] = path.name

            concept = concepts[slug]
            generated_by = raw.get("generated_by")
            verified_at = _parse_verified_at(raw.get("verified_at"), slug)

            concept.quiz_questions.clear()
            concept.interview_questions.clear()
            db.flush()

            for order, q in enumerate(raw.get("quiz", []) or []):
                concept.quiz_questions.append(
                    _build_quiz_question(slug, q, order, generated_by, verified_at)
                )
            for order, iq in enumerate(raw.get("interview", []) or []):
                concept.interview_questions.append(
                    _build_interview_question(slug, iq, order, generated_by, verified_at)
                )

            counts["concepts"] += 1
            counts["quiz"] += len(concept.quiz_questions)
            counts["interview"] += len(concept.interview_questions)
            db.flush()

    return counts


# --------------------------------------------------------------------------
# entrypoint
# --------------------------------------------------------------------------


def seed_all(db: Session, *, verbose: bool = True) -> dict[str, int]:
    domains = seed_domains(db)
    tracks, concepts = seed_tracks(db, domains)
    seed_roles(db, concepts)
    projects = seed_projects(db, concepts)
    companies = seed_companies(db, concepts)
    reviews = seed_reviews(db, companies)
    # After the tracks: upserting a concept clears its child collections, so
    # anything attached before this point would be thrown away.
    quizzes = seed_quizzes(db, concepts)
    db.commit()

    counts = {
        "domains": len(domains),
        "tracks": len(tracks),
        "concepts": len(concepts),
        "projects": len(projects),
        "companies": len(companies),
        "sample_reviews": reviews,
        "quizzed_concepts": quizzes["concepts"],
        "quiz_questions": quizzes["quiz"],
        "interview_questions": quizzes["interview"],
        "with_content": sum(1 for d in domains.values() if d.has_content),
    }
    if verbose:
        print(
            f"Seeded {counts['domains']} domains "
            f"({counts['with_content']} with content), "
            f"{counts['tracks']} tracks, {counts['concepts']} concepts, "
            f"{counts['projects']} projects, {counts['companies']} companies, "
            f"{counts['sample_reviews']} sample reviews, "
            f"{counts['quiz_questions']} quiz + "
            f"{counts['interview_questions']} interview questions "
            f"across {counts['quizzed_concepts']} concepts."
        )
    return counts


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Seed SkillAtlas content.")
    parser.add_argument(
        "--embed",
        action="store_true",
        help="also build RAG embeddings for concepts (requires Ollama running)",
    )
    args = parser.parse_args(argv)

    db = SessionLocal()
    try:
        seed_all(db)
        if args.embed:
            from app.services.rag import rebuild_embeddings

            written = rebuild_embeddings(db)
            print(f"Embedded {written} concept chunks.")
    except SeedError as exc:
        db.rollback()
        print(f"Seed failed: {exc}", file=sys.stderr)
        return 1
    finally:
        db.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
