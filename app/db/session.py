"""Engine / session factory and the request-scoped DB dependency."""
from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings


def build_engine(url: str):
    if url.startswith("sqlite"):
        return create_engine(url, echo=settings.DB_ECHO, connect_args={"check_same_thread": False})
    return create_engine(
        url,
        echo=settings.DB_ECHO,
        pool_pre_ping=True,
        pool_recycle=3600,
        pool_size=settings.DB_POOL_SIZE,
        max_overflow=settings.DB_MAX_OVERFLOW,
        isolation_level="READ COMMITTED",
    )


engine = build_engine(settings.SQLALCHEMY_DATABASE_URI)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db() -> Generator[Session, None, None]:
    """One session per request. Any unhandled error rolls back the whole unit of work."""
    db = SessionLocal()
    try:
        yield db
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
