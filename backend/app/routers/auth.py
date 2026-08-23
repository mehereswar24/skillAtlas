"""Signup, login, token refresh and the current-user endpoint."""

from datetime import date

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app.config import settings
from app.deps import CurrentUser, DbSession, get_profile
from app.models.user import User, UserProfile
from app.schemas.auth import (
    AuthResponse,
    LoginRequest,
    ProfileOut,
    ProfileUpdate,
    RefreshRequest,
    SignupRequest,
    TokenPair,
    UserOut,
)
from app.schemas.roadmap import PACES
from app.security import (
    TokenError,
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.services.gamification import current_streak, level_progress

router = APIRouter(prefix="/auth", tags=["auth"])

_INVALID_CREDENTIALS = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Incorrect email or password",
)

# A real bcrypt hash of a value nobody can log in with, used to spend the same
# time on an unknown email as on a known one. Computed once at import — doing
# it per request would add a `gensalt` to every failed login for no benefit,
# and the cost that matters is the comparison, which is identical either way.
_DUMMY_HASH = hash_password("not-a-real-password-timing-equaliser")


def serialize_user(user: User, profile: UserProfile) -> UserOut:
    level, into_level, for_next = level_progress(profile.xp)
    return UserOut(
        id=user.id,
        email=user.email,
        display_name=user.display_name,
        profile=ProfileOut(
            target_goal=profile.target_goal,
            current_track_id=profile.current_track_id,
            current_track_slug=(
                profile.current_track.slug if profile.current_track else None
            ),
            pace=profile.pace,
            daily_hours=profile.daily_hours,
            target_date=profile.target_date,
            xp=profile.xp,
            level=level,
            xp_into_level=into_level,
            xp_for_next_level=for_next,
            # Report the streak as of today, so a broken streak reads as 0
            # rather than the stale value from the last active day.
            streak_days=current_streak(profile, date.today()),
            longest_streak=profile.longest_streak,
            last_active_on=profile.last_active_on,
        ),
    )


def _token_pair(user_id: int) -> TokenPair:
    return TokenPair(
        access_token=create_access_token(user_id),
        refresh_token=create_refresh_token(user_id),
        expires_in=settings.access_token_expire_minutes * 60,
    )


@router.post("/signup", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
def signup(payload: SignupRequest, db: DbSession):
    email = payload.email.lower().strip()
    if db.scalar(select(User).where(User.email == email)) is not None:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "An account with that email already exists"
        )

    user = User(
        email=email,
        password_hash=hash_password(payload.password),
        display_name=(payload.display_name or email.split("@")[0]).strip(),
    )
    db.add(user)
    db.flush()

    profile = UserProfile(user_id=user.id)
    db.add(profile)
    db.commit()
    db.refresh(user)

    tokens = _token_pair(user.id)
    return AuthResponse(**tokens.model_dump(), user=serialize_user(user, profile))


@router.post("/login", response_model=AuthResponse)
def login(payload: LoginRequest, db: DbSession):
    user = db.scalar(select(User).where(User.email == payload.email.lower().strip()))

    # Same error *and* the same work for "no such user" and "wrong password".
    # The identical error message alone was not enough: short-circuiting on
    # `user is None` skipped bcrypt entirely, so an unregistered address came
    # back in ~22ms against ~283ms for a registered one — a 12.8x gap, and a
    # reliable oracle for testing whether any given email has an account here.
    # Hashing against a dummy of the same cost keeps both paths equal.
    if user is None:
        verify_password(payload.password, _DUMMY_HASH)
        raise _INVALID_CREDENTIALS
    if not verify_password(payload.password, user.password_hash):
        raise _INVALID_CREDENTIALS
    if not user.is_active:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "This account is disabled")

    profile = get_profile(db, user)
    db.commit()

    tokens = _token_pair(user.id)
    return AuthResponse(**tokens.model_dump(), user=serialize_user(user, profile))


@router.post("/refresh", response_model=TokenPair)
def refresh(payload: RefreshRequest, db: DbSession):
    try:
        user_id = decode_token(payload.refresh_token, expected_type="refresh")
    except TokenError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, str(exc)) from exc

    user = db.get(User, user_id)
    if user is None or not user.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not authenticated")
    return _token_pair(user.id)


@router.get("/me", response_model=UserOut)
def me(user: CurrentUser, db: DbSession):
    profile = get_profile(db, user)
    db.commit()
    return serialize_user(user, profile)


@router.patch("/me", response_model=UserOut)
def update_me(payload: ProfileUpdate, user: CurrentUser, db: DbSession):
    profile = get_profile(db, user)
    if payload.display_name is not None:
        user.display_name = payload.display_name.strip()
    if payload.pace is not None:
        profile.pace = payload.pace
        profile.daily_hours = PACES[payload.pace]
    elif payload.daily_hours is not None:
        profile.daily_hours = payload.daily_hours
    if payload.target_goal is not None:
        profile.target_goal = payload.target_goal
    db.commit()
    db.refresh(user)
    return serialize_user(user, profile)
