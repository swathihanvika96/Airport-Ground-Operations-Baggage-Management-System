from sqlalchemy import Boolean, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, enum_type
from app.utils.enums import CounterStatus


class CheckInCounter(Base, TimestampMixin):
    __tablename__ = "checkin_counters"
    __table_args__ = (UniqueConstraint("terminal_id", "counter_number"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    terminal_id: Mapped[int] = mapped_column(ForeignKey("terminals.id", ondelete="CASCADE"), index=True)
    counter_number: Mapped[str] = mapped_column(String(10))
    airline_code: Mapped[str | None] = mapped_column(String(3))
    status: Mapped[CounterStatus] = mapped_column(enum_type(CounterStatus), default=CounterStatus.AVAILABLE, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    terminal: Mapped["Terminal"] = relationship(back_populates="counters")  # noqa: F821
