"""Shared schema building blocks."""
from datetime import datetime
from typing import Annotated, Any, Generic, TypeVar

from pydantic import AfterValidator, BaseModel, ConfigDict, StringConstraints

from app.utils.datetime_utils import to_naive_utc

T = TypeVar("T")

# Any incoming datetime (tz-aware or naive) is normalised to naive UTC for MySQL DATETIME columns.
UTCDateTime = Annotated[datetime, AfterValidator(to_naive_utc)]
UpperStr = Annotated[str, StringConstraints(strip_whitespace=True, to_upper=True)]
NonEmptyStr = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class Page(BaseModel, Generic[T]):
    items: list[T]
    total: int
    page: int
    size: int
    pages: int


class Message(BaseModel):
    message: str
    data: dict[str, Any] | None = None


class ErrorResponse(BaseModel):
    success: bool = False
    error: dict[str, Any]
    request_id: str | None = None
