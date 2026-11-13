"""Registration, login (password + OAuth2/Google), JWT refresh, password reset, user administration."""
import secrets
from datetime import timedelta
from urllib.parse import urlencode

import httpx
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.exceptions import AuthenticationError, BusinessRuleError, ConflictError, PermissionDeniedError
from app.core.jwt import REFRESH, create_access_token, create_refresh_token, decode_token
from app.core.permissions import SELF_REGISTRATION_ROLES
from app.core.security import generate_secure_token, hash_password, hash_token, verify_password
from app.models.password_reset import PasswordResetToken
from app.models.user import User
from app.repositories.auth_repository import AuthRepository
from app.repositories.user_repository import UserRepository
from app.schemas.auth import RegisterRequest
from app.schemas.user import UserAdminCreate
from app.services.audit_service import AuditService, snapshot
from app.utils.datetime_utils import utcnow
from app.utils.enums import AuditAction, AuthProvider, UserRole

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://openidconnect.googleapis.com/v1/userinfo"


class AuthService:
    def __init__(self, db: Session):
        self.db = db
        self.users = UserRepository(db)
        self.tokens = AuthRepository(db)
        self.audit = AuditService(db)

    # ---------- tokens ----------
    @staticmethod
    def issue_tokens(user: User) -> dict:
        return {
            "access_token": create_access_token(user.id, user.role.value, user.token_version),
            "refresh_token": create_refresh_token(user.id, user.token_version),
            "token_type": "bearer",
            "expires_in": settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            "role": user.role,
        }

    # ---------- registration ----------
    def _ensure_unique(self, email: str, username: str | None) -> None:
        if self.users.get_by_email(email):
            raise ConflictError("Email is already registered")
        if username and self.users.exists(username=username):
            raise ConflictError("Username is already taken")

    def register(self, data: RegisterRequest) -> User:
        if data.role not in SELF_REGISTRATION_ROLES:
            raise PermissionDeniedError(
                f"Role {data.role.value} cannot be self-registered; ask an administrator",
                details={"allowed_roles": sorted(r.value for r in SELF_REGISTRATION_ROLES)})
        self._ensure_unique(data.email, data.username)
        user = self.users.create(
            email=data.email.lower(), username=data.username, full_name=data.full_name, phone=data.phone,
            hashed_password=hash_password(data.password), role=data.role,
            is_active=not settings.REGISTRATION_REQUIRES_APPROVAL, auth_provider=AuthProvider.LOCAL,
        )
        self.audit.log(AuditAction.USER_REGISTERED, "user", user.id, None, snapshot(user), user.id)
        self.db.commit()
        return user

    def admin_create_user(self, data: UserAdminCreate, actor: User) -> User:
        if data.role == UserRole.SUPER_ADMIN and actor.role != UserRole.SUPER_ADMIN:
            raise PermissionDeniedError("Only a super admin can create super admins")
        self._ensure_unique(data.email, data.username)
        user = self.users.create(
            email=data.email.lower(), username=data.username, full_name=data.full_name, phone=data.phone,
            hashed_password=hash_password(data.password), role=data.role, is_active=data.is_active,
            is_verified=True, auth_provider=AuthProvider.LOCAL,
        )
        self.audit.log(AuditAction.USER_REGISTERED, "user", user.id, None, snapshot(user), actor.id)
        self.db.commit()
        return user

    # ---------- login ----------
    def authenticate(self, login: str, password: str) -> dict:
        user = self.users.get_by_login(login)
        if not user or not verify_password(password, user.hashed_password):
            raise AuthenticationError("Incorrect email/username or password")
        if not user.is_active:
            raise AuthenticationError("Account is deactivated or awaiting approval", code="ACCOUNT_INACTIVE")
        return self._login(user)

    def _login(self, user: User) -> dict:
        user.last_login_at = utcnow()
        self.audit.log(AuditAction.USER_LOGIN, "user", user.id, None,
                       {"login_at": user.last_login_at, "provider": user.auth_provider}, user.id)
        self.db.commit()
        return self.issue_tokens(user)

    def refresh(self, refresh_token: str) -> dict:
        payload = decode_token(refresh_token, expected_type=REFRESH)
        user = self.users.get(int(payload["sub"]))
        if not user or not user.is_active:
            raise AuthenticationError("User not found or inactive")
        if payload.get("ver", 0) != user.token_version:
            raise AuthenticationError("Refresh token has been revoked")
        return self.issue_tokens(user)

    def logout_all(self, user: User) -> None:
        user.token_version += 1
        self.db.commit()

    # ---------- password management ----------
    def change_password(self, user: User, current: str, new: str) -> None:
        if not verify_password(current, user.hashed_password):
            raise AuthenticationError("Current password is incorrect")
        user.hashed_password = hash_password(new)
        user.token_version += 1  # revoke existing tokens
        self.audit.log(AuditAction.PASSWORD_RESET, "user", user.id, None, {"via": "change_password"}, user.id)
        self.db.commit()

    def forgot_password(self, email: str) -> str | None:
        """Create a one-time reset token. Always succeeds (no user enumeration)."""
        user = self.users.get_by_email(email)
        if not user or not user.is_active:
            return None
        self.tokens.invalidate_user_tokens(user.id)
        raw = generate_secure_token()
        self.db.add(PasswordResetToken(
            user_id=user.id, token_hash=hash_token(raw),
            expires_at=utcnow() + timedelta(minutes=settings.PASSWORD_RESET_TOKEN_EXPIRE_MINUTES)))
        self.db.commit()
        # In production this would be emailed; returned only when EXPOSE_RESET_TOKEN is enabled (dev).
        return raw

    def reset_password(self, token: str, new_password: str) -> None:
        record = self.tokens.get_valid_token(hash_token(token))
        if not record:
            raise BusinessRuleError("Reset token is invalid or has expired", code="INVALID_RESET_TOKEN")
        user = self.users.get_or_404(record.user_id)
        user.hashed_password = hash_password(new_password)
        user.token_version += 1
        record.used_at = utcnow()
        self.audit.log(AuditAction.PASSWORD_RESET, "user", user.id, None, {"via": "reset_token"}, user.id)
        self.db.commit()

    # ---------- user administration ----------
    def set_active(self, user_id: int, active: bool, actor: User) -> User:
        user = self.users.get_or_404(user_id)
        if user.id == actor.id and not active:
            raise BusinessRuleError("You cannot deactivate your own account")
        if user.role == UserRole.SUPER_ADMIN and actor.role != UserRole.SUPER_ADMIN:
            raise PermissionDeniedError("Only a super admin can change another super admin")
        prev = {"is_active": user.is_active}
        user.is_active = active
        if not active:
            user.token_version += 1
        self.audit.log(AuditAction.USER_UPDATED, "user", user.id, prev, {"is_active": active}, actor.id)
        self.db.commit()
        return user

    def change_role(self, user_id: int, role: UserRole, actor: User) -> User:
        user = self.users.get_or_404(user_id)
        if UserRole.SUPER_ADMIN in (role, user.role) and actor.role != UserRole.SUPER_ADMIN:
            raise PermissionDeniedError("Only a super admin can grant or revoke super admin")
        prev = {"role": user.role}
        user.role = role
        user.token_version += 1
        self.audit.log(AuditAction.USER_UPDATED, "user", user.id, prev, {"role": role}, actor.id)
        self.db.commit()
        return user

    # ---------- OAuth2 (Google) ----------
    @staticmethod
    def google_authorization_url() -> dict:
        if not settings.google_oauth_enabled:
            raise BusinessRuleError("Google OAuth2 is not configured (set GOOGLE_CLIENT_ID / GOOGLE_CLIENT_SECRET)",
                                    code="OAUTH_NOT_CONFIGURED")
        state = secrets.token_urlsafe(16)
        params = {
            "client_id": settings.GOOGLE_CLIENT_ID, "redirect_uri": settings.GOOGLE_REDIRECT_URI,
            "response_type": "code", "scope": "openid email profile", "state": state,
            "access_type": "offline", "prompt": "select_account",
        }
        return {"authorization_url": f"{GOOGLE_AUTH_URL}?{urlencode(params)}", "state": state}

    @staticmethod
    def _fetch_google_profile(code: str) -> dict:
        with httpx.Client(timeout=10) as client:
            token_resp = client.post(GOOGLE_TOKEN_URL, data={
                "code": code, "client_id": settings.GOOGLE_CLIENT_ID,
                "client_secret": settings.GOOGLE_CLIENT_SECRET,
                "redirect_uri": settings.GOOGLE_REDIRECT_URI, "grant_type": "authorization_code"})
            if token_resp.status_code != 200:
                raise AuthenticationError("Failed to exchange authorization code with Google")
            access = token_resp.json().get("access_token")
            info = client.get(GOOGLE_USERINFO_URL, headers={"Authorization": f"Bearer {access}"})
            if info.status_code != 200:
                raise AuthenticationError("Failed to fetch Google user profile")
            return info.json()

    def oauth_login_or_register(self, provider: AuthProvider, profile: dict) -> dict:
        """Register a new account on first OAuth2 login, link an existing email, then issue JWTs."""
        subject, email = profile.get("sub"), (profile.get("email") or "").lower()
        if not subject or not email:
            raise AuthenticationError("OAuth provider did not return a subject and email")
        if profile.get("email_verified") is False:
            raise AuthenticationError("OAuth email address is not verified")
        user = self.users.get_by_oauth(provider, subject) or self.users.get_by_email(email)
        if user is None:
            try:
                role = UserRole(settings.OAUTH_DEFAULT_ROLE)
            except ValueError:
                role = UserRole.CHECKIN_AGENT
            user = self.users.create(
                email=email, full_name=profile.get("name") or email.split("@")[0], role=role,
                auth_provider=provider, oauth_subject=subject, is_verified=True, hashed_password=None,
                is_active=not settings.REGISTRATION_REQUIRES_APPROVAL)
            self.audit.log(AuditAction.USER_REGISTERED, "user", user.id, None, snapshot(user), user.id)
        elif not user.oauth_subject:
            user.oauth_subject = subject  # link existing local account to OAuth identity
            user.is_verified = True
        if not user.is_active:
            self.db.commit()
            raise AuthenticationError("Account is deactivated or awaiting approval", code="ACCOUNT_INACTIVE")
        return self._login(user)

    def google_callback(self, code: str) -> dict:
        if not settings.google_oauth_enabled:
            raise BusinessRuleError("Google OAuth2 is not configured", code="OAUTH_NOT_CONFIGURED")
        return self.oauth_login_or_register(AuthProvider.GOOGLE, self._fetch_google_profile(code))
