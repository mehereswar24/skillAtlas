"""Test fixtures.

Every test runs against a real, freshly-seeded SQLite database rather than
mocks — the seed content *is* the product, so exercising it is the point.
The database is built once per session and each test runs in a transaction
that is rolled back, so tests cannot see each other's writes.
"""

from __future__ import annotations

import itertools
import os
import shutil
import tempfile
from pathlib import Path

import pytest

# Point the app at a throwaway database before anything imports app.config.
# A per-process directory: SQLite in WAL mode leaves -wal and -shm sidecars, and
# a shared filename means a crashed run leaves a locked file that fails the next
# one with PermissionError on Windows.
_TMP_DIR = Path(tempfile.mkdtemp(prefix="skillatlas-test-"))
_TMP_DB = _TMP_DIR / "skillatlas_test.db"
os.environ["DATABASE_URL"] = f"sqlite:///{_TMP_DB.as_posix()}"
os.environ["SECRET_KEY"] = "test-secret-key-not-used-anywhere-real"

from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.database import Base, SessionLocal, engine, get_db  # noqa: E402
from app.main import app  # noqa: E402
from app.seed.loader import seed_all  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def _database():
    Base.metadata.create_all(engine)

    with SessionLocal() as session:
        seed_all(session, verbose=False)

    yield

    engine.dispose()
    # Remove the whole directory so the WAL sidecars go with it. Failure to
    # clean up must not fail the suite — the OS clears temp eventually.
    shutil.rmtree(_TMP_DIR, ignore_errors=True)


@pytest.fixture
def db() -> Session:
    """A session inside a transaction that is always rolled back.

    `join_transaction_mode="create_savepoint"` makes the application's own
    `commit()` calls release a SAVEPOINT rather than the outer transaction, so
    routers can commit normally and the test still leaves no trace. SQLAlchemy
    2.0 manages the savepoint lifecycle itself — the pre-2.0 `after_transaction_end`
    listener recipe actively breaks it.
    """
    connection = engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection, join_transaction_mode="create_savepoint")

    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()


@pytest.fixture
def client(db: Session) -> TestClient:
    """A TestClient whose requests share the rolled-back session."""
    app.dependency_overrides[get_db] = lambda: db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


# Module-level so generated addresses stay unique even if a test's writes
# somehow outlive its rollback — a collision would otherwise look like a
# product bug rather than a fixture bug.
_email_counter = itertools.count(1)


@pytest.fixture
def auth(client: TestClient):
    """Register a user and return (headers, user payload)."""

    def _make(email: str | None = None, password: str = "hunter2hunter2"):
        address = email or f"user{next(_email_counter)}@example.com"
        response = client.post(
            "/api/v1/auth/signup", json={"email": address, "password": password}
        )
        assert response.status_code == 201, response.text
        body = response.json()
        return {"Authorization": f"Bearer {body['access_token']}"}, body["user"]

    return _make


@pytest.fixture
def learner(client: TestClient, auth):
    """A signed-up user with a Backend Developer roadmap."""
    headers, user = auth()
    response = client.post(
        "/api/v1/roadmaps",
        json={"track_slug": "backend-developer", "daily_hours": 3},
        headers=headers,
    )
    assert response.status_code == 201, response.text
    return headers, user, response.json()


def complete_concept(client: TestClient, headers: dict, slug: str, minutes: int = 60):
    """Answer a concept's quiz correctly and complete it.

    The API never reveals the correct option up front, so this submits once to
    obtain the review and then resubmits with the right answers — which is also
    a check that a failed attempt records nothing.
    """
    detail = client.get(f"/api/v1/concepts/{slug}", headers=headers).json()
    guess = [
        {"question_id": q["id"], "option_id": q["options"][0]["id"]}
        for q in detail["quiz"]
    ]
    result = client.post(
        f"/api/v1/progress/{slug}/complete",
        json={"answers": guess, "time_spent_minutes": minutes},
        headers=headers,
    ).json()

    if not result["passed"]:
        correct = [
            {"question_id": r["question_id"], "option_id": r["correct_option_id"]}
            for r in result["review"]
        ]
        result = client.post(
            f"/api/v1/progress/{slug}/complete",
            json={"answers": correct, "time_spent_minutes": minutes},
            headers=headers,
        ).json()

    assert result["passed"], f"could not complete {slug}"
    return result
