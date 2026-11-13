from sqlalchemy import JSON, Boolean, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, enum_type
from app.utils.enums import Department, Shift, StaffAvailability


class GroundStaff(Base, TimestampMixin):
    __tablename__ = "ground_staff"

    id: Mapped[int] = mapped_column(primary_key=True)
    employee_code: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), unique=True)
    full_name: Mapped[str] = mapped_column(String(150), index=True)
    email: Mapped[str | None] = mapped_column(String(255))
    phone: Mapped[str | None] = mapped_column(String(30))
    department: Mapped[Department] = mapped_column(enum_type(Department), index=True)
    designation: Mapped[str] = mapped_column(String(100))
    skills: Mapped[list[str]] = mapped_column(JSON, default=list)
    shift: Mapped[Shift] = mapped_column(enum_type(Shift), default=Shift.MORNING)
    availability_status: Mapped[StaffAvailability] = mapped_column(
        enum_type(StaffAvailability), default=StaffAvailability.AVAILABLE, index=True)
    supervisor_id: Mapped[int | None] = mapped_column(ForeignKey("ground_staff.id"))
    terminal_id: Mapped[int | None] = mapped_column(ForeignKey("terminals.id"))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    supervisor: Mapped["GroundStaff | None"] = relationship(remote_side=[id])
