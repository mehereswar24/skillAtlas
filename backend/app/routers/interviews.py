"""Mock interviews.

A text interview against a real company role, drawn from the source-cited
question bank the company profile already shows, graded against the rubric that
company has published, and ending in a list of concepts to go study that can be
appended to the learner's route in one call.

The last part is the point. A mock interview that does not send you back to the
material is just a quiz.

Grading needs the local model. When it is not there the session still runs and
the reference answers are still revealed — the verdict is `ungraded` and the
API says so, rather than inventing a score.
"""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.deps import CurrentUser, DbSession
from app.models.company import Company, CompanyRole
from app.models.interview import (
    GRADED_VERDICTS,
    SESSION_COMPLETED,
    SESSION_IN_PROGRESS,
    VERDICT_UNGRADED,
    InterviewSession,
    InterviewTurn,
)
from app.schemas.interview import (
    AnswerRequest,
    ConceptSuggestionOut,
    InterviewRoleOption,
    InterviewStatus,
    RoundOption,
    SessionOut,
    SessionRow,
    SessionSummaryOut,
    StartSessionRequest,
    TurnOut,
)
from app.services import interview as service
from app.services.llm import get_provider

router = APIRouter(prefix="/interviews", tags=["interviews"])


# --------------------------------------------------------------------------
# serialisation
# --------------------------------------------------------------------------


def _turn_out(turn: InterviewTurn) -> TurnOut:
    answered = turn.verdict is not None
    return TurnOut(
        id=turn.id,
        position=turn.position,
        round=turn.round,
        round_label=service.ROUND_LABELS.get(turn.round, turn.round),
        topic=turn.topic,
        difficulty=turn.difficulty,
        question=turn.question,
        source_name=turn.source_name,
        source_url=turn.source_url,
        answer_text=turn.answer_text,
        verdict=turn.verdict,
        score=turn.score,
        feedback_md=turn.feedback_md,
        missed_points=turn.missed_points.split("\n") if turn.missed_points else [],
        injection_flagged=turn.injection_flagged,
        answered_at=turn.answered_at,
        # Only after answering: otherwise the answer key ships with the question.
        reference_answer_md=turn.reference_answer_md if answered else None,
    )


def _session_row(session: InterviewSession) -> SessionRow:
    return SessionRow(
        id=session.id,
        company_slug=session.company_slug,
        company_name=session.company_name,
        role_slug=session.role_slug,
        role_title=session.role_title,
        status=session.status,
        score=session.score,
        question_count=len(session.turns),
        answered_count=sum(1 for turn in session.turns if turn.verdict),
        was_degraded=session.was_degraded,
        created_at=session.created_at,
        completed_at=session.completed_at,
    )


def _summary_out(summary: service.SessionSummary) -> SessionSummaryOut:
    return SessionSummaryOut(
        score=summary.score,
        graded_count=summary.graded_count,
        answered_count=summary.answered_count,
        question_count=summary.question_count,
        strengths=summary.strengths,
        weak_areas=summary.weak_areas,
        recommended_concepts=[
            ConceptSuggestionOut(**vars(item)) for item in summary.recommended_concepts
        ],
        summary_md=summary.summary_md,
        degraded=summary.degraded,
    )


def _session_out(
    db: DbSession,
    session: InterviewSession,
    user_id: int,
    *,
    grading_available: bool = True,
    summary: service.SessionSummary | None = None,
) -> SessionOut:
    if summary is None and session.status == SESSION_COMPLETED:
        summary = service.summary_from_storage(db, session, user_id)
    return SessionOut(
        **_session_row(session).model_dump(),
        turns=[_turn_out(turn) for turn in session.turns],
        summary=_summary_out(summary) if summary else None,
        grading_available=grading_available,
    )


# --------------------------------------------------------------------------
# lookups
# --------------------------------------------------------------------------


def _load_role(db: DbSession, company_slug: str, role_slug: str) -> CompanyRole:
    role = db.scalar(
        select(CompanyRole)
        .join(Company, Company.id == CompanyRole.company_id)
        .where(Company.slug == company_slug, CompanyRole.slug == role_slug)
        .options(
            selectinload(CompanyRole.questions),
            selectinload(CompanyRole.focus_areas),
            selectinload(CompanyRole.company),
        )
    )
    if role is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such company role")
    return role


