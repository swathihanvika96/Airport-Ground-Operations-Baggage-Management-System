"""Security screening with hold / release workflow."""
from sqlalchemy.orm import Session

from app.core.exceptions import BusinessRuleError, NotFoundError
from app.core.permissions import NOTIFY_BAGGAGE
from app.models.baggage_screening import BaggageScreening
from app.models.user import User
from app.repositories.baggage_repository import BaggageRepository
from app.repositories.screening_repository import ScreeningRepository
from app.schemas.baggage_screening import ScreeningCreate
from app.services.audit_service import AuditService
from app.services.baggage_tracking_service import BaggageTrackingService
from app.services.notification_service import NotificationService
from app.utils.datetime_utils import utcnow
from app.utils.enums import AuditAction, BaggageStatus, NotificationType, ScreeningStatus, Severity

SCREENABLE = {BaggageStatus.CHECKIN_COMPLETED, BaggageStatus.SECURITY_SCREENING}


class BaggageScreeningService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = ScreeningRepository(db)
        self.bags = BaggageRepository(db)
        self.tracking = BaggageTrackingService(db)
        self.audit = AuditService(db)
        self.notifications = NotificationService(db)

    def screen(self, baggage_id: int, data: ScreeningCreate, user: User) -> BaggageScreening:
        bag = self.bags.get_or_404(baggage_id, lock=True)
        if bag.status not in SCREENABLE:
            raise BusinessRuleError(
                f"Baggage in status {bag.status.value} cannot be screened; it must be CHECKIN_COMPLETED first")
        latest = self.repo.latest_for_baggage(bag.id)
        if latest and latest.status == ScreeningStatus.HOLD:
            raise BusinessRuleError("Baggage is currently on hold; release the hold first", code="BAGGAGE_ON_HOLD")
        if bag.status == BaggageStatus.CHECKIN_COMPLETED:
            self.tracking._record(bag, BaggageStatus.SECURITY_SCREENING, user, "Security screening",
                                  "Entered security screening")
        status = ScreeningStatus(data.result)
        record = BaggageScreening(baggage_id=bag.id, status=status, screening_officer_id=user.id,
                                  screened_at=utcnow(), machine_id=data.machine_id, remarks=data.remarks,
                                  hold_reason=data.hold_reason)
        self.db.add(record)
        bag.is_on_hold = status in (ScreeningStatus.HOLD, ScreeningStatus.REJECTED)
        self.db.flush()
        self.audit.log(AuditAction.BAGGAGE_SCREENED, "baggage", bag.id, None,
                       {"screening_id": record.id, "result": status, "hold_reason": data.hold_reason}, user.id)
        if bag.is_on_hold:
            self.notifications.notify_roles(
                NOTIFY_BAGGAGE, NotificationType.BAGGAGE_DELAY, f"Baggage {bag.tag_number} on security hold",
                f"Bag {bag.tag_number} held at screening: {data.hold_reason}", "baggage", bag.id, Severity.HIGH)
        self.db.commit()
        return record

    def release(self, screening_id: int, remarks: str | None, user: User) -> BaggageScreening:
        record = self.repo.get_or_404(screening_id)
        if record.status != ScreeningStatus.HOLD:
            raise BusinessRuleError(f"Only HOLD screenings can be released (current: {record.status.value})")
        bag = self.bags.get_or_404(record.baggage_id, lock=True)
        record.status = ScreeningStatus.RELEASED
        record.released_at = utcnow()
        record.released_by_id = user.id
        record.release_remarks = remarks
        bag.is_on_hold = False
        self.audit.log(AuditAction.BAGGAGE_RELEASED, "baggage", bag.id, {"screening": "HOLD"},
                       {"screening": "RELEASED", "remarks": remarks}, user.id)
        self.db.commit()
        return record

    def get(self, screening_id: int) -> BaggageScreening:
        rec = self.repo.get(screening_id)
        if not rec:
            raise NotFoundError("Screening record", screening_id)
        return rec
