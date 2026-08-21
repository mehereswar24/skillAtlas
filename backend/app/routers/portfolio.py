"""Public learner portfolio.

The differentiator here is not the page — everyone has a profile page — it is
that the projects on it *run*. They already execute in the learner's browser
(Pyodide, sql.js, a sandboxed iframe), so a portfolio can ship the passing
submission's files and let a visitor press Run, instead of showing a
screenshot and asking to be believed. Nothing executes on this server; this
router hands over the same `files` / `tests` / `entry_path` triple the project
workspace consumes, and the visitor's own browser does the work.

Privacy is the other half, and it is the half that can go wrong permanently:
this endpoint publishes personal data to the open internet. The rules it
enforces, in order of how much they matter:

1. **Nothing is public until the learner says so.** A profile row is created
   the first time they open the settings page, and it is created unpublished.
   `GET /portfolio/{handle}` is a 404 for everyone but the owner until
   `is_published` is true — a 404 and not a 403, so an unpublished handle is
   not even confirmed to exist.
2. **Unpublishing is immediate.** The flag is read on every request and no
   response is cached, so the next fetch after unpublishing is a 404.
3. **No email, ever.** `PublicPortfolio` has no field that can hold one. The
   omission is structural, not a filter that someone has to remember.
4. **Only passed submissions.** Failed attempts, in-progress concepts and
   private notes never leave this module.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload

from app.deps import CurrentUser, DbSession, OptionalUser
from app.models.content import Concept, Track, TrackConcept
from app.models.portfolio import (
    RESERVED_HANDLES,
    PortfolioProfile,
    PortfolioProject,
    normalize_handle,
)
from app.models.progress import STATUS_COMPLETED, UserBadge, UserProgress
from app.models.project import SUBMISSION_PASSED, Project, ProjectSubmission
from app.models.user import User
from app.schemas.portfolio import (
    HandleCheck,
    OwnerProject,
    PortfolioSettings,
    PortfolioUpdate,
    PortfolioVisibility,
    ProjectVisibilityUpdate,
    PublicBadge,
    PublicConcept,
    PublicLinks,
    PublicPortfolio,
    PublicProject,
    PublicProjectFile,
    PublicReadiness,
    PublicTest,
    PublicTrackGroup,
    validate_handle,
)
from app.services.readiness import role_readiness

router = APIRouter(prefix="/portfolio", tags=["portfolio"])

# How many roles a public page claims readiness for. The full list runs to
# every role in the seed data, most of them at 0%, which is noise on a page
# meant to make a case.
READINESS_LIMIT = 3


# --------------------------------------------------------------------------
# lookups
# --------------------------------------------------------------------------


def _own_profile(db: DbSession, user_id: int) -> PortfolioProfile | None:
    return db.scalar(
        select(PortfolioProfile).where(PortfolioProfile.user_id == user_id)
    )


def _handle_taken(db: DbSession, handle: str, except_profile_id: int | None) -> bool:
    stmt = select(PortfolioProfile.id).where(
        PortfolioProfile.handle_ci == normalize_handle(handle)
    )
    if except_profile_id is not None:
        stmt = stmt.where(PortfolioProfile.id != except_profile_id)
    return db.scalar(stmt) is not None


class _ShippedProject:
    """Everything known about one project the learner passed."""

    __slots__ = (
        "project",
        "shipped_at",
        "latest_files",
        "passed_count",
        "total_count",
        "attempts",
    )

    def __init__(self, project: Project, shipped_at: datetime):
        self.project = project
        self.shipped_at = shipped_at
        self.latest_files: list[dict] = []
        self.passed_count = 0
        self.total_count = 0
        self.attempts = 0


def _shipped(db: DbSession, user_id: int) -> dict[int, _ShippedProject]:
    """project_id -> the passing work, oldest ship date, newest code.

    ``shipped_at`` is the *first* pass because that is the date the thing was
    achieved; the files come from the *latest* pass because that is the code
    they would want shown. Failed submissions are counted (as attempts, which
    is a fair thing to show) but never read for content.
    """
    submissions = (
        db.scalars(
            select(ProjectSubmission)
            .where(ProjectSubmission.user_id == user_id)
            .options(selectinload(ProjectSubmission.project))
            .order_by(ProjectSubmission.created_at, ProjectSubmission.id)
        )
        .unique()
        .all()
    )

    shipped: dict[int, _ShippedProject] = {}
    attempts: dict[int, int] = {}
    for submission in submissions:
        attempts[submission.project_id] = attempts.get(submission.project_id, 0) + 1
        if submission.status != SUBMISSION_PASSED:
            continue
        entry = shipped.get(submission.project_id)
        if entry is None:
            entry = _ShippedProject(submission.project, submission.created_at)
            shipped[submission.project_id] = entry
        try:
            entry.latest_files = json.loads(submission.files_json)
        except (TypeError, ValueError):
            entry.latest_files = []
        entry.passed_count = submission.passed_count
        entry.total_count = submission.total_count

    for project_id, entry in shipped.items():
        entry.attempts = attempts.get(project_id, 1)
    return shipped


# --------------------------------------------------------------------------
# public serialisation
# --------------------------------------------------------------------------


def _public_files(
    project: Project, submitted: list[dict]
) -> tuple[list[PublicProjectFile], str | None]:
    """The submission's files, annotated from the project's own metadata.

    The visitor's runtime needs to know which file to execute and which are
    fixtures; the submission itself only carries paths and contents.
    """
    meta = {file.path: file for file in project.files}
    files: list[PublicProjectFile] = []
    for item in submitted:
        path = item.get("path") if isinstance(item, dict) else None
        if not path:
            continue
        info = meta.get(path)
        files.append(
            PublicProjectFile(
                path=path,
                content=item.get("content", ""),
                is_readonly=bool(info.is_readonly) if info else False,
                is_entry=bool(info.is_entry) if info else False,
            )
        )

    entry = next((f.path for f in files if f.is_entry), None)
    if entry is None:
        starter_entry = next((f.path for f in project.files if f.is_entry), None)
        entry = starter_entry or (files[0].path if files else None)
    return files, entry


def _public_project(
    entry: _ShippedProject, settings_row: PortfolioProject | None, with_code: bool
) -> PublicProject:
    project = entry.project
    files: list[PublicProjectFile] = []
    tests: list[PublicTest] = []
    entry_path: str | None = None

    if with_code:
        files, entry_path = _public_files(project, entry.latest_files)
        tests = [
            PublicTest(
                id=test.id,
                name=test.name,
                kind=test.kind,
                code=test.code,
                expected=test.expected,
                is_hidden=test.is_hidden,
            )
            for test in project.tests
        ]

    return PublicProject(
        slug=project.slug,
        title=project.title,
        tagline=project.tagline,
        note=(settings_row.note if settings_row else "") or "",
        runtime=project.runtime,
        difficulty=project.difficulty,
        concept_slug=project.concept.slug,
        concept_name=project.concept.name,
        xp_reward=project.xp_reward,
        shipped_at=entry.shipped_at,
        tests_passed=entry.passed_count,
        tests_total=entry.total_count,
        attempts=entry.attempts,
        files=files,
        tests=tests,
        entry_path=entry_path,
    )


def _track_groups(db: DbSession, user_id: int) -> list[PublicTrackGroup]:
    """Completed concepts, grouped by the tracks they belong to.

    A concept can sit in more than one track, so it can appear under more than
    one heading. That is truthful — it *is* part of both — and de-duplicating
    would mean inventing a rule for which track "owns" it.
    """
    completed_ids = set(
        db.scalars(
            select(UserProgress.concept_id).where(
                UserProgress.user_id == user_id,
                UserProgress.status == STATUS_COMPLETED,
            )
        ).all()
    )
    if not completed_ids:
        return []

    rows = db.execute(
        select(Track, Concept, TrackConcept.sort_order)
        .join(TrackConcept, TrackConcept.track_id == Track.id)
        .join(Concept, Concept.id == TrackConcept.concept_id)
        .where(TrackConcept.concept_id.in_(completed_ids))
        .order_by(Track.sort_order, Track.id, TrackConcept.sort_order)
    ).all()

    totals = dict(
        db.execute(
            select(TrackConcept.track_id, func.count(TrackConcept.concept_id)).group_by(
                TrackConcept.track_id
            )
        ).all()
    )

    groups: dict[int, PublicTrackGroup] = {}
    for track, concept, _order in rows:
        group = groups.get(track.id)
        if group is None:
            group = PublicTrackGroup(
                slug=track.slug,
                title=track.title,
                completed=[],
                track_total=totals.get(track.id, 0),
            )
            groups[track.id] = group
        group.completed.append(
            PublicConcept(
                slug=concept.slug,
                name=concept.name,
                difficulty=concept.difficulty,
                est_hours=concept.est_hours,
            )
        )

    return sorted(groups.values(), key=lambda g: -len(g.completed))


def _build_public(
    db: DbSession, profile: PortfolioProfile, owner: User, is_preview: bool
) -> PublicPortfolio:
    """Assemble the public page, honouring every switch on the profile."""
    links = PublicLinks(
        github=profile.github_url,
        linkedin=profile.linkedin_url,
        website=profile.website_url,
    )

    shipped = _shipped(db, owner.id)
    overrides = {row.project_id: row for row in profile.projects}

    projects: list[PublicProject] = []
    if profile.show_projects:
        visible = [
            (entry, overrides.get(project_id))
            for project_id, entry in shipped.items()
            # Absent override means "not touched", which inside an already
            # published profile means shown.
            if overrides.get(project_id) is None
            or overrides[project_id].is_visible
        ]
        visible.sort(
            key=lambda pair: (
                pair[1].sort_order if pair[1] else 0,
                pair[0].shipped_at,
            )
        )
        projects = [
            _public_project(entry, row, profile.show_project_code)
            for entry, row in visible
        ]

    tracks = _track_groups(db, owner.id) if profile.show_concepts else []

    badges: list[PublicBadge] = []
    if profile.show_badges:
        badges = [
            PublicBadge(
                slug=badge.badge_slug,
                name=badge.badge_name,
                description=badge.description,
                icon=badge.icon,
                awarded_at=badge.awarded_at,
            )
            for badge in db.scalars(
                select(UserBadge)
                .where(UserBadge.user_id == owner.id)
                .order_by(UserBadge.awarded_at.desc())
            ).all()
        ]

    readiness: list[PublicReadiness] = []
    if profile.show_readiness:
        readiness = [
            PublicReadiness(slug=r.role.slug, title=r.role.title, percent=r.percent)
            for r in role_readiness(db, owner.id)
            if r.percent > 0
        ][:READINESS_LIMIT]

    learner_profile = owner.profile
    points = level = concepts_completed = None
    if profile.show_points:
        points = learner_profile.xp if learner_profile else 0
        level = learner_profile.level if learner_profile else 1

    concepts_completed = (
        sum(len(group.completed) for group in tracks) if profile.show_concepts else None
    )

    return PublicPortfolio(
        handle=profile.handle,
        # Deliberately *not* falling back to `User.display_name`: signup
        # derives that from the email's local part, so using it here would
        # publish a name taken from an address the learner never chose to
        # show. The handle is the only safe default.
        display_name=profile.display_name or profile.handle,
        headline=profile.headline,
        bio=profile.bio,
        location=profile.location,
        links=links,
        joined_at=owner.created_at,
        projects=projects,
        tracks=tracks,
        badges=badges,
        readiness=readiness,
        points=points,
        level=level,
        concepts_completed=concepts_completed,
        projects_shipped=len(projects) if profile.show_projects else None,
        is_preview=is_preview,
    )


# --------------------------------------------------------------------------
# owner serialisation
# --------------------------------------------------------------------------


def _public_summary(profile: PortfolioProfile, project_count: int) -> list[str]:
    """What a stranger can see, spelled out.

    Six independent switches are exactly the kind of state people misread, and
    the cost of misreading them is publishing something you did not mean to.
    """
    if not profile.is_published:
        return ["Nothing. Your profile is private and its URL returns “not found”."]

    lines = [f"Your handle ({profile.handle}) and anything you typed above."]
    if profile.show_projects and project_count:
        lines.append(
            f"{project_count} shipped "
            f"{'project' if project_count == 1 else 'projects'}"
            + (
                " — including the code you submitted, runnable in the page."
                if profile.show_project_code
                else ", by name only. Your code stays private."
            )
        )
    if profile.show_concepts:
        lines.append("The concepts you have completed, grouped by track.")
    if profile.show_points:
        lines.append("Your points total and level.")
    if profile.show_badges:
        lines.append("Your badges.")
    if profile.show_readiness:
        lines.append("Your readiness score for your strongest roles.")
    lines.append("Never your email address, and never work in progress.")
    return lines


def _settings(db: DbSession, user: User, profile: PortfolioProfile) -> PortfolioSettings:
    shipped = _shipped(db, user.id)
    overrides = {row.project_id: row for row in profile.projects}

    owner_projects = [
        OwnerProject(
            project_id=project_id,
            slug=entry.project.slug,
            title=entry.project.title,
            tagline=entry.project.tagline,
            runtime=entry.project.runtime,
            concept_name=entry.project.concept.name,
            shipped_at=entry.shipped_at,
            is_visible=(
                overrides[project_id].is_visible if project_id in overrides else True
            ),
            note=(overrides[project_id].note if project_id in overrides else "") or "",
            sort_order=(
                overrides[project_id].sort_order if project_id in overrides else 0
            ),
        )
        for project_id, entry in shipped.items()
    ]
    owner_projects.sort(key=lambda p: (p.sort_order, p.shipped_at))

    visible_count = sum(1 for p in owner_projects if p.is_visible)

    return PortfolioSettings(
        exists=True,
        handle=profile.handle,
        display_name=profile.display_name,
        headline=profile.headline,
        bio=profile.bio,
        location=profile.location,
        github_url=profile.github_url,
        linkedin_url=profile.linkedin_url,
        website_url=profile.website_url,
        visibility=PortfolioVisibility(
            show_projects=profile.show_projects,
            show_concepts=profile.show_concepts,
            show_points=profile.show_points,
            show_badges=profile.show_badges,
            show_readiness=profile.show_readiness,
            show_project_code=profile.show_project_code,
        ),
        is_published=profile.is_published,
        published_at=profile.published_at,
        # Relative: the API does not know the public origin, and guessing it
        # wrong would put a broken link in front of the learner.
        public_url=f"/u/{profile.handle}",
        projects=owner_projects,
        public_summary=_public_summary(profile, visible_count),
    )


def _empty_settings() -> PortfolioSettings:
    """Before a handle is chosen there is no profile — and nothing public."""
    return PortfolioSettings(
        exists=False,
        handle=None,
        display_name="",
        headline="",
        bio="",
        location="",
        github_url=None,
        linkedin_url=None,
        website_url=None,
        visibility=PortfolioVisibility(),
        is_published=False,
        published_at=None,
        public_url=None,
        projects=[],
        public_summary=[
            "Nothing. You have not created a portfolio yet.",
        ],
    )


# --------------------------------------------------------------------------
# owner endpoints
#
# Declared before `/{handle}` — FastAPI matches in declaration order, and
# `/portfolio/me` would otherwise be read as a handle lookup. (`me` is also
# reserved, so it is belt and braces.)
# --------------------------------------------------------------------------


@router.get("/me", response_model=PortfolioSettings)
def get_my_portfolio(db: DbSession, user: CurrentUser):
    """The owner's control panel. Never creates anything."""
    profile = _own_profile(db, user.id)
    if profile is None:
        return _empty_settings()
    return _settings(db, user, profile)


