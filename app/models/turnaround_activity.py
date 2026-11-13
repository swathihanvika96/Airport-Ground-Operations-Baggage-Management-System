from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, enum_type
from app.utils.enums import ActivityStatus, TurnaroundActivityType


class TurnaroundActivity(Base, TimestampMixin):
    __tablename__ = "turnaround_activities"

    id: Mapped[int] = mapped_column(primary_key=True)
    turnaround_id: Mapped[int] = mapped_column(ForeignKey("turnarounds.id", ondelete="CASCADE"), index=True)
    activity_type: Mapped[TurnaroundActivityType] = mapped_column(enum_type(TurnaroundActivityType))
    sequence: Mapped[int] = mapped_column(Integer)
    status: Mapped[ActivityStatus] = mapped_column(enum_type(ActivityStatus), default=ActivityStatus.PENDING)
    assigned_team: Mapped[str | None] = mapped_column(String(100))
    assigned_staff_id: Mapped[int | None] = mapped_column(ForeignKey("ground_staff.id"))
    planned_duration_minutes: Mapped[int] = mapped_column(Integer)
    start_time: Mapped[datetime | None] = mapped_column(DateTime)
    completion_time: Mapped[datetime | None] = mapped_column(DateTime)
    actual_duration_minutes: Mapped[int | None] = mapped_column(Integer)
    is_delayed: Mapped[bool] = mapped_column(Boolean, default=False)
    delay_minutes: Mapped[int] = mapped_column(Integer, default=0)
    delay_reason: Mapped[str | None] = mapped_column(String(500))
    remarks: Mapped[str | None] = mapped_column(String(500))

    turnaround: Mapped["Turnaround"] = relationship(back_populates="activities")  # noqa: F821
