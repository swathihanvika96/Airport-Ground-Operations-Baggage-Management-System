"""Gate and check-in counter assignments (with full history)."""
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, enum_type
from app.utils.datetime_utils import utcnow
from app.utils.enums import AssignmentStatus


class GateAssignment(Base):
    __tablename__ = "gate_assignments"
    __table_args__ = (Index("ix_gate_assignment_window", "gate_id", "status", "start_time", "end_time"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    gate_id: Mapped[int] = mapped_column(ForeignKey("gates.id"), index=True)
    flight_id: Mapped[int] = mapped_column(ForeignKey("flights.id", ondelete="CASCADE"), index=True)
    start_time: Mapped[datetime] = mapped_column(DateTime)
    end_time: Mapped[datetime] = mapped_column(DateTime)
    status: Mapped[AssignmentStatus] = mapped_column(enum_type(AssignmentStatus), default=AssignmentStatus.ACTIVE)
    assigned_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    released_at: Mapped[datetime | None] = mapped_column(DateTime)
    remarks: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    gate: Mapped["Gate"] = relationship()  # noqa: F821
    flight: Mapped["Flight"] = relationship()  # noqa: F821


class CounterAssignment(Base):
    __tablename__ = "counter_assignments"
    __table_args__ = (Index("ix_counter_assignment_window", "counter_id", "status", "start_time", "end_time"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    counter_id: Mapped[int] = mapped_column(ForeignKey("checkin_counters.id"), index=True)
    flight_id: Mapped[int] = mapped_column(ForeignKey("flights.id", ondelete="CASCADE"), index=True)
    start_time: Mapped[datetime] = mapped_column(DateTime)
    end_time: Mapped[datetime] = mapped_column(DateTime)
    status: Mapped[AssignmentStatus] = mapped_column(enum_type(AssignmentStatus), default=AssignmentStatus.ACTIVE)
    assigned_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    released_at: Mapped[datetime | None] = mapped_column(DateTime)
    remarks: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    counter: Mapped["CheckInCounter"] = relationship()  # noqa: F821
    flight: Mapped["Flight"] = relationship()  # noqa: F821
