"""Marking concepts started and complete, grading quizzes, awarding XP."""

from datetime import date, datetime, timedelta, timezone

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import select

from app.deps import CurrentUser, DbSession, get_profile
from app.models.content import Concept, QuizOption, QuizQuestion
from app.models.progress import (
    STATUS_COMPLETED,
    STATUS_IN_PROGRESS,
    DailyActivity,
    UserBadge,
    UserProgress,
    UserRoadmapItem,
)
from app.routers.content import concept_summary
from app.schemas.progress import (
    ActivityPoint,
    BadgeOut,
    CompleteRequest,
    CompletionResult,
    ProgressOut,
    QuizReview,
)
from app.services.gamification import apply_completion
from app.services.graph import ConceptGraph
from app.services.roadmap import get_active_roadmap

router = APIRouter(prefix="/progress", tags=["progress"])

# A quiz is a comprehension check, not an exam. Two thirds correct is the bar.
PASS_THRESHOLD = 2 / 3


def _get_concept(db: DbSession, slug: str) -> Concept:
    concept = db.scalar(select(Concept).where(Concept.slug == slug))
    if concept is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Concept not found")
    return concept


def _new_progress(
    db: DbSession, user_id: int, concept_id: int, status_: str
) -> UserProgress:
    """Create a progress row with its counters populated.

    Column defaults are only applied by the INSERT, so a freshly constructed
    instance still has `None` for them — which breaks both `+=` and response
    validation if the row is read before it is flushed.
    """
    row = UserProgress(
        user_id=user_id,
        concept_id=concept_id,
        status=status_,
        confidence_score=1.0,
        time_spent_minutes=0,
        source="study",
    )
    db.add(row)
    db.flush()
    return row


def _completed_ids(db: DbSession, user_id: int) -> set[int]:
    return set(
        db.scalars(
            select(UserProgress.concept_id).where(
                UserProgress.user_id == user_id,
                UserProgress.status == STATUS_COMPLETED,
            )
        ).all()
    )


@router.get("", response_model=list[ProgressOut])
def list_progress(user: CurrentUser, db: DbSession):
    rows = db.scalars(
        select(UserProgress)
        .where(UserProgress.user_id == user.id)
        .order_by(UserProgress.completed_at.desc().nulls_last())
    ).all()
    return [
        ProgressOut(
            concept=concept_summary(row.concept),
            status=row.status,
            quiz_score=row.quiz_score,
            time_spent_minutes=row.time_spent_minutes,
            source=row.source,
            completed_at=row.completed_at,
        )
        for row in rows
    ]


@router.post("/{slug}/start", response_model=ProgressOut)
def start_concept(slug: str, user: CurrentUser, db: DbSession):
    """Mark a concept as in progress. Idempotent, and never demotes a pass."""
    concept = _get_concept(db, slug)
    row = db.scalar(
        select(UserProgress).where(
            UserProgress.user_id == user.id, UserProgress.concept_id == concept.id
        )
    )
    if row is None:
        row = _new_progress(db, user.id, concept.id, STATUS_IN_PROGRESS)
    elif row.status != STATUS_COMPLETED:
        row.status = STATUS_IN_PROGRESS

    _mirror_to_roadmap(db, user.id, concept.id, row.status)
    db.commit()
    db.refresh(row)
    return ProgressOut(
        concept=concept_summary(concept),
        status=row.status,
        quiz_score=row.quiz_score,
        time_spent_minutes=row.time_spent_minutes,
        source=row.source,
        completed_at=row.completed_at,
    )


