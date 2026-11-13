from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, enum_type
from app.utils.datetime_utils import utcnow
from app.utils.enums import BaggageStatus


class BaggageTrackingEvent(Base):
    """Immutable history row for each baggage status change."""
    __tablename__ = "baggage_tracking"

    id: Mapped[int] = mapped_column(primary_key=True)
    baggage_id: Mapped[int] = mapped_column(ForeignKey("baggage.id", ondelete="CASCADE"), index=True)
    previous_status: Mapped[BaggageStatus | None] = mapped_column(enum_type(BaggageStatus))
    status: Mapped[BaggageStatus] = mapped_column(enum_type(BaggageStatus))
    location: Mapped[str | None] = mapped_column(String(100))
    remarks: Mapped[str | None] = mapped_column(String(500))
    updated_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)
