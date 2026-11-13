"""JWT access / refresh token creation and validation."""
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

import jwt

from app.core.config import settings
from app.core.exceptions import AuthenticationError

ACCESS = "access"
REFRESH = "refresh"


def _create_token(subject: str, token_type: str, expires_delta: timedelta, extra: dict[str, Any] | None = None) -> str:
    now = datetime.now(timezone.utc)
    payload: dict[str, Any] = {
        "sub": str(subject),
        "type": token_type,
        "iat": now,
        "exp": now + expires_delta,
        "jti": uuid.uuid4().hex,
    }
    if extra:
        payload.update(extra)
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def create_access_token(user_id: int, role: str, token_version: int = 0) -> str:
    return _create_token(
        str(user_id), ACCESS, timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
        {"role": role, "ver": token_version},
    )


def create_refresh_token(user_id: int, token_version: int = 0) -> str:
    return _create_token(str(user_id), REFRESH, timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS), {"ver": token_version})


def decode_token(token: str, expected_type: str = ACCESS) -> dict[str, Any]:
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
    except jwt.ExpiredSignatureError as exc:
        raise AuthenticationError("Token has expired") from exc
    except jwt.InvalidTokenError as exc:
        raise AuthenticationError("Invalid token") from exc
    if payload.get("type") != expected_type:
        raise AuthenticationError(f"Invalid token type, expected {expected_type} token")
    return payload
