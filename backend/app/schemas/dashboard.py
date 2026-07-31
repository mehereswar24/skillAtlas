"""Dashboard DTOs — everything the page renders, in one response."""

from pydantic import BaseModel

from app.schemas.auth import UserOut
from app.schemas.content import ConceptSummary, TrackSummary
from app.schemas.progress import ActivityPoint, BadgeOut


class DashboardStats(BaseModel):
    concepts_completed: int
    concepts_total_in_track: int
    hours_invested: int
    xp: int
    level: int
    xp_into_level: int
    xp_for_next_level: int
    streak_days: int
    longest_streak: int
    active_days_30: int


class RoleReadinessOut(BaseModel):
    slug: str
    title: str
    description: str | None
    percent: int
    earned_weight: float
    total_weight: float


class MissingSkillOut(BaseModel):
    concept: ConceptSummary
    role_slug: str
    percent_contribution: float
    in_roadmap: bool


class DashboardOut(BaseModel):
    user: UserOut
    stats: DashboardStats
    current_track: TrackSummary | None
    roles: list[RoleReadinessOut]
    missing_skills: list[MissingSkillOut]
    velocity: list[ActivityPoint]
    badges: list[BadgeOut]
    next_up: list[ConceptSummary]
