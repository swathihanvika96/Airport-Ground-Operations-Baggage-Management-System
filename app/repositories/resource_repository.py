from sqlalchemy import select

from app.models.resource_allocation import ResourceAllocation
from app.repositories.base import BaseRepository, overlapping_active
from app.utils.enums import AssignmentStatus, ResourceType


class ResourceRepository(BaseRepository[ResourceAllocation]):
    model = ResourceAllocation
    entity_name = "Resource allocation"

    def by_assignment(self, resource_type: ResourceType, assignment_id: int) -> ResourceAllocation | None:
        return self.db.scalar(select(ResourceAllocation).where(
            ResourceAllocation.resource_type == resource_type, ResourceAllocation.assignment_id == assignment_id))

    def staff_conflicts(self, staff_id, start, end, exclude_flight_id=None):
        stmt = overlapping_active(ResourceAllocation, ResourceAllocation.resource_id, staff_id, start, end,
                                  exclude_flight_id).where(ResourceAllocation.resource_type == ResourceType.STAFF)
        return list(self.db.scalars(stmt).all())

    def busy_resource_ids(self, resource_type, start, end) -> set[int]:
        return set(self.db.scalars(select(ResourceAllocation.resource_id).where(
            ResourceAllocation.resource_type == resource_type,
            ResourceAllocation.status == AssignmentStatus.ACTIVE,
            ResourceAllocation.start_time < end, ResourceAllocation.end_time > start)).all())

    def search(self, resource_type=None, resource_id=None, flight_id=None, status=None, start=None, end=None):
        stmt = select(ResourceAllocation)
        if resource_type:
            stmt = stmt.where(ResourceAllocation.resource_type == resource_type)
        if resource_id:
            stmt = stmt.where(ResourceAllocation.resource_id == resource_id)
        if flight_id:
            stmt = stmt.where(ResourceAllocation.flight_id == flight_id)
        if status:
            stmt = stmt.where(ResourceAllocation.status == status)
        if start:
            stmt = stmt.where(ResourceAllocation.start_time >= start)
        if end:
            stmt = stmt.where(ResourceAllocation.start_time < end)
        return stmt

    # --- ledger helpers used by gate / counter / equipment services ---
    def record(self, resource_type: ResourceType, resource_id: int, flight_id: int, start, end,
               assignment_id: int | None = None, allocated_by_id: int | None = None,
               role_description: str | None = None, remarks: str | None = None) -> ResourceAllocation:
        return self.create(resource_type=resource_type, resource_id=resource_id, flight_id=flight_id,
                           assignment_id=assignment_id, start_time=start, end_time=end,
                           allocated_by_id=allocated_by_id, role_description=role_description, remarks=remarks)

    def release_by_assignment(self, resource_type: ResourceType, assignment_id: int, status, when) -> None:
        alloc = self.by_assignment(resource_type, assignment_id)
        if alloc and alloc.status == AssignmentStatus.ACTIVE:
            alloc.status = status
            alloc.released_at = when
