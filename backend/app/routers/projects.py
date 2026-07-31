"""Projects: the buildable half of every step.

Execution happens in the learner's browser — Pyodide, a sandboxed iframe or
sql.js — so this router never runs submitted code. What it does do is:

* hand out the brief, the starter files and the tests,
* record every attempt in full,
* check the invariants it *can* check server-side (the tests belong to this
  project, the required snippets are present), and
* award the points exactly once.

The pass/fail signal itself is reported by the client, which is the accepted
cost of not running a container per submission. The UI says so plainly.
"""

import json

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import func, select

from app.deps import CurrentUser, DbSession, OptionalUser, get_profile
from app.models.content import Concept, Domain, Track, TrackConcept
from app.models.project import (
    SUBMISSION_FAILED,
    SUBMISSION_PASSED,
    Project,
    ProjectSubmission,
)
from app.routers.content import concept_summary
from app.schemas.progress import BadgeOut
from app.schemas.project import (
    ProjectDetail,
    ProjectFileOut,
    ProjectSubmit,
    ProjectSummary,
    ProjectTestOut,
    SubmissionOut,
    SubmissionResult,
)
from app.services.gamification import award_points, evaluate_badges

router = APIRouter(prefix="/projects", tags=["projects"])


# --------------------------------------------------------------------------
# serialisation
# --------------------------------------------------------------------------


def project_summary(project: Project) -> ProjectSummary:
    return ProjectSummary(
        id=project.id,
        slug=project.slug,
        title=project.title,
        tagline=project.tagline,
        runtime=project.runtime,
        difficulty=project.difficulty,
        est_minutes=project.est_minutes,
        xp_reward=project.xp_reward,
        concept_slug=project.concept.slug,
        concept_name=project.concept.name,
    )


def _best_attempts(db: DbSession, user_id: int) -> dict[int, tuple[str, int]]:
    """project_id -> (best status, most tests passed), in one query.

    'passed' sorts above 'failed' alphabetically by luck, so rank explicitly.
    """
    rows = db.execute(
        select(
            ProjectSubmission.project_id,
            func.max(ProjectSubmission.status == SUBMISSION_PASSED),
            func.max(ProjectSubmission.passed_count),
        )
        .where(ProjectSubmission.user_id == user_id)
        .group_by(ProjectSubmission.project_id)
    ).all()
    return {
        project_id: (SUBMISSION_PASSED if ever_passed else SUBMISSION_FAILED, best)
        for project_id, ever_passed, best in rows
    }


# --------------------------------------------------------------------------
# reads
# --------------------------------------------------------------------------


@router.get("", response_model=list[ProjectSummary])
def list_projects(
    db: DbSession,
    user: OptionalUser,
    track: str | None = Query(None, description="Track slug"),
    domain: str | None = Query(None, description="Domain slug"),
    runtime: str | None = Query(None),
    concept: str | None = Query(None, description="Concept slug"),
):
    stmt = select(Project).join(Concept, Concept.id == Project.concept_id)
    if track:
        stmt = stmt.join(
            TrackConcept, TrackConcept.concept_id == Concept.id
        ).join(Track, Track.id == TrackConcept.track_id).where(Track.slug == track)
    if domain:
        stmt = stmt.join(Domain, Domain.id == Concept.domain_id).where(
            Domain.slug == domain
        )
    if runtime:
        stmt = stmt.where(Project.runtime == runtime)
    if concept:
        stmt = stmt.where(Concept.slug == concept)

    projects = db.scalars(stmt.order_by(Project.sort_order, Project.id)).unique().all()
    summaries = [project_summary(p) for p in projects]

    if user is not None:
        attempts = _best_attempts(db, user.id)
        for summary in summaries:
            attempt = attempts.get(summary.id)
            if attempt is not None:
                summary.status, summary.best_passed = attempt
    return summaries


@router.get("/{slug}", response_model=ProjectDetail)
def get_project(slug: str, db: DbSession, user: OptionalUser):
    project = db.scalar(select(Project).where(Project.slug == slug))
    if project is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Project not found")

    detail = ProjectDetail(
        **project_summary(project).model_dump(),
        brief_md=project.brief_md,
        concept=concept_summary(project.concept),
        files=[ProjectFileOut.model_validate(f) for f in project.files],
        tests=[ProjectTestOut.model_validate(t) for t in project.tests],
    )

    if user is not None:
        attempts = db.scalars(
            select(ProjectSubmission)
            .where(
                ProjectSubmission.user_id == user.id,
                ProjectSubmission.project_id == project.id,
            )
            .order_by(ProjectSubmission.attempt_no.desc())
        ).all()
        detail.attempts = len(attempts)
        if attempts:
            passed = any(a.status == SUBMISSION_PASSED for a in attempts)
            detail.status = SUBMISSION_PASSED if passed else SUBMISSION_FAILED
            detail.best_passed = max(a.passed_count for a in attempts)
            if passed:
                # The worked solution is a reward, not a shortcut.
                detail.solution_md = project.solution_md
    return detail


