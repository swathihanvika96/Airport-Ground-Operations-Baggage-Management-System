from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, enum_type
from app.utils.enums import Priority, TaskStatus, TaskType


class GroundTask(Base, TimestampMixin):
    __tablename__ = "ground_tasks"

    id: Mapped[int] = mapped_column(primary_key=True)
    flight_id: Mapped[int] = mapped_column(ForeignKey("flights.id", ondelete="CASCADE"), index=True)
    turnaround_activity_id: Mapped[int | None] = mapped_column(ForeignKey("turnaround_activities.id"))
    task_type: Mapped[TaskType] = mapped_column(enum_type(TaskType), index=True)
    title: Mapped[str | None] = mapped_column(String(200))
    priority: Mapped[Priority] = mapped_column(enum_type(Priority), default=Priority.MEDIUM)
    status: Mapped[TaskStatus] = mapped_column(enum_type(TaskStatus), default=TaskStatus.PENDING, index=True)
    assigned_staff_id: Mapped[int | None] = mapped_column(ForeignKey("ground_staff.id"), index=True)
    scheduled_start: Mapped[datetime | None] = mapped_column(DateTime)
    due_time: Mapped[datetime | None] = mapped_column(DateTime)
    start_time: Mapped[datetime | None] = mapped_column(DateTime)
    completion_time: Mapped[datetime | None] = mapped_column(DateTime)
    remarks: Mapped[str | None] = mapped_column(Text)
    created_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))

    flight: Mapped["Flight"] = relationship()  # noqa: F821
    assigned_staff: Mapped["GroundStaff | None"] = relationship()  # noqa: F821
