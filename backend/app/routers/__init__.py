"""API routers, aggregated under a single versioned prefix."""

from fastapi import APIRouter

from app.routers import (
    auth,
    chat,
    community,
    companies,
    content,
    dashboard,
    progress,
    projects,
    roadmaps,
)

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(auth.router)
api_router.include_router(content.router)
api_router.include_router(roadmaps.router)
api_router.include_router(progress.router)
api_router.include_router(projects.router)
api_router.include_router(companies.router)
api_router.include_router(dashboard.router)
api_router.include_router(chat.router)
api_router.include_router(community.router)

__all__ = ["api_router"]
