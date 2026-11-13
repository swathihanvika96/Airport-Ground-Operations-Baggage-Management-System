from datetime import datetime

from pydantic import BaseModel, model_validator

from app.schemas.common import ORMModel, UTCDateTime
from app.utils.enums import AssignmentStatus, ResourceType


class AllocationCreate(BaseModel):
    resource_type: ResourceType
    resource_id: int
    flight_id: int
    start_time: UTCDateTime | None = None
    end_time: UTCDateTime | None = None
    role_description: str | None = None
    remarks: str | None = None

    @model_validator(mode="after")
    def _check(self):
        if self.start_time and self.end_time and self.end_time <= self.start_time:
            raise ValueError("end_time must be after start_time")
        return self


class AllocationOut(ORMModel):
    id: int
    resource_type: ResourceType
    resource_id: int
    flight_id: int
    assignment_id: int | None
    start_time: datetime
    end_time: datetime
    status: AssignmentStatus
    role_description: str | None
    remarks: str | None
    allocated_by_id: int | None
    released_at: datetime | None
    created_at: datetime


class AvailableResource(BaseModel):
    resource_type: ResourceType
    resource_id: int
    label: str
    status: str
