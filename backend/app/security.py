"""Password hashing and JWT issuing/verification.

bcrypt is used directly rather than through passlib: passlib 1.7.4 is
unmaintained and raises ``AttributeError: module 'bcrypt' has no attribute
'__about__'`` against bcrypt >= 4.1.
"""

from datetime import datetime, timedelta, timezone
from typing import Any, Literal

import bcrypt
import jwt

from app.config import settings

TokenType = Literal["access", "refresh"]

# bcrypt hashes at most 72 bytes and raises on longer input from 4.x onward.
_BCRYPT_MAX_BYTES = 72


class TokenError(Exception):
    """Raised when a token is missing, malformed, expired or the wrong type."""


def hash_password(password: str) -> str:
    payload = password.encode("utf-8")[:_BCRYPT_MAX_BYTES]
    return bcrypt.hashpw(payload, bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(
            password.encode("utf-8")[:_BCRYPT_MAX_BYTES],
            password_hash.encode("utf-8"),
        )
    except ValueError:
        # Malformed hash in the database — treat as a failed login, not a 500.
        return False


def _create_token(subject: str | int, token_type: TokenType, expires: timedelta) -> str:
    now = datetime.now(timezone.utc)
    payload: dict[str, Any] = {
        "sub": str(subject),
        "type": token_type,
        "iat": now,
        "exp": now + expires,
    }
    return jwt.encode(payload, settings.secret_key, algorithm=settings.algorithm)


def create_access_token(user_id: int) -> str:
    return _create_token(
        user_id, "access", timedelta(minutes=settings.access_token_expire_minutes)
    )


def create_refresh_token(user_id: int) -> str:
    return _create_token(
        user_id, "refresh", timedelta(days=settings.refresh_token_expire_days)
    )


def decode_token(token: str, expected_type: TokenType = "access") -> int:
    """Return the user id encoded in ``token``, or raise ``TokenError``."""
    try:
        payload = jwt.decode(
            token, settings.secret_key, algorithms=[settings.algorithm]
        )
    except jwt.ExpiredSignatureError as exc:
        raise TokenError("Token has expired") from exc
    except jwt.PyJWTError as exc:
        raise TokenError("Invalid token") from exc

    if payload.get("type") != expected_type:
        # Refusing a refresh token at an access-token call site is what stops a
        # long-lived token being used as a session.
        raise TokenError(f"Expected a {expected_type} token")

    subject = payload.get("sub")
    if subject is None:
        raise TokenError("Token is missing a subject")
    try:
        return int(subject)
    except (TypeError, ValueError) as exc:
        raise TokenError("Token subject is not a user id") from exc
