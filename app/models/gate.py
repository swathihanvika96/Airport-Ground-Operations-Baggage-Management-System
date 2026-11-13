from sqlalchemy import Boolean, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, enum_type
from app.utils.enums import GateStatus, GateType


class Gate(Base, TimestampMixin):
    __tablename__ = "gates"
    __table_args__ = (UniqueConstraint("terminal_id", "gate_number"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    terminal_id: Mapped[int] = mapped_column(ForeignKey("terminals.id", ondelete="CASCADE"), index=True)
    gate_number: Mapped[str] = mapped_column(String(10))
    gate_type: Mapped[GateType] = mapped_column(enum_type(GateType), default=GateType.DOMESTIC)
    status: Mapped[GateStatus] = mapped_column(enum_type(GateStatus), default=GateStatus.AVAILABLE, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    terminal: Mapped["Terminal"] = relationship(back_populates="gates")  # noqa: F821
