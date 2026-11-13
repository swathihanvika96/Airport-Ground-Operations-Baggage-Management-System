from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.utils.datetime_utils import utcnow


class BoardingPass(Base):
    __tablename__ = "boarding_passes"

    id: Mapped[int] = mapped_column(primary_key=True)
    checkin_id: Mapped[int] = mapped_column(ForeignKey("checkins.id", ondelete="CASCADE"), unique=True)
    reference: Mapped[str] = mapped_column(String(40), unique=True, index=True)
    flight_id: Mapped[int] = mapped_column(ForeignKey("flights.id", ondelete="CASCADE"), index=True)
    passenger_id: Mapped[int] = mapped_column(ForeignKey("passengers.id"))
    seat_number: Mapped[str] = mapped_column(String(5))
    gate_number: Mapped[str | None] = mapped_column(String(10))
    boarding_time: Mapped[datetime | None] = mapped_column(DateTime)
    boarding_group: Mapped[str] = mapped_column(String(5))
    sequence_number: Mapped[int] = mapped_column(Integer)
    is_valid: Mapped[bool] = mapped_column(Boolean, default=True)
    issued_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    checkin: Mapped["CheckIn"] = relationship(back_populates="boarding_pass")  # noqa: F821
