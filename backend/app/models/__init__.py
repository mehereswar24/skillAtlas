"""SQLAlchemy models.

Importing this package registers every model on ``Base.metadata`` — Alembic's
autogenerate and ``Base.metadata.create_all`` both depend on that.
"""

from app.models.community import CommunityComment, CommunityPost, PostVote
from app.models.company import (
    Company,
    CompanyFocus,
    CompanyQuestion,
    CompanyResource,
    CompanyRole,
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
from app.models.user import User, UserProfile

__all__ = [
    "ChatMessage",
    "CommunityComment",
    "CommunityPost",
    "Company",
    "CompanyFocus",
    "CompanyQuestion",
    "CompanyResource",
    "CompanyRole",
    "Concept",
    "ConceptEmbedding",
    "ConceptPrerequisite",
    "DailyActivity",
    "Domain",
    "InterviewQuestion",
    "PointsEvent",
    "PostVote",
    "Project",
    "ProjectFile",
    "ProjectSubmission",
    "ProjectTest",
    "QuizOption",
    "QuizQuestion",
    "Resource",
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
