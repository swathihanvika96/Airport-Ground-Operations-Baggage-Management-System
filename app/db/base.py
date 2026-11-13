"""Declarative base, mixins and column helpers."""
from datetime import datetime
from enum import Enum as PyEnum

from sqlalchemy import DateTime, Enum as SAEnum, MetaData
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from app.utils.datetime_utils import utcnow

NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)


def enum_type(enum_cls: type[PyEnum]) -> SAEnum:
    """Portable enum column stored as VARCHAR (no MySQL ENUM ALTERs needed when values change)."""
    return SAEnum(enum_cls, native_enum=False, length=40, validate_strings=True)
