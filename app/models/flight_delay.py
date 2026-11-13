from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, enum_type
from app.utils.datetime_utils import utcnow
from app.utils.enums import DelayCategory, Department


class FlightDelay(Base):
    """Each row is one delay event; all rows for a flight form its delay history."""
    __tablename__ = "flight_delays"

    id: Mapped[int] = mapped_column(primary_key=True)
    flight_id: Mapped[int] = mapped_column(ForeignKey("flights.id", ondelete="CASCADE"), index=True)
    delay_category: Mapped[DelayCategory] = mapped_column(enum_type(DelayCategory), index=True)
    reason: Mapped[str] = mapped_column(Text)
    delay_minutes: Mapped[int] = mapped_column(Integer)
    responsible_department: Mapped[Department | None] = mapped_column(enum_type(Department))
    expected_departure: Mapped[datetime] = mapped_column(DateTime)  # departure time before this delay
    updated_departure: Mapped[datetime] = mapped_column(DateTime)   # new departure time
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    recorded_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    recorded_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)

    flight: Mapped["Flight"] = relationship()  # noqa: F821
