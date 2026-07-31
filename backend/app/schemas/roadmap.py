"""Roadmap DTOs."""

from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.content import ConceptSummary, TrackSummary


class RoadmapCreate(BaseModel):
    """Either a track slug or a free-text goal must be supplied."""

    track_slug: str | None = None
    goal: str | None = None
    daily_hours: int = Field(default=2, ge=1, le=16)
    # Concepts the learner says they already know; skipped in the plan and
    # recorded as completed so readiness and unlocking stay consistent.
    known_concept_slugs: list[str] = Field(default_factory=list)


class RoadmapItemOut(BaseModel):
    id: int
    concept: ConceptSummary
    week_no: int
    status: str
    is_locked: bool
    missing_prerequisites: list[str]


class RoadmapWeekOut(BaseModel):
    week_no: int
    title: str
    total_hours: int
    items: list[RoadmapItemOut]


class RoadmapOut(BaseModel):
    id: int
    track: TrackSummary
    daily_hours: int
    created_at: datetime
    total_concepts: int
    completed_concepts: int
    percent_complete: int
    weeks: list[RoadmapWeekOut]


class RoadmapItemUpdate(BaseModel):
    status: str = Field(pattern="^(pending|in-progress|skipped)$")


class RoadmapAppend(BaseModel):
    concept_slugs: list[str] = Field(min_length=1)
