from datetime import datetime

from pydantic import BaseModel, Field, model_validator

from app.schemas.common import ORMModel, UTCDateTime
from app.utils.enums import DelayCategory, Department


class DelayCreate(BaseModel):
    flight_id: int
    delay_category: DelayCategory
    reason: str = Field(min_length=3)
    delay_minutes: int | None = Field(None, gt=0, le=2880, description="Provide this OR updated_departure")
    updated_departure: UTCDateTime | None = None
    responsible_department: Department | None = None

    @model_validator(mode="after")
    def _check(self):
        if self.delay_minutes is None and self.updated_departure is None:
            raise ValueError("Provide delay_minutes or updated_departure")
        return self


class DelayUpdate(BaseModel):
    reason: str | None = None
    delay_category: DelayCategory | None = None
    responsible_department: Department | None = None


class DelayOut(ORMModel):
    id: int
    flight_id: int
    delay_category: DelayCategory
    reason: str
    delay_minutes: int
    responsible_department: Department | None
    expected_departure: datetime
    updated_departure: datetime
    is_active: bool
    recorded_by_id: int | None
    recorded_at: datetime


class FlightDelaySummary(BaseModel):
    flight_id: int
    flight_number: str
    scheduled_departure: datetime
    current_departure: datetime
    total_delay_minutes: int
    delay_count: int
    history: list[DelayOut]
