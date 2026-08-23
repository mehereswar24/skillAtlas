"""The behaviour that only matters once this is on the internet.

Each test here pins a control that has no visible effect in development and is
load-bearing in production: the settings guard, rate limiting, security headers
and the licence-driven content split. They are cheap, and every one of them
protects against a mistake that is silent until it is expensive.
"""

from __future__ import annotations

import pytest

from app.config import PLACEHOLDER_SECRET, Settings
from app.middleware.ratelimit import _Limiter
from app.services.publishing import DEPTH_OUTLINE, DEPTH_WRITTEN, concept_depth

REAL_SECRET = "k" * 48


# --- the production settings guard ----------------------------------------


def test_development_defaults_stay_convenient():
    """Nothing here should make a local checkout harder to run."""
    settings = Settings()
    assert settings.docs_enabled is True
    assert settings.is_production is False


def test_production_refuses_the_placeholder_signing_key():
    with pytest.raises(ValueError, match="SECRET_KEY"):
        Settings(
            environment="production", debug=False, secret_key=PLACEHOLDER_SECRET
        )


def test_production_refuses_a_short_signing_key():
    with pytest.raises(ValueError, match="SECRET_KEY"):
        Settings(environment="production", debug=False, secret_key="tooshort")


def test_production_refuses_debug():
    with pytest.raises(ValueError, match="DEBUG"):
        Settings(environment="production", debug=True, secret_key=REAL_SECRET)


def test_production_refuses_wildcard_cors():
    with pytest.raises(ValueError, match="CORS_ORIGINS"):
        Settings(
            environment="production",
            debug=False,
            secret_key=REAL_SECRET,
            cors_origins=["*"],
        )


def test_production_refuses_plaintext_origins():
    """Cookies are Secure, so a http:// origin cannot hold a session anyway."""
    with pytest.raises(ValueError, match="plaintext"):
        Settings(
            environment="production",
            debug=False,
            secret_key=REAL_SECRET,
            cors_origins=["http://app.example.com"],
        )


def test_a_correctly_configured_production_boots():
    settings = Settings(
        environment="production",
        debug=False,
        secret_key=REAL_SECRET,
        cors_origins=["https://app.example.com"],
    )
    # Docs and JSON logging follow the environment without being set.
    assert settings.docs_enabled is False
    assert settings.json_logs is True
    # Localhost is allowed through the plaintext check: it is how you smoke-test
    # a production image on the machine that built it.
    Settings(
        environment="production",
        debug=False,
        secret_key=REAL_SECRET,
        cors_origins=["http://localhost:3000"],
    )


# --- rate limiting ---------------------------------------------------------


def test_a_bucket_allows_its_burst_then_refuses():
    limiter = _Limiter(10)
    now = 1000.0
    allowed = sum(1 for _ in range(10) if limiter.check("client", now)[0])
    assert allowed == 10

    permitted, retry_after = limiter.check("client", now)
    assert permitted is False
    # The caller is told when to come back rather than being left to guess.
    assert retry_after > 0


def test_one_client_cannot_spend_another_clients_allowance():
    limiter = _Limiter(5)
    now = 1000.0
    for _ in range(5):
        limiter.check("first", now)
    assert limiter.check("first", now)[0] is False
    assert limiter.check("second", now)[0] is True


def test_a_bucket_refills_over_time():
    limiter = _Limiter(60)  # one per second
    now = 1000.0
    for _ in range(60):
        limiter.check("client", now)
    assert limiter.check("client", now)[0] is False
    # Ten seconds later, ten more are available.
    assert limiter.check("client", now + 10)[0] is True


def test_the_hourly_upload_budget_is_not_rounded_to_zero():
    """30/hour expressed as requests-per-minute would floor to 0 and lock out
    every upload. The limiter takes an explicit period for that reason."""
    limiter = _Limiter(30, 3600.0)
    now = 1000.0
    allowed = sum(1 for _ in range(40) if limiter.check("client", now)[0])
    assert allowed == 30


def test_login_is_limited_but_health_checks_are_not(client):
    from app.middleware.ratelimit import RateLimitMiddleware

    assert RateLimitMiddleware._route_class("/api/v1/auth/login") == "auth"
    assert RateLimitMiddleware._route_class("/api/v1/chat/message") == "tutor"
    assert RateLimitMiddleware._route_class("/api/v1/concepts/x") == "default"

    # The upload budget is hourly and small because ingesting a PDF is
    # expensive. It must be charged by *method*, not by path: `GET /uploads`
    # merely lists them and the résumé page reads it on every render, so
    # billing that read to the write budget exhausted the hour in about thirty
    # page views — after which /resume returned 500 instead of a page.
    assert (
        RateLimitMiddleware._route_class("/api/v1/resume/uploads", "POST") == "upload"
    )
    assert (
        RateLimitMiddleware._route_class("/api/v1/resume/uploads", "GET") == "default"
    )
    # Reads default to the cheap class even when the method is left implicit.
    assert RateLimitMiddleware._route_class("/api/v1/resume/uploads") == "default"
    # An orchestrator polls these every few seconds; limiting them would cause
    # the restart loop they exist to prevent.
    assert RateLimitMiddleware._route_class("/health") is None
    assert RateLimitMiddleware._route_class("/health/ready") is None
    assert RateLimitMiddleware._route_class("/") is None
    # "/" is exempt as an exact match only. Treating it as a prefix would
    # exempt every path in the API and make this middleware a no-op — which is
    # exactly the bug this line exists to catch.
    assert RateLimitMiddleware._route_class("/api/v1/anything") is not None


