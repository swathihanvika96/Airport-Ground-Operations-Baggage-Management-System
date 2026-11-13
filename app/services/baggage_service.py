from sqlalchemy.orm import Session

from app.core.constants import BAGGAGE_EDITABLE_STATUSES, BAGGAGE_WEIGHT_LIMITS, FLIGHT_CLOSED_STATUSES
from app.core.exceptions import BusinessRuleError, ConflictError, NotFoundError
from app.models.baggage import Baggage
from app.models.baggage_tracking import BaggageTrackingEvent
from app.models.user import User
from app.repositories.baggage_repository import BaggageRepository
from app.repositories.checkin_repository import CheckInRepository
from app.repositories.flight_repository import FlightRepository
from app.repositories.passenger_repository import PassengerRepository
from app.schemas.baggage import BaggageCreate, BaggageUpdate
from app.services.audit_service import AuditService, snapshot
from app.utils.enums import AuditAction, BaggageCategory, BaggageStatus, BookingStatus, CheckInStatus
from app.utils.reference_generator import baggage_tag_number


def validate_weight(category: BaggageCategory, weight: float) -> None:
    limit = BAGGAGE_WEIGHT_LIMITS[category]
    if weight > limit:
        raise BusinessRuleError(f"{category.value} baggage cannot exceed {limit} kg (got {weight} kg)",
                                code="BAGGAGE_OVERWEIGHT",
                                details={"limit_kg": limit, "suggestion": "Use OVERSIZED or SPECIAL category"})


class BaggageService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = BaggageRepository(db)
        self.flights = FlightRepository(db)
        self.passengers = PassengerRepository(db)
        self.checkins = CheckInRepository(db)
        self.audit = AuditService(db)

    def register(self, data: BaggageCreate, user: User) -> Baggage:
        flight = self.flights.get_or_404(data.flight_id)
        self.passengers.get_or_404(data.passenger_id)
        if flight.status in FLIGHT_CLOSED_STATUSES:
            raise BusinessRuleError(f"Cannot register baggage for a {flight.status.value} flight")
        booking = self.passengers.get_booking(data.passenger_id, data.flight_id)
        if not booking or booking.status in (BookingStatus.CANCELLED, BookingStatus.NO_SHOW):
            raise BusinessRuleError("Passenger has no valid booking on this flight", code="NOT_BOOKED")
        validate_weight(data.category, data.weight_kg)

        if data.tag_number:  # duplicate baggage tag prevention
            tag = data.tag_number.upper()
            if self.repo.get_by_tag(tag):
                raise ConflictError(f"Baggage tag {tag} already exists", code="DUPLICATE_BAGGAGE_TAG")
        else:
            tag = baggage_tag_number(flight.airline_code)
            while self.repo.get_by_tag(tag):
                tag = baggage_tag_number(flight.airline_code)

        checkin = self.checkins.get_for_passenger_flight(data.passenger_id, data.flight_id)
        active_checkin = checkin if checkin and checkin.status == CheckInStatus.CHECKED_IN else None
        destination = (data.destination or flight.arrival_airport.code).upper()
        bag = self.repo.create(
            tag_number=tag, passenger_id=data.passenger_id, flight_id=flight.id,
            checkin_id=active_checkin.id if active_checkin else None, weight_kg=data.weight_kg,
            category=data.category, destination=destination, description=data.description,
            status=BaggageStatus.REGISTERED, current_location="Check-in")
        self.db.add(BaggageTrackingEvent(baggage_id=bag.id, previous_status=None, status=BaggageStatus.REGISTERED,
                                         location="Check-in", remarks="Baggage registered", updated_by_id=user.id))
        if active_checkin:
            active_checkin.baggage_count += 1
        self.audit.log(AuditAction.BAGGAGE_REGISTERED, "baggage", bag.id, None, snapshot(bag), user.id)
        self.db.commit()
        return bag

    def get(self, baggage_id: int) -> Baggage:
        return self.repo.get_or_404(baggage_id)

    def get_by_tag(self, tag: str) -> Baggage:
        bag = self.repo.get_by_tag(tag)
        if not bag:
            raise NotFoundError("Baggage", tag)
        return bag

    def update(self, baggage_id: int, data: BaggageUpdate, user: User) -> Baggage:
        bag = self.repo.get_or_404(baggage_id)
        if bag.status not in BAGGAGE_EDITABLE_STATUSES:
            raise BusinessRuleError(f"Baggage details cannot be edited once it is {bag.status.value}")
        changes = data.model_dump(exclude_unset=True)
        validate_weight(changes.get("category", bag.category), changes.get("weight_kg", bag.weight_kg))
        if "destination" in changes and changes["destination"]:
            changes["destination"] = changes["destination"].upper()
        prev = snapshot(bag, list(changes))
        self.repo.update(bag, changes)
        self.audit.log(AuditAction.BAGGAGE_REGISTERED, "baggage", bag.id, prev, snapshot(bag, list(changes)), user.id)
        self.db.commit()
        return bag
