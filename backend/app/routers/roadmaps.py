"""Roadmap creation and retrieval.

Replaces the original stateless `POST /roadmaps/generate`, which computed a
plan from a hardcoded dict and threw it away. Roadmaps are now derived from the
seeded graph and persisted, which is what makes progress meaningful.
"""

from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app.deps import CurrentUser, DbSession, get_profile
from app.models.content import Concept
from app.models.progress import (
    STATUS_COMPLETED,
    UserProgress,
    UserRoadmap,
    UserRoadmapItem,
)
from app.routers.content import concept_summary, track_summary
from app.schemas.roadmap import (
    RoadmapAppend,
    RoadmapCreate,
    RoadmapItemOut,
    RoadmapItemUpdate,
    RoadmapOut,
    RoadmapWeekOut,
)
from app.services.graph import ConceptGraph
from app.services.roadmap import (
    append_concepts,
    build_roadmap,
    concept_ids_by_slug,
    get_active_roadmap,
    resolve_track,
    sync_item_statuses,
)

router = APIRouter(prefix="/roadmaps", tags=["roadmaps"])


def serialize_roadmap(db: DbSession, roadmap: UserRoadmap, user_id: int) -> RoadmapOut:
    graph = ConceptGraph.load(db)
    completed = set(
        db.scalars(
            select(UserProgress.concept_id).where(
                UserProgress.user_id == user_id,
                UserProgress.status == STATUS_COMPLETED,
            )
        ).all()
    )
    # Slugs for the "missing prerequisites" hint, in one query.
    slugs = {
        concept_id: slug
        for concept_id, slug in db.execute(select(Concept.id, Concept.slug)).all()
    }

    weeks: dict[int, list[RoadmapItemOut]] = {}
    for item in roadmap.items:
        missing = graph.missing_prerequisites(item.concept_id, completed)
        weeks.setdefault(item.week_no, []).append(
            RoadmapItemOut(
                id=item.id,
                concept=concept_summary(item.concept),
                week_no=item.week_no,
                status=item.status,
                is_locked=bool(missing),
                missing_prerequisites=[
                    slugs[i] for i in sorted(missing) if i in slugs
                ],
            )
        )

    week_list = [
        RoadmapWeekOut(
            week_no=week_no,
            title=f"Week {week_no}",
            total_hours=sum(i.concept.est_hours for i in items),
            items=items,
        )
        for week_no, items in sorted(weeks.items())
    ]

    total = len(roadmap.items)
    done = sum(1 for item in roadmap.items if item.status == STATUS_COMPLETED)
    track_concept_count = len(roadmap.track.track_concepts)
    track_hours = sum(tc.concept.est_hours for tc in roadmap.track.track_concepts)

    return RoadmapOut(
        id=roadmap.id,
        track=track_summary(roadmap.track, track_concept_count, track_hours),
        daily_hours=roadmap.daily_hours,
        created_at=roadmap.created_at or datetime.now(timezone.utc),
        total_concepts=total,
        completed_concepts=done,
        percent_complete=round(done / total * 100) if total else 0,
        weeks=week_list,
    )


@router.post("", response_model=RoadmapOut, status_code=status.HTTP_201_CREATED)
def create_roadmap(payload: RoadmapCreate, user: CurrentUser, db: DbSession):
    track = resolve_track(db, slug=payload.track_slug, goal=payload.goal)
    if track is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            "We don't have a curated track for that goal yet. "
            "Pick one from /api/v1/tracks.",
        )

    known_ids = concept_ids_by_slug(db, payload.known_concept_slugs)
    _record_prior_knowledge(db, user.id, known_ids)

    roadmap = build_roadmap(db, user.id, track, payload.daily_hours, known_ids)

    profile = get_profile(db, user)
    profile.current_track_id = track.id
    profile.target_goal = track.title
    profile.daily_hours = payload.daily_hours

    db.commit()
    db.refresh(roadmap)
    return serialize_roadmap(db, roadmap, user.id)


def _record_prior_knowledge(db: DbSession, user_id: int, concept_ids: set[int]) -> None:
    """Mark declared-known concepts complete, without awarding XP.

    XP is for work done here; claiming prior knowledge should skip content, not
    inflate the score.
    """
    if not concept_ids:
        return
    existing = set(
        db.scalars(
            select(UserProgress.concept_id).where(
                UserProgress.user_id == user_id,
                UserProgress.concept_id.in_(concept_ids),
            )
        ).all()
    )
    now = datetime.now(timezone.utc)
    for concept_id in concept_ids - existing:
        db.add(
            UserProgress(
                user_id=user_id,
                concept_id=concept_id,
                status=STATUS_COMPLETED,
                source="prior-knowledge",
                completed_at=now,
                # Set explicitly: column defaults are not applied until INSERT,
                # so these would read as None before the flush below.
                confidence_score=1.0,
                time_spent_minutes=0,
            )
        )
    db.flush()


@router.get("/current", response_model=RoadmapOut)
def current_roadmap(user: CurrentUser, db: DbSession):
    roadmap = get_active_roadmap(db, user.id)
    if roadmap is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, "You don't have a roadmap yet"
        )
    sync_item_statuses(db, roadmap, user.id)
    db.commit()
    return serialize_roadmap(db, roadmap, user.id)


@router.patch("/items/{item_id}", response_model=RoadmapItemOut)
def update_item(
    item_id: int, payload: RoadmapItemUpdate, user: CurrentUser, db: DbSession
):
    item = db.get(UserRoadmapItem, item_id)
    if item is None or item.roadmap.user_id != user.id:
        # Same 404 whether it does not exist or is not yours, so ids cannot be
        # probed for existence.
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Roadmap item not found")

    item.status = payload.status
    db.commit()

    graph = ConceptGraph.load(db)
    completed = set(
        db.scalars(
            select(UserProgress.concept_id).where(
                UserProgress.user_id == user.id,
                UserProgress.status == STATUS_COMPLETED,
            )
        ).all()
    )
    missing = graph.missing_prerequisites(item.concept_id, completed)
    slugs = dict(db.execute(select(Concept.id, Concept.slug)).all())
    return RoadmapItemOut(
        id=item.id,
        concept=concept_summary(item.concept),
        week_no=item.week_no,
        status=item.status,
        is_locked=bool(missing),
        missing_prerequisites=[slugs[i] for i in sorted(missing) if i in slugs],
    )


@router.post("/current/items", response_model=RoadmapOut)
def add_to_roadmap(payload: RoadmapAppend, user: CurrentUser, db: DbSession):
    """Append concepts (plus any prerequisites) to the active roadmap."""
    roadmap = get_active_roadmap(db, user.id)
    if roadmap is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            "Create a roadmap before adding concepts to it",
        )

    concept_ids = concept_ids_by_slug(db, payload.concept_slugs)
    if not concept_ids:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such concepts")

    append_concepts(db, roadmap, concept_ids)
    db.commit()
    db.refresh(roadmap)
    return serialize_roadmap(db, roadmap, user.id)
