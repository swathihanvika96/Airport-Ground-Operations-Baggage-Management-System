from datetime import datetime

from pydantic import BaseModel, EmailStr, Field

from app.schemas.common import ORMModel
from app.utils.enums import AuthProvider, UserRole


class UserOut(ORMModel):
    id: int
    email: str
    username: str | None
    full_name: str
    phone: str | None
    role: UserRole
    is_active: bool
    is_verified: bool
    auth_provider: AuthProvider
    last_login_at: datetime | None
    created_at: datetime


class UserUpdateMe(BaseModel):
    full_name: str | None = Field(None, min_length=2, max_length=150)
    phone: str | None = Field(None, max_length=30)


class UserAdminCreate(BaseModel):
    email: EmailStr
    full_name: str = Field(min_length=2, max_length=150)
    password: str = Field(min_length=8)
    username: str | None = None
    phone: str | None = None
    role: UserRole
    is_active: bool = True


class UserRoleUpdate(BaseModel):
    role: UserRole