# --- security headers and probes -------------------------------------------


def test_every_response_carries_the_hardening_headers(client):
    response = client.get("/")
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    assert response.headers["referrer-policy"] == "no-referrer"
    assert "frame-ancestors 'none'" in response.headers["content-security-policy"]


def test_a_request_id_is_returned_for_correlation(client):
    response = client.get("/")
    assert response.headers.get("x-request-id")


def test_a_supplied_request_id_is_echoed_back(client):
    response = client.get("/", headers={"X-Request-ID": "abc-123"})
    assert response.headers["x-request-id"] == "abc-123"


def test_a_hostile_request_id_is_sanitised(client):
    """The value is echoed into a header and into logs, and it is attacker
    controlled, so it must not be able to carry a newline or run long."""
    response = client.get(
        "/", headers={"X-Request-ID": "bad\r\nInjected: yes" + "x" * 500}
    )
    returned = response.headers["x-request-id"]
    assert "\n" not in returned and "\r" not in returned
    assert len(returned) <= 64
    assert "Injected" not in response.headers


def test_liveness_does_not_depend_on_the_database(client):
    """Restarting a process fixes nothing when the database is down, so
    liveness must not fail with it."""
    assert client.get("/health").status_code == 200


def test_readiness_reports_the_database(client):
    response = client.get("/health/ready")
    assert response.status_code == 200
    assert response.json()["status"] == "ready"


# --- content depth and licensing -------------------------------------------


def test_outline_and_written_concepts_are_distinguishable():
    assert concept_depth("<!-- skillatlas:outline -->\n\n## Docker") == DEPTH_OUTLINE
    assert concept_depth("Real prose about databases.") == DEPTH_WRITTEN
    assert concept_depth(None) == DEPTH_WRITTEN


def test_the_api_reports_depth_so_the_ui_can_be_honest(client):
    """A learner must be able to see that an outline is an outline before
    opening it, not after."""
    written = client.get("/api/v1/concepts/system-design-introduction").json()
    assert written["depth"] == DEPTH_WRITTEN

    outline = client.get("/api/v1/concepts/kubernetes-introduction").json()
    assert outline["depth"] == DEPTH_OUTLINE
    # The skeleton survives the strip: links are what an outline is *for*.
    assert outline["resources"]


def test_no_imported_concept_still_carries_third_party_prose(db):
    """The licence check, as a test.

    Every concept outside the authored tracks must be an outline. If an import
    is re-run without stripping, this is what fails.
    """
    from sqlalchemy import select

    from app.models.content import Concept, Track, TrackConcept
    from app.services.publishing import AUTHORED_TRACK_SLUGS

    authored_ids = {
        tc.concept_id
        for track in db.scalars(
            select(Track).where(Track.slug.in_(AUTHORED_TRACK_SLUGS))
        )
        for tc in track.track_concepts
    }

    offenders = []
    for concept in db.scalars(select(Concept)):
        if concept.id in authored_ids:
            continue
        if concept_depth(concept.content_md) != DEPTH_OUTLINE:
            offenders.append(concept.slug)

    assert not offenders, (
        f"{len(offenders)} imported concepts still carry prose, e.g. "
        f"{offenders[:5]}. Run: python scripts/strip_imported_prose.py"
    )


def test_the_tutor_never_retrieves_an_outline(db):
    """An outline body is the same boilerplate in ~2,500 concepts. Retrieving
    them would let identical text crowd out the tracks that were written, and
    they can answer nothing anyway."""
    from app.services.rag import retrievable_concepts

    for concept in retrievable_concepts(db):
        assert concept_depth(concept.content_md) == DEPTH_WRITTEN, concept.slug


def test_the_limiter_returns_429_through_a_real_app(monkeypatch):
    """End-to-end, not just the bucket.

    The suite runs with RATE_LIMIT_ENABLED=false (see conftest), so this builds
    a small app around the middleware to prove the wiring: that a limited route
    actually refuses, with the status and headers a client needs to back off.
    """
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from app.middleware import ratelimit as module

    monkeypatch.setattr(module.settings, "rate_limit_enabled", True)
    monkeypatch.setattr(module.settings, "rate_limit_auth_per_minute", 3)

    app = FastAPI()
    app.add_middleware(module.RateLimitMiddleware)

    @app.post("/api/v1/auth/login")
    def login():
        return {"ok": True}

    @app.get("/health")
    def health():
        return {"ok": True}

    client = TestClient(app)

    for _ in range(3):
        assert client.post("/api/v1/auth/login").status_code == 200

    blocked = client.post("/api/v1/auth/login")
    assert blocked.status_code == 429
    # A client that reads these can pace itself instead of hammering.
    assert blocked.headers["retry-after"]
    assert blocked.json()["retry_after_seconds"] >= 1

    # The probe an orchestrator calls is never limited, however hard it polls.
    for _ in range(20):
        assert client.get("/health").status_code == 200
