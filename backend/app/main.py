"""SkillAtlas API entrypoint.

Run with:  uvicorn app.main:app --reload --port 8000   (from backend/)
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
from app.config import settings
from app.routers import api_router

app = FastAPI(
    title=settings.app_name,
    description="Backend for SkillAtlas — the unified learning platform.",
    version=__version__,
)

# The browser reaches this API through the Next.js BFF (same-origin), so CORS is
# only needed for local tooling. It is explicitly *not* a wildcard: credentialed
# requests and `allow_origins=["*"]` are incompatible.
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
    return {"name": settings.app_name, "version": __version__, "docs": "/docs"}


@app.get("/health", tags=["meta"])
def health_check():
    """Liveness probe. Deliberately does not touch the database."""
    return {"status": "ok", "environment": settings.environment}
