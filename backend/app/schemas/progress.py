"""Progress, quiz submission and gamification DTOs."""

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.content import ConceptSummary


class QuizAnswer(BaseModel):
    question_id: int
    option_id: int


class CompleteRequest(BaseModel):
    answers: list[QuizAnswer] = Field(default_factory=list)
    time_spent_minutes: int = Field(default=0, ge=0, le=24 * 60)


class QuizReview(BaseModel):
    question_id: int
    correct_option_id: int
    selected_option_id: int | None
    is_correct: bool
    explanation: str | None


class BadgeOut(BaseModel):
    """Flattens the model's `badge_slug` / `badge_name` columns to `slug` / `name`."""

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    slug: str = Field(validation_alias="badge_slug")
    name: str = Field(validation_alias="badge_name")
    description: str | None
    icon: str
    awarded_at: datetime


class CompletionResult(BaseModel):
    concept_slug: str
    quiz_score: float | None
    passed: bool
    correct_count: int
    question_count: int
    xp_earned: int
    total_xp: int
    level: int
    leveled_up: bool
    streak_days: int
    new_badges: list[BadgeOut]
    unlocked_concepts: list[ConceptSummary]
    review: list[QuizReview]


class ProgressOut(BaseModel):
    concept: ConceptSummary
    status: str
    quiz_score: float | None
    time_spent_minutes: int
    source: str
    completed_at: datetime | None


class ActivityPoint(BaseModel):
    day: date
    minutes: int
    concepts: int
    xp: int


class PointsEventOut(BaseModel):
    """One line of the points statement."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    kind: str
    ref_slug: str
    label: str
    points: int
    created_at: datetime
