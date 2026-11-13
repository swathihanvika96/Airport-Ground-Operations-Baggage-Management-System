from datetime import timedelta

from sqlalchemy.orm import Session

from app.core.constants import DEFAULT_RESOURCE_WINDOW_MINUTES, FLIGHT_CLOSED_STATUSES
from app.core.exceptions import BusinessRuleError, ConflictError, NotFoundError
from app.models.equipment import Equipment
from app.models.equipment_assignment import EquipmentAssignment
from app.models.equipment_maintenance import EquipmentMaintenance
from app.models.user import User
from app.repositories.equipment_repository import EquipmentRepository
from app.repositories.flight_repository import FlightRepository
from app.repositories.resource_repository import ResourceRepository
from app.schemas.equipment import EquipmentCreate, EquipmentUpdate, MaintenanceCreate
from app.services.audit_service import AuditService, snapshot
from app.utils.datetime_utils import utcnow
from app.utils.enums import (
    AssignmentStatus,
    AuditAction,
    EquipmentStatus,
    MaintenanceStatus,
    ResourceType,
)


def ensure_equipment_available(eq: Equipment, start=None) -> None:
    if eq.status != EquipmentStatus.AVAILABLE and eq.status != EquipmentStatus.IN_USE:
        raise BusinessRuleError(f"Equipment {eq.equipment_code} is {eq.status.value}", code="EQUIPMENT_UNAVAILABLE")
    ref_date = (start or utcnow()).date()
    if eq.next_maintenance_date and eq.next_maintenance_date < ref_date:
        raise BusinessRuleError(f"Equipment {eq.equipment_code} is overdue for maintenance "
                                f"(due {eq.next_maintenance_date})", code="MAINTENANCE_OVERDUE")


