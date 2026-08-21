"""Résumé DTOs.

The generated résumé and the upload analysis are both *documents*: nested,
evolving reports rather than rows. Pinning every field of them into a Pydantic
tree would freeze the analysis's shape into the API contract and force a
schema change for every new check. They are therefore typed at the top level —
the parts a client must be able to rely on — and carry their detail as open
objects underneath, which is how ``payload_json`` is stored anyway.

Everything that *is* a row (the contact block, an upload's metadata) is fully
typed, because those are stable and the client writes to them.
"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

# Long enough for a real job description; short enough that nobody is pasting a
# book into an endpoint that runs a lexicon scan over it.
MAX_JD_CHARS = 20_000


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# --------------------------------------------------------------------------
# the contact block
# --------------------------------------------------------------------------


class ResumeProfileIn(BaseModel):
    """The only self-reported part of a generated résumé."""

    full_name: str | None = Field(default=None, max_length=160)
    headline: str | None = Field(default=None, max_length=200)
    email: str | None = Field(default=None, max_length=255)
    phone: str | None = Field(default=None, max_length=60)
    location: str | None = Field(default=None, max_length=160)
    links: list[str] = Field(default_factory=list, max_length=8)
    # A summary the learner wrote. When set it is used verbatim and the model
    # is never asked for one.
    summary: str | None = Field(default=None, max_length=1200)

    @field_validator("links")
    @classmethod
    def _clean_links(cls, value: list[str]) -> list[str]:
        return [link.strip()[:400] for link in value if link and link.strip()]


class ResumeProfileOut(BaseModel):
    full_name: str | None
    headline: str | None
    email: str | None
    phone: str | None
    location: str | None
    links: list[str]
    summary: str | None
    updated_at: datetime | None


# --------------------------------------------------------------------------
# generation
# --------------------------------------------------------------------------


class ResumeGenerateIn(BaseModel):
    """Tailoring inputs. Both optional — the default is 'my best role'."""

    target_role_slug: str | None = Field(default=None, max_length=80)
    job_description: str | None = Field(default=None, max_length=MAX_JD_CHARS)
    # Off skips the model entirely, which makes the response deterministic and
    # instant. The tests rely on this so a running Ollama cannot make them flaky.
    polish: bool = True


class ResumeHeaderOut(BaseModel):
    full_name: str
    headline: str | None
    email: str | None
    phone: str | None
    location: str | None
    links: list[str]


class ResumeStatsOut(BaseModel):
    concepts_completed: int
    projects_shipped: int
    hours_invested: int
    xp: int
    level: int
    badges: int


class TargetRoleOut(BaseModel):
    slug: str
    title: str
    percent: int


class ResumeDocumentOut(BaseModel):
    generated_at: str
    header: ResumeHeaderOut
    summary: str
    # Provenance, same contract as QuizQuestion.generated_by: the UI is
    # expected to say which of the two the reader is looking at.
    summary_is_generated: bool
    generated_by: str | None
    degraded: bool

    target_role: TargetRoleOut | None
    stats: ResumeStatsOut

    skills: list[dict[str, Any]]
    projects: list[dict[str, Any]]
    badges: list[dict[str, Any]]
    readiness: list[dict[str, Any]]
    gaps: list[dict[str, Any]]
    job_match: dict[str, Any] | None


# --------------------------------------------------------------------------
# job-description diff
# --------------------------------------------------------------------------


class JobMatchIn(BaseModel):
    job_description: str = Field(min_length=20, max_length=MAX_JD_CHARS)
    target_role_slug: str | None = Field(default=None, max_length=80)


class JobMatchOut(BaseModel):
    coverage_percent: int
    requirements_found: int
    matched: list[dict[str, Any]]
    missing: list[dict[str, Any]]
    # Exactly the payload `POST /roadmaps/current/items` expects, so the gap
    # list is one click from being on the learner's route.
    addable_slugs: list[str]
    unmatched_terms: list[str]


# --------------------------------------------------------------------------
# uploads
# --------------------------------------------------------------------------


class ResumeUploadInline(BaseModel):
    """A base64 upload.

    The browser cannot reach the multipart endpoint: the Next.js BFF proxy
    reads request bodies as text, which mangles binary. Rather than change a
    shared proxy that four features route through, the page sends base64 JSON
    and this endpoint decodes it. Identical validation either way — the bytes
    end up in the same function.
    """

    filename: str = Field(min_length=1, max_length=255)
    content_base64: str = Field(min_length=1)
    content_type: str = Field(default="", max_length=120)


class ResumeUploadOut(ORMModel):
    id: int
    filename: str
    kind: str
    size_bytes: int
    extraction_ok: bool
    extraction_note: str | None
    page_count: int | None
    text_chars: int
    created_at: datetime
    has_analysis: bool


class ResumeAnalyseIn(BaseModel):
    target_role_slug: str | None = Field(default=None, max_length=80)
    job_description: str | None = Field(default=None, max_length=MAX_JD_CHARS)
    # Re-run rather than serving the cached report.
    refresh: bool = False


class ResumeAnalysisOut(BaseModel):
    id: int | None
    upload_id: int
    created_at: datetime | None
    degraded: bool
    generated_by: str | None
    degraded_reason: str | None

    extraction: dict[str, Any]
    ats: dict[str, Any]
    suggestions: list[dict[str, Any]]
    rewrites: list[dict[str, Any]]
    detected_skills: list[dict[str, Any]]
    career_options: list[dict[str, Any]]
    companies: list[dict[str, Any]]
    learn_next: list[dict[str, Any]]
    addable_slugs: list[str]
    job_match: dict[str, Any] | None
    target_role: TargetRoleOut | None
    generated_at: str


class ResumeStatusOut(BaseModel):
    """Whether the language-shaped parts are available, before you commit."""

    available: bool
    model: str | None
    mode: str
    max_upload_mb: float
    accepted_kinds: list[str]
