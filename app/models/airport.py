from sqlalchemy import Float, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, enum_type
from app.utils.enums import AirportStatus


class Airport(Base, TimestampMixin):
    __tablename__ = "airports"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(3), unique=True, index=True)  # IATA
    icao_code: Mapped[str | None] = mapped_column(String(4), unique=True)
    name: Mapped[str] = mapped_column(String(200), index=True)
    city: Mapped[str] = mapped_column(String(100), index=True)
    state: Mapped[str | None] = mapped_column(String(100))
    country: Mapped[str] = mapped_column(String(100), index=True)
    timezone: Mapped[str] = mapped_column(String(64), default="UTC")
    latitude: Mapped[float | None] = mapped_column(Float)
    longitude: Mapped[float | None] = mapped_column(Float)
    operational_status: Mapped[AirportStatus] = mapped_column(enum_type(AirportStatus), default=AirportStatus.OPERATIONAL)

    terminals: Mapped[list["Terminal"]] = relationship(back_populates="airport", cascade="all, delete-orphan")  # noqa: F821
