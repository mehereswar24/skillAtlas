"""Job application tracker — a board the learner drives themselves.

**This router does not fetch anything.** There is no endpoint that takes a
listing URL and goes and reads it: no LinkedIn, Indeed, Naukri or Glassdoor
scraping, and no "import from URL". The learner pastes the job description they
already have in front of them, and `source_url` is stored purely so they can
click back to it. That is a hard rule, not a v1 shortcut — it is the same class
of problem as the roadmap.sh licence, and legally worse.

What this *can* do that a spreadsheet cannot: when an application is linked to
one of the seeded companies, it shows that company's documented hiring loop, the
role's focus areas, and what the learner is still missing for it, computed by
`services/readiness.py` from concepts they have actually completed.

Every application is private to its author. A stranger's id returns 404, never
403 — matching `routers/community.py`, so ids cannot be probed for existence.
"""

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.deps import CurrentUser, DbSession
from app.models.application import (
    APPLICATION_STAGES,
    STAGE_LABELS,
    TERMINAL_STAGES,
    ApplicationEvent,
    JobApplication,
)
from app.models.company import Company, CompanyRole
from app.schemas.application import (
    ApplicationBoard,
    ApplicationCreate,
    ApplicationDetail,
    ApplicationEventOut,
    ApplicationOut,
    ApplicationPrep,
    ApplicationUpdate,
    BoardColumn,
    CompanyRef,
    CompanyRoleRef,
    FocusAreaOut,
    MissingConcept,
    StageInfo,
    StageMove,
)
from app.services.application import build_prep, last_moved_at, record_move

router = APIRouter(prefix="/applications", tags=["applications"])


# --------------------------------------------------------------------------
# serialisation
# --------------------------------------------------------------------------


def _company_ref(company: Company | None) -> CompanyRef | None:
    if company is None:
        return None
    return CompanyRef(slug=company.slug, name=company.name, icon=company.icon)


def _role_ref(role: CompanyRole | None) -> CompanyRoleRef | None:
    if role is None:
        return None
    return CompanyRoleRef(slug=role.slug, title=role.title, level=role.level)


def serialize(application: JobApplication) -> ApplicationOut:
    return ApplicationOut(
        id=application.id,
        company_name=application.company_name,
        role_title=application.role_title,
        stage=application.stage,
        location=application.location,
        salary_note=application.salary_note,
        source_url=application.source_url,
        applied_on=application.applied_on,
        has_job_description=bool(application.job_description),
        has_notes=bool(application.notes),
        company=_company_ref(application.company),
        company_role=_role_ref(application.company_role),
        created_at=application.created_at,
        updated_at=application.updated_at,
        last_moved_at=last_moved_at(application),
    )


def _serialize_prep(db: DbSession, application: JobApplication, user_id: int):
    prep = build_prep(db, application, user_id)
    if prep is None:
        return None
    return ApplicationPrep(
        company=_company_ref(application.company),
        company_role=_role_ref(application.company_role),
        hiring_process_md=prep.hiring_process_md,
        fetched_on=prep.fetched_on,
        focus_md=prep.focus_md,
        focus_areas=[
            FocusAreaOut(
                label=focus.label,
                notes=focus.notes,
                weight=focus.weight,
                concept_slug=focus.concept_slug,
                concept_name=focus.concept_name,
                is_completed=focus.is_completed,
            )
            for focus in prep.focus_areas
        ],
        focus_readiness_percent=prep.focus_readiness_percent,
        role_readiness_percent=prep.role_readiness_percent,
        role_slug=prep.role_slug,
        missing=[
            MissingConcept(
                slug=gap.slug,
                name=gap.name,
                weight=gap.weight,
                adds_percent=gap.adds_percent,
                is_in_roadmap=gap.is_in_roadmap,
            )
            for gap in prep.missing
        ],
        question_count=prep.question_count,
    )


