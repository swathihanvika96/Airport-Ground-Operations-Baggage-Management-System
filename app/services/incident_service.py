from sqlalchemy.orm import Session

from app.core.constants import INCIDENT_STATUS_TRANSITIONS
from app.core.exceptions import BusinessRuleError, InvalidTransitionError
from app.core.permissions import NOTIFY_INCIDENT
from app.models.incident import Incident
from app.models.incident_history import IncidentHistory
from app.models.user import User
from app.repositories.flight_repository import FlightRepository
from app.repositories.incident_repository import IncidentRepository
from app.repositories.terminal_repository import TerminalRepository
from app.repositories.user_repository import UserRepository
from app.schemas.incident import IncidentAssign, IncidentCreate, IncidentStatusUpdate, IncidentUpdate
from app.services.audit_service import AuditService, snapshot
from app.services.notification_service import NotificationService
from app.utils.datetime_utils import utcnow
from app.utils.enums import AuditAction, IncidentStatus, NotificationType, Severity
from app.utils.reference_generator import incident_reference


class IncidentService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = IncidentRepository(db)
        self.flights = FlightRepository(db)
        self.terminals = TerminalRepository(db)
        self.users = UserRepository(db)
        self.audit = AuditService(db)
        self.notifications = NotificationService(db)

    def _history(self, inc: Incident, action: str, user: User, from_s=None, to_s=None, remarks=None):
        inc.history.append(IncidentHistory(action=action, from_status=from_s, to_status=to_s, remarks=remarks,
                                           changed_by_id=user.id, timestamp=utcnow()))

    def create(self, data: IncidentCreate, user: User) -> Incident:
        if data.flight_id:
            self.flights.get_or_404(data.flight_id)
        if data.terminal_id:
            self.terminals.get_or_404(data.terminal_id)
        now = utcnow()
        ref = incident_reference(now)
        while self.repo.exists(reference=ref):
            ref = incident_reference(now)
        inc = Incident(**data.model_dump(), reference=ref, reported_by_id=user.id, reported_at=now,
                       status=IncidentStatus.OPEN)
        self._history(inc, "CREATED", user, None, IncidentStatus.OPEN, data.description[:500])
        self.db.add(inc)
        self.db.flush()
        self.audit.log(AuditAction.INCIDENT_CREATED, "incident", inc.id, None, snapshot(inc), user.id)
        prio = Severity.CRITICAL if data.severity == Severity.CRITICAL else (
            Severity.HIGH if data.severity == Severity.HIGH else Severity.MEDIUM)
        self.notifications.notify_roles(NOTIFY_INCIDENT, NotificationType.OPERATIONAL_INCIDENT,
                                        f"[{data.severity.value}] Incident {ref}: {data.title}",
                                        f"{data.category.value} incident reported. {data.description[:300]}",
                                        "incident", inc.id, prio)
        self.db.commit()
        return inc

    def get(self, incident_id: int) -> Incident:
        return self.repo.get_or_404(incident_id)

    def update(self, incident_id: int, data: IncidentUpdate, user: User) -> Incident:
        inc = self.repo.get_or_404(incident_id)
        if inc.status == IncidentStatus.CLOSED:
            raise BusinessRuleError("Closed incidents cannot be modified")
        changes = data.model_dump(exclude_unset=True)
        prev = snapshot(inc, list(changes))
        self.repo.update(inc, changes)
        self._history(inc, "UPDATED", user, remarks=", ".join(f"{k} changed" for k in changes))
        self.audit.log(AuditAction.INCIDENT_UPDATED, "incident", inc.id, prev, snapshot(inc, list(changes)), user.id)
        self.db.commit()
        return inc

    def assign(self, incident_id: int, data: IncidentAssign, user: User) -> Incident:
        inc = self.repo.get_or_404(incident_id)
        if inc.status in (IncidentStatus.RESOLVED, IncidentStatus.CLOSED):
            raise BusinessRuleError(f"Incident is {inc.status.value}")
        if data.assigned_to_id:
            assignee = self.users.get_or_404(data.assigned_to_id)
            inc.assigned_to_id = assignee.id
            self.notifications.notify_users([assignee.id], NotificationType.OPERATIONAL_INCIDENT,
                                            f"Incident assigned: {inc.reference}", inc.title, "incident", inc.id,
                                            Severity.HIGH)
        if data.assigned_team is not None:
            inc.assigned_team = data.assigned_team
        self._history(inc, "ASSIGNED", user, remarks=data.remarks or
                      f"team={inc.assigned_team}, user={inc.assigned_to_id}")
        self.audit.log(AuditAction.INCIDENT_UPDATED, "incident", inc.id, None,
                       {"assigned_team": inc.assigned_team, "assigned_to_id": inc.assigned_to_id}, user.id)
        self.db.commit()
        return inc

    def change_status(self, incident_id: int, data: IncidentStatusUpdate, user: User) -> Incident:
        inc = self.repo.get_or_404(incident_id)
        allowed = INCIDENT_STATUS_TRANSITIONS.get(inc.status, set())
        if data.status not in allowed:
            raise InvalidTransitionError("incident", inc.status, data.status, allowed)
        prev = inc.status
        if data.status == IncidentStatus.RESOLVED:
            if not (data.resolution_details or inc.resolution_details):
                raise BusinessRuleError("resolution_details are required to resolve an incident")
            inc.resolution_details = data.resolution_details or inc.resolution_details
            inc.resolved_at = utcnow()
            inc.resolved_by_id = user.id
        elif prev == IncidentStatus.RESOLVED and data.status == IncidentStatus.IN_PROGRESS:
            inc.resolved_at = None  # reopened
        inc.status = data.status
        self._history(inc, "STATUS_CHANGED", user, prev, data.status, data.remarks or data.resolution_details)
        action = AuditAction.INCIDENT_RESOLVED if data.status == IncidentStatus.RESOLVED else AuditAction.INCIDENT_UPDATED
        self.audit.log(action, "incident", inc.id, {"status": prev},
                       {"status": data.status, "resolution_details": inc.resolution_details}, user.id)
        self.db.commit()
        return inc