@router.get("/handle-check", response_model=HandleCheck)
def check_handle(db: DbSession, user: CurrentUser, handle: str = Query(min_length=1)):
    """Is this handle usable? Same rules the write path enforces."""
    mine = _own_profile(db, user.id)
    try:
        cleaned = validate_handle(handle)
    except ValueError as error:
        return HandleCheck(handle=handle, available=False, reason=str(error))

    if _handle_taken(db, cleaned, mine.id if mine else None):
        return HandleCheck(
            handle=cleaned, available=False, reason="That handle is taken."
        )
    return HandleCheck(handle=cleaned, available=True)


@router.put("/me", response_model=PortfolioSettings)
def update_my_portfolio(db: DbSession, user: CurrentUser, payload: PortfolioUpdate):
    """Create or update the profile. Creation never publishes it."""
    profile = _own_profile(db, user.id)

    # Checked before anything is added to the session: a pending INSERT would
    # be autoflushed by the lookup below and the caller would collide with
    # themselves.
    if payload.handle is not None and _handle_taken(
        db, payload.handle, profile.id if profile else None
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="That handle is taken."
        )

    if profile is None:
        if not payload.handle:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Choose a handle to create your portfolio.",
            )
        profile = PortfolioProfile(
            user_id=user.id,
            handle=payload.handle,
            handle_ci=normalize_handle(payload.handle),
            # Left blank rather than seeded from the account: `display_name`
            # there is the email's local part until the learner changes it.
            display_name="",
            is_published=False,
        )
        db.add(profile)
    elif payload.handle is not None:
        profile.handle = payload.handle
        profile.handle_ci = normalize_handle(payload.handle)

    for field in ("display_name", "headline", "bio", "location"):
        value = getattr(payload, field)
        if value is not None:
            setattr(profile, field, value.strip())

    for field in ("github_url", "linkedin_url", "website_url"):
        if field in payload.model_fields_set:
            setattr(profile, field, getattr(payload, field))

    for field in (
        "show_projects",
        "show_concepts",
        "show_points",
        "show_badges",
        "show_readiness",
        "show_project_code",
    ):
        value = getattr(payload, field)
        if value is not None:
            setattr(profile, field, value)

    try:
        db.commit()
    except IntegrityError:
        # Two people claiming the same handle in the same instant. The unique
        # index on `handle_ci` is the real guarantee; the check above is only
        # there to produce a nicer message most of the time.
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="That handle is taken."
        ) from None
    db.refresh(profile)
    return _settings(db, user, profile)


