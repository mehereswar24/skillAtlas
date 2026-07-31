"""XP, levels, streaks and badges.

All of it derives from real activity: nothing here can be displayed unless the
learner actually completed something.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import settings
from app.models.content import Concept, TrackConcept
from app.models.progress import (
    STATUS_COMPLETED,
    DailyActivity,
    UserBadge,
    UserProgress,
)
from app.models.user import UserProfile

# Levelling curve: advancing from level L to L+1 costs 100*L XP, so the
# cumulative requirement for level L is 50*L*(L-1). Early levels arrive fast
# and later ones take real work.
_XP_PER_LEVEL_STEP = 100


def xp_for_level(level: int) -> int:
    """Cumulative XP required to *reach* ``level``."""
    return _XP_PER_LEVEL_STEP * level * (level - 1) // 2


def level_for_xp(xp: int) -> int:
    if xp <= 0:
        return 1
    # Inverse of xp_for_level: largest L with 50*L*(L-1) <= xp, which is
    # floor((1 + sqrt(1 + 8*xp/100)) / 2).
    return (1 + math.isqrt(1 + 8 * xp // _XP_PER_LEVEL_STEP)) // 2


def level_progress(xp: int) -> tuple[int, int, int]:
    """Return (level, xp earned into this level, xp needed for the next)."""
    level = level_for_xp(xp)
    floor_xp = xp_for_level(level)
    ceiling_xp = xp_for_level(level + 1)
    return level, xp - floor_xp, ceiling_xp - floor_xp


def xp_for_concept(est_hours: int, quiz_score: float | None) -> int:
    """XP for finishing a concept.

    Scaled by effort, then by how well the quiz went — a pass with 60% earns
    less than a clean sweep, so the number means something.
    """
    base = max(est_hours, 1) * settings.xp_per_hour
    if quiz_score is None:
        multiplier = 1.0
    else:
        multiplier = 0.5 + 0.5 * max(0.0, min(1.0, quiz_score))
    return max(1, round(base * multiplier))


# --------------------------------------------------------------------------
# streaks
# --------------------------------------------------------------------------


def update_streak(profile: UserProfile, today: date) -> None:
    """Advance the streak for activity on ``today``.

    Same day → unchanged. Yesterday → +1. Any earlier → the streak is broken
    and restarts at 1.
    """
    last = profile.last_active_on
    if last == today:
        return
    if last is not None and last == today - timedelta(days=1):
        profile.streak_days += 1
    else:
        profile.streak_days = 1
    profile.last_active_on = today
    profile.longest_streak = max(profile.longest_streak, profile.streak_days)


def current_streak(profile: UserProfile, today: date) -> int:
    """The streak as of ``today`` — zero once a day has been missed.

    Stored ``streak_days`` is only correct on the day it was written; this is
    what the UI should display.
    """
    if profile.last_active_on is None:
        return 0
    if profile.last_active_on >= today - timedelta(days=1):
        return profile.streak_days
    return 0


# --------------------------------------------------------------------------
# activity log
# --------------------------------------------------------------------------


def record_activity(
    db: Session,
    user_id: int,
    day: date,
    *,
    minutes: int = 0,
    concepts_completed: int = 0,
    xp_earned: int = 0,
) -> DailyActivity:
    activity = db.scalar(
        select(DailyActivity).where(
            DailyActivity.user_id == user_id, DailyActivity.day == day
        )
    )
    if activity is None:
        # Counters are set explicitly: column defaults are applied by the
        # INSERT, so a freshly constructed row still holds None until flush.
        activity = DailyActivity(
            user_id=user_id, day=day, minutes=0, concepts_completed=0, xp_earned=0
        )
        db.add(activity)
    activity.minutes += minutes
    activity.concepts_completed += concepts_completed
    activity.xp_earned += xp_earned
    return activity


# --------------------------------------------------------------------------
# badges
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class BadgeDef:
    slug: str
    name: str
    description: str
    icon: str


BADGES: dict[str, BadgeDef] = {
    b.slug: b
    for b in [
        BadgeDef("first-steps", "First Steps", "Completed your first concept.", "Footprints"),
        BadgeDef("getting-serious", "Getting Serious", "Completed 5 concepts.", "Flame"),
        BadgeDef("double-digits", "Double Digits", "Completed 10 concepts.", "Award"),
        BadgeDef("quarter-century", "Quarter Century", "Completed 25 concepts.", "Medal"),
        BadgeDef("week-warrior", "Week Warrior", "Kept a 7-day learning streak.", "CalendarCheck"),
        BadgeDef("month-of-momentum", "Month of Momentum", "Kept a 30-day learning streak.", "CalendarHeart"),
        BadgeDef("perfectionist", "Perfectionist", "Scored 100% on a concept quiz.", "Target"),
        BadgeDef("track-complete", "Track Complete", "Finished every concept in a track.", "Trophy"),
        BadgeDef("level-five", "Level Five", "Reached level 5.", "Star"),
        BadgeDef("level-ten", "Level Ten", "Reached level 10.", "Sparkles"),
    ]
}


def award_badge(db: Session, user_id: int, slug: str) -> UserBadge | None:
    """Grant a badge once. Returns the new badge, or None if already held."""
    definition = BADGES.get(slug)
    if definition is None:
        return None
    existing = db.scalar(
        select(UserBadge).where(
            UserBadge.user_id == user_id, UserBadge.badge_slug == slug
        )
    )
    if existing is not None:
        return None
    badge = UserBadge(
        user_id=user_id,
        badge_slug=definition.slug,
        badge_name=definition.name,
        description=definition.description,
        icon=definition.icon,
    )
    db.add(badge)
    return badge


def evaluate_badges(
    db: Session,
    user_id: int,
    profile: UserProfile,
    *,
    last_quiz_score: float | None = None,
    today: date | None = None,
) -> list[UserBadge]:
    """Check every badge rule and award whatever is newly earned."""
    today = today or date.today()
    earned: list[UserBadge] = []

    completed_count = (
        db.scalar(
            select(func.count(UserProgress.id)).where(
                UserProgress.user_id == user_id,
                UserProgress.status == STATUS_COMPLETED,
            )
        )
        or 0
    )

    for threshold, slug in (
        (1, "first-steps"),
        (5, "getting-serious"),
        (10, "double-digits"),
        (25, "quarter-century"),
    ):
        if completed_count >= threshold:
            earned.append(award_badge(db, user_id, slug))

    if profile.longest_streak >= 7:
        earned.append(award_badge(db, user_id, "week-warrior"))
    if profile.longest_streak >= 30:
        earned.append(award_badge(db, user_id, "month-of-momentum"))

    if last_quiz_score is not None and last_quiz_score >= 1.0:
        earned.append(award_badge(db, user_id, "perfectionist"))

    if profile.level >= 5:
        earned.append(award_badge(db, user_id, "level-five"))
    if profile.level >= 10:
        earned.append(award_badge(db, user_id, "level-ten"))

    if profile.current_track_id and _track_is_complete(
        db, user_id, profile.current_track_id
    ):
        earned.append(award_badge(db, user_id, "track-complete"))

    return [badge for badge in earned if badge is not None]


def _track_is_complete(db: Session, user_id: int, track_id: int) -> bool:
    track_concept_ids = set(
        db.scalars(
            select(TrackConcept.concept_id).where(TrackConcept.track_id == track_id)
        ).all()
    )
    if not track_concept_ids:
        return False
    completed = set(
        db.scalars(
            select(UserProgress.concept_id).where(
                UserProgress.user_id == user_id,
                UserProgress.status == STATUS_COMPLETED,
                UserProgress.concept_id.in_(track_concept_ids),
            )
        ).all()
    )
    return completed >= track_concept_ids


# --------------------------------------------------------------------------
# the entry point used when a concept is completed
# --------------------------------------------------------------------------


@dataclass
class AwardResult:
    xp_earned: int
    total_xp: int
    level: int
    level_before: int
    leveled_up: bool
    streak_days: int
    new_badges: list[UserBadge]


def apply_completion(
    db: Session,
    user_id: int,
    profile: UserProfile,
    concept: Concept,
    *,
    quiz_score: float | None,
    minutes: int,
    today: date | None = None,
) -> AwardResult:
    """Award XP, advance the level and streak, and evaluate badges."""
    today = today or date.today()
    level_before = profile.level

    xp = xp_for_concept(concept.est_hours, quiz_score)
    profile.xp += xp
    profile.level = level_for_xp(profile.xp)

    update_streak(profile, today)
    record_activity(
        db,
        user_id,
        today,
        minutes=minutes,
        concepts_completed=1,
        xp_earned=xp,
    )
    db.flush()

    new_badges = evaluate_badges(
        db, user_id, profile, last_quiz_score=quiz_score, today=today
    )

    return AwardResult(
        xp_earned=xp,
        total_xp=profile.xp,
        level=profile.level,
        level_before=level_before,
        leveled_up=profile.level > level_before,
        streak_days=profile.streak_days,
        new_badges=new_badges,
    )