def _load_session(db: DbSession, session_id: int, user_id: int) -> InterviewSession:
    session = db.get(InterviewSession, session_id)
    # A session belonging to somebody else is indistinguishable from one that
    # does not exist.
    if session is None or session.user_id != user_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such interview session")
    return session


def _role_for(db: DbSession, session: InterviewSession) -> CompanyRole | None:
    """The live role a session came from, if it still exists after a re-seed."""
    if session.company_role_id is None:
        return None
    return db.scalar(
        select(CompanyRole)
        .where(CompanyRole.id == session.company_role_id)
        .options(
            selectinload(CompanyRole.focus_areas),
            selectinload(CompanyRole.company),
        )
    )


# --------------------------------------------------------------------------
# endpoints
# --------------------------------------------------------------------------


@router.get("/status", response_model=InterviewStatus)
async def interview_status():
    """Whether answers can be graded right now."""
    provider = get_provider()
    available = await provider.is_available()
    return InterviewStatus(
        available=available,
        model=provider.chat_model if available else None,
        mode="graded" if available else "ungraded",
    )


@router.get("/roles", response_model=list[InterviewRoleOption])
def interview_roles(
    user: CurrentUser,
    db: DbSession,
    company_slug: str | None = Query(None),
    min_questions: int = Query(2, ge=1, le=20),
):
    """Roles worth interviewing for — those with enough questions banked."""
    query = (
        select(CompanyRole)
        .join(Company, Company.id == CompanyRole.company_id)
        .options(selectinload(CompanyRole.questions), selectinload(CompanyRole.company))
        .order_by(Company.sort_order, Company.name, CompanyRole.sort_order)
    )
    if company_slug:
        query = query.where(Company.slug == company_slug)

    attempts: dict[tuple[str, str], tuple[int, float | None]] = {}
    for row in db.execute(
        select(
            InterviewSession.company_slug,
            InterviewSession.role_slug,
            func.count(InterviewSession.id),
            func.max(InterviewSession.score),
        )
        .where(InterviewSession.user_id == user.id)
        .group_by(InterviewSession.company_slug, InterviewSession.role_slug)
    ).all():
        attempts[(row[0], row[1])] = (row[2], row[3])

    options: list[InterviewRoleOption] = []
    for role in db.scalars(query).unique():
        if len(role.questions) < min_questions:
            continue
        counts: dict[str, int] = {}
        for question in role.questions:
            counts[question.round] = counts.get(question.round, 0) + 1
        rounds = [
            RoundOption(
                name=name,
                label=service.ROUND_LABELS.get(name, name),
                question_count=counts[name],
            )
            for name in service.ROUND_ORDER
            if name in counts
        ]
        attempt_count, best = attempts.get(
            (role.company.slug, role.slug), (0, None)
        )
        options.append(
            InterviewRoleOption(
                company_slug=role.company.slug,
                company_name=role.company.name,
                company_icon=role.company.icon,
                role_slug=role.slug,
                role_title=role.title,
                level=role.level,
                question_count=len(role.questions),
                rounds=rounds,
                attempts=attempt_count,
                best_score=best,
            )
        )
    return options


@router.get("/sessions", response_model=list[SessionRow])
def list_sessions(
    user: CurrentUser, db: DbSession, limit: int = Query(30, ge=1, le=100)
):
    """Past attempts, newest first — progress across attempts is the point."""
    sessions = db.scalars(
        select(InterviewSession)
        .where(InterviewSession.user_id == user.id)
        .options(selectinload(InterviewSession.turns))
        .order_by(InterviewSession.created_at.desc(), InterviewSession.id.desc())
        .limit(limit)
    ).unique()
    return [_session_row(session) for session in sessions]


