"""Role readiness and missing-skill analysis.

readiness % = Σ(weight of completed role skills) / Σ(weight of all role skills)

The weights come from `app/seed/roles.yaml`, so the same concept can be
critical for one role and incidental for another.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.content import Concept, Role, RoleSkill
from app.models.progress import STATUS_COMPLETED, UserProgress


@dataclass
class RoleReadiness:
    role: Role
    percent: int
    earned_weight: float
    total_weight: float
    missing: list[tuple[Concept, float]]  # (concept, weight)


def completed_concept_ids(db: Session, user_id: int) -> set[int]:
    return set(
        db.scalars(
            select(UserProgress.concept_id).where(
                UserProgress.user_id == user_id,
                UserProgress.status == STATUS_COMPLETED,
            )
        ).all()
    )


def role_readiness(db: Session, user_id: int) -> list[RoleReadiness]:
    """Readiness for every role, best first."""
    completed = completed_concept_ids(db, user_id)
    roles = (
        db.scalars(
            select(Role).options(
                selectinload(Role.skills).selectinload(RoleSkill.concept)
            )
        )
        .unique()
        .all()
    )

    results: list[RoleReadiness] = []
    for role in roles:
        total = sum(skill.weight for skill in role.skills)
        if total <= 0:
            continue
        earned = sum(
            skill.weight for skill in role.skills if skill.concept_id in completed
        )
        missing = sorted(
            (
                (skill.concept, skill.weight)
                for skill in role.skills
                if skill.concept_id not in completed
            ),
            key=lambda pair: (-pair[1], pair[0].name),
        )
        results.append(
            RoleReadiness(
                role=role,
                percent=round(earned / total * 100),
                earned_weight=earned,
                total_weight=total,
                missing=missing,
            )
        )

    results.sort(key=lambda r: (-r.percent, r.role.title))
    return results


def missing_skills(
    readiness: list[RoleReadiness],
    preferred_role_slug: str | None = None,
    limit: int = 5,
) -> list[tuple[Concept, Role, float]]:
    """The highest-impact gaps for the role the learner is aiming at.

    Each entry's percentage is what completing that concept would add to that
    role's readiness — a directly actionable number rather than a vague
    "you should learn this".

    The target role is the one matching the learner's chosen track when there
    is one. Falling back to "whichever role scores highest" is only meaningful
    once some progress exists: with everything at 0% the ranking is an
    alphabetical accident, so we return nothing and let the UI ask them to
    pick a goal.
    """
    if not readiness:
        return []

    target: RoleReadiness | None = None
    if preferred_role_slug:
        target = next(
            (r for r in readiness if r.role.slug == preferred_role_slug and r.missing),
            None,
        )
    if target is None:
        target = next((r for r in readiness if r.missing and r.percent > 0), None)
    if target is None:
        return []

    return [
        (concept, target.role, round(weight / target.total_weight * 100, 1))
        for concept, weight in target.missing[:limit]
    ]
