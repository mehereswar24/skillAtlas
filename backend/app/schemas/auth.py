"""Auth and profile DTOs."""

from datetime import date

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class SignupRequest(BaseModel):
    email: EmailStr
    # 8 is the floor, not the advice. Length beats character-class rules.
    password: str = Field(min_length=8, max_length=128)
    display_name: str | None = Field(default=None, max_length=120)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class RefreshRequest(BaseModel):
    refresh_token: str


class ProfileOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    target_goal: str | None
    current_track_id: int | None
    current_track_slug: str | None = None
    daily_hours: int
    xp: int
    level: int
    xp_into_level: int = 0
    xp_for_next_level: int = 0
    streak_days: int
    longest_streak: int
    last_active_on: date | None


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: EmailStr
    display_name: str | None
    profile: ProfileOut


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int  # seconds until the access token expires


class AuthResponse(TokenPair):
    user: UserOut


class ProfileUpdate(BaseModel):
    display_name: str | None = Field(default=None, max_length=120)
    daily_hours: int | None = Field(default=None, ge=1, le=16)
    target_goal: str | None = Field(default=None, max_length=255)
