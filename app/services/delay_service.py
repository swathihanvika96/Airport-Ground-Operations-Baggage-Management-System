"""Flight delay recording with delay calculation and history."""
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.core.constants import FLIGHT_CLOSED_STATUSES, FLIGHT_STATUS_TRANSITIONS
from app.core.exceptions import BusinessRuleError
from app.core.permissions import NOTIFY_BAGGAGE, NOTIFY_CHECKIN, NOTIFY_FLIGHT_OPS, NOTIFY_GATE
from app.models.flight_delay import FlightDelay
from app.models.user import User
from app.repositories.delay_repository import DelayRepository
from app.repositories.flight_repository import FlightRepository
from app.schemas.flight_delay import DelayCreate, DelayUpdate
from app.services.audit_service import AuditService, snapshot
from app.services.notification_service import NotificationService
from app.utils.datetime_utils import minutes_between
from app.utils.enums import AuditAction, FlightStatus, NotificationType, Severity


def calculate_delay(expected_departure: datetime, delay_minutes: int | None = None,
                    updated_departure: datetime | None = None) -> tuple[int, datetime]:
    """Return (delay_minutes, updated_departure) from either input. Both given -> must agree."""
    if delay_minutes is None and updated_departure is None:
        raise BusinessRuleError("Provide delay_minutes or updated_departure")
    if updated_departure is not None:
        computed = minutes_between(expected_departure, updated_departure)
        if computed is None or computed <= 0:
            raise BusinessRuleError("updated_departure must be later than the current expected departure")
        if delay_minutes is not None and delay_minutes != computed:
            raise BusinessRuleError(
                f"delay_minutes ({delay_minutes}) does not match updated_departure ({computed} min later)")
        return computed, updated_departure
    if delay_minutes <= 0:
        raise BusinessRuleError("delay_minutes must be positive")
    return delay_minutes, expected_departure + timedelta(minutes=delay_minutes)


def total_delay_minutes(scheduled: datetime, current: datetime) -> int:
    return max(0, minutes_between(scheduled, current) or 0)


def delay_severity(minutes: int) -> Severity:
    if minutes >= 180:
        return Severity.CRITICAL
    if minutes >= 60:
        return Severity.HIGH
    if minutes >= 15:
        return Severity.MEDIUM
    return Severity.LOW


class DelayService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = DelayRepository(db)
        self.flights = FlightRepository(db)
        self.audit = AuditService(db)
        self.notifications = NotificationService(db)

    def record(self, data: DelayCreate, user: User) -> FlightDelay:
        flight = self.flights.get_or_404(data.flight_id, lock=True)
        if flight.status in FLIGHT_CLOSED_STATUSES:
            raise BusinessRuleError(f"Cannot delay a {flight.status.value} flight")
        expected = flight.current_departure
        minutes, updated = calculate_delay(expected, data.delay_minutes, data.updated_departure)
        prev = snapshot(flight, ["status", "estimated_departure"])

        delay = FlightDelay(flight_id=flight.id, delay_category=data.delay_category, reason=data.reason,
                            delay_minutes=minutes, responsible_department=data.responsible_department,
                            expected_departure=expected, updated_departure=updated, recorded_by_id=user.id)
        self.db.add(delay)
        flight.estimated_departure = updated
        if flight.status != FlightStatus.DELAYED and FlightStatus.DELAYED in FLIGHT_STATUS_TRANSITIONS[flight.status]:
            flight.status = FlightStatus.DELAYED
        # keep the arrival consistent with the new departure
        self.db.flush()
        total = total_delay_minutes(flight.scheduled_departure, updated)
        self.audit.log(AuditAction.FLIGHT_DELAY_RECORDED, "flight", flight.id, prev,
                       {**snapshot(flight, ["status", "estimated_departure"]), "delay_id": delay.id,
                        "delay_minutes": minutes, "total_delay_minutes": total,
                        "category": data.delay_category}, user.id)
        self.notifications.notify_roles(
            NOTIFY_FLIGHT_OPS + NOTIFY_GATE + NOTIFY_CHECKIN + NOTIFY_BAGGAGE, NotificationType.FLIGHT_DELAY,
            f"Flight {flight.flight_number} delayed {minutes} min",
            f"{data.delay_category.value}: {data.reason}. New departure {updated:%Y-%m-%d %H:%M} UTC "
            f"(total delay {total} min).", "flight", flight.id, delay_severity(total))
        self.db.commit()
        return delay

    def update(self, delay_id: int, data: DelayUpdate, user: User) -> FlightDelay:
        delay = self.repo.get_or_404(delay_id)
        changes = data.model_dump(exclude_unset=True)
        prev = snapshot(delay, list(changes))
        self.repo.update(delay, changes)
        self.audit.log(AuditAction.FLIGHT_DELAY_UPDATED, "flight_delay", delay.id, prev,
                       snapshot(delay, list(changes)), user.id)
        self.db.commit()
        return delay

    def get(self, delay_id: int) -> FlightDelay:
        return self.repo.get_or_404(delay_id)

    def summary(self, flight_id: int) -> dict:
        flight = self.flights.get_or_404(flight_id)
        history = self.repo.history(flight.id)
        return {
            "flight_id": flight.id, "flight_number": flight.flight_number,
            "scheduled_departure": flight.scheduled_departure, "current_departure": flight.current_departure,
            "total_delay_minutes": total_delay_minutes(flight.scheduled_departure, flight.current_departure),
            "delay_count": len(history), "history": history,
        }
