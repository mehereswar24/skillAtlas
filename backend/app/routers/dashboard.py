"""The dashboard: everything derived from the learner's own activity.

Every number here is computed. A brand-new account sees zeros, not the
fabricated "Level 17 / 82% readiness" the prototype hardcoded.
"""

from datetime import date, timedelta

from fastapi import APIRouter, Query
from sqlalchemy import func, select

from app.deps import CurrentUser, DbSession, get_profile
from app.models.content import Concept, TrackConcept
from app.models.progress import (
    STATUS_COMPLETED,
    DailyActivity,
    UserBadge,
    UserProgress,
    UserRoadmapItem,
)
from app.routers.auth import serialize_user
from app.routers.content import concept_summary, track_summary
from app.schemas.dashboard import (
    DashboardOut,
    DashboardStats,
    MissingSkillOut,
    RoleReadinessOut,
)
from app.schemas.progress import ActivityPoint, BadgeOut
from app.services.gamification import level_progress
from app.services.graph import ConceptGraph
from app.services.readiness import missing_skills, role_readiness
from app.services.roadmap import get_active_roadmap

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("", response_model=DashboardOut)
def get_dashboard(
    user: CurrentUser,
    db: DbSession,
    days: int = Query(30, ge=7, le=365),
):
    profile = get_profile(db, user)
    db.commit()

    completed_rows = db.scalars(
        select(UserProgress).where(
            UserProgress.user_id == user.id,
            UserProgress.status == STATUS_COMPLETED,
        )
    ).all()
    completed_ids = {row.concept_id for row in completed_rows}

    # --- stats ---------------------------------------------------------
    minutes_total = (
        db.scalar(
            select(func.coalesce(func.sum(DailyActivity.minutes), 0)).where(
                DailyActivity.user_id == user.id
            )
        )
        or 0
    )

    track = profile.current_track
    track_total = 0
    if track is not None:
        track_total = (
            db.scalar(
                select(func.count(TrackConcept.concept_id)).where(
                    TrackConcept.track_id == track.id
                )
            )
            or 0
        )

    level, into_level, for_next = level_progress(profile.xp)

    start = date.today() - timedelta(days=days - 1)
    activity_rows = {
        row.day: row
        for row in db.scalars(
            select(DailyActivity).where(
                DailyActivity.user_id == user.id, DailyActivity.day >= start
            )
        ).all()
    }
    velocity = [
        ActivityPoint(
            day=day,
            minutes=activity_rows[day].minutes if day in activity_rows else 0,
            concepts=activity_rows[day].concepts_completed if day in activity_rows else 0,
            xp=activity_rows[day].xp_earned if day in activity_rows else 0,
        )
        for day in (start + timedelta(days=i) for i in range(days))
    ]

    stats = DashboardStats(
        concepts_completed=len(completed_ids),
        concepts_total_in_track=track_total,
        hours_invested=round(minutes_total / 60),
        xp=profile.xp,
        level=level,
        xp_into_level=into_level,
        xp_for_next_level=for_next,
        streak_days=serialize_user(user, profile).profile.streak_days,
        longest_streak=profile.longest_streak,
        active_days_30=sum(1 for point in velocity if point.minutes > 0),
    )

    # --- readiness -----------------------------------------------------
    readiness = role_readiness(db, user.id)
    roadmap = get_active_roadmap(db, user.id)
    roadmap_concept_ids = (
        set(
            db.scalars(
                select(UserRoadmapItem.concept_id).where(
                    UserRoadmapItem.roadmap_id == roadmap.id
                )
            ).all()
        )
        if roadmap
        else set()
    )

    gaps = [
        MissingSkillOut(
            concept=concept_summary(concept),
            role_slug=role.slug,
            percent_contribution=contribution,
            in_roadmap=concept.id in roadmap_concept_ids,
        )
        # Role slugs mirror track slugs in the seed data, so the learner's
        # chosen goal picks the role their gaps are measured against.
        for concept, role, contribution in missing_skills(
            readiness, track.slug if track else None
        )
    ]

    # --- what to do next ------------------------------------------------
    graph = ConceptGraph.load(db)
    next_ids: list[int] = []
    if roadmap:
        for item in roadmap.items:
            if item.status == STATUS_COMPLETED or item.concept_id in completed_ids:
                continue
            if graph.is_unlocked(item.concept_id, completed_ids):
                next_ids.append(item.concept_id)
            if len(next_ids) == 3:
                break

    next_concepts = (
        db.scalars(select(Concept).where(Concept.id.in_(next_ids))).unique().all()
        if next_ids
        else []
    )
    by_id = {c.id: c for c in next_concepts}

    badges = db.scalars(
        select(UserBadge)
        .where(UserBadge.user_id == user.id)
        .order_by(UserBadge.awarded_at.desc())
    ).all()

    return DashboardOut(
        user=serialize_user(user, profile),
        stats=stats,
        current_track=(
            track_summary(
                track,
                track_total,
                sum(tc.concept.est_hours for tc in track.track_concepts),
            )
            if track
            else None
        ),
        roles=[
            RoleReadinessOut(
                slug=r.role.slug,
                title=r.role.title,
                description=r.role.description,
                percent=r.percent,
                earned_weight=r.earned_weight,
                total_weight=r.total_weight,
            )
            for r in readiness
        ],
        missing_skills=gaps,
        velocity=velocity,
        badges=[BadgeOut.model_validate(b) for b in badges],
        next_up=[concept_summary(by_id[i]) for i in next_ids if i in by_id],
    )
