"""Community posts, comments and votes.

Reading is public; writing requires an account. The prototype's three
hardcoded posts and dead "New Post" button are gone.
"""

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.deps import CurrentUser, DbSession, OptionalUser
from app.models.community import CommunityComment, CommunityPost, PostVote
from app.models.content import Domain
from app.schemas.community import (
    AuthorOut,
    CommentCreate,
    CommentOut,
    DomainRef,
    PostCreate,
    PostDetail,
    PostOut,
    VoteResult,
)

router = APIRouter(prefix="/community", tags=["community"])


def _author(user) -> AuthorOut:
    return AuthorOut(id=user.id, display_name=user.display_name)


def _serialize(post: CommunityPost, voted: bool) -> PostOut:
    return PostOut(
        id=post.id,
        title=post.title,
        content=post.content,
        author=_author(post.author),
        domain=(
            DomainRef(slug=post.domain.slug, name=post.domain.name)
            if post.domain
            else None
        ),
        upvotes=post.upvotes,
        comment_count=post.comment_count,
        created_at=post.created_at,
        viewer_has_voted=voted,
    )


def _voted_post_ids(db: DbSession, user, post_ids: list[int]) -> set[int]:
    if user is None or not post_ids:
        return set()
    return set(
        db.scalars(
            select(PostVote.post_id).where(
                PostVote.user_id == user.id, PostVote.post_id.in_(post_ids)
            )
        ).all()
    )


@router.get("/posts", response_model=list[PostOut])
def list_posts(
    db: DbSession,
    user: OptionalUser,
    domain: str | None = Query(None, description="Filter by domain slug"),
    sort: str = Query("new", pattern="^(new|top)$"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    stmt = select(CommunityPost).options(
        selectinload(CommunityPost.author), selectinload(CommunityPost.domain)
    )
    if domain:
        stmt = stmt.join(Domain).where(Domain.slug == domain)
    stmt = stmt.order_by(
        CommunityPost.upvotes.desc()
        if sort == "top"
        else CommunityPost.created_at.desc()
    )

    posts = db.scalars(stmt.limit(limit).offset(offset)).unique().all()
    voted = _voted_post_ids(db, user, [p.id for p in posts])
    return [_serialize(post, post.id in voted) for post in posts]


@router.post("/posts", response_model=PostOut, status_code=status.HTTP_201_CREATED)
def create_post(payload: PostCreate, user: CurrentUser, db: DbSession):
    domain_id = None
    if payload.domain_slug:
        domain = db.scalar(select(Domain).where(Domain.slug == payload.domain_slug))
        if domain is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Unknown domain")
        domain_id = domain.id

    post = CommunityPost(
        user_id=user.id,
        title=payload.title.strip(),
        content=payload.content.strip(),
        domain_id=domain_id,
        # Counters set explicitly: column defaults only apply at INSERT, and
        # the row is serialised before the transaction commits.
        upvotes=0,
        comment_count=0,
    )
    db.add(post)
    db.commit()
    db.refresh(post)
    return _serialize(post, voted=False)


@router.get("/posts/{post_id}", response_model=PostDetail)
def get_post(post_id: int, db: DbSession, user: OptionalUser):
    post = db.scalar(
        select(CommunityPost)
        .where(CommunityPost.id == post_id)
        .options(
            selectinload(CommunityPost.author),
            selectinload(CommunityPost.domain),
            selectinload(CommunityPost.comments).selectinload(CommunityComment.author),
        )
    )
    if post is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Post not found")

    voted = bool(_voted_post_ids(db, user, [post.id]))
    return PostDetail(
        **_serialize(post, voted).model_dump(),
        comments=[
            CommentOut(
                id=comment.id,
                content=comment.content,
                author=_author(comment.author),
                created_at=comment.created_at,
            )
            for comment in post.comments
        ],
    )


@router.delete("/posts/{post_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_post(post_id: int, user: CurrentUser, db: DbSession):
    post = db.get(CommunityPost, post_id)
    # Same 404 for "missing" and "not yours", so ids cannot be probed.
    if post is None or post.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Post not found")
    db.delete(post)
    db.commit()


@router.post(
    "/posts/{post_id}/comments",
    response_model=CommentOut,
    status_code=status.HTTP_201_CREATED,
)
def add_comment(
    post_id: int, payload: CommentCreate, user: CurrentUser, db: DbSession
):
    post = db.get(CommunityPost, post_id)
    if post is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Post not found")

    comment = CommunityComment(
        post_id=post.id, user_id=user.id, content=payload.content.strip()
    )
    db.add(comment)
    post.comment_count = (post.comment_count or 0) + 1
    db.commit()
    db.refresh(comment)

    return CommentOut(
        id=comment.id,
        content=comment.content,
        author=_author(user),
        created_at=comment.created_at,
    )


@router.post("/posts/{post_id}/vote", response_model=VoteResult)
def toggle_vote(post_id: int, user: CurrentUser, db: DbSession):
    """Upvote, or remove your existing upvote. One vote per user, enforced by
    a unique constraint on (post_id, user_id)."""
    post = db.get(CommunityPost, post_id)
    if post is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Post not found")

    existing = db.scalar(
        select(PostVote).where(
            PostVote.post_id == post.id, PostVote.user_id == user.id
        )
    )
    if existing is not None:
        db.delete(existing)
        post.upvotes = max(0, (post.upvotes or 0) - 1)
        voted = False
    else:
        db.add(PostVote(post_id=post.id, user_id=user.id, value=1))
        post.upvotes = (post.upvotes or 0) + 1
        voted = True

    db.commit()
    return VoteResult(upvotes=post.upvotes, viewer_has_voted=voted)
