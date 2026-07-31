"""SQLAlchemy models.

Importing this package registers every model on ``Base.metadata`` — Alembic's
autogenerate and ``Base.metadata.create_all`` both depend on that.
"""

from app.models.assessment import (
    AssessmentOption,
    AssessmentQuestion,
    AssessmentResult,
)
from app.models.community import CommunityComment, CommunityPost, PostVote
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
    UserBadge,
    UserProgress,
    UserRoadmap,
    UserRoadmapItem,
)
from app.models.user import User, UserProfile

__all__ = [
    "AssessmentOption",
    "AssessmentQuestion",
    "AssessmentResult",
    "ChatMessage",
    "CommunityComment",
    "CommunityPost",
    "Concept",
    "ConceptEmbedding",
    "ConceptPrerequisite",
    "DailyActivity",
    "Domain",
    "InterviewQuestion",
    "PostVote",
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