@router.post("/me/publish", response_model=PortfolioSettings)
def publish(db: DbSession, user: CurrentUser):
    """Make the profile public. The one act that exposes anything."""
    profile = _own_profile(db, user.id)
    if profile is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Choose a handle before publishing.",
        )
    if not profile.is_published:
        profile.is_published = True
        profile.published_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(profile)
    return _settings(db, user, profile)


@router.post("/me/unpublish", response_model=PortfolioSettings)
def unpublish(db: DbSession, user: CurrentUser):
    """Take it down. Effective immediately — nothing here is cached."""
    profile = _own_profile(db, user.id)
    if profile is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="No portfolio to unpublish."
        )
    if profile.is_published:
        profile.is_published = False
        db.commit()
        db.refresh(profile)
    return _settings(db, user, profile)


@router.patch("/me/projects/{project_id}", response_model=PortfolioSettings)
def update_project_visibility(
    db: DbSession,
    user: CurrentUser,
    project_id: int,
    payload: ProjectVisibilityUpdate,
):
    """Show, hide, annotate or reorder one shipped project."""
    profile = _own_profile(db, user.id)
    if profile is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="No portfolio yet."
        )

    # Only projects the learner actually passed can appear, so only those can
    # be configured — otherwise the settings table becomes a way to assert a
    # ship that never happened.
    if project_id not in _shipped(db, user.id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="You have not shipped that project.",
        )

    row = db.scalar(
        select(PortfolioProject).where(
            PortfolioProject.profile_id == profile.id,
            PortfolioProject.project_id == project_id,
        )
    )
    if row is None:
        row = PortfolioProject(profile_id=profile.id, project_id=project_id)
        db.add(row)

    if payload.is_visible is not None:
        row.is_visible = payload.is_visible
    if payload.note is not None:
        row.note = payload.note.strip()
    if payload.sort_order is not None:
        row.sort_order = payload.sort_order

    db.commit()
    db.refresh(profile)
    return _settings(db, user, profile)


