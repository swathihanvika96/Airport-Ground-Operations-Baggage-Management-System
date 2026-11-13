from datetime import date

from sqlalchemy import Date, Float, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, enum_type
from app.utils.enums import EquipmentStatus, EquipmentType


class Equipment(Base, TimestampMixin):
    __tablename__ = "equipment"

    id: Mapped[int] = mapped_column(primary_key=True)
    equipment_code: Mapped[str] = mapped_column(String(30), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(100))
    equipment_type: Mapped[EquipmentType] = mapped_column(enum_type(EquipmentType), index=True)
    manufacturer: Mapped[str | None] = mapped_column(String(100))
    model: Mapped[str | None] = mapped_column(String(100))
    status: Mapped[EquipmentStatus] = mapped_column(enum_type(EquipmentStatus), default=EquipmentStatus.AVAILABLE, index=True)
    airport_id: Mapped[int | None] = mapped_column(ForeignKey("airports.id"))
    terminal_id: Mapped[int | None] = mapped_column(ForeignKey("terminals.id"))
    usage_hours: Mapped[float] = mapped_column(Float, default=0.0)
    last_maintenance_date: Mapped[date | None] = mapped_column(Date)
    next_maintenance_date: Mapped[date | None] = mapped_column(Date)
