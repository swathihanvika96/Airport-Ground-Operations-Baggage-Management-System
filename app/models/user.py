from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, enum_type
from app.utils.enums import AuthProvider, UserRole


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    username: Mapped[str | None] = mapped_column(String(100), unique=True)
    full_name: Mapped[str] = mapped_column(String(150))
    phone: Mapped[str | None] = mapped_column(String(30))
    hashed_password: Mapped[str | None] = mapped_column(String(255))  # null for OAuth-only accounts
    role: Mapped[UserRole] = mapped_column(enum_type(UserRole), default=UserRole.CHECKIN_AGENT, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    auth_provider: Mapped[AuthProvider] = mapped_column(enum_type(AuthProvider), default=AuthProvider.LOCAL)
    oauth_subject: Mapped[str | None] = mapped_column(String(255), index=True)
    token_version: Mapped[int] = mapped_column(Integer, default=0)  # bump to revoke all tokens
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime)