@router.post("/sessions", response_model=SessionOut, status_code=201)
async def start_session(payload: StartSessionRequest, user: CurrentUser, db: DbSession):
    """Draw a paper for one company role and open a session on it."""
    role = _load_role(db, payload.company_slug, payload.role_slug)

    unknown = [r for r in payload.rounds if r not in service.ROUND_ORDER]
    if unknown:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            f"Unknown round(s): {', '.join(unknown)}",
        )

    questions = service.select_questions(
        role, count=payload.question_count, rounds=payload.rounds or None
    )
    if not questions:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            "No questions are banked for that role and round selection",
        )

    grading_available = await get_provider().is_available()

    session = InterviewSession(
        user_id=user.id,
        company_role_id=role.id,
        company_slug=role.company.slug,
        company_name=role.company.name,
        role_slug=role.slug,
        role_title=role.title,
        status=SESSION_IN_PROGRESS,
        was_degraded=not grading_available,
    )
    service.build_turns(session, questions)
    db.add(session)
    db.commit()
    db.refresh(session)
    return _session_out(db, session, user.id, grading_available=grading_available)


@router.get("/sessions/{session_id}", response_model=SessionOut)
def get_session(session_id: int, user: CurrentUser, db: DbSession):
    session = _load_session(db, session_id, user.id)
    return _session_out(db, session, user.id)


@router.delete("/sessions/{session_id}", status_code=204)
def delete_session(session_id: int, user: CurrentUser, db: DbSession):
    session = _load_session(db, session_id, user.id)
    db.delete(session)
    db.commit()


@router.post("/sessions/{session_id}/turns/{turn_id}/answer", response_model=TurnOut)
async def answer_turn(
    session_id: int,
    turn_id: int,
    payload: AnswerRequest,
    user: CurrentUser,
    db: DbSession,
):
    """Submit an answer and get a verdict with reasons, plus the reference answer.

    An empty body is a legitimate submission: it records that the question was
    passed on, and reveals the reference answer.
    """
    session = _load_session(db, session_id, user.id)
    if session.status == SESSION_COMPLETED:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "This session is already finished"
        )

    turn = next((t for t in session.turns if t.id == turn_id), None)
    if turn is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such question in this session")

    rubric = service.build_rubric(session, _role_for(db, session))

    # Grading takes tens of seconds against a local model. Everything above
    # this line ran inside a read transaction, and on SQLite a transaction that
    # read first and writes later cannot be promoted once another connection
    # has written — it fails immediately with "database is locked", however
    # generous the busy timeout. Detaching first (so no attribute access can
    # re-open one) and then ending the transaction means the model call is
    # awaited with no lock held at all; the rows are re-read below for the
    # write, which is short.
    db.expunge_all()
    db.rollback()

    grade = await service.grade_answer(session, turn, payload.answer, rubric)

    session = _load_session(db, session_id, user.id)
    turn = next((t for t in session.turns if t.id == turn_id), None)
    if turn is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such question in this session")

    turn.answer_text = payload.answer.strip() or None
    turn.verdict = grade.verdict
    turn.score = grade.score
    turn.feedback_md = grade.feedback_md
    turn.missed_points = "\n".join(grade.missed) or None
    turn.injection_flagged = grade.injection_flagged
    turn.answered_at = datetime.now(timezone.utc)

    if grade.degraded:
        session.was_degraded = True

    graded = [
        t.score
        for t in session.turns
        if t.verdict in GRADED_VERDICTS and t.score is not None
    ]
    session.score = round(sum(graded) / len(graded), 1) if graded else None

    db.commit()
    db.refresh(turn)
    return _turn_out(turn)


@router.post("/sessions/{session_id}/complete", response_model=SessionOut)
async def complete_session(session_id: int, user: CurrentUser, db: DbSession):
    """Close the session and build the feedback that sends the learner back.

    Idempotent: finishing an already-finished session redraws the stored
    summary rather than recomputing different advice.
    """
    session = _load_session(db, session_id, user.id)
    if session.status == SESSION_COMPLETED:
        return _session_out(db, session, user.id)

    summary = await service.build_summary(db, session, user.id, _role_for(db, session))

    session.status = SESSION_COMPLETED
    session.score = summary.score
    session.summary_md = summary.summary_md
    session.recommendations_json = service.dump_recommendations(
        summary.recommended_concepts
    )
    session.completed_at = datetime.now(timezone.utc)
    if summary.degraded or any(t.verdict == VERDICT_UNGRADED for t in session.turns):
        session.was_degraded = True

    db.commit()
    db.refresh(session)
    return _session_out(db, session, user.id, summary=summary)
