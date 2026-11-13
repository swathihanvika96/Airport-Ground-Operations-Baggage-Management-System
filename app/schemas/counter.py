from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.common import ORMModel
from app.utils.enums import CounterStatus


class CounterCreate(BaseModel):
    terminal_id: int
    counter_number: str = Field(min_length=1, max_length=10)
    airline_code: str | None = Field(None, max_length=3)


class CounterUpdate(BaseModel):
    airline_code: str | None = None
    status: CounterStatus | None = None
    is_active: bool | None = None


class CounterOut(ORMModel):
    id: int
    terminal_id: int
    counter_number: str
    airline_code: str | None
    status: CounterStatus
    is_active: bool
    created_at: datetime
