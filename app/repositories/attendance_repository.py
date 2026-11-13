from sqlalchemy import select

from app.models.attendance import StaffAttendance
from app.repositories.base import BaseRepository


class AttendanceRepository(BaseRepository[StaffAttendance]):
    model = StaffAttendance
    entity_name = "Attendance record"

    def for_day(self, staff_id, day) -> StaffAttendance | None:
        return self.db.scalar(select(StaffAttendance).where(StaffAttendance.staff_id == staff_id,
                                                            StaffAttendance.attendance_date == day))

    def search(self, staff_id=None, date_from=None, date_to=None, status=None):
        stmt = select(StaffAttendance)
        if staff_id:
            stmt = stmt.where(StaffAttendance.staff_id == staff_id)
        if date_from:
            stmt = stmt.where(StaffAttendance.attendance_date >= date_from)
        if date_to:
            stmt = stmt.where(StaffAttendance.attendance_date <= date_to)
        if status:
            stmt = stmt.where(StaffAttendance.status == status)
        return stmt