@router.delete("/me", status_code=status.HTTP_204_NO_CONTENT)
def delete_my_portfolio(db: DbSession, user: CurrentUser):
    """Delete the profile and free the handle. Learning progress is untouched."""
    profile = _own_profile(db, user.id)
    if profile is not None:
        db.delete(profile)
        db.commit()


# --------------------------------------------------------------------------
# public endpoint
# --------------------------------------------------------------------------


@router.get("/{handle}", response_model=PublicPortfolio)
def get_public_portfolio(db: DbSession, viewer: OptionalUser, handle: str):
    """One learner's public page.

    404 covers three different situations on purpose — no such handle, an
    unpublished profile, and a deactivated account all look identical from
    outside. A 403 would confirm the handle exists and that someone is hiding
    something behind it, which is information the visitor is not entitled to.
    """
    normalized = normalize_handle(handle)
    if not normalized or normalized in RESERVED_HANDLES:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")

    profile = db.scalar(
        select(PortfolioProfile)
        .where(PortfolioProfile.handle_ci == normalized)
        .options(selectinload(PortfolioProfile.projects))
    )
    if profile is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")

    is_owner = viewer is not None and viewer.id == profile.user_id
    if not profile.is_published and not is_owner:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")

    owner = db.get(User, profile.user_id)
    if owner is None or (not owner.is_active and not is_owner):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")

    return _build_public(db, profile, owner, is_preview=not profile.is_published)
