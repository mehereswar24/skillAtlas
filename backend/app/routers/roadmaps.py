"""Roadmap creation and retrieval.

Replaces the original stateless `POST /roadmaps/generate`, which computed a
plan from a hardcoded dict and threw it away. Roadmaps are now derived from the
seeded graph and persisted, which is what makes progress meaningful.
"""

from datetime import date, datetime, timedelta, timezone

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
    PACES,
    RoadmapAppend,
    RoadmapCreate,
    RoadmapItemOut,
    RoadmapItemUpdate,
    RoadmapOut,
    RoadmapSummaryOut,
    RoadmapWeekOut,
)
from app.services.graph import ConceptGraph
from app.services.roadmap import (
    append_concepts,
    build_roadmap,
    concept_ids_by_slug,
    get_active_roadmap,
    get_active_roadmaps,
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
                is_locked=not graph.is_unlocked(item.concept_id, completed),
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
        pace=pace_for_hours(roadmap.daily_hours),
        created_at=roadmap.created_at or datetime.now(timezone.utc),
        total_concepts=total,
        completed_concepts=done,
        percent_complete=round(done / total * 100) if total else 0,
        target_date=finish_date(roadmap, week_list),
        weeks=week_list,
    )


def pace_for_hours(daily_hours: int) -> str:
    """The closest named pace to a raw hours figure."""
    return min(PACES, key=lambda name: abs(PACES[name] - daily_hours))


def finish_date(roadmap: UserRoadmap, weeks: list[RoadmapWeekOut]) -> date | None:
    """When the *remaining* work runs out, at the roadmap's pace.

    Counted from today over the weeks that still hold unfinished items, rather
    than from the creation date over all of them — a learner who is ahead
    should see the date move towards them, not sit where it was on day one.
    """
    outstanding = [
        week
        for week in weeks
        if any(item.status != STATUS_COMPLETED for item in week.items)
    ]
    if not outstanding:
        return None
    return date.today() + timedelta(weeks=len(outstanding))


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

    daily_hours = payload.hours_per_day
    roadmap = build_roadmap(db, user.id, track, daily_hours, known_ids)

    profile = get_profile(db, user)
    profile.current_track_id = track.id
    profile.target_goal = track.title
    profile.daily_hours = daily_hours
    profile.pace = payload.pace or pace_for_hours(daily_hours)

    db.commit()
    db.refresh(roadmap)

    serialized = serialize_roadmap(db, roadmap, user.id)
    # Cached on the profile so the dashboard can show the finish date without
    # rebuilding the whole roadmap.
    profile.target_date = serialized.target_date
    db.commit()
    return serialized


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


def summarize_roadmap(
    db: DbSession, roadmap: UserRoadmap, user_id: int, *, is_focused: bool
) -> RoadmapSummaryOut:
    """The list view of a route. Cheaper than `serialize_roadmap` by a graph load."""
    total = len(roadmap.items)
    done = sum(1 for item in roadmap.items if item.status == STATUS_COMPLETED)

    weeks: dict[int, list[UserRoadmapItem]] = {}
    for item in roadmap.items:
        weeks.setdefault(item.week_no, []).append(item)
    outstanding = [
        week_no
        for week_no, items in weeks.items()
        if any(i.status != STATUS_COMPLETED for i in items)
    ]

    track_concept_count = len(roadmap.track.track_concepts)
    track_hours = sum(tc.concept.est_hours for tc in roadmap.track.track_concepts)

    return RoadmapSummaryOut(
        id=roadmap.id,
        track=track_summary(roadmap.track, track_concept_count, track_hours),
        daily_hours=roadmap.daily_hours,
        pace=pace_for_hours(roadmap.daily_hours),
        created_at=roadmap.created_at or datetime.now(timezone.utc),
        total_concepts=total,
        completed_concepts=done,
        percent_complete=round(done / total * 100) if total else 0,
        target_date=(
            date.today() + timedelta(weeks=len(outstanding)) if outstanding else None
        ),
        is_focused=is_focused,
    )


@router.get("", response_model=list[RoadmapSummaryOut])
def list_roadmaps(user: CurrentUser, db: DbSession):
    """Every route the learner is running, focused one first."""
    roadmaps = get_active_roadmaps(db, user.id)
    if not roadmaps:
        return []

    focused = get_active_roadmap(db, user.id)
    focused_id = focused.id if focused else None

    summaries = []
    for roadmap in roadmaps:
        sync_item_statuses(db, roadmap, user.id)
        summaries.append(
            summarize_roadmap(db, roadmap, user.id, is_focused=roadmap.id == focused_id)
        )
    db.commit()
    summaries.sort(key=lambda r: (not r.is_focused, r.track.title))
    return summaries


@router.post("/{roadmap_id}/focus", response_model=RoadmapOut)
def focus_roadmap(roadmap_id: int, user: CurrentUser, db: DbSession):
    """Make this the route the dashboard and tutor act on."""
    roadmap = _owned_roadmap(db, roadmap_id, user.id)

    profile = get_profile(db, user)
    profile.current_track_id = roadmap.track_id
    profile.target_goal = roadmap.track.title
    profile.daily_hours = roadmap.daily_hours
    profile.pace = pace_for_hours(roadmap.daily_hours)

    sync_item_statuses(db, roadmap, user.id)
    db.commit()
    db.refresh(roadmap)

    serialized = serialize_roadmap(db, roadmap, user.id)
    profile.target_date = serialized.target_date
    db.commit()
    return serialized


@router.delete("/{roadmap_id}", status_code=status.HTTP_204_NO_CONTENT)
def drop_roadmap(roadmap_id: int, user: CurrentUser, db: DbSession):
    """Stop running a route.

    Completed concepts live in `user_progress`, not here, so dropping a route
    loses the plan but never the progress — picking it up again rebuilds around
    what is already done.
    """
    roadmap = _owned_roadmap(db, roadmap_id, user.id)
    was_focused = roadmap.track_id

    roadmap.is_active = False
    db.flush()

    profile = get_profile(db, user)
    if profile.current_track_id == was_focused:
        remaining = get_active_roadmaps(db, user.id)
        nxt = remaining[0] if remaining else None
        profile.current_track_id = nxt.track_id if nxt else None
        profile.target_goal = nxt.track.title if nxt else None
        profile.target_date = None
    db.commit()


def _owned_roadmap(db: DbSession, roadmap_id: int, user_id: int) -> UserRoadmap:
    """404 rather than 403 — a roadmap you do not own should not be discoverable."""
    roadmap = db.scalar(
        select(UserRoadmap).where(
            UserRoadmap.id == roadmap_id,
            UserRoadmap.user_id == user_id,
            UserRoadmap.is_active.is_(True),
        )
    )
    if roadmap is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such roadmap")
    return roadmap


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
        is_locked=not graph.is_unlocked(item.concept_id, completed),
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
