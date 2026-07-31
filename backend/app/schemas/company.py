"""DTOs for companies, their roles and the questions those roles ask."""

from datetime import date

from pydantic import BaseModel, ConfigDict, Field


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class CompanyResourceOut(ORMModel):
    id: int
    kind: str
    title: str
    url: str


class CompanyRoleSummary(ORMModel):
    id: int
    slug: str
    title: str
    level: str
    description: str | None
    focus_count: int
    question_count: int
    # Populated for an authenticated caller.
    readiness_percent: int | None = None


class CompanySummary(ORMModel):
    id: int
    slug: str
    name: str
    industry: str
    hq: str | None
    website: str | None
    icon: str
    description: str | None
    fetched_on: date | None
    role_count: int


class CompanyDetail(CompanySummary):
    hiring_process_md: str | None
    roles: list[CompanyRoleSummary]
    resources: list[CompanyResourceOut]


class FocusAreaOut(ORMModel):
    id: int
    label: str
    notes: str | None
    weight: float
    concept_slug: str | None
    concept_name: str | None
    # Populated for an authenticated caller.
    is_completed: bool = False
    in_roadmap: bool = False


class CompanyQuestionOut(ORMModel):
    id: int
    kind: str
    round: str
    topic: str | None
    question: str
    answer_md: str | None
    difficulty: str
    year: int | None
    source_name: str
    source_url: str


class CompanyRoleDetail(CompanyRoleSummary):
    company: CompanySummary
    focus_md: str | None
    source_url: str | None
    focus_areas: list[FocusAreaOut]
    questions: list[CompanyQuestionOut]
    # Weighted over the focus areas that map to a concept.
    readiness_percent: int = 0
    covered_weight: float = 0.0
    total_weight: float = 0.0


class AddFocusToRoadmap(BaseModel):
    """Empty by default: add every unmet focus area for the role."""

    concept_slugs: list[str] = Field(default_factory=list)
