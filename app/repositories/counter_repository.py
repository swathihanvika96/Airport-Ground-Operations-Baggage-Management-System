from sqlalchemy import select

from app.models.assignment import CounterAssignment
from app.models.counter import CheckInCounter
from app.models.terminal import Terminal
from app.repositories.base import BaseRepository, overlapping_active
from app.utils.enums import AssignmentStatus


class CounterRepository(BaseRepository[CheckInCounter]):
    model = CheckInCounter
    entity_name = "Check-in counter"

    def search(self, terminal_id=None, airport_id=None, status=None, is_active=None):
        stmt = select(CheckInCounter)
        if terminal_id:
            stmt = stmt.where(CheckInCounter.terminal_id == terminal_id)
        if airport_id:
            stmt = stmt.join(Terminal, Terminal.id == CheckInCounter.terminal_id).where(Terminal.airport_id == airport_id)
        if status:
            stmt = stmt.where(CheckInCounter.status == status)
        if is_active is not None:
            stmt = stmt.where(CheckInCounter.is_active.is_(is_active))
        return stmt

    def conflicts(self, counter_id, start, end, exclude_flight_id=None):
        return list(self.db.scalars(overlapping_active(
            CounterAssignment, CounterAssignment.counter_id, counter_id, start, end, exclude_flight_id)).all())

    def active_assignment(self, counter_id, flight_id) -> CounterAssignment | None:
        return self.db.scalar(select(CounterAssignment).where(
            CounterAssignment.counter_id == counter_id, CounterAssignment.flight_id == flight_id,
            CounterAssignment.status == AssignmentStatus.ACTIVE))

    def active_assignments_for_flight(self, flight_id) -> list[CounterAssignment]:
        return list(self.db.scalars(select(CounterAssignment).where(
            CounterAssignment.flight_id == flight_id, CounterAssignment.status == AssignmentStatus.ACTIVE)).all())

    def has_active_assignments(self, counter_id) -> bool:
        return self.db.scalar(select(CounterAssignment.id).where(
            CounterAssignment.counter_id == counter_id,
            CounterAssignment.status == AssignmentStatus.ACTIVE).limit(1)) is not None

    def get_assignment(self, assignment_id) -> CounterAssignment | None:
        return self.db.get(CounterAssignment, assignment_id)

    def assignments(self, counter_id=None, flight_id=None, status=None):
        stmt = select(CounterAssignment)
        if counter_id:
            stmt = stmt.where(CounterAssignment.counter_id == counter_id)
        if flight_id:
            stmt = stmt.where(CounterAssignment.flight_id == flight_id)
        if status:
            stmt = stmt.where(CounterAssignment.status == status)
        return stmt.order_by(CounterAssignment.created_at.desc(), CounterAssignment.id.desc())
