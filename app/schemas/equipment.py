from datetime import date, datetime

from pydantic import BaseModel, Field, model_validator

from app.schemas.common import ORMModel, UTCDateTime
from app.utils.enums import AssignmentStatus, EquipmentStatus, EquipmentType, MaintenanceStatus, MaintenanceType


class EquipmentCreate(BaseModel):
    equipment_code: str = Field(min_length=2, max_length=30)
    name: str = Field(min_length=2, max_length=100)
    equipment_type: EquipmentType
    manufacturer: str | None = None
    model: str | None = None
    airport_id: int | None = None
    terminal_id: int | None = None
    next_maintenance_date: date | None = None


class EquipmentUpdate(BaseModel):
    name: str | None = None
    manufacturer: str | None = None
    model: str | None = None
    terminal_id: int | None = None
    next_maintenance_date: date | None = None


class EquipmentStatusUpdate(BaseModel):
    status: EquipmentStatus
    remarks: str | None = None


class EquipmentOut(ORMModel):
    id: int
    equipment_code: str
    name: str
    equipment_type: EquipmentType
    manufacturer: str | None
    model: str | None
    status: EquipmentStatus
    airport_id: int | None
    terminal_id: int | None
    usage_hours: float
    last_maintenance_date: date | None
    next_maintenance_date: date | None
    created_at: datetime


class EquipmentAssignRequest(BaseModel):
    equipment_id: int
    flight_id: int
    start_time: UTCDateTime | None = None
    end_time: UTCDateTime | None = None
    remarks: str | None = None

    @model_validator(mode="after")
    def _check(self):
        if self.start_time and self.end_time and self.end_time <= self.start_time:
            raise ValueError("end_time must be after start_time")
        return self


class EquipmentAssignmentOut(ORMModel):
    id: int
    equipment_id: int
    flight_id: int
    start_time: datetime
    end_time: datetime
    status: AssignmentStatus
    assigned_by_id: int | None
    released_at: datetime | None
    usage_hours: float | None
    remarks: str | None
    created_at: datetime


class MaintenanceCreate(BaseModel):
    equipment_id: int
    maintenance_type: MaintenanceType = MaintenanceType.PREVENTIVE
    scheduled_date: date
    description: str | None = None
    technician_id: int | None = None


class MaintenanceComplete(BaseModel):
    remarks: str | None = None
    next_maintenance_date: date | None = None


class MaintenanceOut(ORMModel):
    id: int
    equipment_id: int
    maintenance_type: MaintenanceType
    scheduled_date: date
    started_at: datetime | None
    completed_at: datetime | None
    status: MaintenanceStatus
    technician_id: int | None
    description: str | None
    remarks: str | None
