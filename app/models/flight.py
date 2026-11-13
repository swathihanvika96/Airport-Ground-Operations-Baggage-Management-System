from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, enum_type
from app.utils.enums import FlightStatus


class Flight(Base, TimestampMixin):
    __tablename__ = "flights"
    __table_args__ = (UniqueConstraint("flight_number", "scheduled_departure"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    flight_number: Mapped[str] = mapped_column(String(10), index=True)
    airline_name: Mapped[str] = mapped_column(String(100))
    airline_code: Mapped[str] = mapped_column(String(3), index=True)
    aircraft_type: Mapped[str] = mapped_column(String(50))
    aircraft_registration: Mapped[str | None] = mapped_column(String(20))
    seat_capacity: Mapped[int] = mapped_column(Integer, default=180)

    departure_airport_id: Mapped[int] = mapped_column(ForeignKey("airports.id"), index=True)
    arrival_airport_id: Mapped[int] = mapped_column(ForeignKey("airports.id"), index=True)
    departure_terminal_id: Mapped[int | None] = mapped_column(ForeignKey("terminals.id"))
    gate_id: Mapped[int | None] = mapped_column(ForeignKey("gates.id"))  # current gate

    scheduled_departure: Mapped[datetime] = mapped_column(DateTime, index=True)
    scheduled_arrival: Mapped[datetime] = mapped_column(DateTime)
    estimated_departure: Mapped[datetime | None] = mapped_column(DateTime)
    actual_departure: Mapped[datetime | None] = mapped_column(DateTime)
    actual_arrival: Mapped[datetime | None] = mapped_column(DateTime)
    status: Mapped[FlightStatus] = mapped_column(enum_type(FlightStatus), default=FlightStatus.SCHEDULED, index=True)

    departure_airport: Mapped["Airport"] = relationship(foreign_keys=[departure_airport_id])  # noqa: F821
    arrival_airport: Mapped["Airport"] = relationship(foreign_keys=[arrival_airport_id])  # noqa: F821
    departure_terminal: Mapped["Terminal | None"] = relationship()  # noqa: F821
    gate: Mapped["Gate | None"] = relationship()  # noqa: F821

    @property
    def current_departure(self) -> datetime:
        return self.estimated_departure or self.scheduled_departure

    @property
    def gate_number(self) -> str | None:
        return self.gate.gate_number if self.gate else None

    @property
    def departure_airport_code(self) -> str | None:
        return self.departure_airport.code if self.departure_airport else None

    @property
    def arrival_airport_code(self) -> str | None:
        return self.arrival_airport.code if self.arrival_airport else None
