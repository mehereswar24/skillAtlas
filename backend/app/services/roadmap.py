"""Roadmap generation and persistence.

The scheduling half of this (topological order → weekly chunks) is the same
algorithm the original prototype had in `routers/roadmaps.py`, lifted out of
the router, fed by the real graph instead of a hardcoded dict, and extended to
pull in transitive prerequisites and skip what the learner already knows.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.content import Concept, Track
from app.models.progress import (
    STATUS_COMPLETED,
    STATUS_PENDING,
    UserProgress,
    UserRoadmap,
    UserRoadmapItem,
)
from app.services.graph import ConceptGraph, track_concept_ids

# A concept bigger than one week's budget still gets its own week rather than
# being split — half a concept is not a deliverable.
MIN_WEEKLY_HOURS = 1


@dataclass
class ScheduledWeek:
    week_no: int
    concept_ids: list[int]
    total_hours: int


def chunk_into_weeks(
    ordered_ids: list[int], hours: dict[int, int], weekly_hours: int
) -> list[ScheduledWeek]:
    """Pack a topologically ordered list into weeks under an hours budget.

    Order is preserved, so a prerequisite always lands in the same week as or an
    earlier week than the concept that requires it.
    """
    weekly_hours = max(weekly_hours, MIN_WEEKLY_HOURS)
    weeks: list[ScheduledWeek] = []
    current: list[int] = []
    current_hours = 0

    for concept_id in ordered_ids:
        cost = hours.get(concept_id, 0)
        if current and current_hours + cost > weekly_hours:
            weeks.append(ScheduledWeek(len(weeks) + 1, current, current_hours))
            current, current_hours = [], 0
        current.append(concept_id)
        current_hours += cost

    if current:
        weeks.append(ScheduledWeek(len(weeks) + 1, current, current_hours))
    return weeks


def plan_concepts(
    graph: ConceptGraph, track_concept_ids_: list[int], known: set[int]
) -> list[int]:
    """Concepts to schedule, in learning order.

    Takes the track's curated concepts, adds everything they transitively
    require (which is how the AI track picks up `containers-docker` from the
    backend track), then drops what the learner already knows — but keeps a
    known concept if something still-to-learn depends on it having been
    covered... which it does not, since "known" means completed.
    """
    required = graph.closure(set(track_concept_ids_))
    remaining = required - known
    return graph.topological_order(remaining)


def build_roadmap(
    db: Session,
    user_id: int,
    track: Track,
    daily_hours: int,
    known_concept_ids: set[int] | None = None,
) -> UserRoadmap:
    """Create (or replace) the user's active roadmap for ``track``."""
    graph = ConceptGraph.load(db)

    completed = set(
        db.scalars(
            select(UserProgress.concept_id).where(
                UserProgress.user_id == user_id,
                UserProgress.status == STATUS_COMPLETED,
            )
        ).all()
    )
    known = completed | (known_concept_ids or set())

    ordered = plan_concepts(graph, track_concept_ids(db, track.id), known)
    weeks = chunk_into_weeks(ordered, graph.hours, daily_hours * 7)

    # Only one roadmap is active at a time; older ones are kept for history.
    for existing in db.scalars(
        select(UserRoadmap).where(
            UserRoadmap.user_id == user_id, UserRoadmap.is_active.is_(True)
        )
    ).all():
        existing.is_active = False

    roadmap = UserRoadmap(
        user_id=user_id,
        track_id=track.id,
        daily_hours=daily_hours,
        is_active=True,
    )
    db.add(roadmap)
    db.flush()

    for week in weeks:
        for position, concept_id in enumerate(week.concept_ids):
            roadmap.items.append(
                UserRoadmapItem(
                    concept_id=concept_id,
                    week_no=week.week_no,
                    sort_order=position,
                    status=STATUS_PENDING,
                )
            )

    db.flush()
    sync_item_statuses(db, roadmap, user_id)
    return roadmap


def sync_item_statuses(db: Session, roadmap: UserRoadmap, user_id: int) -> None:
    """Mirror `user_progress` onto the roadmap's items.

    Progress is the source of truth: a concept completed from its own page, or
    from a different roadmap, shows as done here too.
    """
    progress = {
        row.concept_id: row.status
        for row in db.scalars(
            select(UserProgress).where(UserProgress.user_id == user_id)
        ).all()
    }
    for item in roadmap.items:
        status = progress.get(item.concept_id)
        if status is not None:
            item.status = status
    db.flush()


def get_active_roadmap(db: Session, user_id: int) -> UserRoadmap | None:
    return db.scalar(
        select(UserRoadmap)
        .where(UserRoadmap.user_id == user_id, UserRoadmap.is_active.is_(True))
        .order_by(UserRoadmap.created_at.desc())
    )


def append_concepts(
    db: Session, roadmap: UserRoadmap, concept_ids: set[int]
) -> list[UserRoadmapItem]:
    """Add concepts (and their missing prerequisites) to the end of a roadmap.

    This backs the dashboard's "Add to Roadmap" action on a missing skill.
    """
    graph = ConceptGraph.load(db)
    already = {item.concept_id for item in roadmap.items}
    wanted = graph.closure(concept_ids) - already
    if not wanted:
        return []

    ordered = graph.topological_order(wanted)
    weeks = chunk_into_weeks(ordered, graph.hours, roadmap.daily_hours * 7)
    offset = max((item.week_no for item in roadmap.items), default=0)

    added: list[UserRoadmapItem] = []
    for week in weeks:
        for position, concept_id in enumerate(week.concept_ids):
            item = UserRoadmapItem(
                concept_id=concept_id,
                week_no=offset + week.week_no,
                sort_order=position,
                status=STATUS_PENDING,
            )
            roadmap.items.append(item)
            added.append(item)

    db.flush()
    return added


def resolve_track(db: Session, *, slug: str | None, goal: str | None) -> Track | None:
    """Find a track by slug, or by a human-entered goal string.

    The onboarding UI posts a slug; older links may pass a title like
    "Become a Backend Developer".
    """
    if slug:
        track = db.scalar(select(Track).where(Track.slug == slug))
        if track:
            return track
    if goal:
        needle = goal.strip()
        return db.scalar(
            select(Track).where(
                (Track.title.ilike(needle)) | (Track.target_role.ilike(needle))
            )
        )
    return None


def concept_ids_by_slug(db: Session, slugs: list[str]) -> set[int]:
    if not slugs:
        return set()
    return set(
        db.scalars(select(Concept.id).where(Concept.slug.in_(slugs))).all()
    )
