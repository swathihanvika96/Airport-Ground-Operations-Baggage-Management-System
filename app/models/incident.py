from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, enum_type
from app.utils.enums import IncidentCategory, IncidentStatus, Severity


class Incident(Base, TimestampMixin):
    __tablename__ = "incidents"

    id: Mapped[int] = mapped_column(primary_key=True)
    reference: Mapped[str] = mapped_column(String(30), unique=True, index=True)
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text)
    category: Mapped[IncidentCategory] = mapped_column(enum_type(IncidentCategory), index=True)
    severity: Mapped[Severity] = mapped_column(enum_type(Severity), index=True)
    status: Mapped[IncidentStatus] = mapped_column(enum_type(IncidentStatus), default=IncidentStatus.OPEN, index=True)
    flight_id: Mapped[int | None] = mapped_column(ForeignKey("flights.id"))
    terminal_id: Mapped[int | None] = mapped_column(ForeignKey("terminals.id"))
    location: Mapped[str | None] = mapped_column(String(150))
    assigned_team: Mapped[str | None] = mapped_column(String(100))
    assigned_to_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    reported_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    reported_at: Mapped[datetime] = mapped_column(DateTime)
    resolution_details: Mapped[str | None] = mapped_column(Text)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime)
    resolved_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))

    history: Mapped[list["IncidentHistory"]] = relationship(  # noqa: F821
        back_populates="incident", cascade="all, delete-orphan", order_by="IncidentHistory.timestamp")
