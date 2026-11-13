"""Aircraft turnaround workflow with activity dependencies, timings and delay tracking."""
from sqlalchemy.orm import Session

from app.core.constants import (
    ACTIVITY_DONE_STATUSES,
    FLIGHT_CLOSED_STATUSES,
    TURNAROUND_ACTIVITY_PLAN,
    TURNAROUND_PREREQUISITES,
)
from app.core.exceptions import BusinessRuleError, ConflictError, NotFoundError
from app.core.permissions import NOTIFY_FLIGHT_OPS, NOTIFY_GROUND
from app.models.turnaround import Turnaround
from app.models.turnaround_activity import TurnaroundActivity
from app.models.user import User
from app.repositories.flight_repository import FlightRepository
from app.repositories.staff_repository import StaffRepository
from app.repositories.turnaround_repository import TurnaroundRepository
from app.schemas.turnaround import ActivityAssign, ActivityComplete, ActivityStart, TurnaroundCreate
from app.services.audit_service import AuditService
from app.services.notification_service import NotificationService
from app.services.staff_service import ensure_staff_available
from app.utils.datetime_utils import minutes_between, utcnow
from app.utils.enums import (
    ActivityStatus,
    AuditAction,
    NotificationType,
    Severity,
    TurnaroundActivityType,
    TurnaroundStatus,
)

TA = TurnaroundActivityType


def compute_activity_delay(planned_minutes: int, start, end) -> tuple[int, int]:
    """Return (actual_duration, delay_minutes) for an activity."""
    actual = minutes_between(start, end) or 0
    return actual, max(0, actual - planned_minutes)


