"""Résumés: the one the platform generates, and the one the learner uploads.

Two different kinds of data live here and they are deliberately separate.

``ResumeProfile`` is the small amount of self-reported detail a résumé needs
that the platform cannot derive — a name, a phone number, links. Everything
*else* on a generated résumé (skills, projects, hours, readiness) is read live
from ``user_progress`` and ``project_submissions`` at render time, so a
generated résumé can never drift out of step with the evidence behind it.
Nothing about a generated résumé is stored, because there is nothing to store
that is not already a fact somewhere else.

``ResumeUpload`` is the opposite: a file that came from outside. It is
personal data belonging to exactly one person, so it is scoped to its owner by
``user_id`` on every row, cascades away with the account, and the API exposes
a delete. The bytes are kept in the database rather than on disk on purpose —
an upload directory inside the repo would be picked up by the seeder, by git,
and by anything that walks the tree, and a file outside it would outlive the
row that describes it.
"""

from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    LargeBinary,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

# The three types a résumé may be uploaded as. Anything else is refused
# outright rather than sniffed at — a résumé is not an archive, a script or an
# image, and widening this list is how file-upload handling goes wrong.
ALLOWED_UPLOAD_KINDS = ("pdf", "docx", "txt")

# 2 MB. A text-layer PDF résumé is tens of kilobytes; anything approaching
# this is a scan, and a scan has no text for a parser to read anyway.
MAX_UPLOAD_BYTES = 2 * 1024 * 1024


class ResumeProfile(Base):
    """The contact block — the only part of a résumé that is self-reported.

    One row per user, created lazily the first time they fill anything in.
    """

    __tablename__ = "resume_profiles"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), unique=True, index=True
    )

    full_name: Mapped[str | None] = mapped_column(String(160), nullable=True)
    headline: Mapped[str | None] = mapped_column(String(200), nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(60), nullable=True)
    location: Mapped[str | None] = mapped_column(String(160), nullable=True)
    # One URL per line. A list column would need JSON on SQLite and an array on
    # Postgres; this stays portable and the API splits it.
    links: Mapped[str | None] = mapped_column(Text, nullable=True)
    # An override for the generated summary paragraph. NULL means "write one
    # for me from my progress".
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    user = relationship("User")


class ResumeUpload(Base):
    """One résumé file a learner uploaded, plus the text pulled out of it."""

    __tablename__ = "resume_uploads"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )

    # The name the browser sent, kept only for display. It is never used to
    # build a path, and never used to decide how the file is parsed.
    filename: Mapped[str] = mapped_column(String(255))
    # "pdf" | "docx" | "txt", decided from the bytes, not from the name.
    kind: Mapped[str] = mapped_column(String(10), index=True)
    content_type: Mapped[str] = mapped_column(String(120), default="")
    size_bytes: Mapped[int] = mapped_column(Integer, default=0)
    sha256: Mapped[str] = mapped_column(String(64), default="")

    # The original bytes, so the ATS check can be re-run against what a parser
    # would actually be handed rather than against our own extraction.
    data: Mapped[bytes] = mapped_column(LargeBinary)

    extracted_text: Mapped[str] = mapped_column(Text, default="")
    # False when the file parsed but yielded no usable text — a scanned PDF,
    # for instance. The distinction matters: it is the single most important
    # thing an ATS check can tell someone.
    extraction_ok: Mapped[bool] = mapped_column(Boolean, default=True)
    extraction_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    page_count: Mapped[int | None] = mapped_column(Integer, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )

    analyses: Mapped[list["ResumeAnalysis"]] = relationship(
        back_populates="upload",
        cascade="all, delete-orphan",
        order_by="ResumeAnalysis.created_at.desc()",
    )


class ResumeAnalysis(Base):
    """The result of analysing one upload, cached so a reload is free.

    ``degraded`` and ``generated_by`` are provenance, following the same
    contract as ``QuizQuestion``: the UI is expected to say whether a learner
    is reading model output or deterministic analysis, rather than letting one
    pass for the other.
    """

    __tablename__ = "resume_analyses"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    upload_id: Mapped[int] = mapped_column(
        ForeignKey("resume_uploads.id", ondelete="CASCADE"), index=True
    )
    # Denormalised from the upload so an ownership check never needs a join.
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )

    target_role_slug: Mapped[str | None] = mapped_column(String(80), nullable=True)
    # The whole analysis document as JSON. It is a report, not a set of
    # queryable facts, and its shape will change as the analysis improves.
    payload_json: Mapped[str] = mapped_column(Text, default="{}")

    # NULL means every word of it was computed, not generated.
    generated_by: Mapped[str | None] = mapped_column(String(80), nullable=True)
    degraded: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )

    upload: Mapped["ResumeUpload"] = relationship(back_populates="analyses")
