"""DTOs for domains, tracks and concepts."""

from pydantic import BaseModel, ConfigDict


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class DomainOut(ORMModel):
    id: int
    slug: str
    name: str
    category: str
    icon: str
    color: str
    description: str | None
    has_content: bool


class TrackSummary(ORMModel):
    id: int
    slug: str
    title: str
    target_role: str
    description: str | None
    difficulty: str
    domain_slug: str
    concept_count: int
    total_hours: int


class ResourceOut(ORMModel):
    id: int
    kind: str
    title: str
    url: str
    provider: str | None
    duration_min: int | None
    is_free: bool


class QuizOptionOut(ORMModel):
    """Deliberately omits `is_correct` — answers are graded server-side."""

    id: int
    text: str


class QuizQuestionOut(ORMModel):
    id: int
    prompt: str
    options: list[QuizOptionOut]


class InterviewQuestionOut(ORMModel):
    id: int
    question: str
    answer_md: str | None
    difficulty: str


class ConceptSummary(ORMModel):
    id: int
    slug: str
    name: str
    summary: str
    est_hours: int
    difficulty: str
    domain_slug: str


class ConceptDetail(ConceptSummary):
    content_md: str
    prerequisites: list[ConceptSummary]
    unlocks: list[ConceptSummary]
    resources: list[ResourceOut]
    quiz: list[QuizQuestionOut]
    interview_questions: list[InterviewQuestionOut]
    # Populated only for an authenticated caller.
    status: str | None = None
    is_locked: bool = False
    missing_prerequisites: list[ConceptSummary] = []


class TrackDetail(TrackSummary):
    concepts: list[ConceptSummary]
