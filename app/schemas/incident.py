from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.common import ORMModel
from app.utils.enums import IncidentCategory, IncidentStatus, Severity


class IncidentCreate(BaseModel):
    title: str = Field(min_length=3, max_length=200)
    description: str = Field(min_length=3)
    category: IncidentCategory
    severity: Severity
    flight_id: int | None = None
    terminal_id: int | None = None
    location: str | None = Field(None, max_length=150)
    assigned_team: str | None = Field(None, max_length=100)


class IncidentUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    category: IncidentCategory | None = None
    severity: Severity | None = None
    location: str | None = None


class IncidentAssign(BaseModel):
    assigned_team: str | None = None
    assigned_to_id: int | None = None
    remarks: str | None = None


class IncidentStatusUpdate(BaseModel):
    status: IncidentStatus
    remarks: str | None = None
    resolution_details: str | None = Field(None, description="Required when resolving")


class IncidentHistoryOut(ORMModel):
    id: int
    action: str
    from_status: IncidentStatus | None
    to_status: IncidentStatus | None
    remarks: str | None
    changed_by_id: int | None
    timestamp: datetime


class IncidentOut(ORMModel):
    id: int
    reference: str
    title: str
    description: str
    category: IncidentCategory
    severity: Severity
    status: IncidentStatus
    flight_id: int | None
    terminal_id: int | None
    location: str | None
    assigned_team: str | None
    assigned_to_id: int | None
    reported_by_id: int | None
    reported_at: datetime
    resolution_details: str | None
    resolved_at: datetime | None


class IncidentDetail(IncidentOut):
    history: list[IncidentHistoryOut] = []
