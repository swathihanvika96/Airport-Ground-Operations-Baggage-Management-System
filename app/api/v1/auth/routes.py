from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from fastapi.security import OAuth2PasswordRequestForm

from app.api.dependencies import DB, CurrentUser, allow
from app.core.config import settings
from app.core.permissions import Permissions
from app.models.user import User
from app.repositories.user_repository import UserRepository
from app.schemas.auth import (
    ChangePasswordRequest,
    ForgotPasswordRequest,
    LoginRequest,
    OAuthLoginURL,
    RefreshRequest,
    RegisterRequest,
    ResetPasswordRequest,
    TokenResponse,
)
from app.schemas.common import Message, Page
from app.schemas.user import UserAdminCreate, UserOut, UserRoleUpdate, UserUpdateMe
from app.services.auth_service import AuthService
from app.utils.enums import UserRole
from app.utils.pagination import PageParams, page_params, paginate

router = APIRouter(prefix="/auth", tags=["Authentication"])
users_router = APIRouter(prefix="/users", tags=["User Management"])


@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def register(data: RegisterRequest, db: DB):
    """Self-registration (privileged roles such as SUPER_ADMIN must be created by an admin)."""
    return AuthService(db).register(data)


@router.post("/token", response_model=TokenResponse, summary="OAuth2 password flow (form data)")
def token(form: Annotated[OAuth2PasswordRequestForm, Depends()], db: DB):
    """Standard OAuth2 token endpoint used by Swagger's **Authorize** button.
    `username` accepts email or username."""
    return AuthService(db).authenticate(form.username, form.password)


@router.post("/login", response_model=TokenResponse, summary="Login with JSON body")
def login(data: LoginRequest, db: DB):
    return AuthService(db).authenticate(data.username, data.password)


@router.post("/refresh", response_model=TokenResponse)
def refresh(data: RefreshRequest, db: DB):
    return AuthService(db).refresh(data.refresh_token)


@router.post("/logout-all", response_model=Message)
def logout_all(user: CurrentUser, db: DB):
    """Revoke every access/refresh token issued to the current user."""
    AuthService(db).logout_all(user)
    return {"message": "All sessions revoked"}


@router.get("/me", response_model=UserOut)
def me(user: CurrentUser):
    return user


@router.patch("/me", response_model=UserOut)
def update_me(data: UserUpdateMe, user: CurrentUser, db: DB):
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(user, k, v)
    db.commit()
    return user


@router.post("/change-password", response_model=Message)
def change_password(data: ChangePasswordRequest, user: CurrentUser, db: DB):
    AuthService(db).change_password(user, data.current_password, data.new_password)
    return {"message": "Password changed. Please log in again."}


@router.post("/forgot-password", response_model=Message)
def forgot_password(data: ForgotPasswordRequest, db: DB):
    token_value = AuthService(db).forgot_password(data.email)
    resp = {"message": "If the email exists, a password reset link has been sent."}
    if settings.EXPOSE_RESET_TOKEN and token_value:
        resp["data"] = {"reset_token": token_value, "note": "Returned only because EXPOSE_RESET_TOKEN=true (dev)"}
    return resp


@router.post("/reset-password", response_model=Message)
def reset_password(data: ResetPasswordRequest, db: DB):
    AuthService(db).reset_password(data.token, data.new_password)
    return {"message": "Password has been reset. Please log in."}


# ---- OAuth2 social registration / login (Google) ----
@router.get("/oauth/google/login", response_model=OAuthLoginURL, tags=["OAuth2 (Google)"])
def google_login():
    """Returns the Google consent URL. Open it in a browser; Google redirects back to the callback."""
    return AuthService.google_authorization_url()


@router.get("/oauth/google/callback", response_model=TokenResponse, tags=["OAuth2 (Google)"])
def google_callback(db: DB, code: str = Query(...), state: str | None = Query(None)):
    """Registers the user on first login (role = OAUTH_DEFAULT_ROLE) and returns JWT tokens."""
    return AuthService(db).google_callback(code)


# ---- user administration ----
@users_router.get("", response_model=Page[UserOut])
def list_users(db: DB, _: User = allow(Permissions.USER_ADMIN), q: str | None = None,
               role: UserRole | None = None, is_active: bool | None = None,
               params: PageParams = Depends(page_params)):
    stmt = UserRepository(db).search(q, role, is_active).order_by(User.id)
    return paginate(db, stmt, params)


@users_router.post("", response_model=UserOut, status_code=201)
def create_user(data: UserAdminCreate, db: DB, actor: User = allow(Permissions.USER_ADMIN)):
    return AuthService(db).admin_create_user(data, actor)


@users_router.get("/{user_id}", response_model=UserOut)
def get_user(user_id: int, db: DB, _: User = allow(Permissions.USER_ADMIN)):
    return UserRepository(db).get_or_404(user_id)


@users_router.post("/{user_id}/activate", response_model=UserOut)
def activate_user(user_id: int, db: DB, actor: User = allow(Permissions.USER_ADMIN)):
    return AuthService(db).set_active(user_id, True, actor)


@users_router.post("/{user_id}/deactivate", response_model=UserOut)
def deactivate_user(user_id: int, db: DB, actor: User = allow(Permissions.USER_ADMIN)):
    return AuthService(db).set_active(user_id, False, actor)


@users_router.patch("/{user_id}/role", response_model=UserOut)
def change_role(user_id: int, data: UserRoleUpdate, db: DB, actor: User = allow(Permissions.USER_ADMIN)):
    return AuthService(db).change_role(user_id, data.role, actor)
