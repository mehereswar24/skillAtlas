"""Idempotent content seeder.

    python -m app.seed.loader              # seed everything
    python -m app.seed.loader --embed      # also build RAG embeddings (needs Ollama)

Everything is keyed by slug and upserted, so re-running is safe and editing a
YAML file then re-running propagates the edit. Child collections (resources,
quiz questions, interview questions, role skills) are replaced wholesale —
they have no independent identity and no user data hangs off them.

Concepts are loaded across *all* track files before prerequisites are wired,
because tracks share concepts: `programming-language-python` and
`containers-docker` appear in both the backend and AI-engineer tracks, which is
exactly what makes this a graph rather than a set of lists.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

import yaml
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models.assessment import AssessmentOption, AssessmentQuestion
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

SEED_DIR = Path(__file__).resolve().parent
TRACKS_DIR = SEED_DIR / "tracks"


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
        options = q.get("options", [])
        if not any(o.get("correct") for o in options):
            raise SeedError(
                f"Quiz question on '{concept.slug}' has no correct option: {q['prompt'][:60]!r}"
            )
        question = QuizQuestion(
            prompt=q["prompt"],
            explanation=q.get("explanation"),
            sort_order=q_order,
        )
        for o_order, opt in enumerate(options):
            question.options.append(
                QuizOption(
                    text=opt["text"],
                    is_correct=bool(opt.get("correct", False)),
                    sort_order=o_order,
                )
            )
        concept.quiz_questions.append(question)

    concept.interview_questions.clear()
    for order, iq in enumerate(raw.get("interview", [])):
        concept.interview_questions.append(
            InterviewQuestion(
                question=iq["question"],
                answer_md=iq.get("answer_md"),
                difficulty=iq.get("difficulty", "medium"),
                sort_order=order,
            )
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


def seed_tracks(
    db: Session, domains: dict[str, Domain]
) -> tuple[dict[str, Track], dict[str, Concept]]:
    files = sorted(TRACKS_DIR.glob("*.yaml"))
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
# roles + assessment
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


def seed_assessment(db: Session) -> None:
    data = _read_yaml(SEED_DIR / "assessment.yaml")

    # Questions carry no user data (results reference categories, not option
    # ids), so a clean rebuild keeps the file authoritative.
    db.query(AssessmentOption).delete()
    db.query(AssessmentQuestion).delete()
    db.flush()

    for q_order, raw in enumerate(data.get("questions", [])):
        question = AssessmentQuestion(prompt=raw["prompt"], sort_order=q_order)
        for o_order, opt in enumerate(raw.get("options", [])):
            question.options.append(
                AssessmentOption(
                    text=opt["text"],
                    category=opt["category"],
                    weight=float(opt.get("weight", 1.0)),
                    sort_order=o_order,
                )
            )
        db.add(question)
    db.flush()


# --------------------------------------------------------------------------
# entrypoint
# --------------------------------------------------------------------------


def seed_all(db: Session, *, verbose: bool = True) -> dict[str, int]:
    domains = seed_domains(db)
    tracks, concepts = seed_tracks(db, domains)
    seed_roles(db, concepts)
    seed_assessment(db)
    db.commit()

    counts = {
        "domains": len(domains),
        "tracks": len(tracks),
        "concepts": len(concepts),
        "with_content": sum(1 for d in domains.values() if d.has_content),
    }
    if verbose:
        print(
            f"Seeded {counts['domains']} domains "
            f"({counts['with_content']} with content), "
            f"{counts['tracks']} tracks, {counts['concepts']} concepts."
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
