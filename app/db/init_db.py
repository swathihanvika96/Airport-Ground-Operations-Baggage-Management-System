"""Bootstrap: optional table creation + first super admin."""
import logging

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import hash_password
from app.db.base import Base
from app.db.session import engine
from app.models.user import User
from app.repositories.user_repository import UserRepository
from app.utils.enums import AuthProvider, UserRole

logger = logging.getLogger(__name__)


def create_tables() -> None:
    import app.models  # noqa: F401  (register models)
    Base.metadata.create_all(bind=engine)


def ensure_superuser(db: Session) -> User:
    repo = UserRepository(db)
    user = repo.get_by_email(settings.FIRST_SUPERUSER_EMAIL)
    if user:
        return user
    user = repo.create(email=settings.FIRST_SUPERUSER_EMAIL.lower(), username="admin",
                       full_name=settings.FIRST_SUPERUSER_NAME,
                       hashed_password=hash_password(settings.FIRST_SUPERUSER_PASSWORD),
                       role=UserRole.SUPER_ADMIN, is_active=True, is_verified=True, auth_provider=AuthProvider.LOCAL)
    db.commit()
    logger.info("Created first super admin %s", user.email)
    return user


def init_db(db: Session) -> None:
    if settings.AUTO_CREATE_TABLES:
        create_tables()
    ensure_superuser(db)
