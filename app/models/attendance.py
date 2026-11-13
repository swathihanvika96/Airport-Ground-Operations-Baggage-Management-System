from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, enum_type
from app.utils.enums import AttendanceStatus, Shift


class StaffAttendance(Base, TimestampMixin):
    __tablename__ = "staff_attendance"
    __table_args__ = (UniqueConstraint("staff_id", "attendance_date"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    staff_id: Mapped[int] = mapped_column(ForeignKey("ground_staff.id", ondelete="CASCADE"), index=True)
    attendance_date: Mapped[date] = mapped_column(Date, index=True)
    shift: Mapped[Shift] = mapped_column(enum_type(Shift))
    check_in_time: Mapped[datetime | None] = mapped_column(DateTime)
    check_out_time: Mapped[datetime | None] = mapped_column(DateTime)
    status: Mapped[AttendanceStatus] = mapped_column(enum_type(AttendanceStatus))
    remarks: Mapped[str | None] = mapped_column(String(255))

    staff: Mapped["GroundStaff"] = relationship()  # noqa: F821
