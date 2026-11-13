from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, enum_type
from app.utils.enums import TurnaroundStatus


class Turnaround(Base, TimestampMixin):
    __tablename__ = "turnarounds"

    id: Mapped[int] = mapped_column(primary_key=True)
    flight_id: Mapped[int] = mapped_column(ForeignKey("flights.id", ondelete="CASCADE"), unique=True)  # outbound
    arrival_flight_id: Mapped[int | None] = mapped_column(ForeignKey("flights.id"))  # inbound (optional)
    parking_stand: Mapped[str | None] = mapped_column(String(20))
    status: Mapped[TurnaroundStatus] = mapped_column(enum_type(TurnaroundStatus), default=TurnaroundStatus.PLANNED, index=True)
    planned_start: Mapped[datetime | None] = mapped_column(DateTime)
    actual_start: Mapped[datetime | None] = mapped_column(DateTime)
    actual_end: Mapped[datetime | None] = mapped_column(DateTime)
    target_duration_minutes: Mapped[int] = mapped_column(Integer, default=60)
    total_duration_minutes: Mapped[int | None] = mapped_column(Integer)
    delay_minutes: Mapped[int] = mapped_column(Integer, default=0)
    delay_reason: Mapped[str | None] = mapped_column(Text)
    created_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))

    flight: Mapped["Flight"] = relationship(foreign_keys=[flight_id])  # noqa: F821
    activities: Mapped[list["TurnaroundActivity"]] = relationship(  # noqa: F821
        back_populates="turnaround", cascade="all, delete-orphan", order_by="TurnaroundActivity.sequence")

    @property
    def is_delayed(self) -> bool:
        return (self.delay_minutes or 0) > 0
