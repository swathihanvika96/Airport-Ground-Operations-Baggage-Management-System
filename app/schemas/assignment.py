from datetime import datetime

from pydantic import BaseModel, model_validator

from app.schemas.common import ORMModel, UTCDateTime
from app.utils.enums import AssignmentStatus


class _Window(BaseModel):
    start_time: UTCDateTime | None = None
    end_time: UTCDateTime | None = None
    remarks: str | None = None

    @model_validator(mode="after")
    def _check(self):
        if self.start_time and self.end_time and self.end_time <= self.start_time:
            raise ValueError("end_time must be after start_time")
        return self


class GateAssignRequest(_Window):
    flight_id: int


class CounterAssignRequest(_Window):
    flight_id: int


class GateAssignmentOut(ORMModel):
    id: int
    gate_id: int
    flight_id: int
    start_time: datetime
    end_time: datetime
    status: AssignmentStatus
    assigned_by_id: int | None
    released_at: datetime | None
    remarks: str | None
    created_at: datetime


class CounterAssignmentOut(ORMModel):
    id: int
    counter_id: int
    flight_id: int
    start_time: datetime
    end_time: datetime
    status: AssignmentStatus
    assigned_by_id: int | None
    released_at: datetime | None
    remarks: str | None
    created_at: datetime
