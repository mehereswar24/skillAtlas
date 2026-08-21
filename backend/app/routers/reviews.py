"""Member-submitted company reviews.

This is the one part of the companies section that is *not* researched. Every
other claim under `/companies` cites a public source and records when it was
last checked; a review cites nobody but its author. The endpoints live in their
own router, under their own `kind="member-review"` discriminator, so the two
never arrive through the same door and get rendered the same way.

Reading is public — a signed-out visitor evaluating a company should see what
members said. Writing needs an account, and one account gets one review per
company: a review is a standing opinion you edit, not a thread you post to.

Someone else's review returns 404 rather than 403 on edit and delete, matching
`community.py`: a 403 confirms the row exists, which turns the id space into an
oracle for who has reviewed where.
"""

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.deps import CurrentUser, DbSession, OptionalUser
from app.models.company import Company, CompanyReview, CompanyRole, ReviewVote
from app.schemas.review import (
    RatingSummary,
    ReviewAuthor,
    ReviewCreate,
    ReviewList,
    ReviewOut,
    ReviewRoleRef,
    ReviewUpdate,
    ReviewVoteResult,
)

router = APIRouter(tags=["reviews"])


# --------------------------------------------------------------------------
# serialisation
# --------------------------------------------------------------------------


def _author(review: CompanyReview) -> ReviewAuthor:
    """Withhold identity when the review is anonymous. The email never ships.

    Anonymity is applied here, once, rather than at each call site — a caller
    that forgets is the whole failure mode this guards against.
    """
    if review.is_anonymous or review.author is None:
        return ReviewAuthor(id=None, display_name=None)
    return ReviewAuthor(id=review.author.id, display_name=review.author.display_name)


def serialize_review(
    review: CompanyReview,
    company_slug: str,
    *,
    viewer_id: int | None = None,
    viewer_vote: int | None = None,
) -> ReviewOut:
    role = review.company_role
    return ReviewOut(
        id=review.id,
        company_slug=company_slug,
        rating=review.rating,
        title=review.title,
        body_md=review.body_md,
        interview_outcome=review.interview_outcome,
        interview_year=review.interview_year,
        is_anonymous=review.is_anonymous,
        is_sample=review.is_sample,
        author=_author(review),
        role=ReviewRoleRef(slug=role.slug, title=role.title) if role else None,
        helpful_count=review.helpful_count,
        not_helpful_count=review.not_helpful_count,
        created_at=review.created_at,
        updated_at=review.updated_at,
        # Truthful even for an anonymous review: the author is allowed to know
        # which one is theirs, and nobody else can see this flag set.
        viewer_is_author=viewer_id is not None and review.user_id == viewer_id,
        viewer_vote=viewer_vote,
    )


def rating_summary(db: DbSession, company_id: int) -> RatingSummary:
    """Average and per-star counts, computed in one grouped query.

    Aggregating in SQL rather than over loaded rows keeps this usable from the
    company detail endpoint, which does not want the review bodies at all.
    """
    rows = db.execute(
        select(CompanyReview.rating, func.count(CompanyReview.id))
        .where(CompanyReview.company_id == company_id)
        .group_by(CompanyReview.rating)
    ).all()

    distribution = {str(n): 0 for n in range(1, 6)}
    total = 0
    weighted = 0
    for rating, count in rows:
        distribution[str(rating)] = count
        total += count
        weighted += rating * count

    return RatingSummary(
        review_count=total,
        # None, not 0: "nobody has reviewed this" is not "rated zero stars",
        # and 0 is not a point on the scale.
        average_rating=round(weighted / total, 2) if total else None,
        distribution=distribution,
    )


# --------------------------------------------------------------------------
# lookups
# --------------------------------------------------------------------------


def _company(db: DbSession, slug: str) -> Company:
    company = db.scalar(select(Company).where(Company.slug == slug))
    if company is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Company not found")
    return company


def _own_review(db: DbSession, review_id: int, user_id: int) -> CompanyReview:
    """The caller's own review, or 404.

    Deliberately the same 404 for "no such review" and "not yours" — see the
    module docstring.
    """
    review = db.get(CompanyReview, review_id)
    if review is None or review.user_id != user_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Review not found")
    return review


def _resolve_role_id(db: DbSession, company_id: int, role_slug: str | None) -> int | None:
    if not role_slug:
        return None
    role = db.scalar(
        select(CompanyRole).where(
            CompanyRole.company_id == company_id, CompanyRole.slug == role_slug
        )
    )
    if role is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Unknown role for this company")
    return role.id


def _viewer_votes(db: DbSession, user, review_ids: list[int]) -> dict[int, int]:
    if user is None or not review_ids:
        return {}
    rows = db.execute(
        select(ReviewVote.review_id, ReviewVote.value).where(
            ReviewVote.user_id == user.id, ReviewVote.review_id.in_(review_ids)
        )
    ).all()
    return {review_id: value for review_id, value in rows}


# --------------------------------------------------------------------------
# reads — public
# --------------------------------------------------------------------------


