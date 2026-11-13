from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, enum_type
from app.utils.datetime_utils import utcnow
from app.utils.enums import IncidentStatus


class IncidentHistory(Base):
    __tablename__ = "incident_history"

    id: Mapped[int] = mapped_column(primary_key=True)
    incident_id: Mapped[int] = mapped_column(ForeignKey("incidents.id", ondelete="CASCADE"), index=True)
    action: Mapped[str] = mapped_column(String(50))
    from_status: Mapped[IncidentStatus | None] = mapped_column(enum_type(IncidentStatus))
    to_status: Mapped[IncidentStatus | None] = mapped_column(enum_type(IncidentStatus))
    remarks: Mapped[str | None] = mapped_column(Text)
    changed_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    incident: Mapped["Incident"] = relationship(back_populates="history")  # noqa: F821