@router.get("/{slug}/submissions", response_model=list[SubmissionOut])
def list_submissions(slug: str, user: CurrentUser, db: DbSession):
    project = db.scalar(select(Project).where(Project.slug == slug))
    if project is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Project not found")
    rows = db.scalars(
        select(ProjectSubmission)
        .where(
            ProjectSubmission.user_id == user.id,
            ProjectSubmission.project_id == project.id,
        )
        .order_by(ProjectSubmission.attempt_no.desc())
    ).all()
    return [SubmissionOut.model_validate(r) for r in rows]


# --------------------------------------------------------------------------
# submission
# --------------------------------------------------------------------------


@router.post(
    "/{slug}/submit",
    response_model=SubmissionResult,
    status_code=status.HTTP_201_CREATED,
)
def submit_project(
    slug: str, payload: ProjectSubmit, user: CurrentUser, db: DbSession
):
    project = db.scalar(select(Project).where(Project.slug == slug))
    if project is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Project not found")

    test_ids = {t.id for t in project.tests}
    reported = {r.test_id: r.passed for r in payload.results if r.test_id in test_ids}
    passed_count = sum(1 for ok in reported.values() if ok)
    total_count = len(test_ids)

    # A client that simply omits the tests it failed must not read as a pass.
    all_green = total_count > 0 and passed_count == total_count
    rejected_reason = _missing_snippet(project, payload)
    passed = all_green and rejected_reason is None

    previous = db.scalars(
        select(ProjectSubmission).where(
            ProjectSubmission.user_id == user.id,
            ProjectSubmission.project_id == project.id,
        )
    ).all()
    already_awarded = any(p.xp_awarded > 0 for p in previous)

    submission = ProjectSubmission(
        user_id=user.id,
        project_id=project.id,
        files_json=json.dumps([f.model_dump() for f in payload.files]),
        passed_count=passed_count,
        total_count=total_count,
        status=SUBMISSION_PASSED if passed else SUBMISSION_FAILED,
        xp_awarded=0,
        attempt_no=len(previous) + 1,
    )
    db.add(submission)
    db.flush()

    profile = get_profile(db, user)
    xp_earned = 0
    level_before = profile.level
    new_badges: list[BadgeOut] = []

    if passed and not already_awarded:
        xp_earned = project.xp_reward
        submission.xp_awarded = xp_earned
        award_points(
            db,
            profile,
            user.id,
            "project",
            ref_slug=project.slug,
            label=f"Built {project.title}",
            points=xp_earned,
        )
        db.flush()
        awarded = evaluate_badges(
            db,
            user.id,
            profile,
            flawless_build=submission.attempt_no == 1,
        )
        new_badges = [BadgeOut.model_validate(b) for b in awarded]

    db.commit()
    db.refresh(submission)

    return SubmissionResult(
        submission=SubmissionOut.model_validate(submission),
        passed=passed,
        rejected_reason=rejected_reason if all_green else None,
        xp_earned=xp_earned,
        total_xp=profile.xp,
        level=profile.level,
        leveled_up=profile.level > level_before,
        new_badges=new_badges,
        solution_md=project.solution_md if passed else None,
    )


def _missing_snippet(project: Project, payload: ProjectSubmit) -> str | None:
    """The one thing the server can verify without running the code.

    ``must_contain`` names the API the brief asked for. It stops a submission
    that passes by hard-coding the expected answer rather than by solving the
    problem — a weak check, deliberately used only for rejections a human would
    also make on sight.
    """
    required = project.required_snippets
    if not required:
        return None
    blob = "\n".join(f.content for f in payload.files)
    missing = [snippet for snippet in required if snippet not in blob]
    if not missing:
        return None
    return (
        "Every test passed, but the solution does not use "
        + ", ".join(f"`{s}`" for s in missing)
        + " as the brief requires. Points are held until it does."
    )
