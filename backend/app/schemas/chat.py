"""AI tutor DTOs."""

from datetime import datetime

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    # Optional page context, e.g. the concept the learner is reading.
    concept_slug: str | None = None


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
