"""AI tutor DTOs."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.services.tutor import (
    ANON_MAX_HISTORY_CHARS,
    ANON_MAX_HISTORY_TURNS,
    ANON_MAX_MESSAGE_CHARS,
    PageLocation,
    clean_page,
    clean_slug,
)


class PageContextIn(BaseModel):
    """Where the caller says it is.

    Slugs only, plus a page kind from a closed set. Nothing free-text: the
    helper's sense of place is resolved from our own tables in
    `app.services.tutor`, so a caller cannot describe a fictional page — or
    smuggle instructions in as a "page title".
    """

    model_config = ConfigDict(extra="forbid")

    page: str | None = Field(default=None, max_length=40)
    concept_slug: str | None = Field(default=None, max_length=120)
    company_slug: str | None = Field(default=None, max_length=120)
    role_slug: str | None = Field(default=None, max_length=120)
    project_slug: str | None = Field(default=None, max_length=120)
    track_slug: str | None = Field(default=None, max_length=120)

    def to_location(self) -> PageLocation:
        return PageLocation(
            page=clean_page(self.page),
            concept_slug=clean_slug(self.concept_slug),
            company_slug=clean_slug(self.company_slug),
            role_slug=clean_slug(self.role_slug),
            project_slug=clean_slug(self.project_slug),
            track_slug=clean_slug(self.track_slug),
        )


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    # Optional page context, e.g. the concept the learner is reading.
    concept_slug: str | None = None
    context: PageContextIn | None = None


class AnonTurn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role: Literal["user", "assistant"]
    content: str = Field(max_length=ANON_MAX_HISTORY_CHARS)


class AnonChatRequest(BaseModel):
    """The anonymous helper's request body.

    `extra="forbid"` is load-bearing, not tidiness: it is what stops an
    unauthenticated caller from slipping in `model`, `system`, `temperature` or
    `num_predict` and turning a public endpoint into a general-purpose proxy to
    somebody else's GPU.
    """

    model_config = ConfigDict(extra="forbid")

    message: str = Field(min_length=1, max_length=ANON_MAX_MESSAGE_CHARS)
    context: PageContextIn | None = None
    # The conversation lives in the visitor's tab — nothing anonymous is
    # stored server-side — so they replay it to us, capped hard.
    history: list[AnonTurn] = Field(
        default_factory=list, max_length=ANON_MAX_HISTORY_TURNS
    )


class OpeningRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    context: PageContextIn | None = None


class OpeningOut(BaseModel):
    """What the helper offers before the visitor has typed anything."""

    greeting: str
    suggestions: list[str]
    authenticated: bool


class ChatHistoryItem(BaseModel):
    id: int
    role: str
    content: str
    sources: list[str]
    created_at: datetime


class TutorStatus(BaseModel):
    available: bool
    model: str | None
    mode: str
    # So the launcher knows which endpoint to talk to without guessing from a
    # cookie it cannot read.
    authenticated: bool = False
