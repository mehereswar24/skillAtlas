"""Portfolio DTOs.

Two families, and the split between them is the security boundary:

* ``Public*`` is what a stranger receives. There is no field on it that could
  carry an email address, a user id, or anything about work in progress — the
  omission is structural rather than a filter someone has to remember to apply.
* ``PortfolioSettings`` is the owner's view: the same profile plus every
  switch, every shipped project including the hidden ones, and a plain
  statement of what is currently public.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.portfolio import (
    HANDLE_MAX_LENGTH,
    HANDLE_MIN_LENGTH,
    HANDLE_PATTERN,
    RESERVED_HANDLES,
    normalize_handle,
)


def validate_handle(raw: str) -> str:
    """Normalise and check a handle, raising ``ValueError`` on anything unusable.

    Returns the handle with its original capitalisation intact; the caller
    stores ``normalize_handle()`` of it alongside for uniqueness.
    """
    handle = raw.strip().lstrip("@")
    if len(handle) < HANDLE_MIN_LENGTH or len(handle) > HANDLE_MAX_LENGTH:
        raise ValueError(
            f"Handles are {HANDLE_MIN_LENGTH}–{HANDLE_MAX_LENGTH} characters long."
        )
    if not HANDLE_PATTERN.match(handle):
        raise ValueError(
            "Handles may use letters, numbers, dashes and underscores, and must "
            "start and end with a letter or number."
        )
    if normalize_handle(handle) in RESERVED_HANDLES:
        raise ValueError("That handle is reserved.")
    return handle


# --------------------------------------------------------------------------
# public — everything below is served to anonymous visitors
# --------------------------------------------------------------------------


class PublicLinks(BaseModel):
    github: str | None = None
    linkedin: str | None = None
    website: str | None = None


class PublicProjectFile(BaseModel):
    """One file of the submission that passed, as the learner left it."""

    path: str
    content: str
    is_readonly: bool
    is_entry: bool


class PublicTest(BaseModel):
    """A test the visitor's browser re-runs against the embedded demo.

    Same shape the workspace already consumes, so the public page reuses the
    existing runtime harness rather than a second one.
    """

    id: int
    name: str
    kind: str
    code: str
    expected: str | None
    is_hidden: bool


class PublicProject(BaseModel):
    """A shipped project, with enough to actually run it in the page."""

    slug: str
    title: str
    tagline: str
    note: str
    runtime: str
    difficulty: str
    concept_slug: str
    concept_name: str
    xp_reward: int
    shipped_at: datetime
    tests_passed: int
    tests_total: int
    attempts: int
    # Present only when the learner opted into publishing their code. Without
    # them the card is a record of the ship, not a live demo.
    files: list[PublicProjectFile] = Field(default_factory=list)
    tests: list[PublicTest] = Field(default_factory=list)
    entry_path: str | None = None


class PublicConcept(BaseModel):
    slug: str
    name: str
    difficulty: str
    est_hours: int


class PublicTrackGroup(BaseModel):
    slug: str
    title: str
    completed: list[PublicConcept]
    track_total: int


class PublicBadge(BaseModel):
    slug: str
    name: str
    description: str | None
    icon: str
    awarded_at: datetime


class PublicReadiness(BaseModel):
    slug: str
    title: str
    percent: int


class PublicPortfolio(BaseModel):
    """The whole public page in one response.

    Note what is *not* here: no email, no user id, no in-progress concepts, no
    failed submissions. A section the learner switched off arrives empty rather
    than as a redacted placeholder, so nothing leaks by implication either.
    """

    handle: str
    display_name: str
    headline: str
    bio: str
    location: str
    links: PublicLinks
    joined_at: datetime

    projects: list[PublicProject] = Field(default_factory=list)
    tracks: list[PublicTrackGroup] = Field(default_factory=list)
    badges: list[PublicBadge] = Field(default_factory=list)
    readiness: list[PublicReadiness] = Field(default_factory=list)
    points: int | None = None
    level: int | None = None
    concepts_completed: int | None = None
    projects_shipped: int | None = None

    # True when the viewer is the owner looking at an unpublished profile.
    # Anonymous visitors never see this response at all in that state.
    is_preview: bool = False


# --------------------------------------------------------------------------
# owner-only
# --------------------------------------------------------------------------


class PortfolioVisibility(BaseModel):
    show_projects: bool = True
    show_concepts: bool = True
    show_points: bool = True
    show_badges: bool = True
    show_readiness: bool = True
    show_project_code: bool = False


class PortfolioUpdate(BaseModel):
    """Everything the owner can set. Every field optional; absent means unchanged."""

    handle: str | None = None
    display_name: str | None = Field(default=None, max_length=120)
    headline: str | None = Field(default=None, max_length=200)
    bio: str | None = Field(default=None, max_length=4000)
    location: str | None = Field(default=None, max_length=120)
    github_url: str | None = Field(default=None, max_length=300)
    linkedin_url: str | None = Field(default=None, max_length=300)
    website_url: str | None = Field(default=None, max_length=300)

    show_projects: bool | None = None
    show_concepts: bool | None = None
    show_points: bool | None = None
    show_badges: bool | None = None
    show_readiness: bool | None = None
    show_project_code: bool | None = None

    @field_validator("handle")
    @classmethod
    def _check_handle(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return validate_handle(value)

    @field_validator("github_url", "linkedin_url", "website_url")
    @classmethod
    def _check_url(cls, value: str | None) -> str | None:
        """Only http(s). A `javascript:` link on a public page is an XSS vector."""
        if value is None:
            return None
        url = value.strip()
        if not url:
            return None
        if not url.lower().startswith(("http://", "https://")):
            raise ValueError("Links must start with http:// or https://")
        return url


class ProjectVisibilityUpdate(BaseModel):
    is_visible: bool | None = None
    note: str | None = Field(default=None, max_length=1000)
    sort_order: int | None = Field(default=None, ge=0, le=999)


class OwnerProject(BaseModel):
    """One shipped project as its owner sees it — including hidden ones."""

    model_config = ConfigDict(from_attributes=True)

    project_id: int
    slug: str
    title: str
    tagline: str
    runtime: str
    concept_name: str
    shipped_at: datetime
    is_visible: bool
    note: str
    sort_order: int


class PortfolioSettings(BaseModel):
    """The owner's control panel, plus a plain answer to "what is public?"."""

    exists: bool
    handle: str | None
    display_name: str
    headline: str
    bio: str
    location: str
    github_url: str | None
    linkedin_url: str | None
    website_url: str | None
    visibility: PortfolioVisibility
    is_published: bool
    published_at: datetime | None
    public_url: str | None
    projects: list[OwnerProject] = Field(default_factory=list)
    # What a stranger would see right now, in words, so the answer never has to
    # be inferred from six switches.
    public_summary: list[str] = Field(default_factory=list)


class HandleCheck(BaseModel):
    handle: str
    available: bool
    reason: str | None = None
