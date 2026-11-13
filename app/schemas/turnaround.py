from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.common import ORMModel, UTCDateTime
from app.utils.enums import ActivityStatus, TurnaroundActivityType, TurnaroundStatus


class TurnaroundCreate(BaseModel):
    flight_id: int = Field(description="Outbound (departing) flight")
    arrival_flight_id: int | None = Field(None, description="Inbound flight operated by the same aircraft")
    parking_stand: str | None = Field(None, max_length=20)
    planned_start: UTCDateTime | None = None
    target_duration_minutes: int = Field(60, ge=15, le=600)


class ParkingAssign(BaseModel):
    parking_stand: str = Field(min_length=1, max_length=20)


class ActivityAssign(BaseModel):
    assigned_team: str | None = Field(None, max_length=100)
    assigned_staff_id: int | None = None


class ActivityStart(BaseModel):
    start_time: UTCDateTime | None = None
    assigned_team: str | None = None
    assigned_staff_id: int | None = None


class ActivityComplete(BaseModel):
    completion_time: UTCDateTime | None = None
    delay_reason: str | None = Field(None, max_length=500)
    remarks: str | None = Field(None, max_length=500)


class ActivityOut(ORMModel):
    id: int
    turnaround_id: int
    activity_type: TurnaroundActivityType
    sequence: int
    status: ActivityStatus
    assigned_team: str | None
    assigned_staff_id: int | None
    planned_duration_minutes: int
    start_time: datetime | None
    completion_time: datetime | None
    actual_duration_minutes: int | None
    is_delayed: bool
    delay_minutes: int
    delay_reason: str | None
    remarks: str | None


class TurnaroundOut(ORMModel):
    id: int
    flight_id: int
    arrival_flight_id: int | None
    parking_stand: str | None
    status: TurnaroundStatus
    planned_start: datetime | None
    actual_start: datetime | None
    actual_end: datetime | None
    target_duration_minutes: int
    total_duration_minutes: int | None
    delay_minutes: int
    delay_reason: str | None
    is_delayed: bool
    created_at: datetime
    activities: list[ActivityOut] = []
