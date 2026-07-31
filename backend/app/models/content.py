"""The knowledge graph and everything hanging off it.

This is the relational replacement for the Neo4j design: ``concepts`` are the
nodes and ``concept_prerequisites`` are the edges. Traversal happens in
``app/services/graph.py`` — the graph is a few hundred nodes, so an in-memory
adjacency map is faster and simpler than a graph database.
"""

from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    LargeBinary,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

# Resource kinds (kept as plain strings for portability across SQLite/Postgres)
RESOURCE_KINDS = ("video", "doc", "book", "course", "project", "article")


class Domain(Base):
    """A top-level area of study, e.g. 'Backend' or 'UI/UX Design'."""

    __tablename__ = "domains"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    slug: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(120))
    category: Mapped[str] = mapped_column(String(80), index=True)
    icon: Mapped[str] = mapped_column(String(60), default="BookOpen")
    color: Mapped[str] = mapped_column(String(60), default="text-primary")
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Honest flag: false means the UI shows "Coming soon" instead of a dead link.
    has_content: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)

    tracks: Mapped[list["Track"]] = relationship(back_populates="domain")
    concepts: Mapped[list["Concept"]] = relationship(back_populates="domain")


class Track(Base):
    """A goal a learner can pick, e.g. 'Become a Backend Developer'."""

    __tablename__ = "tracks"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    slug: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    title: Mapped[str] = mapped_column(String(160))
    domain_id: Mapped[int] = mapped_column(ForeignKey("domains.id", ondelete="CASCADE"))
    target_role: Mapped[str] = mapped_column(String(160))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    difficulty: Mapped[str] = mapped_column(String(20), default="beginner")
    sort_order: Mapped[int] = mapped_column(Integer, default=0)

    domain: Mapped["Domain"] = relationship(back_populates="tracks")
    track_concepts: Mapped[list["TrackConcept"]] = relationship(
        back_populates="track", cascade="all, delete-orphan"
    )


class Concept(Base):
    """A single learnable unit — a node in the knowledge graph."""

    __tablename__ = "concepts"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    slug: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(200))
    domain_id: Mapped[int] = mapped_column(ForeignKey("domains.id", ondelete="CASCADE"))
    summary: Mapped[str] = mapped_column(Text, default="")
    content_md: Mapped[str] = mapped_column(Text, default="")
    est_hours: Mapped[int] = mapped_column(Integer, default=8)
    difficulty: Mapped[str] = mapped_column(String(20), default="beginner")

    domain: Mapped["Domain"] = relationship(back_populates="concepts")
    resources: Mapped[list["Resource"]] = relationship(
        back_populates="concept", cascade="all, delete-orphan"
    )
    quiz_questions: Mapped[list["QuizQuestion"]] = relationship(
        back_populates="concept", cascade="all, delete-orphan"
    )
    interview_questions: Mapped[list["InterviewQuestion"]] = relationship(
        back_populates="concept", cascade="all, delete-orphan"
    )