class TurnaroundService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = TurnaroundRepository(db)
        self.flights = FlightRepository(db)
        self.staff = StaffRepository(db)
        self.audit = AuditService(db)
        self.notifications = NotificationService(db)

    def create(self, data: TurnaroundCreate, user: User) -> Turnaround:
        flight = self.flights.get_or_404(data.flight_id)
        if flight.status in FLIGHT_CLOSED_STATUSES:
            raise BusinessRuleError(f"Cannot plan a turnaround for a {flight.status.value} flight")
        if data.arrival_flight_id:
            inbound = self.flights.get_or_404(data.arrival_flight_id)
            if inbound.arrival_airport_id != flight.departure_airport_id:
                raise BusinessRuleError("Inbound flight must arrive at the outbound flight's departure airport")
        if self.repo.exists(flight_id=flight.id):
            raise ConflictError("A turnaround already exists for this flight")
        ta = Turnaround(**data.model_dump(), created_by_id=user.id)
        for seq, (atype, minutes, _) in enumerate(TURNAROUND_ACTIVITY_PLAN, start=1):
            ta.activities.append(TurnaroundActivity(activity_type=atype, sequence=seq,
                                                    planned_duration_minutes=minutes))
        self.db.add(ta)
        self.db.flush()
        self.audit.log(AuditAction.TURNAROUND_UPDATED, "turnaround", ta.id, None,
                       {"created": True, "flight_id": flight.id}, user.id)
        self.db.commit()
        return ta

    def get(self, turnaround_id: int) -> Turnaround:
        return self.repo.get_or_404(turnaround_id)

    def get_for_flight(self, flight_id: int) -> Turnaround:
        ta = self.repo.get_by(flight_id=flight_id)
        if not ta:
            raise NotFoundError("Turnaround for flight", flight_id)
        return ta

    def _activity(self, turnaround_id: int, activity_id: int) -> TurnaroundActivity:
        act = self.repo.get_activity(activity_id)
        if not act or act.turnaround_id != turnaround_id:
            raise NotFoundError("Turnaround activity", activity_id)
        return act

    def assign_parking(self, turnaround_id: int, stand: str, user: User) -> Turnaround:
        ta = self.repo.get_or_404(turnaround_id)
        if ta.status in (TurnaroundStatus.COMPLETED, TurnaroundStatus.CANCELLED):
            raise BusinessRuleError(f"Turnaround is {ta.status.value}")
        prev = {"parking_stand": ta.parking_stand}
        ta.parking_stand = stand.upper()
        self.audit.log(AuditAction.TURNAROUND_UPDATED, "turnaround", ta.id, prev,
                       {"parking_stand": ta.parking_stand}, user.id)
        self.db.commit()
        return ta

    def assign_activity(self, turnaround_id: int, activity_id: int, data: ActivityAssign, user: User):
        act = self._activity(turnaround_id, activity_id)
        if act.status in ACTIVITY_DONE_STATUSES:
            raise BusinessRuleError("Activity is already finished")
        if data.assigned_staff_id:
            ensure_staff_available(self.staff.get_or_404(data.assigned_staff_id))
            act.assigned_staff_id = data.assigned_staff_id
        if data.assigned_team is not None:
            act.assigned_team = data.assigned_team
        self.db.commit()
        return act

    def start_activity(self, turnaround_id: int, activity_id: int, data: ActivityStart, user: User):
        ta = self.repo.get_or_404(turnaround_id, lock=True)
        if ta.status in (TurnaroundStatus.COMPLETED, TurnaroundStatus.CANCELLED):
            raise BusinessRuleError(f"Turnaround is {ta.status.value}")
        act = self._activity(turnaround_id, activity_id)
        if act.status != ActivityStatus.PENDING:
            raise BusinessRuleError(f"Activity is already {act.status.value}")
        done = {a.activity_type for a in ta.activities if a.status in ACTIVITY_DONE_STATUSES}
        missing = TURNAROUND_PREREQUISITES[act.activity_type] - done
        if missing:
            raise BusinessRuleError(f"Cannot start {act.activity_type.value}; prerequisites not completed",
                                    code="PREREQUISITES_PENDING", details={"pending": sorted(m.value for m in missing)})
        if data.assigned_staff_id:
            ensure_staff_available(self.staff.get_or_404(data.assigned_staff_id))
            act.assigned_staff_id = data.assigned_staff_id
        if data.assigned_team:
            act.assigned_team = data.assigned_team
        act.status = ActivityStatus.IN_PROGRESS
        act.start_time = data.start_time or utcnow()
        if ta.status == TurnaroundStatus.PLANNED:
            ta.status = TurnaroundStatus.IN_PROGRESS
            ta.actual_start = act.start_time
        self.audit.log(AuditAction.TURNAROUND_UPDATED, "turnaround_activity", act.id, {"status": "PENDING"},
                       {"status": "IN_PROGRESS", "activity": act.activity_type}, user.id)
        self.db.commit()
        return act

    def complete_activity(self, turnaround_id: int, activity_id: int, data: ActivityComplete, user: User):
        ta = self.repo.get_or_404(turnaround_id, lock=True)
        act = self._activity(turnaround_id, activity_id)
        if act.status != ActivityStatus.IN_PROGRESS:
            raise BusinessRuleError("Only an IN_PROGRESS activity can be completed")
        if act.activity_type == TA.PARKING_ASSIGNMENT and not ta.parking_stand:
            raise BusinessRuleError("Assign a parking stand before completing PARKING_ASSIGNMENT")
        end = data.completion_time or utcnow()
        if end < act.start_time:
            raise BusinessRuleError("completion_time cannot be before start_time")
        actual, delay = compute_activity_delay(act.planned_duration_minutes, act.start_time, end)
        if delay > 0 and not data.delay_reason:
            raise BusinessRuleError(
                f"Activity overran its planned {act.planned_duration_minutes} min by {delay} min; delay_reason required",
                code="DELAY_REASON_REQUIRED")
        act.status = ActivityStatus.COMPLETED
        act.completion_time = end
        act.actual_duration_minutes = actual
        act.delay_minutes = delay
        act.is_delayed = delay > 0
        act.delay_reason = data.delay_reason
        act.remarks = data.remarks or act.remarks
        if act.is_delayed:
            self.notifications.notify_roles(
                NOTIFY_GROUND + NOTIFY_FLIGHT_OPS, NotificationType.TURNAROUND_DELAY,
                f"Turnaround delay: {ta.flight.flight_number}",
                f"{act.activity_type.value} overran by {delay} min. Reason: {data.delay_reason}",
                "turnaround", ta.id, Severity.HIGH if delay >= 15 else Severity.MEDIUM)
        if act.activity_type == TA.DEPARTURE_READINESS:
            self._finish(ta, end)
        self.audit.log(AuditAction.TURNAROUND_UPDATED, "turnaround_activity", act.id, {"status": "IN_PROGRESS"},
                       {"status": "COMPLETED", "activity": act.activity_type, "delay_minutes": delay}, user.id)
        self.db.commit()
        return act

    def skip_activity(self, turnaround_id: int, activity_id: int, remarks: str, user: User):
        act = self._activity(turnaround_id, activity_id)
        if act.activity_type in (TA.AIRCRAFT_ARRIVAL, TA.FINAL_INSPECTION, TA.DEPARTURE_READINESS):
            raise BusinessRuleError(f"{act.activity_type.value} is mandatory and cannot be skipped")
        if act.status != ActivityStatus.PENDING:
            raise BusinessRuleError("Only PENDING activities can be skipped")
        act.status = ActivityStatus.SKIPPED
        act.remarks = remarks
        self.db.commit()
        return act

    def _finish(self, ta: Turnaround, end) -> None:
        ta.status = TurnaroundStatus.COMPLETED
        ta.actual_end = end
        ta.total_duration_minutes = minutes_between(ta.actual_start, end)
        ta.delay_minutes = max(0, (ta.total_duration_minutes or 0) - ta.target_duration_minutes)
        reasons = [f"{a.activity_type.value}: {a.delay_reason}" for a in ta.activities if a.is_delayed]
        ta.delay_reason = "; ".join(reasons) or None
        if ta.delay_minutes > 0:
            self.notifications.notify_roles(
                NOTIFY_GROUND + NOTIFY_FLIGHT_OPS, NotificationType.TURNAROUND_DELAY,
                f"Turnaround over target: {ta.flight.flight_number}",
                f"Turnaround took {ta.total_duration_minutes} min (target {ta.target_duration_minutes}).",
                "turnaround", ta.id, Severity.MEDIUM)

    def cancel(self, turnaround_id: int, user: User) -> Turnaround:
        ta = self.repo.get_or_404(turnaround_id)
        if ta.status == TurnaroundStatus.COMPLETED:
            raise BusinessRuleError("Completed turnarounds cannot be cancelled")
        ta.status = TurnaroundStatus.CANCELLED
        self.db.commit()
        return ta
