"""Companies, the roles they hire for, and what those roles actually ask.

The point of this table set is the edge from a role's focus area back to a
`Concept`: "what to focus on for this job" is not prose, it is a set of nodes
in the same graph the roadmap is plotted through, so a learner can add a gap
straight to their route.

Every question carries the public source it came from. Nothing here is
mirrored from a proprietary question bank — items are written in our own words
and cite where the claim came from, and `fetched_on` records when that source
was last checked so stale data is visible rather than silently trusted.
"""

from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
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

QUESTION_KINDS = ("interview", "exam", "online-assessment")

# The stage of a hiring process a question belongs to.
ROUNDS = (
    "aptitude",
    "coding",
    "technical",
    "system-design",
    "managerial",
    "hr",
)

# How a reviewer's own run at this company ended. `not-interviewed` covers
# someone writing about working there rather than about getting hired.
INTERVIEW_OUTCOMES = (
    "offer",
    "rejected",
    "withdrew",
    "pending",
    "not-interviewed",
)


class Company(Base):
    __tablename__ = "companies"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    slug: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(160))
    industry: Mapped[str] = mapped_column(String(80), index=True)
    hq: Mapped[str | None] = mapped_column(String(160), nullable=True)
    website: Mapped[str | None] = mapped_column(String(400), nullable=True)
    # A lucide-react icon name, matching how domains are rendered.
    icon: Mapped[str] = mapped_column(String(60), default="Building2")
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    hiring_process_md: Mapped[str | None] = mapped_column(Text, nullable=True)
    fetched_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)

    roles: Mapped[list["CompanyRole"]] = relationship(
        back_populates="company",
        cascade="all, delete-orphan",
        order_by="CompanyRole.sort_order",
    )
    resources: Mapped[list["CompanyResource"]] = relationship(
        back_populates="company",
        cascade="all, delete-orphan",
        order_by="CompanyResource.sort_order",
    )
    reviews: Mapped[list["CompanyReview"]] = relationship(
        back_populates="company",
        cascade="all, delete-orphan",
        order_by="CompanyReview.created_at.desc()",
    )


class CompanyRole(Base):
    """A role at a company. ``slug`` is unique per company, not globally."""

    __tablename__ = "company_roles"
    __table_args__ = (
        UniqueConstraint("company_id", "slug", name="uq_company_role_slug"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    company_id: Mapped[int] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), index=True
    )
    # Optional link to the generic role the dashboard already measures.
    role_id: Mapped[int | None] = mapped_column(
        ForeignKey("roles.id", ondelete="SET NULL"), nullable=True
    )
    slug: Mapped[str] = mapped_column(String(80), index=True)
    title: Mapped[str] = mapped_column(String(160))
    level: Mapped[str] = mapped_column(String(40), default="entry")
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    focus_md: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_url: Mapped[str | None] = mapped_column(String(600), nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)

    company: Mapped["Company"] = relationship(back_populates="roles")
    focus_areas: Mapped[list["CompanyFocus"]] = relationship(
        back_populates="company_role",
        cascade="all, delete-orphan",
        order_by="CompanyFocus.sort_order",
    )
    questions: Mapped[list["CompanyQuestion"]] = relationship(
        back_populates="company_role",
        cascade="all, delete-orphan",
        order_by="CompanyQuestion.sort_order",
    )


class CompanyFocus(Base):
    """One thing to focus on for a role, ideally a concept in the graph."""

    __tablename__ = "company_focus_areas"

    id: Mapped[int] = mapped_column(primary_key=True)
    company_role_id: Mapped[int] = mapped_column(
        ForeignKey("company_roles.id", ondelete="CASCADE"), index=True
    )
    # Null when the focus area has no concept written for it yet — the label
    # still shows, it just is not clickable.
    concept_id: Mapped[int | None] = mapped_column(
        ForeignKey("concepts.id", ondelete="SET NULL"), nullable=True
    )
    label: Mapped[str] = mapped_column(String(200))
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    # 1-5, same scale as RoleSkill: 5 = asked in every loop.
    weight: Mapped[float] = mapped_column(Float, default=3.0)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)

    company_role: Mapped["CompanyRole"] = relationship(back_populates="focus_areas")
    concept = relationship("Concept", lazy="joined")


