from datetime import date, datetime

from pydantic import BaseModel

from app.schemas.common import ORMModel
from app.utils.enums import AttendanceStatus, Shift


class AttendanceMark(BaseModel):
    staff_id: int
    attendance_date: date
    status: AttendanceStatus
    remarks: str | None = None


class AttendanceOut(ORMModel):
    id: int
    staff_id: int
    attendance_date: date
    shift: Shift
    check_in_time: datetime | None
    check_out_time: datetime | None
    status: AttendanceStatus
    remarks: str | None
