"""The public learner portfolio.

A portfolio is a *derived* view: it owns no achievements of its own. Every
project, concept, point and badge it shows already lives in
``project_submissions``, ``user_progress`` and ``points_events``. What these
two tables add is the one thing that cannot be derived — the learner's consent
about what a stranger on the internet may see.

That is why the shape is "one row of switches" rather than a copy of the data:

* ``PortfolioProfile`` exists only once the learner opens the settings page.
  It starts unpublished, and stays invisible to everyone but its owner until
  ``is_published`` is explicitly flipped. Unpublishing is the same flip back,
  and takes effect on the next request because nothing is cached.
* ``PortfolioProject`` is per-project consent. A row is written only when the
  learner changes something about that project — absent means "shown, as
  submitted", which is the sensible default *inside an already-published
  profile*. It never widens what is public: a hidden project stays hidden
  whatever the profile says.

Handles are stored twice on purpose. ``handle`` keeps the capitalisation the
learner chose because it is their name; ``handle_ci`` is the lowercase form
carrying the unique index, so ``Alice`` and ``alice`` cannot both exist and a
link works whichever way it was typed.
"""

from __future__ import annotations

import re
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

HANDLE_MIN_LENGTH = 3
HANDLE_MAX_LENGTH = 30

# Letters, digits, dash and underscore; must start and end with an
# alphanumeric so a handle cannot be mistaken for a flag, a file extension or
# a trailing-punctuation typo in a pasted link.
HANDLE_PATTERN = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9_-]*[A-Za-z0-9])?$")

# Words a handle may not take. Two separate risks:
#
# 1. Shadowing: `/u/{handle}` is its own namespace today, but handles are the
#    kind of thing that gets promoted to a top-level `/{handle}` route later,
#    and by then the bad ones are already registered.
# 2. Impersonation: `support`, `security` and `billing` are the handles a
#    phisher wants, and "SkillAtlas Support asked me for my password" is not a
#    conversation worth having.
RESERVED_HANDLES = frozenset(
    {
        # platform routes, current and plausible
        "about",
        "account",
        "admin",
        "administrator",
        "api",
        "app",
        "assets",
        "auth",
        "blog",
        "careers",
        "chat",
        "community",
        "companies",
        "company",
        "concepts",
        "contact",
        "dashboard",
        "docs",
        "explore",
        "faq",
        "help",
        "home",
        "index",
        "interviews",
        "jobs",
        "legal",
        "login",
        "logout",
        "me",
        "new",
        "onboarding",
        "portfolio",
        "press",
        "pricing",
        "privacy",
        "profile",
        "projects",
        "public",
        "resume",
        "reviews",
        "roadmap",
        "roadmaps",
        "root",
        "search",
        "settings",
        "signin",
        "signout",
        "signup",
        "static",
        "status",
        "terms",
        "tracks",
        "u",
        "user",
        "users",
        # platform identity
        "billing",
        "moderator",
        "official",
        "security",
        "skillatlas",
        "staff",
        "support",
        "system",
        "team",
        # protocol-ish words that make for confusing URLs
        "favicon",
        "null",
        "robots",
        "sitemap",
        "undefined",
        "www",
    }
)


def normalize_handle(handle: str) -> str:
    """The comparison form of a handle: trimmed, lowercased, no leading ``@``."""
    return handle.strip().lstrip("@").lower()


class PortfolioProfile(Base):
    """One learner's public page, and the switches governing it."""

    __tablename__ = "portfolio_profiles"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), unique=True, index=True
    )

    # As typed, for display.
    handle: Mapped[str] = mapped_column(String(HANDLE_MAX_LENGTH))
    # Lowercased, for lookup and uniqueness.
    handle_ci: Mapped[str] = mapped_column(
        String(HANDLE_MAX_LENGTH), unique=True, index=True
    )

    # Deliberately separate from `User.display_name`: the name on a public page
    # is a publishing decision, and editing it must not rename the account.
    display_name: Mapped[str] = mapped_column(String(120), default="")
    headline: Mapped[str] = mapped_column(String(200), default="")
    bio: Mapped[str] = mapped_column(Text, default="")
    location: Mapped[str] = mapped_column(String(120), default="")

    github_url: Mapped[str | None] = mapped_column(String(300), nullable=True)
    linkedin_url: Mapped[str | None] = mapped_column(String(300), nullable=True)
    website_url: Mapped[str | None] = mapped_column(String(300), nullable=True)

    # The single gate. False (the default) means the page 404s for everyone
    # except the owner, who sees it marked as a preview.
    is_published: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False, index=True
    )
    published_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Section-level consent. Each one is an independent decision; none of them
    # matters while `is_published` is False.
    show_projects: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    show_concepts: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    show_points: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    show_badges: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    show_readiness: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    # Opt-in, unlike the rest: source code is the most revealing thing here, so
    # "embed a runnable demo" is a choice the learner makes rather than one
    # they have to notice and undo.
    show_project_code: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    user = relationship("User", lazy="joined")
    projects: Mapped[list["PortfolioProject"]] = relationship(
        back_populates="profile",
        cascade="all, delete-orphan",
        order_by="PortfolioProject.sort_order",
    )


class PortfolioProject(Base):
    """Per-project consent and presentation, for one shipped project.

    The absence of a row means "visible, no note" — the profile's own
    ``is_published`` flag is the thing that made anything public at all, so an
    untouched project inside a published profile is shown. Hiding one writes a
    row with ``is_visible`` false.
    """

    __tablename__ = "portfolio_projects"
    __table_args__ = (
        UniqueConstraint("profile_id", "project_id", name="uq_portfolio_project"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    profile_id: Mapped[int] = mapped_column(
        ForeignKey("portfolio_profiles.id", ondelete="CASCADE"), index=True
    )
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True
    )

    is_visible: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    # The learner's own words about what they built. Optional; the project's
    # tagline stands in when it is empty.
    note: Mapped[str] = mapped_column(Text, default="")
    sort_order: Mapped[int] = mapped_column(Integer, default=0)

    profile: Mapped["PortfolioProfile"] = relationship(back_populates="projects")
    project = relationship("Project", lazy="joined")
