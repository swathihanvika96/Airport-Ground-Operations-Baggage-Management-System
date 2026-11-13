from datetime import datetime

from pydantic import BaseModel, EmailStr, Field

from app.schemas.common import ORMModel
from app.utils.enums import Department, Shift, StaffAvailability


class StaffCreate(BaseModel):
    employee_code: str = Field(min_length=2, max_length=20)
    full_name: str = Field(min_length=2, max_length=150)
    email: EmailStr | None = None
    phone: str | None = None
    department: Department
    designation: str = Field(min_length=2, max_length=100)
    skills: list[str] = []
    shift: Shift = Shift.MORNING
    supervisor_id: int | None = None
    terminal_id: int | None = None
    user_id: int | None = Field(None, description="Link to a login account (for 'my tasks' & notifications)")


class StaffUpdate(BaseModel):
    full_name: str | None = None
    email: EmailStr | None = None
    phone: str | None = None
    department: Department | None = None
    designation: str | None = None
    skills: list[str] | None = None
    shift: Shift | None = None
    supervisor_id: int | None = None
    terminal_id: int | None = None
    is_active: bool | None = None


class AvailabilityUpdate(BaseModel):
    availability_status: StaffAvailability


class StaffOut(ORMModel):
    id: int
    employee_code: str
    user_id: int | None
    full_name: str
    email: str | None
    phone: str | None
    department: Department
    designation: str
    skills: list[str]
    shift: Shift
    availability_status: StaffAvailability
    supervisor_id: int | None
    terminal_id: int | None
    is_active: bool
    created_at: datetime
