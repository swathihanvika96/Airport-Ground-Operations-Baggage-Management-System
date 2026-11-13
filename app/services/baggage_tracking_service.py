from sqlalchemy.orm import Session

from app.core.constants import BAGGAGE_STATUS_TRANSITIONS
from app.core.exceptions import BusinessRuleError, InvalidTransitionError
from app.core.permissions import NOTIFY_BAGGAGE, NOTIFY_FLIGHT_OPS
from app.models.baggage import Baggage
from app.models.baggage_tracking import BaggageTrackingEvent
from app.models.user import User
from app.repositories.baggage_repository import BaggageRepository
from app.repositories.checkin_repository import CheckInRepository
from app.repositories.screening_repository import ScreeningRepository
from app.repositories.tracking_repository import TrackingRepository
from app.services.audit_service import AuditService
from app.services.notification_service import NotificationService
from app.utils.datetime_utils import utcnow
from app.utils.enums import (
    AuditAction,
    BaggageStatus,
    CheckInStatus,
    NotificationType,
    ScreeningStatus,
    Severity,
)

BS = BaggageStatus
# Statuses that can only be reached after the bag passed security screening
POST_SCREENING = {BS.SORTING, BS.LOADED, BS.IN_TRANSIT, BS.UNLOADED, BS.DELIVERED}


def validate_baggage_transition(current: BaggageStatus, target: BaggageStatus) -> None:
    allowed = BAGGAGE_STATUS_TRANSITIONS.get(current, set())
    if target not in allowed:
        raise InvalidTransitionError("baggage", current, target, allowed)


class BaggageTrackingService:
    def __init__(self, db: Session):
        self.db = db
        self.bags = BaggageRepository(db)
        self.repo = TrackingRepository(db)
        self.screenings = ScreeningRepository(db)
        self.checkins = CheckInRepository(db)
        self.audit = AuditService(db)
        self.notifications = NotificationService(db)

    def _record(self, bag: Baggage, target: BaggageStatus, user: User | None, location=None, remarks=None):
        prev = bag.status
        bag.status = target
        if location:
            bag.current_location = location
        event = BaggageTrackingEvent(baggage_id=bag.id, previous_status=prev, status=target, location=location,
                                     remarks=remarks, updated_by_id=user.id if user else None, timestamp=utcnow())
        self.db.add(event)
        self.audit.log(AuditAction.BAGGAGE_STATUS_CHANGED, "baggage", bag.id, {"status": prev},
                       {"status": target, "location": location, "remarks": remarks},
                       user.id if user else None)
        return event

    def update_status(self, baggage_id: int, target: BaggageStatus, user: User, location=None,
                      remarks=None) -> Baggage:
        bag = self.bags.get_or_404(baggage_id, lock=True)
        validate_baggage_transition(bag.status, target)
        if bag.is_on_hold and target not in (BS.MISSING, BS.DELAYED):
            raise BusinessRuleError("Baggage is on security hold; release it before moving it", code="BAGGAGE_ON_HOLD")
        if target == BS.CHECKIN_COMPLETED:
            ci = self.checkins.get_for_passenger_flight(bag.passenger_id, bag.flight_id)
            if not ci or ci.status == CheckInStatus.CANCELLED:
                raise BusinessRuleError("Passenger must be checked in before baggage check-in is completed")
            if bag.checkin_id is None:
                bag.checkin_id = ci.id
                ci.baggage_count += 1
        if target in POST_SCREENING:
            latest = self.screenings.latest_for_baggage(bag.id)
            if not latest or latest.status not in (ScreeningStatus.CLEARED, ScreeningStatus.RELEASED):
                raise BusinessRuleError("Baggage must be cleared by security screening first",
                                        code="SCREENING_REQUIRED")
        self._record(bag, target, user, location, remarks)
        self._notify(bag, target, remarks)
        self.db.commit()
        return bag

    def _notify(self, bag: Baggage, status: BaggageStatus, remarks: str | None) -> None:
        if status == BS.MISSING:
            self.notifications.notify_roles(NOTIFY_BAGGAGE + NOTIFY_FLIGHT_OPS, NotificationType.MISSING_BAGGAGE,
                                            f"Missing baggage {bag.tag_number}",
                                            f"Bag {bag.tag_number} (flight {bag.flight.flight_number}) reported missing. "
                                            f"{remarks or ''}".strip(), "baggage", bag.id, Severity.HIGH)
        elif status == BS.DELAYED:
            self.notifications.notify_roles(NOTIFY_BAGGAGE, NotificationType.BAGGAGE_DELAY,
                                            f"Delayed baggage {bag.tag_number}",
                                            f"Bag {bag.tag_number} (flight {bag.flight.flight_number}) is delayed. "
                                            f"{remarks or ''}".strip(), "baggage", bag.id, Severity.MEDIUM)

    def history(self, baggage_id: int) -> list[BaggageTrackingEvent]:
        self.bags.get_or_404(baggage_id)
        return self.repo.history(baggage_id)

    def track_by_tag(self, tag: str) -> dict:
        from app.services.baggage_service import BaggageService
        bag = BaggageService(self.db).get_by_tag(tag)
        return {"baggage": bag, "timeline": self.repo.history(bag.id)}
