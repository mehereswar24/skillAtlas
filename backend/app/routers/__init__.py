"""API routers, aggregated under a single versioned prefix."""

from fastapi import APIRouter

from app.routers import (
    applications,
    auth,
    chat,
    community,
    companies,
    content,
    dashboard,
    interviews,
    portfolio,
    progress,
    projects,
    resume,
    reviews,
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
# Its paths sit under /companies and /reviews rather than one prefix, so it is
# a separate router rather than more routes bolted onto companies.py.
api_router.include_router(reviews.router)
# Career features. Registered here so parallel work on each never contends on
# this file; each owns only its own module.
api_router.include_router(resume.router)
api_router.include_router(applications.router)
api_router.include_router(interviews.router)
api_router.include_router(portfolio.router)

__all__ = ["api_router"]
