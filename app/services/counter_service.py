from datetime import timedelta

from sqlalchemy.orm import Session

from app.core.constants import (
    COUNTER_WINDOW_BEFORE_DEPARTURE,
    COUNTER_WINDOW_CLOSE_BEFORE_DEPARTURE,
    FLIGHT_CLOSED_STATUSES,
)
from app.core.exceptions import BusinessRuleError, ConflictError, NotFoundError
from app.models.assignment import CounterAssignment
from app.models.counter import CheckInCounter
from app.models.flight import Flight
from app.models.user import User
from app.repositories.counter_repository import CounterRepository
from app.repositories.flight_repository import FlightRepository
from app.repositories.resource_repository import ResourceRepository
from app.repositories.terminal_repository import TerminalRepository
from app.schemas.counter import CounterCreate, CounterUpdate
from app.services.audit_service import AuditService
from app.utils.datetime_utils import utcnow
from app.utils.enums import AssignmentStatus, AuditAction, CounterStatus, ResourceType

UNUSABLE = {CounterStatus.MAINTENANCE, CounterStatus.CLOSED}


def default_counter_window(flight: Flight):
    dep = flight.current_departure
    return (dep - timedelta(minutes=COUNTER_WINDOW_BEFORE_DEPARTURE),
            dep - timedelta(minutes=COUNTER_WINDOW_CLOSE_BEFORE_DEPARTURE))


class CounterService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = CounterRepository(db)
        self.terminals = TerminalRepository(db)
        self.flights = FlightRepository(db)
        self.ledger = ResourceRepository(db)
        self.audit = AuditService(db)

    def create(self, data: CounterCreate, user: User) -> CheckInCounter:
        self.terminals.get_or_404(data.terminal_id)
        number = data.counter_number.upper()
        if self.repo.exists(terminal_id=data.terminal_id, counter_number=number):
            raise ConflictError(f"Counter {number} already exists in this terminal")
        counter = self.repo.create(terminal_id=data.terminal_id, counter_number=number,
                                   airline_code=data.airline_code.upper() if data.airline_code else None)
        self.db.commit()
        return counter

    def get(self, counter_id: int) -> CheckInCounter:
        return self.repo.get_or_404(counter_id)

    def update(self, counter_id: int, data: CounterUpdate, user: User) -> CheckInCounter:
        counter = self.repo.get_or_404(counter_id)
        changes = data.model_dump(exclude_unset=True)
        if changes.get("status") in UNUSABLE and self.repo.has_active_assignments(counter.id):
            raise ConflictError("Counter has active assignments; release them first")
        self.repo.update(counter, changes)
        self.db.commit()
        return counter

    def available(self, start, end, terminal_id=None, airport_id=None) -> list[CheckInCounter]:
        counters = self.repo.list(self.repo.search(terminal_id=terminal_id, airport_id=airport_id, is_active=True))
        return [c for c in counters if c.status not in UNUSABLE and not self.repo.conflicts(c.id, start, end)]

    def assign(self, counter_id: int, flight_id: int, user: User, start=None, end=None, remarks=None,
               commit: bool = True) -> CounterAssignment:
        counter = self.repo.get_or_404(counter_id, lock=True)
        flight = self.flights.get_or_404(flight_id)
        if flight.status in FLIGHT_CLOSED_STATUSES:
            raise BusinessRuleError(f"Cannot assign a counter to a {flight.status.value} flight")
        if not counter.is_active or counter.status in UNUSABLE:
            raise BusinessRuleError(f"Counter {counter.counter_number} is not usable ({counter.status.value})")
        if self.terminals.get_or_404(counter.terminal_id).airport_id != flight.departure_airport_id:
            raise BusinessRuleError("Counter must be at the flight's departure airport")
        if counter.airline_code and counter.airline_code != flight.airline_code:
            raise BusinessRuleError(f"Counter is dedicated to airline {counter.airline_code}")
        if not (start and end):
            start, end = default_counter_window(flight)
        if self.repo.active_assignment(counter.id, flight.id):
            raise ConflictError("Counter is already assigned to this flight")
        conflicts = self.repo.conflicts(counter.id, start, end, exclude_flight_id=flight.id)
        if conflicts:
            raise ConflictError(f"Counter {counter.counter_number} is already assigned in this time window",
                                details=[{"assignment_id": c.id, "flight_id": c.flight_id} for c in conflicts])
        assignment = CounterAssignment(counter_id=counter.id, flight_id=flight.id, start_time=start, end_time=end,
                                       assigned_by_id=user.id, remarks=remarks)
        self.db.add(assignment)
        self.db.flush()
        self.ledger.record(ResourceType.COUNTER, counter.id, flight.id, start, end, assignment.id, user.id,
                           remarks=remarks)
        counter.status = CounterStatus.OPEN
        self.audit.log(AuditAction.COUNTER_ASSIGNED, "flight", flight.id, None,
                       {"counter": counter.counter_number, "assignment_id": assignment.id,
                        "start_time": start, "end_time": end}, user.id)
        if commit:
            self.db.commit()
        return assignment

    def release(self, assignment_id: int, user: User, commit: bool = True) -> CounterAssignment:
        assignment = self.repo.get_assignment(assignment_id)
        if not assignment:
            raise NotFoundError("Counter assignment", assignment_id)
        if assignment.status != AssignmentStatus.ACTIVE:
            raise BusinessRuleError("Assignment is not active")
        now = utcnow()
        assignment.status = AssignmentStatus.RELEASED
        assignment.released_at = now
        self.ledger.release_by_assignment(ResourceType.COUNTER, assignment.id, AssignmentStatus.RELEASED, now)
        self.db.flush()
        counter = assignment.counter
        if not self.repo.has_active_assignments(counter.id) and counter.status == CounterStatus.OPEN:
            counter.status = CounterStatus.AVAILABLE
        self.audit.log(AuditAction.COUNTER_RELEASED, "counter_assignment", assignment.id,
                       {"status": "ACTIVE"}, {"status": "RELEASED"}, user.id)
        if commit:
            self.db.commit()
        return assignment
