"""Mock interview sessions and the turns inside them.

A session is drawn from `company_questions` — the same source-cited bank the
company profile shows — so a mock interview asks what the role has actually
asked rather than what a model invented.

Two things are deliberately denormalised onto these rows:

* the company/role name and slug, and
* the question text and its reference answer.

The seeder rebuilds `companies`, `company_roles` and `company_questions`
wholesale on every run, so a foreign key alone would leave last month's
attempt showing "(deleted)". A past attempt is a record of what the learner
was asked and how they answered; it has to survive a re-seed intact, and the
FKs are kept alongside (ON DELETE SET NULL) purely so a live session can still
link back to the profile it came from.
"""

from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

# Session lifecycle.
SESSION_IN_PROGRESS = "in-progress"
SESSION_COMPLETED = "completed"
SESSION_STATUSES = (SESSION_IN_PROGRESS, SESSION_COMPLETED)

# What a graded answer came out as. `ungraded` is not a failure state for the
# learner — it means no model was available to judge, and the UI says so.
VERDICT_STRONG = "strong"
VERDICT_ADEQUATE = "adequate"
VERDICT_WEAK = "weak"
VERDICT_NO_ANSWER = "no-answer"
VERDICT_UNGRADED = "ungraded"
VERDICTS = (
    VERDICT_STRONG,
    VERDICT_ADEQUATE,
    VERDICT_WEAK,
    VERDICT_NO_ANSWER,
    VERDICT_UNGRADED,
)

# A turn counts towards the session score only when a model actually judged it.
GRADED_VERDICTS = (VERDICT_STRONG, VERDICT_ADEQUATE, VERDICT_WEAK)


class InterviewSession(Base):
    """One attempt at one company role."""

    __tablename__ = "interview_sessions"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    company_role_id: Mapped[int | None] = mapped_column(
        ForeignKey("company_roles.id", ondelete="SET NULL"), nullable=True, index=True
    )

    # Snapshot of who this was for, so history reads correctly after a re-seed.
    company_slug: Mapped[str] = mapped_column(String(80), index=True)
    company_name: Mapped[str] = mapped_column(String(160))
    role_slug: Mapped[str] = mapped_column(String(80), index=True)
    role_title: Mapped[str] = mapped_column(String(160))

    status: Mapped[str] = mapped_column(
        String(20), default=SESSION_IN_PROGRESS, index=True
    )
    # Mean of the graded turns, 0-100. Null until at least one turn is graded.
    score: Mapped[float | None] = mapped_column(Float, nullable=True)
    summary_md: Mapped[str | None] = mapped_column(Text, nullable=True)
    # JSON: [{"slug": ..., "reason": ...}] — the concepts the summary sent the
    # learner back to. Stored flat rather than as a join table: it is a
    # snapshot of advice given at a point in time, not a live relationship, and
    # re-opening a finished session must not re-run retrieval to redraw it.
    recommendations_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    # True when any part of this session ran without a model behind it.
    was_degraded: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    turns: Mapped[list["InterviewTurn"]] = relationship(
        back_populates="session",
        cascade="all, delete-orphan",
        order_by="InterviewTurn.position",
    )


class InterviewTurn(Base):
    """One question in a session, plus the learner's answer and its verdict."""

    __tablename__ = "interview_turns"
    __table_args__ = (
        UniqueConstraint("session_id", "position", name="uq_interview_turn_position"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    session_id: Mapped[int] = mapped_column(
        ForeignKey("interview_sessions.id", ondelete="CASCADE"), index=True
    )
    company_question_id: Mapped[int | None] = mapped_column(
        ForeignKey("company_questions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    position: Mapped[int] = mapped_column(Integer)
    round: Mapped[str] = mapped_column(String(24), index=True)
    topic: Mapped[str | None] = mapped_column(String(120), nullable=True)
    difficulty: Mapped[str] = mapped_column(String(20), default="medium")

    # Snapshot of the question as asked, and of the reference answer it was
    # graded against — a later edit to the seed must not rewrite history.
    question: Mapped[str] = mapped_column(Text)
    reference_answer_md: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_name: Mapped[str | None] = mapped_column(String(160), nullable=True)
    source_url: Mapped[str | None] = mapped_column(String(600), nullable=True)

    answer_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    verdict: Mapped[str | None] = mapped_column(String(20), nullable=True, index=True)
    score: Mapped[float | None] = mapped_column(Float, nullable=True)
    feedback_md: Mapped[str | None] = mapped_column(Text, nullable=True)
    # What the reference answer covers that the learner did not, one per line.
    missed_points: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Set when the answer tried to address the grader rather than answer the
    # question. Surfaced to the learner instead of being silently swallowed.
    injection_flagged: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )
    answered_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    session: Mapped["InterviewSession"] = relationship(back_populates="turns")
