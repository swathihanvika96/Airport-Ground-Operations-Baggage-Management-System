from datetime import date

from fastapi import APIRouter, Depends

from app.api.dependencies import DB, allow
from app.core.permissions import Permissions
from app.models.attendance import StaffAttendance
from app.models.user import User
from app.repositories.attendance_repository import AttendanceRepository
from app.schemas.attendance import AttendanceMark, AttendanceOut
from app.schemas.common import Page
from app.services.attendance_service import AttendanceService
from app.utils.enums import AttendanceStatus
from app.utils.pagination import PageParams, page_params, paginate

router = APIRouter(prefix="/attendance", tags=["Staff Attendance"])


@router.post("/{staff_id}/check-in", response_model=AttendanceOut, status_code=201)
def staff_check_in(staff_id: int, db: DB, user: User = allow(Permissions.TASK_EXECUTE)):
    return AttendanceService(db).check_in(staff_id, user)


@router.post("/{staff_id}/check-out", response_model=AttendanceOut)
def staff_check_out(staff_id: int, db: DB, user: User = allow(Permissions.TASK_EXECUTE)):
    return AttendanceService(db).check_out(staff_id, user)


@router.post("/mark", response_model=AttendanceOut, summary="Manually mark attendance (absent / leave)")
def mark(data: AttendanceMark, db: DB, user: User = allow(Permissions.STAFF_MANAGE)):
    return AttendanceService(db).mark(data, user)


@router.get("", response_model=Page[AttendanceOut])
def list_attendance(db: DB, _: User = allow(Permissions.STAFF_MANAGE), staff_id: int | None = None,
                    date_from: date | None = None, date_to: date | None = None,
                    status: AttendanceStatus | None = None, params: PageParams = Depends(page_params)):
    stmt = AttendanceRepository(db).search(staff_id, date_from, date_to, status) \
        .order_by(StaffAttendance.attendance_date.desc())
    return paginate(db, stmt, params)
