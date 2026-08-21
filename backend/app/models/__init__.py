"""SQLAlchemy models.

Importing this package registers every model on ``Base.metadata`` — Alembic's
autogenerate and ``Base.metadata.create_all`` both depend on that.
"""

from app.models.application import ApplicationEvent, JobApplication
from app.models.community import CommunityComment, CommunityPost, PostVote
from app.models.company import (
    Company,
    CompanyFocus,
    CompanyQuestion,
    CompanyResource,
    CompanyReview,
    CompanyRole,
    ReviewVote,
)
from app.models.content import (
    Concept,
    ConceptEmbedding,
    ConceptPrerequisite,
    Domain,
    InterviewQuestion,
    QuizOption,
    QuizQuestion,
    Resource,
    Role,
    RoleSkill,
    Track,
    TrackConcept,
)
from app.models.interview import InterviewSession, InterviewTurn
from app.models.portfolio import PortfolioProfile, PortfolioProject
from app.models.progress import (
    ChatMessage,
    DailyActivity,
    PointsEvent,
    UserBadge,
    UserProgress,
    UserRoadmap,
    UserRoadmapItem,
)
from app.models.project import (
    Project,
    ProjectFile,
    ProjectSubmission,
    ProjectTest,
)
from app.models.resume import ResumeAnalysis, ResumeProfile, ResumeUpload
from app.models.user import User, UserProfile

__all__ = [
    "ApplicationEvent",
    "ChatMessage",
    "CommunityComment",
    "CommunityPost",
    "Company",
    "CompanyFocus",
    "CompanyQuestion",
    "CompanyResource",
    "CompanyReview",
    "CompanyRole",
    "Concept",
    "ConceptEmbedding",
    "ConceptPrerequisite",
    "DailyActivity",
    "Domain",
    "InterviewQuestion",
    "InterviewSession",
    "InterviewTurn",
    "JobApplication",
    "PointsEvent",
    "PortfolioProfile",
    "PortfolioProject",
    "PostVote",
    "Project",
    "ProjectFile",
    "ProjectSubmission",
    "ProjectTest",
    "QuizOption",
    "QuizQuestion",
    "Resource",
    "ResumeAnalysis",
    "ResumeProfile",
    "ResumeUpload",
    "ReviewVote",
    "Role",
    "RoleSkill",
    "Track",
    "TrackConcept",
    "User",
    "UserBadge",
    "UserProfile",
    "UserProgress",
    "UserRoadmap",
    "UserRoadmapItem",
]
