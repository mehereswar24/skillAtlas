"""Community DTOs."""

from datetime import datetime

from pydantic import BaseModel, Field


class AuthorOut(BaseModel):
    id: int
    display_name: str | None


class DomainRef(BaseModel):
    slug: str
    name: str


class PostCreate(BaseModel):
    title: str = Field(min_length=4, max_length=255)
    content: str = Field(min_length=1, max_length=20000)
    domain_slug: str | None = None


class CommentCreate(BaseModel):
    content: str = Field(min_length=1, max_length=5000)


class CommentOut(BaseModel):
    id: int
    content: str
    author: AuthorOut
    created_at: datetime


class PostOut(BaseModel):
    id: int
    title: str
    content: str
    author: AuthorOut
    domain: DomainRef | None
    upvotes: int
    comment_count: int
    created_at: datetime
    viewer_has_voted: bool


class PostDetail(PostOut):
    comments: list[CommentOut]


class VoteResult(BaseModel):
    upvotes: int
    viewer_has_voted: bool
