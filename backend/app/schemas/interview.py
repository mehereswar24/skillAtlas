"""DTOs for mock interview sessions."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class InterviewStatus(BaseModel):
    """Whether answers can be graded, so the UI can set expectations up front."""

    available: bool
    model: str | None = None
    mode: str  # "graded" | "ungraded"


class RoundOption(BaseModel):
    name: str
    label: str
    question_count: int


class InterviewRoleOption(BaseModel):
    """A role that has enough questions for a session to be worth running."""

    company_slug: str
    company_name: str
    company_icon: str
    role_slug: str
    role_title: str
    level: str
    question_count: int
    rounds: list[RoundOption]
    # Populated for an authenticated caller.
    attempts: int = 0
    best_score: float | None = None


class StartSessionRequest(BaseModel):
    company_slug: str
    role_slug: str
    question_count: int = Field(default=5, ge=1, le=10)
    # Empty means "the whole loop".
    rounds: list[str] = Field(default_factory=list)


class AnswerRequest(BaseModel):
    # Bounded because it goes into a model prompt; the service truncates too.
    answer: str = Field(default="", max_length=20000)


class TurnOut(BaseModel):
    id: int
    position: int
    round: str
    round_label: str
    topic: str | None
    difficulty: str
    question: str
    source_name: str | None
    source_url: str | None

    answer_text: str | None = None
    verdict: str | None = None
    score: float | None = None
    feedback_md: str | None = None
    missed_points: list[str] = Field(default_factory=list)
    injection_flagged: bool = False
    answered_at: datetime | None = None
    # Withheld until the turn has been answered — otherwise the reference
    # answer is sitting in the page source of the question being asked.
    reference_answer_md: str | None = None


class ConceptSuggestionOut(BaseModel):
    slug: str
    name: str
    summary: str
    reason: str
    is_completed: bool = False
    in_roadmap: bool = False


class SessionSummaryOut(BaseModel):
    score: float | None
    graded_count: int
    answered_count: int
    question_count: int
    strengths: list[str]
    weak_areas: list[str]
    recommended_concepts: list[ConceptSuggestionOut]
    summary_md: str
    degraded: bool


class SessionRow(BaseModel):
    """One past attempt, for the history list."""

    id: int
    company_slug: str
    company_name: str
    role_slug: str
    role_title: str
    status: str
    score: float | None
    question_count: int
    answered_count: int
    was_degraded: bool
    created_at: datetime
    completed_at: datetime | None


class SessionOut(SessionRow):
    turns: list[TurnOut]
    summary: SessionSummaryOut | None = None
    # False when Ollama is unreachable right now; the session still runs.
    grading_available: bool = True