class ConceptPrerequisite(Base):
    """Edge: ``concept_id`` requires ``prerequisite_id`` first."""

    __tablename__ = "concept_prerequisites"
    __table_args__ = (
        UniqueConstraint("concept_id", "prerequisite_id", name="uq_concept_prereq"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    concept_id: Mapped[int] = mapped_column(
        ForeignKey("concepts.id", ondelete="CASCADE"), index=True
    )
    prerequisite_id: Mapped[int] = mapped_column(
        ForeignKey("concepts.id", ondelete="CASCADE"), index=True
    )


class TrackConcept(Base):
    """Membership of a concept in a track, with its curated ordering."""

    __tablename__ = "track_concepts"
    __table_args__ = (
        UniqueConstraint("track_id", "concept_id", name="uq_track_concept"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    track_id: Mapped[int] = mapped_column(
        ForeignKey("tracks.id", ondelete="CASCADE"), index=True
    )
    concept_id: Mapped[int] = mapped_column(
        ForeignKey("concepts.id", ondelete="CASCADE"), index=True
    )
    is_core: Mapped[bool] = mapped_column(Boolean, default=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)

    track: Mapped["Track"] = relationship(back_populates="track_concepts")
    concept: Mapped["Concept"] = relationship()


class Resource(Base):
    """A real, linkable learning resource attached to a concept."""

    __tablename__ = "resources"

    id: Mapped[int] = mapped_column(primary_key=True)
    concept_id: Mapped[int] = mapped_column(
        ForeignKey("concepts.id", ondelete="CASCADE"), index=True
    )
    kind: Mapped[str] = mapped_column(String(20), index=True)
    title: Mapped[str] = mapped_column(String(255))
    url: Mapped[str] = mapped_column(String(600))
    provider: Mapped[str | None] = mapped_column(String(120), nullable=True)
    duration_min: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_free: Mapped[bool] = mapped_column(Boolean, default=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)

    concept: Mapped["Concept"] = relationship(back_populates="resources")


class QuizQuestion(Base):
    """Comprehension check gating 'mark complete'."""

    __tablename__ = "quiz_questions"

    id: Mapped[int] = mapped_column(primary_key=True)
    concept_id: Mapped[int] = mapped_column(
        ForeignKey("concepts.id", ondelete="CASCADE"), index=True
    )
    prompt: Mapped[str] = mapped_column(Text)
    explanation: Mapped[str | None] = mapped_column(Text, nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)

    concept: Mapped["Concept"] = relationship(back_populates="quiz_questions")
    options: Mapped[list["QuizOption"]] = relationship(
        back_populates="question", cascade="all, delete-orphan"
    )


class QuizOption(Base):
    __tablename__ = "quiz_options"

    id: Mapped[int] = mapped_column(primary_key=True)
    question_id: Mapped[int] = mapped_column(
        ForeignKey("quiz_questions.id", ondelete="CASCADE"), index=True
    )
    text: Mapped[str] = mapped_column(Text)
    is_correct: Mapped[bool] = mapped_column(Boolean, default=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)

    question: Mapped["QuizQuestion"] = relationship(back_populates="options")


class InterviewQuestion(Base):
    """The interview prep the landing page promises."""

    __tablename__ = "interview_questions"

    id: Mapped[int] = mapped_column(primary_key=True)
    concept_id: Mapped[int] = mapped_column(
        ForeignKey("concepts.id", ondelete="CASCADE"), index=True
    )
    question: Mapped[str] = mapped_column(Text)
    answer_md: Mapped[str | None] = mapped_column(Text, nullable=True)
    difficulty: Mapped[str] = mapped_column(String(20), default="medium")
    sort_order: Mapped[int] = mapped_column(Integer, default=0)

    concept: Mapped["Concept"] = relationship(back_populates="interview_questions")


class Role(Base):
    """A job role the dashboard measures readiness against."""

    __tablename__ = "roles"

    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    title: Mapped[str] = mapped_column(String(160))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    skills: Mapped[list["RoleSkill"]] = relationship(
        back_populates="role", cascade="all, delete-orphan"
    )


class RoleSkill(Base):
    """Weighted concept requirement for a role — drives readiness %."""

    __tablename__ = "role_skills"
    __table_args__ = (UniqueConstraint("role_id", "concept_id", name="uq_role_skill"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    role_id: Mapped[int] = mapped_column(
        ForeignKey("roles.id", ondelete="CASCADE"), index=True
    )
    concept_id: Mapped[int] = mapped_column(
        ForeignKey("concepts.id", ondelete="CASCADE"), index=True
    )
    weight: Mapped[float] = mapped_column(Float, default=1.0)

    role: Mapped["Role"] = relationship(back_populates="skills")
    concept: Mapped["Concept"] = relationship()


class ConceptEmbedding(Base):
    """A chunk of concept text plus its nomic-embed-text vector (float32 blob)."""

    __tablename__ = "concept_embeddings"

    id: Mapped[int] = mapped_column(primary_key=True)
    concept_id: Mapped[int] = mapped_column(
        ForeignKey("concepts.id", ondelete="CASCADE"), index=True
    )
    chunk_index: Mapped[int] = mapped_column(Integer, default=0)
    chunk_text: Mapped[str] = mapped_column(Text)
    vector: Mapped[bytes] = mapped_column(LargeBinary)
    dim: Mapped[int] = mapped_column(Integer)
    model: Mapped[str] = mapped_column(String(80))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    concept: Mapped["Concept"] = relationship()