def _detail(db: DbSession, application: JobApplication, user_id: int):
    return ApplicationDetail(
        **serialize(application).model_dump(),
        job_description=application.job_description,
        notes=application.notes,
        events=[
            ApplicationEventOut.model_validate(event)
            for event in sorted(
                application.events, key=lambda e: (e.occurred_at, e.id)
            )
        ],
        prep=_serialize_prep(db, application, user_id),
    )


# --------------------------------------------------------------------------
# lookup
# --------------------------------------------------------------------------


def _load(db: DbSession, application_id: int, user_id: int) -> JobApplication:
    """The caller's application, or 404.

    Deliberately the same 404 for "does not exist" and "belongs to someone
    else": an application is private, and a 403 would confirm that somebody
    else is tracking application #12.
    """
    application = db.scalar(
        select(JobApplication)
        .where(JobApplication.id == application_id)
        .options(selectinload(JobApplication.events))
    )
    if application is None or application.user_id != user_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Application not found")
    return application


def _resolve_link(
    db: DbSession, company_slug: str | None, role_slug: str | None
) -> tuple[Company | None, CompanyRole | None]:
    if not company_slug:
        return None, None

    company = db.scalar(select(Company).where(Company.slug == company_slug))
    if company is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Unknown company")
    if not role_slug:
        return company, None

    role = db.scalar(
        select(CompanyRole)
        .where(CompanyRole.company_id == company.id, CompanyRole.slug == role_slug)
        .options(
            selectinload(CompanyRole.focus_areas), selectinload(CompanyRole.questions)
        )
    )
    if role is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, f"{company.name} has no role '{role_slug}'"
        )
    return company, role


# --------------------------------------------------------------------------
# reads
# --------------------------------------------------------------------------


@router.get("/stages", response_model=list[StageInfo])
def list_stages():
    """The pipeline, in order. Kept server-side so the board and the API cannot
    disagree about what the stages are."""
    return [
        StageInfo(
            value=stage,
            label=STAGE_LABELS[stage],
            is_terminal=stage in TERMINAL_STAGES,
        )
        for stage in APPLICATION_STAGES
    ]


@router.get("", response_model=list[ApplicationOut])
def list_applications(
    user: CurrentUser,
    db: DbSession,
    stage: str | None = Query(None, description="Filter to one stage"),
):
    stmt = (
        select(JobApplication)
        .where(JobApplication.user_id == user.id)
        .options(selectinload(JobApplication.events))
        .order_by(JobApplication.created_at.desc())
    )
    if stage:
        if stage not in APPLICATION_STAGES:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Unknown stage")
        stmt = stmt.where(JobApplication.stage == stage)
    return [serialize(a) for a in db.scalars(stmt).unique().all()]


@router.get("/board", response_model=ApplicationBoard)
def get_board(user: CurrentUser, db: DbSession):
    """Every application, grouped into the columns the board renders."""
    applications = (
        db.scalars(
            select(JobApplication)
            .where(JobApplication.user_id == user.id)
            .options(selectinload(JobApplication.events))
            .order_by(JobApplication.updated_at.desc(), JobApplication.id.desc())
        )
        .unique()
        .all()
    )

    grouped: dict[str, list[ApplicationOut]] = {s: [] for s in APPLICATION_STAGES}
    for application in applications:
        grouped.setdefault(application.stage, []).append(serialize(application))

    return ApplicationBoard(
        columns=[
            BoardColumn(
                stage=stage,
                label=STAGE_LABELS[stage],
                is_terminal=stage in TERMINAL_STAGES,
                applications=grouped.get(stage, []),
            )
            for stage in APPLICATION_STAGES
        ],
        total=len(applications),
        active=sum(1 for a in applications if a.stage not in TERMINAL_STAGES),
    )


@router.get("/{application_id}", response_model=ApplicationDetail)
def get_application(application_id: int, user: CurrentUser, db: DbSession):
    return _detail(db, _load(db, application_id, user.id), user.id)


