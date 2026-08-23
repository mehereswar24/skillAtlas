"""SkillAtlas API entrypoint.

Development:  uvicorn app.main:app --reload --port 8010   (from backend/)
Production:   see deploy/ — gunicorn with uvicorn workers, behind the Next BFF.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app import __version__
from app.config import settings
from app.database import engine
from app.middleware import (
    RateLimitMiddleware,
    RequestLogMiddleware,
    SecurityHeadersMiddleware,
)
from app.middleware.logging import configure_logging
from app.routers import api_router

configure_logging()

app = FastAPI(
    title=settings.app_name,
    description="Backend for SkillAtlas — the unified learning platform.",
    version=__version__,
    # Interactive docs publish every request schema. Off in production unless
    # ENABLE_DOCS says otherwise; see Settings.docs_enabled.
    docs_url="/docs" if settings.docs_enabled else None,
    redoc_url="/redoc" if settings.docs_enabled else None,
    openapi_url="/openapi.json" if settings.docs_enabled else None,
)

# Middleware runs in reverse registration order, so the last one added is the
# outermost. The order below is deliberate:
#   1. logging outermost — it must see every request, including ones the rate
#      limiter rejects, and it is what turns an unhandled exception into a 500
#      rather than a dropped connection.
#   2. rate limiting next — cheap rejection before any real work happens.
#   3. security headers innermost of the three, so they are attached to
#      whatever response comes back, 429s and 500s included.
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(RateLimitMiddleware)
app.add_middleware(RequestLogMiddleware)

# The browser reaches this API through the Next.js BFF (same-origin), so CORS is
# only needed for local tooling. It is explicitly *not* a wildcard: credentialed
# requests and `allow_origins=["*"]` are incompatible, and the production guard
# in app/config.py refuses to start if one is configured.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)


@app.get("/", tags=["meta"])
def read_root():
    return {
        "name": settings.app_name,
        "version": __version__,
        "docs": "/docs" if settings.docs_enabled else None,
    }


@app.get("/health", tags=["meta"])
def health_check():
    """Liveness probe. Deliberately does not touch the database.

    Liveness answers "is this process wedged", and the honest answer when the
    database is down is *no* — the process is fine and restarting it fixes
    nothing. Tying liveness to the database is how a brief database blip
    becomes an orchestrator restart-looping every replica.
    """
    return {"status": "ok", "environment": settings.environment}


@app.get("/health/ready", tags=["meta"])
def readiness_check():
    """Readiness probe. Fails when this instance cannot serve traffic.

    This one *does* touch the database, because an instance that cannot reach
    it should be taken out of the load balancer rotation — which is exactly
    what readiness means, and exactly what liveness must not do.
    """
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except Exception as exc:  # noqa: BLE001 - reported, not handled
        return JSONResponse(
            status_code=503,
            content={"status": "unavailable", "database": type(exc).__name__},
        )
    return {"status": "ready"}
