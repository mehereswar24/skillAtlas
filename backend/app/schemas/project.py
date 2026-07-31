"""DTOs for projects, their workspaces and submissions."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.content import ConceptSummary
from app.schemas.progress import BadgeOut


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class ProjectFileOut(ORMModel):
    path: str
    content: str
    is_readonly: bool
    is_entry: bool


class ProjectTestOut(ORMModel):
    """A test the browser will run.

    ``code`` is sent even for hidden tests — the runtime executes in the
    learner's browser, so it has to be. ``is_hidden`` only tells the UI to keep
    the body collapsed until the project passes; it is a nudge against writing
    to the test, not a secret.
    """

    id: int
    name: str
    kind: str
    code: str
    expected: str | None
    is_hidden: bool


class ProjectSummary(ORMModel):
    id: int
    slug: str
    title: str
    tagline: str
    runtime: str
    difficulty: str
    est_minutes: int
    xp_reward: int
    concept_slug: str
    concept_name: str
    # Populated for an authenticated caller.
    status: str | None = None
    best_passed: int = 0


class ProjectDetail(ProjectSummary):
    brief_md: str
    concept: ConceptSummary
    files: list[ProjectFileOut]
    tests: list[ProjectTestOut]
    # Withheld until the learner has passed.
    solution_md: str | None = None
    attempts: int = 0


class SubmittedFile(BaseModel):
    path: str = Field(min_length=1, max_length=160)
    content: str = Field(max_length=200_000)


class TestResult(BaseModel):
    test_id: int
    passed: bool


class ProjectSubmit(BaseModel):
    files: list[SubmittedFile] = Field(min_length=1, max_length=40)
    results: list[TestResult] = Field(max_length=100)


class SubmissionOut(ORMModel):
    id: int
    passed_count: int
    total_count: int
    status: str
    xp_awarded: int
    attempt_no: int
    created_at: datetime


class SubmissionResult(BaseModel):
    submission: SubmissionOut
    passed: bool
    # Why a fully-green run can still be rejected.
    rejected_reason: str | None = None
    xp_earned: int
    total_xp: int
    level: int
    leveled_up: bool
    new_badges: list[BadgeOut]
    solution_md: str | None = None
