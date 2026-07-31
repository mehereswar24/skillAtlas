"""Roadmap DTOs."""

from datetime import date, datetime

from pydantic import BaseModel, Field

from app.schemas.content import ConceptSummary, TrackSummary

# A learner picks a pace, not a number of hours. The mapping lives here so the
# label and the scheduling unit can never drift apart.
PACES: dict[str, int] = {
    "casual": 1,
    "steady": 2,
    "focused": 4,
    "intense": 6,
}


class RoadmapCreate(BaseModel):
    """Either a track slug or a free-text goal must be supplied."""

    track_slug: str | None = None
    goal: str | None = None
    # `pace` is what the UI sends; `daily_hours` remains accepted so older
    # links and the smoke script keep working.
    pace: str | None = Field(default=None, pattern="^(casual|steady|focused|intense)$")
    daily_hours: int = Field(default=2, ge=1, le=16)
    # Concepts the learner says they already know; skipped in the plan and
    # recorded as completed so readiness and unlocking stay consistent.
    known_concept_slugs: list[str] = Field(default_factory=list)

    @property
    def hours_per_day(self) -> int:
        return PACES[self.pace] if self.pace else self.daily_hours


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
    pace: str
    created_at: datetime
    total_concepts: int
    completed_concepts: int
    percent_complete: int
    # When the remaining weeks run out at this pace. Recomputed on every read,
    # so it moves as the learner gets ahead or falls behind.
    target_date: date | None
    weeks: list[RoadmapWeekOut]


class RoadmapItemUpdate(BaseModel):
    status: str = Field(pattern="^(pending|in-progress|skipped)$")


class RoadmapAppend(BaseModel):
    concept_slugs: list[str] = Field(min_length=1)
