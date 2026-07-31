"""Practical projects — the "now build it" half of every step.

A project hangs off exactly one concept, which is what makes it *the* project
for that roadmap step rather than a loose exercise. Its starter files, its
tests and the learner's submissions all live here.

Code runs in the learner's browser (Pyodide, a sandboxed iframe, or sql.js),
so the server never executes anything. It stores what was submitted, checks
the cheap invariants it can (``must_contain``), and awards the points once.
"""

from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

# Which in-browser runtime executes the project.
RUNTIMES = ("python", "web", "sql")

# How a single test is evaluated. Each maps to one runtime.
TEST_KINDS = ("python-assert", "dom-assert", "sql-result")

RUNTIME_FOR_TEST_KIND = {
    "python-assert": "python",
    "dom-assert": "web",
    "sql-result": "sql",
}

SUBMISSION_PASSED = "passed"
SUBMISSION_FAILED = "failed"


class Project(Base):
    """A buildable brief attached to a concept."""

    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    slug: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    concept_id: Mapped[int] = mapped_column(
        ForeignKey("concepts.id", ondelete="CASCADE"), index=True
    )
    title: Mapped[str] = mapped_column(String(200))
    tagline: Mapped[str] = mapped_column(Text, default="")
    brief_md: Mapped[str] = mapped_column(Text, default="")
    runtime: Mapped[str] = mapped_column(String(20), index=True)
    difficulty: Mapped[str] = mapped_column(String(20), default="beginner")
    est_minutes: Mapped[int] = mapped_column(Integer, default=60)
    xp_reward: Mapped[int] = mapped_column(Integer, default=100)
    # Shown only after a pass, so it cannot be used to skip the work.
    solution_md: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Newline-separated substrings the submission must contain. The only
    # server-side check available when execution happens in the browser.
    must_contain: Mapped[str | None] = mapped_column(Text, nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)

    concept = relationship("Concept", lazy="joined")
    files: Mapped[list["ProjectFile"]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
        order_by="ProjectFile.sort_order",
    )
    tests: Mapped[list["ProjectTest"]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
        order_by="ProjectTest.sort_order",
    )

    @property
    def required_snippets(self) -> list[str]:
        if not self.must_contain:
            return []
        return [line.strip() for line in self.must_contain.splitlines() if line.strip()]


class ProjectFile(Base):
    """One starter file in the workspace."""

    __tablename__ = "project_files"
    __table_args__ = (
        UniqueConstraint("project_id", "path", name="uq_project_file_path"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True
    )
    path: Mapped[str] = mapped_column(String(160))
    content: Mapped[str] = mapped_column(Text, default="")
    # Fixture data and harness files the learner should read but not edit.
    is_readonly: Mapped[bool] = mapped_column(Boolean, default=False)
    # The file the editor opens on.
    is_entry: Mapped[bool] = mapped_column(Boolean, default=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)

    project: Mapped["Project"] = relationship(back_populates="files")


class ProjectTest(Base):
    """One automated check, run in the browser against the learner's files.

    ``code`` is runtime-specific: a Python expression for ``python-assert``, a
    JavaScript expression evaluated against the rendered document for
    ``dom-assert``, and a SQL query for ``sql-result`` (whose result set is
    compared against ``expected``).
    """

    __tablename__ = "project_tests"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(200))
    kind: Mapped[str] = mapped_column(String(20))
    code: Mapped[str] = mapped_column(Text)
    expected: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Hidden tests still run in the browser, but their name is all the learner
    # sees until they pass — enough to stop them writing to the test.
    is_hidden: Mapped[bool] = mapped_column(Boolean, default=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)

    project: Mapped["Project"] = relationship(back_populates="tests")


class ProjectSubmission(Base):
    """One attempt. Kept in full so progress is auditable and resumable."""

    __tablename__ = "project_submissions"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True
    )
    files_json: Mapped[str] = mapped_column(Text)
    passed_count: Mapped[int] = mapped_column(Integer, default=0)
    total_count: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(20), default=SUBMISSION_FAILED)
    xp_awarded: Mapped[int] = mapped_column(Integer, default=0)
    attempt_no: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )

    project = relationship("Project", lazy="joined")
