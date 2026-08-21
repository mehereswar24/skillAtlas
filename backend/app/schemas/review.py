"""DTOs for member-submitted company reviews.

These are deliberately a different shape from `schemas/company.py`. A company
profile carries `fetched_on` and every question carries a `source_url` because
it is a researched claim. A review carries an author, a rating and a date, and
nothing else — it is one person's experience, and the payload says so via
`kind="member-review"` so a client cannot accidentally render it as sourced
fact.

The author's email is never serialised. When `is_anonymous` is set the display
name is withheld too, so anonymity is a property of the response rather than
something each caller has to remember to strip.
"""

from datetime import datetime

from pydantic import BaseModel, Field

from app.models.company import INTERVIEW_OUTCOMES

OUTCOME_PATTERN = f"^({'|'.join(INTERVIEW_OUTCOMES)})$"


class ReviewAuthor(BaseModel):
    """Never includes the email. ``None`` id and name mean an anonymous post."""

    id: int | None
    display_name: str | None


class ReviewRoleRef(BaseModel):
    slug: str
    title: str


class ReviewCreate(BaseModel):
    rating: int = Field(ge=1, le=5)
    title: str = Field(min_length=4, max_length=200)
    body_md: str = Field(min_length=20, max_length=20000)
    interview_outcome: str = Field(
        default="not-interviewed", pattern=OUTCOME_PATTERN
    )
    # Bounded rather than open: a year outside living memory of the current
    # hiring process is a typo, not a review.
    interview_year: int | None = Field(default=None, ge=1990, le=2100)
    is_anonymous: bool = False
    role_slug: str | None = None


class ReviewUpdate(BaseModel):
    """Every field optional — a PATCH only changes what it names."""

    rating: int | None = Field(default=None, ge=1, le=5)
    title: str | None = Field(default=None, min_length=4, max_length=200)
    body_md: str | None = Field(default=None, min_length=20, max_length=20000)
    interview_outcome: str | None = Field(default=None, pattern=OUTCOME_PATTERN)
    interview_year: int | None = Field(default=None, ge=1990, le=2100)
    is_anonymous: bool | None = None
    role_slug: str | None = None


class ReviewOut(BaseModel):
    id: int
    # Constant discriminator. It is here so a client rendering a mixed page
    # cannot mistake this for a researched, source-cited claim.
    kind: str = "member-review"
    company_slug: str
    rating: int
    title: str
    body_md: str
    interview_outcome: str
    interview_year: int | None
    is_anonymous: bool
    # True for the seeded illustrative reviews. The UI labels these as samples
    # so they never masquerade as a real member's testimony.
    is_sample: bool
    author: ReviewAuthor
    role: ReviewRoleRef | None
    helpful_count: int
    not_helpful_count: int
    created_at: datetime
    updated_at: datetime
    viewer_is_author: bool = False
    viewer_vote: int | None = None


class RatingSummary(BaseModel):
    """Aggregate over a company's reviews.

    ``average_rating`` is ``None``, not 0, when there is nothing to average —
    "no reviews yet" and "rated zero" are different statements, and 0 is not
    even on the 1-5 scale.
    """

    review_count: int = 0
    average_rating: float | None = None
    # rating value (as a string key, so it survives JSON) -> how many reviews
    distribution: dict[str, int] = Field(
        default_factory=lambda: {str(n): 0 for n in range(1, 6)}
    )


class ReviewList(BaseModel):
    summary: RatingSummary
    reviews: list[ReviewOut]
    # Present so the client knows whether to render a write form or a sign-in
    # prompt without a second round trip.
    viewer_can_write: bool = False
    viewer_review_id: int | None = None


class ReviewVoteResult(BaseModel):
    helpful_count: int
    not_helpful_count: int
    viewer_vote: int | None
