from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.common import ORMModel, UTCDateTime
from app.utils.enums import Priority, TaskStatus, TaskType


class TaskCreate(BaseModel):
    flight_id: int
    task_type: TaskType
    title: str | None = Field(None, max_length=200)
    priority: Priority = Priority.MEDIUM
    assigned_staff_id: int | None = None
    scheduled_start: UTCDateTime | None = None
    due_time: UTCDateTime | None = None
    turnaround_activity_id: int | None = None
    remarks: str | None = None


class TaskUpdate(BaseModel):
    title: str | None = None
    priority: Priority | None = None
    scheduled_start: UTCDateTime | None = None
    due_time: UTCDateTime | None = None
    remarks: str | None = None


class TaskAssign(BaseModel):
    staff_id: int


class TaskProgress(BaseModel):
    remarks: str | None = None


class TaskOut(ORMModel):
    id: int
    flight_id: int
    turnaround_activity_id: int | None
    task_type: TaskType
    title: str | None
    priority: Priority
    status: TaskStatus
    assigned_staff_id: int | None
    scheduled_start: datetime | None
    due_time: datetime | None
    start_time: datetime | None
    completion_time: datetime | None
    remarks: str | None
    created_by_id: int | None
    created_at: datetime
