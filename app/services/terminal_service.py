from sqlalchemy.orm import Session

from app.core.exceptions import BusinessRuleError, ConflictError
from app.models.terminal import Terminal
from app.models.user import User
from app.repositories.airport_repository import AirportRepository
from app.repositories.terminal_repository import TerminalRepository
from app.schemas.terminal import TerminalCreate, TerminalUpdate
from app.services.audit_service import AuditService, snapshot
from app.utils.enums import AirportStatus, AuditAction, GateStatus


class TerminalService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = TerminalRepository(db)
        self.airports = AirportRepository(db)
        self.audit = AuditService(db)

    def create(self, data: TerminalCreate, user: User) -> Terminal:
        airport = self.airports.get_or_404(data.airport_id)
        if airport.operational_status == AirportStatus.CLOSED:
            raise BusinessRuleError("Cannot add a terminal to a closed airport")
        code = data.code.upper()
        if self.repo.exists(airport_id=airport.id, code=code):
            raise ConflictError(f"Terminal {code} already exists at {airport.code}")
        terminal = self.repo.create(**data.model_dump(exclude={"code"}), code=code)
        self.audit.log(AuditAction.TERMINAL_CREATED, "terminal", terminal.id, None, snapshot(terminal), user.id)
        self.db.commit()
        return terminal

    def get(self, terminal_id: int) -> Terminal:
        return self.repo.get_or_404(terminal_id)

    def update(self, terminal_id: int, data: TerminalUpdate, user: User) -> Terminal:
        terminal = self.repo.get_or_404(terminal_id)
        changes = data.model_dump(exclude_unset=True)
        prev = snapshot(terminal, list(changes))
        self.repo.update(terminal, changes)
        self.audit.log(AuditAction.TERMINAL_UPDATED, "terminal", terminal.id, prev, snapshot(terminal, list(changes)), user.id)
        self.db.commit()
        return terminal

    def map(self, terminal_id: int) -> dict:
        """Terminal mapping: terminal with its gates and check-in counters."""
        t = self.repo.get_or_404(terminal_id)
        gates = [{"id": g.id, "gate_number": g.gate_number, "gate_type": g.gate_type, "status": g.status,
                  "is_active": g.is_active} for g in sorted(t.gates, key=lambda g: g.gate_number)]
        counters = [{"id": c.id, "counter_number": c.counter_number, "airline_code": c.airline_code,
                     "status": c.status, "is_active": c.is_active}
                    for c in sorted(t.counters, key=lambda c: c.counter_number)]
        return {
            "id": t.id, "airport_id": t.airport_id, "code": t.code, "name": t.name, "capacity": t.capacity,
            "is_international": t.is_international, "status": t.status, "created_at": t.created_at,
            "gates": gates, "counters": counters,
            "summary": {
                "total_gates": len(gates),
                "available_gates": sum(1 for g in t.gates if g.is_active and g.status == GateStatus.AVAILABLE),
                "total_counters": len(counters),
            },
        }
