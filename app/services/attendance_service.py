from datetime import datetime, time, timedelta

from sqlalchemy.orm import Session

from app.core.constants import LATE_GRACE_MINUTES, SHIFT_START_HOURS
from app.core.exceptions import BusinessRuleError, ConflictError
from app.models.attendance import StaffAttendance
from app.models.user import User
from app.repositories.attendance_repository import AttendanceRepository
from app.repositories.staff_repository import StaffRepository
from app.schemas.attendance import AttendanceMark
from app.utils.datetime_utils import utcnow
from app.utils.enums import AttendanceStatus, Shift, StaffAvailability


def attendance_status_for(shift: Shift, check_in: datetime) -> AttendanceStatus:
    start = datetime.combine(check_in.date(), time(SHIFT_START_HOURS[shift]))
    return AttendanceStatus.LATE if check_in > start + timedelta(minutes=LATE_GRACE_MINUTES) else AttendanceStatus.PRESENT


class AttendanceService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = AttendanceRepository(db)
        self.staff = StaffRepository(db)

    def check_in(self, staff_id: int, user: User, when: datetime | None = None) -> StaffAttendance:
        staff = self.staff.get_or_404(staff_id)
        now = when or utcnow()
        if self.repo.for_day(staff.id, now.date()):
            raise ConflictError("Attendance already recorded for today")
        record = self.repo.create(staff_id=staff.id, attendance_date=now.date(), shift=staff.shift,
                                  check_in_time=now, status=attendance_status_for(staff.shift, now))
        if staff.availability_status == StaffAvailability.OFF_DUTY:
            staff.availability_status = StaffAvailability.AVAILABLE
        self.db.commit()
        return record

    def check_out(self, staff_id: int, user: User, when: datetime | None = None) -> StaffAttendance:
        staff = self.staff.get_or_404(staff_id)
        now = when or utcnow()
        record = self.repo.for_day(staff.id, now.date())
        if not record or not record.check_in_time:
            raise BusinessRuleError("No check-in found for today")
        if record.check_out_time:
            raise ConflictError("Already checked out")
        record.check_out_time = now
        staff.availability_status = StaffAvailability.OFF_DUTY
        self.db.commit()
        return record

    def mark(self, data: AttendanceMark, user: User) -> StaffAttendance:
        staff = self.staff.get_or_404(data.staff_id)
        record = self.repo.for_day(staff.id, data.attendance_date)
        if record:
            record.status, record.remarks = data.status, data.remarks
        else:
            record = self.repo.create(staff_id=staff.id, attendance_date=data.attendance_date, shift=staff.shift,
                                      status=data.status, remarks=data.remarks)
        if data.status == AttendanceStatus.ON_LEAVE and data.attendance_date == utcnow().date():
            staff.availability_status = StaffAvailability.ON_LEAVE
        self.db.commit()
        return record
