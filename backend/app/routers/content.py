"""Public content endpoints: domains, tracks and concepts.

These replace the hardcoded dictionaries the original `routers/domains.py` and
`routers/roadmaps.py` returned — every row here comes from the seeded database.
"""

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import func, select

from app.deps import DbSession, OptionalUser
from app.models.content import Concept, Domain, Track, TrackConcept
from app.models.progress import STATUS_COMPLETED, UserProgress
from app.schemas.content import (
    ConceptDetail,
    ConceptSummary,
    DomainOut,
    InterviewQuestionOut,
    QuizOptionOut,
    QuizQuestionOut,
    ResourceOut,
    TrackDetail,
    TrackSummary,
)
from app.services.graph import ConceptGraph

router = APIRouter(tags=["content"])


# --------------------------------------------------------------------------
# serialisation helpers
# --------------------------------------------------------------------------


def concept_summary(concept: Concept) -> ConceptSummary:
    return ConceptSummary(
        id=concept.id,
        slug=concept.slug,
        name=concept.name,
        summary=concept.summary,
        est_hours=concept.est_hours,
        difficulty=concept.difficulty,
        domain_slug=concept.domain.slug,
    )


def track_summary(track: Track, concept_count: int, total_hours: int) -> TrackSummary:
    return TrackSummary(
        id=track.id,
        slug=track.slug,
        title=track.title,
        target_role=track.target_role,
        description=track.description,
        difficulty=track.difficulty,
        domain_slug=track.domain.slug,
        concept_count=concept_count,
        total_hours=total_hours,
    )


def _track_stats(db: DbSession) -> dict[int, tuple[int, int]]:
    """track_id -> (concept count, summed estimated hours), in one query."""
    rows = db.execute(
        select(
            TrackConcept.track_id,
            func.count(TrackConcept.concept_id),
            func.coalesce(func.sum(Concept.est_hours), 0),
        )
        .join(Concept, Concept.id == TrackConcept.concept_id)
        .group_by(TrackConcept.track_id)
    ).all()
    return {track_id: (count, hours) for track_id, count, hours in rows}


# --------------------------------------------------------------------------
# domains
# --------------------------------------------------------------------------


@router.get("/domains", response_model=list[DomainOut])
def list_domains(
    db: DbSession,
    category: str | None = Query(None, description="Filter by category"),
    search: str | None = Query(None, description="Case-insensitive name search"),
    with_content: bool | None = Query(
        None, description="Only domains that have (or lack) curated tracks"
    ),
):
    stmt = select(Domain).order_by(Domain.sort_order)
    if category:
        stmt = stmt.where(Domain.category == category)
    if with_content is not None:
        stmt = stmt.where(Domain.has_content.is_(with_content))
    if search:
        stmt = stmt.where(Domain.name.ilike(f"%{search}%"))
    return list(db.scalars(stmt).all())


@router.get("/domains/categories", response_model=list[str])
def list_domain_categories(db: DbSession):
    return list(
        db.scalars(
            select(Domain.category).distinct().order_by(Domain.category)
        ).all()
    )


@router.get("/domains/{slug}", response_model=DomainOut)
def get_domain(slug: str, db: DbSession):
    domain = db.scalar(select(Domain).where(Domain.slug == slug))
    if domain is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Domain not found")
    return domain


# --------------------------------------------------------------------------
# tracks
# --------------------------------------------------------------------------


@router.get("/tracks", response_model=list[TrackSummary])
def list_tracks(db: DbSession, domain: str | None = Query(None)):
    stmt = select(Track).order_by(Track.sort_order)
    if domain:
        stmt = stmt.join(Domain).where(Domain.slug == domain)
    tracks = list(db.scalars(stmt).unique().all())
    stats = _track_stats(db)
    return [track_summary(t, *stats.get(t.id, (0, 0))) for t in tracks]


@router.get("/tracks/{slug}", response_model=TrackDetail)
def get_track(slug: str, db: DbSession):
    track = db.scalar(select(Track).where(Track.slug == slug))
    if track is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Track not found")

    concepts = [tc.concept for tc in track.track_concepts]
    total_hours = sum(c.est_hours for c in concepts)
    base = track_summary(track, len(concepts), total_hours)
    return TrackDetail(
        **base.model_dump(),
        concepts=[concept_summary(c) for c in concepts],
    )


# --------------------------------------------------------------------------
# concepts
# --------------------------------------------------------------------------


@router.get("/concepts", response_model=list[ConceptSummary])
def list_concepts(
    db: DbSession,
    domain: str | None = Query(None),
    search: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    stmt = select(Concept).order_by(Concept.name)
    if domain:
        stmt = stmt.join(Domain).where(Domain.slug == domain)
    if search:
        stmt = stmt.where(Concept.name.ilike(f"%{search}%"))
    concepts = db.scalars(stmt.limit(limit).offset(offset)).unique().all()
    return [concept_summary(c) for c in concepts]


@router.get("/concepts/{slug}", response_model=ConceptDetail)
def get_concept(slug: str, db: DbSession, user: OptionalUser):
    concept = db.scalar(select(Concept).where(Concept.slug == slug))
    if concept is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Concept not found")

    graph = ConceptGraph.load(db)
    prereq_ids = graph.direct_prerequisites(concept.id)
    unlock_ids = graph.direct_dependents(concept.id)

    related = {
        c.id: c
        for c in db.scalars(
            select(Concept).where(Concept.id.in_(prereq_ids | unlock_ids))
        ).unique()
    }

    detail = ConceptDetail(
        **concept_summary(concept).model_dump(),
        content_md=concept.content_md,
        prerequisites=[
            concept_summary(related[i]) for i in sorted(prereq_ids) if i in related
        ],
        unlocks=[
            concept_summary(related[i]) for i in sorted(unlock_ids) if i in related
        ],
        resources=[ResourceOut.model_validate(r) for r in concept.resources],
        quiz=[
            QuizQuestionOut(
                id=q.id,
                prompt=q.prompt,
                options=[QuizOptionOut(id=o.id, text=o.text) for o in q.options],
            )
            for q in concept.quiz_questions
        ],
        interview_questions=[
            InterviewQuestionOut.model_validate(q) for q in concept.interview_questions
        ],
    )

    if user is not None:
        completed = set(
            db.scalars(
                select(UserProgress.concept_id).where(
                    UserProgress.user_id == user.id,
                    UserProgress.status == STATUS_COMPLETED,
                )
            ).all()
        )
        own = db.scalar(
            select(UserProgress).where(
                UserProgress.user_id == user.id,
                UserProgress.concept_id == concept.id,
            )
        )
        missing = graph.missing_prerequisites(concept.id, completed)
        detail.status = own.status if own else None
        detail.is_locked = bool(missing)
        detail.missing_prerequisites = [
            concept_summary(related[i]) for i in sorted(missing) if i in related
        ]

    return detail
