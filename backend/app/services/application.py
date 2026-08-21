"""Application tracking: stage moves, and the prep material behind a linked role.

The readiness maths is *not* here. `app/services/readiness.py` already computes
"how ready are you for this role, and what is missing", weighted by the same
`roles.yaml` weights the dashboard uses — this module calls it. A second,
slightly different readiness number attached to job applications would be a bug
the moment the two disagreed.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.application import (
    STAGE_APPLIED,
    ApplicationEvent,
    JobApplication,
)
from app.models.company import CompanyFocus, CompanyRole
from app.models.content import Concept
from app.services.readiness import completed_concept_ids, role_readiness
from app.services.roadmap import get_active_roadmap

# How many gaps to surface per application. The full list for a role can run to
# thirty concepts, which is a wall rather than a next action.
MAX_GAPS = 8


def record_move(
    application: JobApplication,
    to_stage: str,
    *,
    note: str | None = None,
    occurred_at: datetime | None = None,
) -> ApplicationEvent:
    """Move the application and append the matching timeline row.

    Both halves happen here so that no caller can update `stage` without the
    history catching it. The caller still owns the transaction.
    """
    event = ApplicationEvent(
        from_stage=application.stage if application.events else None,
        to_stage=to_stage,
        note=(note or "").strip() or None,
    )
    if occurred_at is not None:
        # SQLite hands datetimes back without a timezone, so an aware value is
        # normalised to UTC on the way in. Otherwise a backdated move and a
        # server-stamped one cannot be compared to each other.
        if occurred_at.tzinfo is not None:
            occurred_at = occurred_at.astimezone(timezone.utc).replace(tzinfo=None)
        event.occurred_at = occurred_at
    application.events.append(event)
    application.stage = to_stage

    # Reaching "applied" without an applied-on date is almost always the learner
    # forgetting to fill it in, not a deliberate blank.
    if to_stage == STAGE_APPLIED and application.applied_on is None:
        application.applied_on = (
            occurred_at.date() if occurred_at is not None else date.today()
        )
    return event


def last_moved_at(application: JobApplication) -> datetime | None:
    """When this application last changed stage."""
    stamps = [event.occurred_at for event in application.events if event.occurred_at]
    if not stamps:
        return application.created_at
    return max(stamps)


# --------------------------------------------------------------------------
# prep material for a linked company role
# --------------------------------------------------------------------------


@dataclass
class FocusView:
    label: str
    notes: str | None
    weight: float
    concept_slug: str | None
    concept_name: str | None
    is_completed: bool


@dataclass
class GapView:
    slug: str
    name: str
    weight: float
    adds_percent: float
    is_in_roadmap: bool


@dataclass
class PrepView:
    """Everything we can say about preparing for one linked application."""

    hiring_process_md: str | None
    fetched_on: date | None
    focus_md: str | None
    focus_areas: list[FocusView] = field(default_factory=list)
    focus_readiness_percent: int = 0
    role_readiness_percent: int | None = None
    role_slug: str | None = None
    missing: list[GapView] = field(default_factory=list)
    question_count: int = 0


def _focus_readiness(focus_areas: list[CompanyFocus], completed: set[int]) -> int:
    """Weighted coverage of the focus areas that map to a concept.

    Focus areas with no concept behind them are excluded from both sides — the
    same rule `routers/companies.py` uses, so the two numbers agree.
    """
    mapped = [f for f in focus_areas if f.concept_id is not None]
    total = sum(f.weight for f in mapped)
    if total <= 0:
        return 0
    covered = sum(f.weight for f in mapped if f.concept_id in completed)
    return round(covered / total * 100)


def build_prep(
    db: Session, application: JobApplication, user_id: int
) -> PrepView | None:
    """The company's documented loop, the role's focus areas, and the gaps.

    Returns ``None`` for a free-text application — there is nothing researched
    to show, and inventing a hiring process from a pasted JD would be exactly
    the unsourced filler the company section exists to avoid.
    """
    company = application.company
    if company is None:
        return None

    completed = completed_concept_ids(db, user_id)
    role: CompanyRole | None = application.company_role

    prep = PrepView(
        hiring_process_md=company.hiring_process_md,
        fetched_on=company.fetched_on,
        focus_md=role.focus_md if role else None,
    )
    if role is None:
        return prep

    prep.question_count = len(role.questions)
    prep.focus_areas = [
        FocusView(
            label=focus.label,
            notes=focus.notes,
            weight=focus.weight,
            concept_slug=focus.concept.slug if focus.concept else None,
            concept_name=focus.concept.name if focus.concept else None,
            is_completed=focus.concept_id in completed,
        )
        for focus in role.focus_areas
    ]
    prep.focus_readiness_percent = _focus_readiness(role.focus_areas, completed)

    # The seeded role usually maps onto one of the generic roles the dashboard
    # measures ("Google SWE L3/L4" → "backend-developer"). When it does, the
    # readiness service is the authority on what is still missing.
    if role.role_id is not None:
        target = next(
            (r for r in role_readiness(db, user_id) if r.role.id == role.role_id), None
        )
        if target is not None:
            in_roadmap = _roadmap_concept_ids(db, user_id)
            prep.role_readiness_percent = target.percent
            prep.role_slug = target.role.slug
            prep.missing = [
                GapView(
                    slug=concept.slug,
                    name=concept.name,
                    weight=weight,
                    adds_percent=round(weight / target.total_weight * 100, 1),
                    is_in_roadmap=concept.id in in_roadmap,
                )
                for concept, weight in target.missing[:MAX_GAPS]
            ]

    # A focus area the learner has not covered is a gap too, and for roles the
    # seed did not map onto a generic role it is the only one available.
    if not prep.missing:
        prep.missing = _gaps_from_focus_areas(db, role, completed, user_id)

    return prep


def _roadmap_concept_ids(db: Session, user_id: int) -> set[int]:
    roadmap = get_active_roadmap(db, user_id)
    if roadmap is None:
        return set()
    return {item.concept_id for item in roadmap.items}


def _gaps_from_focus_areas(
    db: Session, role: CompanyRole, completed: set[int], user_id: int
) -> list[GapView]:
    unmet = [
        focus
        for focus in role.focus_areas
        if focus.concept_id is not None and focus.concept_id not in completed
    ]
    total = sum(f.weight for f in role.focus_areas if f.concept_id is not None)
    if not unmet or total <= 0:
        return []

    in_roadmap = _roadmap_concept_ids(db, user_id)
    concepts = {
        concept.id: concept
        for concept in db.scalars(
            select(Concept).where(Concept.id.in_([f.concept_id for f in unmet]))
        ).all()
    }
    gaps = [
        GapView(
            slug=concepts[focus.concept_id].slug,
            name=concepts[focus.concept_id].name,
            weight=focus.weight,
            adds_percent=round(focus.weight / total * 100, 1),
            is_in_roadmap=focus.concept_id in in_roadmap,
        )
        for focus in sorted(unmet, key=lambda f: -f.weight)
        if focus.concept_id in concepts
    ]
    return gaps[:MAX_GAPS]
