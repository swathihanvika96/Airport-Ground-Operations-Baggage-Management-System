from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, enum_type
from app.utils.datetime_utils import utcnow
from app.utils.enums import AssignmentStatus


class EquipmentAssignment(Base):
    """Equipment-to-flight assignment; doubles as usage history."""
    __tablename__ = "equipment_assignments"

    id: Mapped[int] = mapped_column(primary_key=True)
    equipment_id: Mapped[int] = mapped_column(ForeignKey("equipment.id", ondelete="CASCADE"), index=True)
    flight_id: Mapped[int] = mapped_column(ForeignKey("flights.id", ondelete="CASCADE"), index=True)
    start_time: Mapped[datetime] = mapped_column(DateTime)
    end_time: Mapped[datetime] = mapped_column(DateTime)
    status: Mapped[AssignmentStatus] = mapped_column(enum_type(AssignmentStatus), default=AssignmentStatus.ACTIVE)
    assigned_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    released_at: Mapped[datetime | None] = mapped_column(DateTime)
    usage_hours: Mapped[float | None] = mapped_column(Float)
    remarks: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    equipment: Mapped["Equipment"] = relationship()  # noqa: F821
