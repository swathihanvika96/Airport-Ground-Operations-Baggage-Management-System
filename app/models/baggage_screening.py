from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, enum_type
from app.utils.datetime_utils import utcnow
from app.utils.enums import ScreeningStatus


class BaggageScreening(Base):
    __tablename__ = "baggage_screenings"

    id: Mapped[int] = mapped_column(primary_key=True)
    baggage_id: Mapped[int] = mapped_column(ForeignKey("baggage.id", ondelete="CASCADE"), index=True)
    status: Mapped[ScreeningStatus] = mapped_column(enum_type(ScreeningStatus), index=True)
    screening_officer_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    screened_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    machine_id: Mapped[str | None] = mapped_column(String(30))
    remarks: Mapped[str | None] = mapped_column(String(500))
    hold_reason: Mapped[str | None] = mapped_column(String(255))
    released_at: Mapped[datetime | None] = mapped_column(DateTime)
    released_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    release_remarks: Mapped[str | None] = mapped_column(String(500))