@router.post("/{slug}/complete", response_model=CompletionResult)
def complete_concept(
    slug: str, payload: CompleteRequest, user: CurrentUser, db: DbSession
):
    concept = _get_concept(db, slug)
    graph = ConceptGraph.load(db)
    completed = _completed_ids(db, user.id)

    missing = graph.missing_prerequisites(concept.id, completed)
    if missing:
        names = db.scalars(
            select(Concept.name).where(Concept.id.in_(missing))
        ).all()
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"Finish the prerequisites first: {', '.join(sorted(names))}",
        )

    score, correct_count, question_count, review = _grade(db, concept, payload)
    passed = question_count == 0 or score >= PASS_THRESHOLD

    if not passed:
        # Nothing is recorded on a failed attempt — the learner gets the review
        # and can try again.
        return CompletionResult(
            concept_slug=concept.slug,
            quiz_score=score,
            passed=False,
            correct_count=correct_count,
            question_count=question_count,
            xp_earned=0,
            total_xp=user.profile.xp if user.profile else 0,
            level=user.profile.level if user.profile else 1,
            leveled_up=False,
            streak_days=user.profile.streak_days if user.profile else 0,
            new_badges=[],
            unlocked_concepts=[],
            review=review,
        )

    profile = get_profile(db, user)
    row = db.scalar(
        select(UserProgress).where(
            UserProgress.user_id == user.id, UserProgress.concept_id == concept.id
        )
    )
    already_complete = row is not None and row.status == STATUS_COMPLETED

    if row is None:
        row = _new_progress(db, user.id, concept.id, STATUS_COMPLETED)
    row.status = STATUS_COMPLETED
    row.completed_at = datetime.now(timezone.utc)
    row.time_spent_minutes += payload.time_spent_minutes
    row.source = "study"
    if score is not None:
        # Keep the best attempt rather than overwriting a better earlier one.
        row.quiz_score = max(score, row.quiz_score or 0.0)
    db.flush()

    if already_complete:
        # Re-submitting a finished concept refreshes the score but must not
        # award XP again, or the leaderboard becomes a clicking contest.
        db.commit()
        return CompletionResult(
            concept_slug=concept.slug,
            quiz_score=row.quiz_score,
            passed=True,
            correct_count=correct_count,
            question_count=question_count,
            xp_earned=0,
            total_xp=profile.xp,
            level=profile.level,
            leveled_up=False,
            streak_days=profile.streak_days,
            new_badges=[],
            unlocked_concepts=[],
            review=review,
        )

    _mirror_to_roadmap(db, user.id, concept.id, STATUS_COMPLETED)

    award = apply_completion(
        db,
        user.id,
        profile,
        concept,
        quiz_score=score,
        minutes=payload.time_spent_minutes,
    )

    newly_completed = completed | {concept.id}
    unlocked = [
        cid
        for cid in graph.direct_dependents(concept.id)
        if graph.is_unlocked(cid, newly_completed) and cid not in newly_completed
    ]
    unlocked_concepts = db.scalars(
        select(Concept).where(Concept.id.in_(unlocked))
    ).unique().all()

    db.commit()

    return CompletionResult(
        concept_slug=concept.slug,
        quiz_score=row.quiz_score,
        passed=True,
        correct_count=correct_count,
        question_count=question_count,
        xp_earned=award.xp_earned,
        total_xp=award.total_xp,
        level=award.level,
        leveled_up=award.leveled_up,
        streak_days=award.streak_days,
        new_badges=[BadgeOut.model_validate(b) for b in award.new_badges],
        unlocked_concepts=[concept_summary(c) for c in unlocked_concepts],
        review=review,
    )


def _grade(
    db: DbSession, concept: Concept, payload: CompleteRequest
) -> tuple[float | None, int, int, list[QuizReview]]:
    """Grade the submission server-side. Clients never see the correct answers."""
    questions = list(concept.quiz_questions)
    if not questions:
        return None, 0, 0, []

    chosen = {a.question_id: a.option_id for a in payload.answers}
    review: list[QuizReview] = []
    correct_count = 0

    for question in questions:
        correct_option = next((o for o in question.options if o.is_correct), None)
        if correct_option is None:
            # The seeder rejects this, so it means the row was edited by hand.
            continue
        selected = chosen.get(question.id)
        is_correct = selected == correct_option.id
        correct_count += int(is_correct)
        review.append(
            QuizReview(
                question_id=question.id,
                correct_option_id=correct_option.id,
                selected_option_id=selected,
                is_correct=is_correct,
                explanation=question.explanation,
            )
        )

    total = len(review)
    return (correct_count / total if total else None), correct_count, total, review


def _mirror_to_roadmap(db: DbSession, user_id: int, concept_id: int, status_: str):
    """Keep the active roadmap's item in step with progress."""
    roadmap = get_active_roadmap(db, user_id)
    if roadmap is None:
        return
    item = db.scalar(
        select(UserRoadmapItem).where(
            UserRoadmapItem.roadmap_id == roadmap.id,
            UserRoadmapItem.concept_id == concept_id,
        )
    )
    if item is not None:
        item.status = status_


@router.get("/badges", response_model=list[BadgeOut])
def list_badges(user: CurrentUser, db: DbSession):
    badges = db.scalars(
        select(UserBadge)
        .where(UserBadge.user_id == user.id)
        .order_by(UserBadge.awarded_at.desc())
    ).all()
    return [BadgeOut.model_validate(b) for b in badges]


@router.get("/activity", response_model=list[ActivityPoint])
def activity(
    user: CurrentUser,
    db: DbSession,
    days: int = Query(30, ge=1, le=365),
):
    """Daily activity for the last N days, zero-filled so the chart has no gaps."""
    today = date.today()
    start = today - timedelta(days=days - 1)

    rows = {
        row.day: row
        for row in db.scalars(
            select(DailyActivity).where(
                DailyActivity.user_id == user.id, DailyActivity.day >= start
            )
        ).all()
    }

    return [
        ActivityPoint(
            day=day,
            minutes=rows[day].minutes if day in rows else 0,
            concepts=rows[day].concepts_completed if day in rows else 0,
            xp=rows[day].xp_earned if day in rows else 0,
        )
        for day in (start + timedelta(days=i) for i in range(days))
    ]
