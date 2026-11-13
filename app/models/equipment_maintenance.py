from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, enum_type
from app.utils.enums import MaintenanceStatus, MaintenanceType


class EquipmentMaintenance(Base, TimestampMixin):
    __tablename__ = "equipment_maintenance"

    id: Mapped[int] = mapped_column(primary_key=True)
    equipment_id: Mapped[int] = mapped_column(ForeignKey("equipment.id", ondelete="CASCADE"), index=True)
    maintenance_type: Mapped[MaintenanceType] = mapped_column(enum_type(MaintenanceType))
    scheduled_date: Mapped[date] = mapped_column(Date, index=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime)
    status: Mapped[MaintenanceStatus] = mapped_column(enum_type(MaintenanceStatus), default=MaintenanceStatus.SCHEDULED)
    technician_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    description: Mapped[str | None] = mapped_column(String(255))
    remarks: Mapped[str | None] = mapped_column(Text)
