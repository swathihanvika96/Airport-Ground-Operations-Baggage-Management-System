from pydantic import BaseModel, EmailStr, Field, field_validator

from app.core.security import is_strong_password
from app.utils.enums import UserRole

PASSWORD_HELP = "Min 8 chars with upper, lower, digit and special character"


def _check_password(v: str) -> str:
    if not is_strong_password(v):
        raise ValueError(PASSWORD_HELP)
    return v


class RegisterRequest(BaseModel):
    email: EmailStr
    full_name: str = Field(min_length=2, max_length=150)
    password: str = Field(description=PASSWORD_HELP)
    username: str | None = Field(None, min_length=3, max_length=100, pattern=r"^[a-zA-Z0-9_.-]+$")
    phone: str | None = Field(None, max_length=30)
    role: UserRole = UserRole.CHECKIN_AGENT

    _pw = field_validator("password")(_check_password)


class LoginRequest(BaseModel):
    username: str = Field(description="Email or username")
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    role: UserRole | None = None


class RefreshRequest(BaseModel):
    refresh_token: str


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str

    _pw = field_validator("new_password")(_check_password)


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str

    _pw = field_validator("new_password")(_check_password)


class OAuthLoginURL(BaseModel):
    authorization_url: str
    state: str
