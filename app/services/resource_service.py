"""Unified resource allocation (gates, counters, staff, equipment) with conflict prevention and history."""
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.constants import DEFAULT_RESOURCE_WINDOW_MINUTES, FLIGHT_CLOSED_STATUSES
from app.core.exceptions import BusinessRuleError, ConflictError
from app.models.assignment import CounterAssignment, GateAssignment
from app.models.equipment_assignment import EquipmentAssignment
from app.models.flight import Flight
from app.models.resource_allocation import ResourceAllocation
from app.models.user import User
from app.repositories.flight_repository import FlightRepository
from app.repositories.resource_repository import ResourceRepository
from app.repositories.staff_repository import StaffRepository
from app.schemas.resource_allocation import AllocationCreate
from app.services.audit_service import AuditService
from app.services.counter_service import CounterService
from app.services.equipment_service import EquipmentService
from app.services.gate_service import GateService
from app.services.staff_service import UNAVAILABLE, ensure_staff_available
from app.utils.datetime_utils import utcnow
from app.utils.enums import AssignmentStatus, AuditAction, ResourceType


class ResourceService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = ResourceRepository(db)
        self.flights = FlightRepository(db)
        self.staff = StaffRepository(db)
        self.audit = AuditService(db)

    def _window(self, flight: Flight, start, end):
        if start and end:
            return start, end
        dep = flight.current_departure
        return dep - timedelta(minutes=DEFAULT_RESOURCE_WINDOW_MINUTES), dep

    def allocate(self, data: AllocationCreate, user: User) -> ResourceAllocation:
        rt = data.resource_type
        if rt == ResourceType.GATE:
            a = GateService(self.db).assign(data.resource_id, data.flight_id, user, data.start_time, data.end_time,
                                            data.remarks, commit=False)
        elif rt == ResourceType.COUNTER:
            a = CounterService(self.db).assign(data.resource_id, data.flight_id, user, data.start_time,
                                               data.end_time, data.remarks, commit=False)
        elif rt == ResourceType.EQUIPMENT:
            a = EquipmentService(self.db).assign(data.resource_id, data.flight_id, user, data.start_time,
                                                 data.end_time, data.remarks, commit=False)
        else:
            alloc = self._allocate_staff(data, user)
            self.db.commit()
            return alloc
        alloc = self.repo.by_assignment(rt, a.id)
        if data.role_description:
            alloc.role_description = data.role_description
        self.db.commit()
        return alloc

    def _allocate_staff(self, data: AllocationCreate, user: User) -> ResourceAllocation:
        staff = self.staff.get_or_404(data.resource_id, lock=True)
        flight = self.flights.get_or_404(data.flight_id)
        if flight.status in FLIGHT_CLOSED_STATUSES:
            raise BusinessRuleError(f"Cannot allocate staff to a {flight.status.value} flight")
        ensure_staff_available(staff)
        start, end = self._window(flight, data.start_time, data.end_time)
        conflicts = self.repo.staff_conflicts(staff.id, start, end)
        if conflicts:
            raise ConflictError(f"{staff.full_name} is already allocated in this time window",
                                code="STAFF_CONFLICT",
                                details=[{"allocation_id": c.id, "flight_id": c.flight_id} for c in conflicts])
        alloc = self.repo.record(ResourceType.STAFF, staff.id, flight.id, start, end, None, user.id,
                                 data.role_description, data.remarks)
        self.audit.log(AuditAction.STAFF_ALLOCATED, "flight", flight.id, None,
                       {"staff_id": staff.id, "allocation_id": alloc.id, "start_time": start, "end_time": end},
                       user.id)
        return alloc

    def release(self, allocation_id: int, user: User) -> ResourceAllocation:
        alloc = self.repo.get_or_404(allocation_id)
        if alloc.status != AssignmentStatus.ACTIVE:
            raise BusinessRuleError("Allocation is not active")
        if alloc.resource_type == ResourceType.GATE:
            GateService(self.db).release(alloc.assignment_id, user, commit=False)
        elif alloc.resource_type == ResourceType.COUNTER:
            CounterService(self.db).release(alloc.assignment_id, user, commit=False)
        elif alloc.resource_type == ResourceType.EQUIPMENT:
            EquipmentService(self.db).release(alloc.assignment_id, user, commit=False)
        else:
            alloc.status = AssignmentStatus.RELEASED
            alloc.released_at = utcnow()
            self.audit.log(AuditAction.RESOURCE_RELEASED, "resource_allocation", alloc.id,
                           {"status": "ACTIVE"}, {"status": "RELEASED"}, user.id)
        self.db.commit()
        self.db.refresh(alloc)
        return alloc

    def release_all_for_flight(self, flight: Flight, user: User) -> None:
        """Called when a flight departs or is cancelled (no commit; caller owns the transaction)."""
        active = AssignmentStatus.ACTIVE
        gs, cs, es = GateService(self.db), CounterService(self.db), EquipmentService(self.db)
        for a in self.db.scalars(select(GateAssignment).where(GateAssignment.flight_id == flight.id,
                                                              GateAssignment.status == active)).all():
            gs.release(a.id, user, commit=False)
        for a in self.db.scalars(select(CounterAssignment).where(CounterAssignment.flight_id == flight.id,
                                                                 CounterAssignment.status == active)).all():
            cs.release(a.id, user, commit=False)
        for a in self.db.scalars(select(EquipmentAssignment).where(EquipmentAssignment.flight_id == flight.id,
                                                                   EquipmentAssignment.status == active)).all():
            es.release(a.id, user, commit=False)
        now = utcnow()
        for alloc in self.repo.list(self.repo.search(resource_type=ResourceType.STAFF, flight_id=flight.id,
                                                     status=active)):
            alloc.status = AssignmentStatus.RELEASED
            alloc.released_at = now

    def availability(self, resource_type: ResourceType, start, end, terminal_id=None, airport_id=None) -> list[dict]:
        if end <= start:
            raise BusinessRuleError("end_time must be after start_time")
        if resource_type == ResourceType.GATE:
            return [{"resource_type": resource_type, "resource_id": g.id, "label": f"Gate {g.gate_number}",
                     "status": g.status.value}
                    for g in GateService(self.db).available(start, end, terminal_id, airport_id)]
        if resource_type == ResourceType.COUNTER:
            return [{"resource_type": resource_type, "resource_id": c.id, "label": f"Counter {c.counter_number}",
                     "status": c.status.value}
                    for c in CounterService(self.db).available(start, end, terminal_id, airport_id)]
        if resource_type == ResourceType.EQUIPMENT:
            return [{"resource_type": resource_type, "resource_id": e.id,
                     "label": f"{e.equipment_code} ({e.equipment_type.value})", "status": e.status.value}
                    for e in EquipmentService(self.db).available(start, end, terminal_id=terminal_id)]
        busy = self.repo.busy_resource_ids(ResourceType.STAFF, start, end)
        staff = self.staff.list(self.staff.search(is_active=True))
        return [{"resource_type": resource_type, "resource_id": s.id, "label": f"{s.full_name} ({s.designation})",
                 "status": s.availability_status.value}
                for s in staff if s.id not in busy and s.availability_status not in UNAVAILABLE]
