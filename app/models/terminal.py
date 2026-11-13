from sqlalchemy import Boolean, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, enum_type
from app.utils.enums import TerminalStatus


class Terminal(Base, TimestampMixin):
    __tablename__ = "terminals"
    __table_args__ = (UniqueConstraint("airport_id", "code"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    airport_id: Mapped[int] = mapped_column(ForeignKey("airports.id", ondelete="CASCADE"), index=True)
    code: Mapped[str] = mapped_column(String(10))
    name: Mapped[str] = mapped_column(String(100))
    capacity: Mapped[int] = mapped_column(Integer, default=0)  # passengers per hour
    is_international: Mapped[bool] = mapped_column(Boolean, default=False)
    status: Mapped[TerminalStatus] = mapped_column(enum_type(TerminalStatus), default=TerminalStatus.ACTIVE)

    airport: Mapped["Airport"] = relationship(back_populates="terminals")  # noqa: F821
    gates: Mapped[list["Gate"]] = relationship(back_populates="terminal")  # noqa: F821
    counters: Mapped[list["CheckInCounter"]] = relationship(back_populates="terminal")  # noqa: F821
