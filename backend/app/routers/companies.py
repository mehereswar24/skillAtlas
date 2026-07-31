"""Companies, their roles, and what those roles actually ask for.

The useful thing this does that a list of interview questions cannot: a role's
focus areas point at concepts in the same graph the roadmap is plotted through,
so "you are 40% ready for this job" is computed from work the learner has
actually completed, and the gap can be appended to their route in one call.
"""

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.deps import CurrentUser, DbSession, OptionalUser
from app.models.company import Company, CompanyRole
from app.models.progress import STATUS_COMPLETED, UserProgress
from app.routers.roadmaps import serialize_roadmap
from app.schemas.company import (
    AddFocusToRoadmap,
    CompanyDetail,
    CompanyQuestionOut,
    CompanyResourceOut,
    CompanyRoleDetail,
    CompanyRoleSummary,
    CompanySummary,
    FocusAreaOut,
)
from app.schemas.roadmap import RoadmapOut
from app.services.roadmap import append_concepts, get_active_roadmap

router = APIRouter(prefix="/companies", tags=["companies"])


# --------------------------------------------------------------------------
# serialisation
# --------------------------------------------------------------------------


def company_summary(company: Company) -> CompanySummary:
    return CompanySummary(
        id=company.id,
        slug=company.slug,
        name=company.name,
        industry=company.industry,
        hq=company.hq,
        website=company.website,
        icon=company.icon,
        description=company.description,
        fetched_on=company.fetched_on,
        role_count=len(company.roles),
    )


def role_summary(role: CompanyRole) -> CompanyRoleSummary:
    return CompanyRoleSummary(
        id=role.id,
        slug=role.slug,
        title=role.title,
        level=role.level,
        description=role.description,
        focus_count=len(role.focus_areas),
        question_count=len(role.questions),
    )


def _completed_ids(db: DbSession, user_id: int) -> set[int]:
    return set(
        db.scalars(
            select(UserProgress.concept_id).where(
                UserProgress.user_id == user_id,
                UserProgress.status == STATUS_COMPLETED,
            )
        ).all()
    )


def _role_readiness(role: CompanyRole, completed: set[int]) -> tuple[int, float, float]:
    """Readiness over the focus areas that map to a concept.

    Focus areas with no concept behind them are excluded from both sides of the
    fraction — counting them as "not done" would make every role look worse
    than it is purely because we have not written that concept yet.
    """
    mapped = [f for f in role.focus_areas if f.concept_id is not None]
    total = sum(f.weight for f in mapped)
    if total <= 0:
        return 0, 0.0, 0.0
    covered = sum(f.weight for f in mapped if f.concept_id in completed)
    return round(covered / total * 100), covered, total


def _load_role(db: DbSession, slug: str, role_slug: str) -> CompanyRole:
    role = db.scalar(
        select(CompanyRole)
        .join(Company)
        .where(Company.slug == slug, CompanyRole.slug == role_slug)
        .options(
            selectinload(CompanyRole.focus_areas),
            selectinload(CompanyRole.questions),
        )
    )
    if role is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Role not found")
    return role


# --------------------------------------------------------------------------
# reads
# --------------------------------------------------------------------------


@router.get("", response_model=list[CompanySummary])
def list_companies(
    db: DbSession,
    industry: str | None = Query(None),
    search: str | None = Query(None, description="Case-insensitive name search"),
):
    stmt = select(Company).order_by(Company.sort_order, Company.name)
    if industry:
        stmt = stmt.where(Company.industry == industry)
    if search:
        stmt = stmt.where(Company.name.ilike(f"%{search}%"))
    return [company_summary(c) for c in db.scalars(stmt).unique().all()]


@router.get("/industries", response_model=list[str])
def list_industries(db: DbSession):
    return list(
        db.scalars(select(Company.industry).distinct().order_by(Company.industry)).all()
    )


@router.get("/{slug}", response_model=CompanyDetail)
def get_company(slug: str, db: DbSession, user: OptionalUser):
    company = db.scalar(select(Company).where(Company.slug == slug))
    if company is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Company not found")

    completed = _completed_ids(db, user.id) if user is not None else None
    roles = []
    for role in company.roles:
        summary = role_summary(role)
        if completed is not None:
            summary.readiness_percent = _role_readiness(role, completed)[0]
        roles.append(summary)

    return CompanyDetail(
        **company_summary(company).model_dump(),
        hiring_process_md=company.hiring_process_md,
        roles=roles,
        resources=[CompanyResourceOut.model_validate(r) for r in company.resources],
    )


@router.get("/{slug}/roles/{role_slug}", response_model=CompanyRoleDetail)
def get_company_role(slug: str, role_slug: str, db: DbSession, user: OptionalUser):
    role = _load_role(db, slug, role_slug)
    completed = _completed_ids(db, user.id) if user is not None else set()

    in_roadmap: set[int] = set()
    if user is not None:
        roadmap = get_active_roadmap(db, user.id)
        if roadmap is not None:
            in_roadmap = {item.concept_id for item in roadmap.items}

    percent, covered, total = _role_readiness(role, completed)

    focus_areas = [
        FocusAreaOut(
            id=focus.id,
            label=focus.label,
            notes=focus.notes,
            weight=focus.weight,
            concept_slug=focus.concept.slug if focus.concept else None,
            concept_name=focus.concept.name if focus.concept else None,
            is_completed=focus.concept_id in completed,
            in_roadmap=focus.concept_id in in_roadmap,
        )
        for focus in role.focus_areas
    ]

    return CompanyRoleDetail(
        **role_summary(role).model_dump(exclude={"readiness_percent"}),
        company=company_summary(role.company),
        focus_md=role.focus_md,
        source_url=role.source_url,
        focus_areas=focus_areas,
        questions=[CompanyQuestionOut.model_validate(q) for q in role.questions],
        readiness_percent=percent,
        covered_weight=covered,
        total_weight=total,
    )


# --------------------------------------------------------------------------
# acting on a role
# --------------------------------------------------------------------------


@router.post("/{slug}/roles/{role_slug}/add-to-roadmap", response_model=RoadmapOut)
def add_focus_to_roadmap(
    slug: str,
    role_slug: str,
    payload: AddFocusToRoadmap,
    user: CurrentUser,
    db: DbSession,
):
    """Append this role's unmet focus areas (and their prerequisites) to the route."""
    role = _load_role(db, slug, role_slug)
    roadmap = get_active_roadmap(db, user.id)
    if roadmap is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            "Plot a route before adding a role's focus areas to it",
        )

    completed = _completed_ids(db, user.id)
    wanted = {
        focus.concept_id
        for focus in role.focus_areas
        if focus.concept_id is not None and focus.concept_id not in completed
    }
    if payload.concept_slugs:
        # Narrow to an explicit selection, but never outside this role.
        chosen = {
            focus.concept_id
            for focus in role.focus_areas
            if focus.concept and focus.concept.slug in set(payload.concept_slugs)
        }
        wanted &= chosen

    if not wanted:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Nothing to add — you have already covered this role's focus areas.",
        )

    append_concepts(db, roadmap, wanted)
    db.commit()
    db.refresh(roadmap)
    return serialize_roadmap(db, roadmap, user.id)
