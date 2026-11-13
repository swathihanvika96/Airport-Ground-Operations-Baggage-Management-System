from sqlalchemy import Boolean, Float, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, enum_type
from app.utils.enums import BaggageCategory, BaggageStatus


class Baggage(Base, TimestampMixin):
    __tablename__ = "baggage"

    id: Mapped[int] = mapped_column(primary_key=True)
    tag_number: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    passenger_id: Mapped[int] = mapped_column(ForeignKey("passengers.id"), index=True)
    flight_id: Mapped[int] = mapped_column(ForeignKey("flights.id", ondelete="CASCADE"), index=True)
    checkin_id: Mapped[int | None] = mapped_column(ForeignKey("checkins.id"))
    weight_kg: Mapped[float] = mapped_column(Float)
    category: Mapped[BaggageCategory] = mapped_column(enum_type(BaggageCategory), default=BaggageCategory.CHECKED)
    destination: Mapped[str] = mapped_column(String(3))  # airport IATA code
    description: Mapped[str | None] = mapped_column(String(255))
    status: Mapped[BaggageStatus] = mapped_column(enum_type(BaggageStatus), default=BaggageStatus.REGISTERED, index=True)
    current_location: Mapped[str | None] = mapped_column(String(100))
    is_on_hold: Mapped[bool] = mapped_column(Boolean, default=False)

    passenger: Mapped["Passenger"] = relationship()  # noqa: F821
    flight: Mapped["Flight"] = relationship()  # noqa: F821
