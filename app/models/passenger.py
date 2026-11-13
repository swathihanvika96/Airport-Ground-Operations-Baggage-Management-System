from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, enum_type
from app.utils.datetime_utils import utcnow
from app.utils.enums import BookingStatus, IdentificationType, PassengerStatus, TravelClass


class Passenger(Base, TimestampMixin):
    __tablename__ = "passengers"
    __table_args__ = (UniqueConstraint("id_type", "id_reference"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    first_name: Mapped[str] = mapped_column(String(100), index=True)
    last_name: Mapped[str] = mapped_column(String(100), index=True)
    email: Mapped[str | None] = mapped_column(String(255), index=True)
    phone: Mapped[str | None] = mapped_column(String(30))
    date_of_birth: Mapped[date | None] = mapped_column(Date)
    nationality: Mapped[str | None] = mapped_column(String(60))
    id_type: Mapped[IdentificationType] = mapped_column(enum_type(IdentificationType), default=IdentificationType.PASSPORT)
    id_reference: Mapped[str] = mapped_column(String(50), index=True)  # synthetic document reference
    status: Mapped[PassengerStatus] = mapped_column(enum_type(PassengerStatus), default=PassengerStatus.ACTIVE)

    bookings: Mapped[list["PassengerFlight"]] = relationship(back_populates="passenger", cascade="all, delete-orphan")

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}"


class PassengerFlight(Base):
    """Passenger <-> flight mapping (a booking)."""
    __tablename__ = "passenger_flights"
    __table_args__ = (UniqueConstraint("passenger_id", "flight_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    passenger_id: Mapped[int] = mapped_column(ForeignKey("passengers.id", ondelete="CASCADE"), index=True)
    flight_id: Mapped[int] = mapped_column(ForeignKey("flights.id", ondelete="CASCADE"), index=True)
    booking_reference: Mapped[str] = mapped_column(String(10), unique=True)
    travel_class: Mapped[TravelClass] = mapped_column(enum_type(TravelClass), default=TravelClass.ECONOMY)
    status: Mapped[BookingStatus] = mapped_column(enum_type(BookingStatus), default=BookingStatus.BOOKED, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)

    passenger: Mapped["Passenger"] = relationship(back_populates="bookings")
    flight: Mapped["Flight"] = relationship()  # noqa: F821