@router.get("/companies/{slug}/reviews", response_model=ReviewList)
def list_company_reviews(
    slug: str,
    db: DbSession,
    user: OptionalUser,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    """Newest first, with the aggregate. Works signed out."""
    company = _company(db, slug)

    reviews = (
        db.scalars(
            select(CompanyReview)
            .where(CompanyReview.company_id == company.id)
            .options(
                selectinload(CompanyReview.author),
                selectinload(CompanyReview.company_role),
            )
            .order_by(CompanyReview.created_at.desc(), CompanyReview.id.desc())
            .limit(limit)
            .offset(offset)
        )
        .unique()
        .all()
    )

    votes = _viewer_votes(db, user, [r.id for r in reviews])
    viewer_id = user.id if user is not None else None
    mine = next((r.id for r in reviews if viewer_id and r.user_id == viewer_id), None)
    if viewer_id is not None and mine is None:
        # The caller's review may be past `limit`; the write form still needs
        # to know it exists so it offers "edit" rather than "write".
        mine = db.scalar(
            select(CompanyReview.id).where(
                CompanyReview.company_id == company.id,
                CompanyReview.user_id == viewer_id,
            )
        )

    return ReviewList(
        summary=rating_summary(db, company.id),
        reviews=[
            serialize_review(
                review,
                company.slug,
                viewer_id=viewer_id,
                viewer_vote=votes.get(review.id),
            )
            for review in reviews
        ],
        viewer_can_write=viewer_id is not None and mine is None,
        viewer_review_id=mine,
    )


# --------------------------------------------------------------------------
# writes — authenticated
# --------------------------------------------------------------------------


@router.post(
    "/companies/{slug}/reviews",
    response_model=ReviewOut,
    status_code=status.HTTP_201_CREATED,
)
def create_company_review(
    slug: str, payload: ReviewCreate, user: CurrentUser, db: DbSession
):
    company = _company(db, slug)

    existing = db.scalar(
        select(CompanyReview).where(
            CompanyReview.company_id == company.id, CompanyReview.user_id == user.id
        )
    )
    if existing is not None:
        # Checked before the insert so the caller gets this message rather than
        # a bare IntegrityError from the unique constraint behind it.
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "You have already reviewed this company — edit that review instead.",
        )

    review = CompanyReview(
        company_id=company.id,
        user_id=user.id,
        company_role_id=_resolve_role_id(db, company.id, payload.role_slug),
        rating=payload.rating,
        title=payload.title.strip(),
        body_md=payload.body_md.strip(),
        interview_outcome=payload.interview_outcome,
        interview_year=payload.interview_year,
        is_anonymous=payload.is_anonymous,
        # Only the seeder writes samples. Nothing a user submits can claim to
        # be one, and nothing they submit can shed the flag either.
        is_sample=False,
        helpful_count=0,
        not_helpful_count=0,
    )
    db.add(review)
    db.commit()
    db.refresh(review)
    return serialize_review(review, company.slug, viewer_id=user.id)


@router.patch("/reviews/{review_id}", response_model=ReviewOut)
def update_review(
    review_id: int, payload: ReviewUpdate, user: CurrentUser, db: DbSession
):
    review = _own_review(db, review_id, user.id)
    fields = payload.model_dump(exclude_unset=True)

    if "role_slug" in fields:
        review.company_role_id = _resolve_role_id(
            db, review.company_id, fields.pop("role_slug")
        )
    for key, value in fields.items():
        setattr(review, key, value.strip() if isinstance(value, str) else value)

    db.commit()
    db.refresh(review)
    return serialize_review(review, review.company.slug, viewer_id=user.id)


@router.delete("/reviews/{review_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_review(review_id: int, user: CurrentUser, db: DbSession):
    review = _own_review(db, review_id, user.id)
    db.delete(review)
    db.commit()


@router.post("/reviews/{review_id}/vote", response_model=ReviewVoteResult)
def vote_on_review(
    review_id: int,
    user: CurrentUser,
    db: DbSession,
    helpful: bool = Query(True, description="False marks the review unhelpful"),
):
    """Mark a review helpful or not. Voting the same way twice clears the vote.

    Unlike the edit endpoints this does not 404 on someone else's review —
    other people's reviews are exactly what there is to vote on. Your own is
    excluded, because a self-endorsement is not a signal.
    """
    review = db.get(CompanyReview, review_id)
    if review is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Review not found")
    if review.user_id == user.id:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "You cannot vote on your own review"
        )

    value = 1 if helpful else -1
    existing = db.scalar(
        select(ReviewVote).where(
            ReviewVote.review_id == review.id, ReviewVote.user_id == user.id
        )
    )

    if existing is None:
        db.add(ReviewVote(review_id=review.id, user_id=user.id, value=value))
        current = value
    elif existing.value == value:
        db.delete(existing)  # toggling the same way off
        current = None
    else:
        existing.value = value  # switched sides
        current = value

    # Recount from the votes table rather than nudging the counters: a nudge
    # that races or throws leaves the denormalised count permanently wrong.
    db.flush()
    counts = dict(
        db.execute(
            select(ReviewVote.value, func.count(ReviewVote.id))
            .where(ReviewVote.review_id == review.id)
            .group_by(ReviewVote.value)
        ).all()
    )
    review.helpful_count = counts.get(1, 0)
    review.not_helpful_count = counts.get(-1, 0)
    db.commit()

    return ReviewVoteResult(
        helpful_count=review.helpful_count,
        not_helpful_count=review.not_helpful_count,
        viewer_vote=current,
    )