# --------------------------------------------------------------------------
# writes
# --------------------------------------------------------------------------


@router.post("", response_model=ApplicationDetail, status_code=status.HTTP_201_CREATED)
def create_application(payload: ApplicationCreate, user: CurrentUser, db: DbSession):
    company, role = _resolve_link(db, payload.company_slug, payload.company_role_slug)

    application = JobApplication(
        user_id=user.id,
        company_id=company.id if company else None,
        company_role_id=role.id if role else None,
        # The labels are stored even when linked, so the card still reads
        # correctly if the seed later drops that company row.
        company_name=(payload.company_name or "").strip()
        or (company.name if company else ""),
        role_title=(payload.role_title or "").strip() or (role.title if role else ""),
        location=payload.location,
        salary_note=payload.salary_note,
        source_url=payload.source_url,
        job_description=payload.job_description,
        notes=payload.notes,
        applied_on=payload.applied_on,
    )
    # Set explicitly rather than leaning on the column default: `record_move`
    # needs the stage before the INSERT, and so does the first timeline row.
    record_move(application, payload.stage)

    db.add(application)
    db.commit()
    db.refresh(application)
    return _detail(db, application, user.id)


@router.patch("/{application_id}", response_model=ApplicationDetail)
def update_application(
    application_id: int,
    payload: ApplicationUpdate,
    user: CurrentUser,
    db: DbSession,
):
    """Edit the details. Stage moves go through `POST /{id}/stage`."""
    application = _load(db, application_id, user.id)

    fields = payload.model_dump(exclude_unset=True, exclude={"unlink_company"})
    for name, value in fields.items():
        if name in {"company_name", "role_title"}:
            value = (value or "").strip()
            if not value:
                # Blanking the only label an application has would leave an
                # unidentifiable card on the board.
                raise HTTPException(
                    status.HTTP_422_UNPROCESSABLE_ENTITY,
                    f"{name.replace('_', ' ')} cannot be empty",
                )
        setattr(application, name, value)

    if payload.unlink_company:
        application.company_id = None
        application.company_role_id = None

    db.commit()
    db.refresh(application)
    return _detail(db, application, user.id)


@router.post("/{application_id}/stage", response_model=ApplicationDetail)
def move_stage(
    application_id: int, payload: StageMove, user: CurrentUser, db: DbSession
):
    """Move to another stage and record the move.

    Any stage can follow any other: real pipelines skip screens, and a learner
    correcting a mistyped stage should not have to delete the application. What
    is not allowed is a move to the stage it is already in, which would put a
    meaningless row in the timeline.
    """
    application = _load(db, application_id, user.id)
    if application.stage == payload.stage:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"Already in '{STAGE_LABELS[payload.stage]}'",
        )

    record_move(
        application,
        payload.stage,
        note=payload.note,
        occurred_at=payload.occurred_at,
    )
    db.commit()
    db.refresh(application)
    return _detail(db, application, user.id)


@router.delete("/{application_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_application(application_id: int, user: CurrentUser, db: DbSession):
    application = _load(db, application_id, user.id)
    db.delete(application)
    db.commit()


@router.delete(
    "/{application_id}/events/{event_id}", status_code=status.HTTP_204_NO_CONTENT
)
def delete_event(
    application_id: int, event_id: int, user: CurrentUser, db: DbSession
):
    """Remove a mis-logged move from the timeline.

    The current stage is left alone: this deletes a history row, it does not
    move the application back. The last remaining event cannot be deleted —
    an application with no timeline at all has lost the fact that it exists.
    """
    application = _load(db, application_id, user.id)
    if len(application.events) <= 1:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "An application keeps at least one event"
        )

    event = db.get(ApplicationEvent, event_id)
    if event is None or event.application_id != application.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Event not found")
    db.delete(event)
    db.commit()
