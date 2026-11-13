from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, enum_type
from app.utils.enums import CheckInChannel, CheckInStatus


class CheckIn(Base, TimestampMixin):
    __tablename__ = "checkins"
    # DB-level guarantee: one check-in per passenger per flight
    __table_args__ = (UniqueConstraint("passenger_id", "flight_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    passenger_id: Mapped[int] = mapped_column(ForeignKey("passengers.id"), index=True)
    flight_id: Mapped[int] = mapped_column(ForeignKey("flights.id", ondelete="CASCADE"), index=True)
    booking_id: Mapped[int] = mapped_column(ForeignKey("passenger_flights.id"))
    counter_id: Mapped[int | None] = mapped_column(ForeignKey("checkin_counters.id"))
    seat_number: Mapped[str] = mapped_column(String(5))
    checkin_time: Mapped[datetime] = mapped_column(DateTime)
    boarded_at: Mapped[datetime | None] = mapped_column(DateTime)
    channel: Mapped[CheckInChannel] = mapped_column(enum_type(CheckInChannel), default=CheckInChannel.COUNTER)
    status: Mapped[CheckInStatus] = mapped_column(enum_type(CheckInStatus), default=CheckInStatus.CHECKED_IN, index=True)
    baggage_count: Mapped[int] = mapped_column(Integer, default=0)
    checked_in_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))

    passenger: Mapped["Passenger"] = relationship()  # noqa: F821
    flight: Mapped["Flight"] = relationship()  # noqa: F821
    counter: Mapped["CheckInCounter | None"] = relationship()  # noqa: F821
    boarding_pass: Mapped["BoardingPass | None"] = relationship(back_populates="checkin", uselist=False)  # noqa: F821
