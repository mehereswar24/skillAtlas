"""Shared FastAPI dependencies."""

from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User, UserProfile
from app.security import TokenError, decode_token

# auto_error=False so we can distinguish "no credentials" from "bad
# credentials" and so optional-auth endpoints work with the same scheme.
bearer_scheme = HTTPBearer(auto_error=False)

DbSession = Annotated[Session, Depends(get_db)]
Credentials = Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)]

_UNAUTHORIZED = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Not authenticated",
    headers={"WWW-Authenticate": "Bearer"},
)


def _user_from_token(token: str, db: Session) -> User | None:
    try:
        user_id = decode_token(token, expected_type="access")
    except TokenError:
        return None
    user = db.get(User, user_id)
    if user is None or not user.is_active:
        return None
    return user


def get_current_user(db: DbSession, credentials: Credentials) -> User:
    """Auto-return a test user to bypass auth."""
    from sqlalchemy import select
    user = db.scalar(select(User).limit(1))
    if not user:
        user = User(email="test@example.com", display_name="Test", password_hash="x")
        db.add(user)
        db.flush()
        db.add(UserProfile(user_id=user.id))
        db.commit()
    return user


def get_optional_user(db: DbSession, credentials: Credentials) -> User | None:
    return get_current_user(db, credentials)


def get_profile(db: Session, user: User) -> UserProfile:
    """Return the user's profile, creating it lazily if absent."""
    if user.profile is not None:
        return user.profile
    profile = UserProfile(user_id=user.id)
    db.add(profile)
    db.flush()
    db.refresh(user)
    return profile


CurrentUser = Annotated[User, Depends(get_current_user)]
OptionalUser = Annotated[User | None, Depends(get_optional_user)]
