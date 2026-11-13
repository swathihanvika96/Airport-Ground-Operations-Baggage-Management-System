from sqlalchemy import select

from app.models.assignment import GateAssignment
from app.models.gate import Gate
from app.models.terminal import Terminal
from app.repositories.base import BaseRepository, overlapping_active
from app.utils.enums import AssignmentStatus


class GateRepository(BaseRepository[Gate]):
    model = Gate
    entity_name = "Gate"

    def search(self, terminal_id=None, airport_id=None, status=None, is_active=None):
        stmt = select(Gate)
        if terminal_id:
            stmt = stmt.where(Gate.terminal_id == terminal_id)
        if airport_id:
            stmt = stmt.join(Terminal, Terminal.id == Gate.terminal_id).where(Terminal.airport_id == airport_id)
        if status:
            stmt = stmt.where(Gate.status == status)
        if is_active is not None:
            stmt = stmt.where(Gate.is_active.is_(is_active))
        return stmt

    def conflicts(self, gate_id, start, end, exclude_flight_id=None) -> list[GateAssignment]:
        return list(self.db.scalars(overlapping_active(
            GateAssignment, GateAssignment.gate_id, gate_id, start, end, exclude_flight_id)).all())

    def active_assignment_for_flight(self, flight_id) -> GateAssignment | None:
        return self.db.scalar(select(GateAssignment).where(
            GateAssignment.flight_id == flight_id, GateAssignment.status == AssignmentStatus.ACTIVE))

    def has_active_assignments(self, gate_id) -> bool:
        return self.db.scalar(select(GateAssignment.id).where(
            GateAssignment.gate_id == gate_id, GateAssignment.status == AssignmentStatus.ACTIVE).limit(1)) is not None

    def get_assignment(self, assignment_id) -> GateAssignment | None:
        return self.db.get(GateAssignment, assignment_id)

    def assignments(self, gate_id=None, flight_id=None, status=None):
        stmt = select(GateAssignment)
        if gate_id:
            stmt = stmt.where(GateAssignment.gate_id == gate_id)
        if flight_id:
            stmt = stmt.where(GateAssignment.flight_id == flight_id)
        if status:
            stmt = stmt.where(GateAssignment.status == status)
        return stmt.order_by(GateAssignment.created_at.desc(), GateAssignment.id.desc())
