"""DTOs for the job tracker.

Note what is absent: there is no "import from URL" payload anywhere in this
module. The learner pastes a job description; the server never fetches one.
"""

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.application import APPLICATION_STAGES, STAGE_SAVED

# The stage vocabulary lives on the model; the API validates against it rather
# than restating it, so adding a stage is a one-file change.
_STAGE_PATTERN = f"^({'|'.join(APPLICATION_STAGES)})$"


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class StageInfo(BaseModel):
    """One column of the board, in pipeline order."""

    value: str
    label: str
    is_terminal: bool


class CompanyRef(BaseModel):
    slug: str
    name: str
    icon: str


class CompanyRoleRef(BaseModel):
    slug: str
    title: str
    level: str


# --------------------------------------------------------------------------
# writes
# --------------------------------------------------------------------------


class ApplicationCreate(BaseModel):
    """Create an application.

    Either name the company and role as free text, or point at one of the
    seeded companies with ``company_slug`` (+ optionally ``company_role_slug``)
    and let the labels be filled in from it. Most applications will be the
    former — the seeded set is 30 companies, and the learner applies wherever
    they like.
    """

    company_name: str | None = Field(None, max_length=160)
    role_title: str | None = Field(None, max_length=200)
    company_slug: str | None = Field(None, max_length=80)
    company_role_slug: str | None = Field(None, max_length=80)

    stage: str = Field(STAGE_SAVED, pattern=_STAGE_PATTERN)
    location: str | None = Field(None, max_length=160)
    salary_note: str | None = Field(None, max_length=160)
    source_url: str | None = Field(None, max_length=600)
    job_description: str | None = Field(None, max_length=60000)
    notes: str | None = Field(None, max_length=20000)
    applied_on: date | None = None

    @model_validator(mode="after")
    def _needs_an_identity(self):
        if not self.company_slug and not (self.company_name or "").strip():
            raise ValueError("Give a company name, or link a seeded company")
        if not self.company_role_slug and not (self.role_title or "").strip():
            raise ValueError("Give a role title, or link a seeded role")
        if self.company_role_slug and not self.company_slug:
            raise ValueError("company_role_slug needs company_slug")
        return self


class ApplicationUpdate(BaseModel):
    """Edit the details. Stage moves go through ``POST /{id}/stage`` instead, so
    that every move lands in the timeline rather than silently overwriting it."""

    company_name: str | None = Field(None, max_length=160)
    role_title: str | None = Field(None, max_length=200)
    location: str | None = Field(None, max_length=160)
    salary_note: str | None = Field(None, max_length=160)
    source_url: str | None = Field(None, max_length=600)
    job_description: str | None = Field(None, max_length=60000)
    notes: str | None = Field(None, max_length=20000)
    applied_on: date | None = None
    # Explicitly clear the company/role link. `None` means "leave alone", which
    # is why unlinking needs its own flag rather than sending nulls.
    unlink_company: bool = False


class StageMove(BaseModel):
    stage: str = Field(pattern=_STAGE_PATTERN)
    note: str | None = Field(None, max_length=2000)
    # The learner may log a move they forgot about at the time.
    occurred_at: datetime | None = None


# --------------------------------------------------------------------------
# reads
# --------------------------------------------------------------------------


class ApplicationEventOut(ORMModel):
    id: int
    from_stage: str | None
    to_stage: str
    note: str | None
    occurred_at: datetime


class ApplicationOut(ORMModel):
    id: int
    company_name: str
    role_title: str
    stage: str
    location: str | None
    salary_note: str | None
    source_url: str | None
    applied_on: date | None
    has_job_description: bool
    has_notes: bool
    company: CompanyRef | None
    company_role: CompanyRoleRef | None
    created_at: datetime
    updated_at: datetime
    # When the application last moved, so the board can show "12 days in screen".
    last_moved_at: datetime | None = None


class MissingConcept(BaseModel):
    """A gap between the learner and this role, worth a concrete amount."""

    slug: str
    name: str
    weight: float
    # Percentage points this concept would add to the role's readiness.
    adds_percent: float
    is_in_roadmap: bool = False


class FocusAreaOut(BaseModel):
    label: str
    notes: str | None
    weight: float
    concept_slug: str | None
    concept_name: str | None
    is_completed: bool


class ApplicationPrep(BaseModel):
    """What we actually know about this employer's process.

    Only present when the application is linked to a seeded company. Everything
    in here is the researched, source-dated company data — none of it is
    inferred from the pasted job description.
    """

    company: CompanyRef
    company_role: CompanyRoleRef | None
    # The documented loop, verbatim from the company profile.
    hiring_process_md: str | None
    fetched_on: date | None
    focus_md: str | None
    focus_areas: list[FocusAreaOut] = Field(default_factory=list)
    # Readiness over the focus areas that map to a concept.
    focus_readiness_percent: int = 0
    # Readiness against the generic role this one maps to, from the same
    # service the dashboard uses. Null when the seed did not map it.
    role_readiness_percent: int | None = None
    role_slug: str | None = None
    missing: list[MissingConcept] = Field(default_factory=list)
    question_count: int = 0


class ApplicationDetail(ApplicationOut):
    job_description: str | None
    notes: str | None
    events: list[ApplicationEventOut]
    prep: ApplicationPrep | None = None


class BoardColumn(BaseModel):
    stage: str
    label: str
    is_terminal: bool
    applications: list[ApplicationOut]


class ApplicationBoard(BaseModel):
    columns: list[BoardColumn]
    total: int
    active: int
