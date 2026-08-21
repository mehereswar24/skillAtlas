"""The learner's own job applications, and how each one moved.

Two rules shape this table set.

**Nothing here is fetched.** SkillAtlas does not crawl LinkedIn, Indeed, Naukri
or Glassdoor, and there is deliberately no "import from a URL" that would go and
read a listing. Every field below is typed or pasted by the learner. ``source_url``
is stored as a link for *them* to click, never as something the server retrieves.
That is a hard constraint, for the same reason the roadmap.sh licence is: it is
someone else's content, and here it is also someone else's terms of service.

**The company and role are denormalised on purpose.** Most applications will not
match one of the 30 seeded companies, and the ones that do still have to survive
`seed_all()` rebuilding `company_roles` wholesale. So ``company_name`` and
``role_title`` are always populated free text, and the foreign keys are an
optional enrichment on top — when they are set, the application can surface that
company's documented loop and that role's focus areas.
"""

from datetime import date, datetime

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

# The pipeline, in the order a hire actually happens. The last three are
# terminal: an application that reaches one of them is done moving forward,
# though the learner may still drag it back if they mistyped.
STAGE_SAVED = "saved"
STAGE_APPLIED = "applied"
STAGE_SCREEN = "screen"
STAGE_ONSITE = "onsite"
STAGE_OFFER = "offer"
STAGE_REJECTED = "rejected"
STAGE_WITHDRAWN = "withdrawn"

APPLICATION_STAGES: tuple[str, ...] = (
    STAGE_SAVED,
    STAGE_APPLIED,
    STAGE_SCREEN,
    STAGE_ONSITE,
    STAGE_OFFER,
    STAGE_REJECTED,
    STAGE_WITHDRAWN,
)

# Stages that end the pipeline. Kept out of the "active" count on the board.
TERMINAL_STAGES: tuple[str, ...] = (STAGE_OFFER, STAGE_REJECTED, STAGE_WITHDRAWN)

STAGE_LABELS: dict[str, str] = {
    STAGE_SAVED: "Saved",
    STAGE_APPLIED: "Applied",
    STAGE_SCREEN: "Screen",
    STAGE_ONSITE: "Onsite",
    STAGE_OFFER: "Offer",
    STAGE_REJECTED: "Rejected",
    STAGE_WITHDRAWN: "Withdrawn",
}

_STAGE_IN = ", ".join(f"'{stage}'" for stage in APPLICATION_STAGES)


class JobApplication(Base):
    """One application, private to the learner who created it."""

    __tablename__ = "job_applications"
    __table_args__ = (
        CheckConstraint(f"stage IN ({_STAGE_IN})", name="ck_job_application_stage"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )

    # Optional links into the seeded company set. ``SET NULL`` rather than
    # ``CASCADE``: re-seeding must never delete a learner's application.
    company_id: Mapped[int | None] = mapped_column(
        ForeignKey("companies.id", ondelete="SET NULL"), nullable=True, index=True
    )
    company_role_id: Mapped[int | None] = mapped_column(
        ForeignKey("company_roles.id", ondelete="SET NULL"), nullable=True, index=True
    )

    # Always set, linked or not — see the module docstring.
    company_name: Mapped[str] = mapped_column(String(160))
    role_title: Mapped[str] = mapped_column(String(200))

    stage: Mapped[str] = mapped_column(String(24), default=STAGE_SAVED, index=True)
    location: Mapped[str | None] = mapped_column(String(160), nullable=True)
    # Free text, not a number: "₹18 LPA", "$140-160k + equity", "not disclosed".
    # Parsing salary into a currency and a range is a data-modelling problem the
    # learner does not need us to have opinions about.
    salary_note: Mapped[str | None] = mapped_column(String(160), nullable=True)
    # A link the learner keeps for themselves. Never fetched by the server.
    source_url: Mapped[str | None] = mapped_column(String(600), nullable=True)
    # Pasted by the learner from wherever they found it.
    job_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    applied_on: Mapped[date | None] = mapped_column(Date, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    events: Mapped[list["ApplicationEvent"]] = relationship(
        back_populates="application",
        cascade="all, delete-orphan",
        order_by="ApplicationEvent.id",
    )
    company = relationship("Company", lazy="joined")
    company_role = relationship("CompanyRole", lazy="joined")


class ApplicationEvent(Base):
    """One stage move, kept so the application has a timeline.

    Rows are append-only: the current stage lives on ``JobApplication.stage``
    and this table is the history behind it. "Applied on the 3rd, screen on the
    11th, onsite on the 24th" is the thing a tracker exists to tell you, and it
    cannot be reconstructed from a single mutable column.
    """

    __tablename__ = "application_events"
    __table_args__ = (
        CheckConstraint(f"to_stage IN ({_STAGE_IN})", name="ck_application_event_stage"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    application_id: Mapped[int] = mapped_column(
        ForeignKey("job_applications.id", ondelete="CASCADE"), index=True
    )
    # Null for the row written at creation — there was no previous stage.
    from_stage: Mapped[str | None] = mapped_column(String(24), nullable=True)
    to_stage: Mapped[str] = mapped_column(String(24), index=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Defaults to now, but the learner can backdate a move they forgot to log.
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
    sort_order: Mapped[int] = mapped_column(Integer, default=0)

    application: Mapped["JobApplication"] = relationship(back_populates="events")
