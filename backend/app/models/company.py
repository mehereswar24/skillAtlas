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

from datetime import date

from sqlalchemy import (
    Date,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
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