class CompanyQuestion(Base):
    """A question this role has actually been asked, with its source."""

    __tablename__ = "company_questions"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    company_role_id: Mapped[int] = mapped_column(
        ForeignKey("company_roles.id", ondelete="CASCADE"), index=True
    )
    kind: Mapped[str] = mapped_column(String(24), index=True)
    round: Mapped[str] = mapped_column(String(24), index=True)
    topic: Mapped[str | None] = mapped_column(String(120), nullable=True)
    question: Mapped[str] = mapped_column(Text)
    answer_md: Mapped[str | None] = mapped_column(Text, nullable=True)
    difficulty: Mapped[str] = mapped_column(String(20), default="medium")
    year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    source_name: Mapped[str] = mapped_column(String(160))
    source_url: Mapped[str] = mapped_column(String(600))
    sort_order: Mapped[int] = mapped_column(Integer, default=0)

    company_role: Mapped["CompanyRole"] = relationship(back_populates="questions")


class CompanyResource(Base):
    """An official page worth reading: careers, engineering blog, exam paper."""

    __tablename__ = "company_resources"

    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), index=True
    )
    kind: Mapped[str] = mapped_column(String(40), default="careers")
    title: Mapped[str] = mapped_column(String(255))
    url: Mapped[str] = mapped_column(String(600))
    sort_order: Mapped[int] = mapped_column(Integer, default=0)

    company: Mapped["Company"] = relationship(back_populates="resources")


# --------------------------------------------------------------------------
# member-submitted reviews
#
# Everything above this line is researched and source-cited: a `CompanyQuestion`
# cannot exist without a `source_url`, and `Company.fetched_on` says when the
# claim was last checked. A `CompanyReview` is the opposite kind of claim — one
# person's account of their own experience, unverified by us. The two are kept
# in separate tables, and the API and UI must keep saying which is which.
# --------------------------------------------------------------------------


class CompanyReview(Base):
    """One member's account of interviewing at, or working for, a company.

    One review per user per company, enforced by a unique constraint: a review
    is a standing opinion the author edits, not a thread they post to.
    """

    __tablename__ = "company_reviews"
    __table_args__ = (
        UniqueConstraint("company_id", "user_id", name="uq_company_review_author"),
        CheckConstraint("rating BETWEEN 1 AND 5", name="ck_company_review_rating"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    company_id: Mapped[int] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    # A review is usually about interviewing for one specific role, but it does
    # not have to be — and the seeder rebuilds `company_roles` wholesale, so
    # this has to survive the role row going away.
    company_role_id: Mapped[int | None] = mapped_column(
        ForeignKey("company_roles.id", ondelete="SET NULL"), nullable=True, index=True
    )

    rating: Mapped[int] = mapped_column(Integer)  # 1-5
    title: Mapped[str] = mapped_column(String(200))
    body_md: Mapped[str] = mapped_column(Text)
    interview_outcome: Mapped[str] = mapped_column(
        String(24), default="not-interviewed", index=True
    )
    interview_year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # When set, the API withholds the author's display name. It never sends the
    # email either way.
    is_anonymous: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    # Seeded illustrative content, flagged so the UI can say out loud that it is
    # a sample and not a real member's testimony.
    is_sample: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Denormalised, like CommunityPost.upvotes, so a list page needs no
    # aggregate subquery per row.
    helpful_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    not_helpful_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    company: Mapped["Company"] = relationship(back_populates="reviews")
    author = relationship("User", lazy="joined")
    company_role = relationship("CompanyRole", lazy="joined")
    votes: Mapped[list["ReviewVote"]] = relationship(
        back_populates="review", cascade="all, delete-orphan"
    )


class ReviewVote(Base):
    """One helpful/not-helpful vote per user per review, like ``PostVote``."""

    __tablename__ = "review_votes"
    __table_args__ = (
        UniqueConstraint("review_id", "user_id", name="uq_review_vote"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    review_id: Mapped[int] = mapped_column(
        ForeignKey("company_reviews.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    value: Mapped[int] = mapped_column(Integer, default=1)  # +1 helpful / -1 not
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    review: Mapped["CompanyReview"] = relationship(back_populates="votes")