class EquipmentService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = EquipmentRepository(db)
        self.flights = FlightRepository(db)
        self.ledger = ResourceRepository(db)
        self.audit = AuditService(db)

    def create(self, data: EquipmentCreate, user: User) -> Equipment:
        code = data.equipment_code.upper()
        if self.repo.exists(equipment_code=code):
            raise ConflictError(f"Equipment code {code} already exists")
        eq = self.repo.create(**data.model_dump(exclude={"equipment_code"}), equipment_code=code)
        self.db.commit()
        return eq

    def get(self, equipment_id: int) -> Equipment:
        return self.repo.get_or_404(equipment_id)

    def update(self, equipment_id: int, data: EquipmentUpdate, user: User) -> Equipment:
        eq = self.repo.get_or_404(equipment_id)
        changes = data.model_dump(exclude_unset=True)
        prev = snapshot(eq, list(changes))
        self.repo.update(eq, changes)
        self.audit.log(AuditAction.EQUIPMENT_UPDATED, "equipment", eq.id, prev, snapshot(eq, list(changes)), user.id)
        self.db.commit()
        return eq

    def set_status(self, equipment_id: int, status: EquipmentStatus, user: User, remarks=None) -> Equipment:
        eq = self.repo.get_or_404(equipment_id)
        if status == EquipmentStatus.IN_USE:
            raise BusinessRuleError("IN_USE is set automatically by flight assignments")
        active = self.repo.list(self.repo.assignments(equipment_id=eq.id, status=AssignmentStatus.ACTIVE))
        if active and status in (EquipmentStatus.MAINTENANCE, EquipmentStatus.OUT_OF_SERVICE):
            raise ConflictError("Equipment has active assignments; release them first")
        prev = {"status": eq.status}
        eq.status = status
        self.audit.log(AuditAction.EQUIPMENT_UPDATED, "equipment", eq.id, prev,
                       {"status": status, "remarks": remarks}, user.id)
        self.db.commit()
        return eq

    def available(self, start, end, equipment_type=None, terminal_id=None) -> list[Equipment]:
        items = self.repo.list(self.repo.search(equipment_type=equipment_type, terminal_id=terminal_id))
        out = []
        for eq in items:
            try:
                ensure_equipment_available(eq, start)
            except BusinessRuleError:
                continue
            if not self.repo.conflicts(eq.id, start, end):
                out.append(eq)
        return out

    def assign(self, equipment_id: int, flight_id: int, user: User, start=None, end=None, remarks=None,
               commit: bool = True) -> EquipmentAssignment:
        eq = self.repo.get_or_404(equipment_id, lock=True)
        flight = self.flights.get_or_404(flight_id)
        if flight.status in FLIGHT_CLOSED_STATUSES:
            raise BusinessRuleError(f"Cannot allocate equipment to a {flight.status.value} flight")
        if not (start and end):
            dep = flight.current_departure
            start, end = dep - timedelta(minutes=DEFAULT_RESOURCE_WINDOW_MINUTES), dep
        ensure_equipment_available(eq, start)
        conflicts = self.repo.conflicts(eq.id, start, end)
        if conflicts:
            raise ConflictError(f"Equipment {eq.equipment_code} is already allocated in this time window",
                                code="EQUIPMENT_CONFLICT",
                                details=[{"assignment_id": c.id, "flight_id": c.flight_id} for c in conflicts])
        assignment = EquipmentAssignment(equipment_id=eq.id, flight_id=flight.id, start_time=start, end_time=end,
                                         assigned_by_id=user.id, remarks=remarks)
        self.db.add(assignment)
        self.db.flush()
        self.ledger.record(ResourceType.EQUIPMENT, eq.id, flight.id, start, end, assignment.id, user.id,
                           remarks=remarks)
        eq.status = EquipmentStatus.IN_USE
        self.audit.log(AuditAction.EQUIPMENT_ALLOCATED, "equipment", eq.id, None,
                       {"flight_id": flight.id, "assignment_id": assignment.id, "start_time": start,
                        "end_time": end}, user.id)
        if commit:
            self.db.commit()
        return assignment

    def release(self, assignment_id: int, user: User, commit: bool = True) -> EquipmentAssignment:
        a = self.repo.get_assignment(assignment_id)
        if not a:
            raise NotFoundError("Equipment assignment", assignment_id)
        if a.status != AssignmentStatus.ACTIVE:
            raise BusinessRuleError("Assignment is not active")
        now = utcnow()
        a.status = AssignmentStatus.RELEASED
        a.released_at = now
        used_from = min(max(a.start_time, a.created_at), now)
        a.usage_hours = round(max(0.0, (now - used_from).total_seconds() / 3600), 2)
        eq = a.equipment
        eq.usage_hours = round((eq.usage_hours or 0) + a.usage_hours, 2)
        self.ledger.release_by_assignment(ResourceType.EQUIPMENT, a.id, AssignmentStatus.RELEASED, now)
        self.db.flush()
        if eq.status == EquipmentStatus.IN_USE and not self.repo.list(
                self.repo.assignments(equipment_id=eq.id, status=AssignmentStatus.ACTIVE)):
            eq.status = EquipmentStatus.AVAILABLE
        self.audit.log(AuditAction.EQUIPMENT_RELEASED, "equipment", eq.id, {"assignment_id": a.id, "status": "ACTIVE"},
                       {"status": "RELEASED", "usage_hours": a.usage_hours}, user.id)
        if commit:
            self.db.commit()
        return a

    # ---------- maintenance ----------
    def schedule_maintenance(self, data: MaintenanceCreate, user: User) -> EquipmentMaintenance:
        eq = self.repo.get_or_404(data.equipment_id)
        m = EquipmentMaintenance(**data.model_dump())
        self.db.add(m)
        if not eq.next_maintenance_date or data.scheduled_date < eq.next_maintenance_date:
            eq.next_maintenance_date = data.scheduled_date
        self.db.commit()
        return m

    def _maintenance(self, maintenance_id) -> EquipmentMaintenance:
        m = self.repo.get_maintenance(maintenance_id)
        if not m:
            raise NotFoundError("Maintenance record", maintenance_id)
        return m

    def start_maintenance(self, maintenance_id: int, user: User) -> EquipmentMaintenance:
        m = self._maintenance(maintenance_id)
        if m.status != MaintenanceStatus.SCHEDULED:
            raise BusinessRuleError(f"Maintenance is {m.status.value}")
        eq = self.repo.get_or_404(m.equipment_id)
        if self.repo.list(self.repo.assignments(equipment_id=eq.id, status=AssignmentStatus.ACTIVE)):
            raise ConflictError("Equipment is allocated to a flight; release it first")
        m.status = MaintenanceStatus.IN_PROGRESS
        m.started_at = utcnow()
        m.technician_id = m.technician_id or user.id
        eq.status = EquipmentStatus.MAINTENANCE
        self.db.commit()
        return m

    def complete_maintenance(self, maintenance_id: int, user: User, remarks=None, next_date=None):
        m = self._maintenance(maintenance_id)
        if m.status != MaintenanceStatus.IN_PROGRESS:
            raise BusinessRuleError("Only IN_PROGRESS maintenance can be completed")
        eq = self.repo.get_or_404(m.equipment_id)
        now = utcnow()
        m.status = MaintenanceStatus.COMPLETED
        m.completed_at = now
        m.remarks = remarks or m.remarks
        eq.status = EquipmentStatus.AVAILABLE
        eq.last_maintenance_date = now.date()
        eq.next_maintenance_date = next_date or (now.date() + timedelta(days=90))
        self.audit.log(AuditAction.EQUIPMENT_UPDATED, "equipment", eq.id, {"status": "MAINTENANCE"},
                       {"status": "AVAILABLE", "maintenance_id": m.id}, user.id)
        self.db.commit()
        return m

    def cancel_maintenance(self, maintenance_id: int, user: User):
        m = self._maintenance(maintenance_id)
        if m.status != MaintenanceStatus.SCHEDULED:
            raise BusinessRuleError("Only SCHEDULED maintenance can be cancelled")
        m.status = MaintenanceStatus.CANCELLED
        self.db.commit()
        return m
