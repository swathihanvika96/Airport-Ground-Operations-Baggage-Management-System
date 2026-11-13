from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, enum_type
from app.utils.datetime_utils import utcnow
from app.utils.enums import AssignmentStatus, ResourceType


class ResourceAllocation(Base):
    """Unified allocation ledger for gates, counters, staff and equipment."""
    __tablename__ = "resource_allocations"
    __table_args__ = (Index("ix_resource_alloc_lookup", "resource_type", "resource_id", "status"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    resource_type: Mapped[ResourceType] = mapped_column(enum_type(ResourceType))
    resource_id: Mapped[int] = mapped_column(Integer)
    flight_id: Mapped[int] = mapped_column(ForeignKey("flights.id", ondelete="CASCADE"), index=True)
    assignment_id: Mapped[int | None] = mapped_column(Integer)  # id in gate/counter/equipment assignment table
    start_time: Mapped[datetime] = mapped_column(DateTime)
    end_time: Mapped[datetime] = mapped_column(DateTime)
    status: Mapped[AssignmentStatus] = mapped_column(enum_type(AssignmentStatus), default=AssignmentStatus.ACTIVE)
    role_description: Mapped[str | None] = mapped_column(String(100))
    remarks: Mapped[str | None] = mapped_column(String(255))
    allocated_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    released_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
