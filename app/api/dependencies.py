"""Shared FastAPI dependencies: DB session, OAuth2 bearer auth, current user and RBAC."""
from collections.abc import Callable, Iterable
from typing import Annotated

from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.exceptions import AuthenticationError, PermissionDeniedError
from app.core.jwt import ACCESS, decode_token
from app.db.session import get_db
from app.models.user import User
from app.utils.enums import UserRole

# OAuth2 password flow - powers the "Authorize" button in Swagger UI
oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl=f"{settings.API_V1_PREFIX}/auth/token",
    scopes={},
    description="Log in with email/username + password to obtain a JWT access token",
)

DB = Annotated[Session, Depends(get_db)]


def get_current_user(token: Annotated[str, Depends(oauth2_scheme)], db: DB) -> User:
    payload = decode_token(token, expected_type=ACCESS)
    try:
        user_id = int(payload["sub"])
    except (KeyError, ValueError) as exc:
        raise AuthenticationError("Invalid token subject") from exc
    user = db.get(User, user_id)
    if user is None:
        raise AuthenticationError("User no longer exists")
    if payload.get("ver", 0) != user.token_version:
        raise AuthenticationError("Token has been revoked; please log in again")
    if not user.is_active:
        raise AuthenticationError("Account is deactivated", code="ACCOUNT_INACTIVE")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_roles(roles: Iterable[UserRole]) -> Callable[..., User]:
    allowed = frozenset(roles) | {UserRole.SUPER_ADMIN}

    def checker(user: CurrentUser) -> User:
        if user.role not in allowed:
            raise PermissionDeniedError(
                f"Role {user.role.value} is not permitted to perform this action",
                details={"required_any_of": sorted(r.value for r in allowed)})
        return user

    return checker


def allow(roles: Iterable[UserRole]):
    """Shorthand: `user: User = allow(Permissions.X)`."""
    return Depends(require_roles(roles))
