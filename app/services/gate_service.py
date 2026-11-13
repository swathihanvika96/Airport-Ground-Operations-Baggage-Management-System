from datetime import timedelta

from sqlalchemy.orm import Session

from app.core.constants import FLIGHT_CLOSED_STATUSES, GATE_WINDOW_AFTER_DEPARTURE, GATE_WINDOW_BEFORE_DEPARTURE
from app.core.exceptions import BusinessRuleError, ConflictError, NotFoundError
from app.core.permissions import NOTIFY_FLIGHT_OPS, NOTIFY_GATE
from app.models.assignment import GateAssignment
from app.models.flight import Flight
from app.models.gate import Gate
from app.models.user import User
from app.repositories.flight_repository import FlightRepository
from app.repositories.gate_repository import GateRepository
from app.repositories.resource_repository import ResourceRepository
from app.repositories.terminal_repository import TerminalRepository
from app.schemas.gate import GateCreate, GateUpdate
from app.services.audit_service import AuditService
from app.services.notification_service import NotificationService
from app.utils.datetime_utils import utcnow
from app.utils.enums import AssignmentStatus, AuditAction, GateStatus, NotificationType, ResourceType, Severity

UNUSABLE = {GateStatus.MAINTENANCE, GateStatus.CLOSED}


def default_gate_window(flight: Flight):
    dep = flight.current_departure
    return dep - timedelta(minutes=GATE_WINDOW_BEFORE_DEPARTURE), dep + timedelta(minutes=GATE_WINDOW_AFTER_DEPARTURE)


class GateService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = GateRepository(db)
        self.terminals = TerminalRepository(db)
        self.flights = FlightRepository(db)
        self.ledger = ResourceRepository(db)
        self.audit = AuditService(db)
        self.notifications = NotificationService(db)

    def create(self, data: GateCreate, user: User) -> Gate:
        self.terminals.get_or_404(data.terminal_id)
        number = data.gate_number.upper()
        if self.repo.exists(terminal_id=data.terminal_id, gate_number=number):
            raise ConflictError(f"Gate {number} already exists in this terminal")
        gate = self.repo.create(terminal_id=data.terminal_id, gate_number=number, gate_type=data.gate_type)
        self.db.commit()
        return gate

    def get(self, gate_id: int) -> Gate:
        return self.repo.get_or_404(gate_id)

    def update(self, gate_id: int, data: GateUpdate, user: User) -> Gate:
        gate = self.repo.get_or_404(gate_id)
        changes = data.model_dump(exclude_unset=True)
        if changes.get("status") in UNUSABLE and self.repo.has_active_assignments(gate.id):
            raise ConflictError("Gate has active assignments; release or reassign them first")
        self.repo.update(gate, changes)
        self.db.commit()
        return gate

    def available(self, start, end, terminal_id=None, airport_id=None) -> list[Gate]:
        gates = self.repo.list(self.repo.search(terminal_id=terminal_id, airport_id=airport_id, is_active=True))
        return [g for g in gates if g.status not in UNUSABLE and not self.repo.conflicts(g.id, start, end)]

    def assign(self, gate_id: int, flight_id: int, user: User, start=None, end=None, remarks=None,
               commit: bool = True) -> GateAssignment:
        gate = self.repo.get_or_404(gate_id, lock=True)  # row lock serialises concurrent assignments
        flight = self.flights.get_or_404(flight_id, lock=True)
        if flight.status in FLIGHT_CLOSED_STATUSES:
            raise BusinessRuleError(f"Cannot assign a gate to a {flight.status.value} flight")
        if not gate.is_active or gate.status in UNUSABLE:
            raise BusinessRuleError(f"Gate {gate.gate_number} is not usable ({gate.status.value})")
        terminal = self.terminals.get_or_404(gate.terminal_id)
        if terminal.airport_id != flight.departure_airport_id:
            raise BusinessRuleError("Gate must be at the flight's departure airport")
        if not (start and end):
            start, end = default_gate_window(flight)
        conflicts = self.repo.conflicts(gate.id, start, end, exclude_flight_id=flight.id)
        if conflicts:
            raise ConflictError(f"Gate {gate.gate_number} is already assigned in this time window",
                                details=[{"assignment_id": c.id, "flight_id": c.flight_id, "start_time": c.start_time,
                                          "end_time": c.end_time} for c in conflicts])
        previous = self.repo.active_assignment_for_flight(flight.id)
        if previous and previous.gate_id == gate.id:
            raise ConflictError("Flight is already assigned to this gate")
        old_gate_number = None
        if previous:  # gate change
            old_gate_number = previous.gate.gate_number
            self._release(previous, user, AssignmentStatus.CANCELLED)
        assignment = GateAssignment(gate_id=gate.id, flight_id=flight.id, start_time=start, end_time=end,
                                    assigned_by_id=user.id, remarks=remarks)
        self.db.add(assignment)
        self.db.flush()
        self.ledger.record(ResourceType.GATE, gate.id, flight.id, start, end, assignment.id, user.id, remarks=remarks)
        gate.status = GateStatus.OCCUPIED
        flight.gate_id = gate.id
        self.audit.log(AuditAction.GATE_ASSIGNED, "flight", flight.id,
                       {"gate": old_gate_number}, {"gate": gate.gate_number, "assignment_id": assignment.id,
                                                   "start_time": start, "end_time": end}, user.id)
        if old_gate_number:
            self.notifications.notify_roles(
                NOTIFY_GATE + NOTIFY_FLIGHT_OPS, NotificationType.GATE_CHANGE, f"Gate change: {flight.flight_number}",
                f"Flight {flight.flight_number} moved from gate {old_gate_number} to gate {gate.gate_number}.",
                "flight", flight.id, Severity.HIGH)
        if commit:
            self.db.commit()
        return assignment

    def _release(self, assignment: GateAssignment, user: User, status=AssignmentStatus.RELEASED) -> None:
        now = utcnow()
        assignment.status = status
        assignment.released_at = now
        self.ledger.release_by_assignment(ResourceType.GATE, assignment.id, status, now)
        self.db.flush()
        gate = assignment.gate
        if not self.repo.has_active_assignments(gate.id) and gate.status == GateStatus.OCCUPIED:
            gate.status = GateStatus.AVAILABLE
        flight = assignment.flight
        if flight.gate_id == gate.id and status == AssignmentStatus.CANCELLED:
            flight.gate_id = None
        self.audit.log(AuditAction.GATE_RELEASED, "gate_assignment", assignment.id,
                       {"status": AssignmentStatus.ACTIVE}, {"status": status}, user.id)

    def release(self, assignment_id: int, user: User, commit: bool = True) -> GateAssignment:
        assignment = self.repo.get_assignment(assignment_id)
        if not assignment:
            raise NotFoundError("Gate assignment", assignment_id)
        if assignment.status != AssignmentStatus.ACTIVE:
            raise BusinessRuleError("Assignment is not active")
        self._release(assignment, user)
        if commit:
            self.db.commit()
        return assignment
