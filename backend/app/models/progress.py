"""Persisted roadmaps, per-concept progress, activity and badges."""

from datetime import date, datetime

from sqlalchemy import (
    Date,
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

# Progress / roadmap item statuses
STATUS_PENDING = "pending"
STATUS_IN_PROGRESS = "in-progress"
STATUS_COMPLETED = "completed"
STATUS_SKIPPED = "skipped"


class UserRoadmap(Base):
    """A generated plan. Persisting this is what makes progress meaningful."""

    __tablename__ = "user_roadmaps"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    track_id: Mapped[int] = mapped_column(ForeignKey("tracks.id", ondelete="CASCADE"))
    daily_hours: Mapped[int] = mapped_column(Integer, default=2)
    is_active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    track = relationship("Track", lazy="joined")
    items: Mapped[list["UserRoadmapItem"]] = relationship(
        back_populates="roadmap",
        cascade="all, delete-orphan",
        order_by="UserRoadmapItem.week_no, UserRoadmapItem.sort_order",
    )


class UserRoadmapItem(Base):
    __tablename__ = "user_roadmap_items"
    __table_args__ = (
        UniqueConstraint("roadmap_id", "concept_id", name="uq_roadmap_concept"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    roadmap_id: Mapped[int] = mapped_column(
        ForeignKey("user_roadmaps.id", ondelete="CASCADE"), index=True
    )
    concept_id: Mapped[int] = mapped_column(
        ForeignKey("concepts.id", ondelete="CASCADE"), index=True
    )
    week_no: Mapped[int] = mapped_column(Integer, default=1)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(20), default=STATUS_PENDING)

    roadmap: Mapped["UserRoadmap"] = relationship(back_populates="items")
    concept = relationship("Concept", lazy="joined")


class UserProgress(Base):
    """One row per (user, concept) — the source of truth for completion."""

    __tablename__ = "user_progress"
    __table_args__ = (
        UniqueConstraint("user_id", "concept_id", name="uq_user_concept_progress"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    concept_id: Mapped[int] = mapped_column(
        ForeignKey("concepts.id", ondelete="CASCADE"), index=True
    )
    status: Mapped[str] = mapped_column(String(20), default=STATUS_IN_PROGRESS)
    confidence_score: Mapped[float] = mapped_column(Float, default=1.0)
    quiz_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    time_spent_minutes: Mapped[int] = mapped_column(Integer, default=0)
    # Set when the learner declares prior knowledge during onboarding rather
    # than working through the concept here.
    source: Mapped[str] = mapped_column(String(20), default="study")
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    concept = relationship("Concept", lazy="joined")


class DailyActivity(Base):
    """Per-day rollup powering the 30-day velocity chart."""

    __tablename__ = "daily_activity"
    __table_args__ = (UniqueConstraint("user_id", "day", name="uq_user_day"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    day: Mapped[date] = mapped_column(Date, index=True)
    minutes: Mapped[int] = mapped_column(Integer, default=0)
    concepts_completed: Mapped[int] = mapped_column(Integer, default=0)
    xp_earned: Mapped[int] = mapped_column(Integer, default=0)


class UserBadge(Base):
    __tablename__ = "user_badges"
    __table_args__ = (UniqueConstraint("user_id", "badge_slug", name="uq_user_badge"),)

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    badge_slug: Mapped[str] = mapped_column(String(80), index=True)
    badge_name: Mapped[str] = mapped_column(String(160))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    icon: Mapped[str] = mapped_column(String(60), default="Trophy")
    awarded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class ChatMessage(Base):
    """AI tutor conversation history, so the thread survives a reload."""

    __tablename__ = "chat_messages"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    role: Mapped[str] = mapped_column(String(20))  # "user" | "assistant"
    content: Mapped[str] = mapped_column(Text)
    # Concept slugs the answer was grounded in, comma-separated.
    sources: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
