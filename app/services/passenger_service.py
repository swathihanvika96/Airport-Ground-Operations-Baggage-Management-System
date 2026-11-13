from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.constants import FLIGHT_CLOSED_STATUSES
from app.core.exceptions import BusinessRuleError, ConflictError, NotFoundError
from app.models.baggage import Baggage
from app.models.passenger import Passenger, PassengerFlight
from app.models.user import User
from app.repositories.checkin_repository import CheckInRepository
from app.repositories.flight_repository import FlightRepository
from app.repositories.passenger_repository import PassengerRepository
from app.schemas.passenger import PassengerCreate, PassengerUpdate
from app.services.audit_service import AuditService, snapshot
from app.utils.enums import AuditAction, BookingStatus, TravelClass
from app.utils.reference_generator import booking_reference


class PassengerService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = PassengerRepository(db)
        self.flights = FlightRepository(db)
        self.checkins = CheckInRepository(db)
        self.audit = AuditService(db)

    def create(self, data: PassengerCreate, user: User) -> Passenger:
        ref = data.id_reference.upper()
        if self.repo.exists(id_type=data.id_type, id_reference=ref):
            raise ConflictError("A passenger with this identification reference already exists")
        passenger = self.repo.create(**data.model_dump(exclude={"id_reference", "flight_id", "travel_class"}),
                                     id_reference=ref)
        self.audit.log(AuditAction.PASSENGER_CREATED, "passenger", passenger.id, None, snapshot(passenger), user.id)
        if data.flight_id:
            self.add_booking(passenger.id, data.flight_id, data.travel_class, user, commit=False)
        self.db.commit()
        return passenger

    def get(self, passenger_id: int) -> Passenger:
        return self.repo.get_or_404(passenger_id)

    def update(self, passenger_id: int, data: PassengerUpdate, user: User) -> Passenger:
        p = self.repo.get_or_404(passenger_id)
        changes = data.model_dump(exclude_unset=True)
        self.repo.update(p, changes)
        self.db.commit()
        return p

    def add_booking(self, passenger_id: int, flight_id: int, travel_class: TravelClass, user: User,
                    commit: bool = True) -> PassengerFlight:
        self.repo.get_or_404(passenger_id)
        flight = self.flights.get_or_404(flight_id)
        if flight.status in FLIGHT_CLOSED_STATUSES:
            raise BusinessRuleError(f"Cannot book a {flight.status.value} flight")
        if self.repo.get_booking(passenger_id, flight_id):
            raise ConflictError("Passenger is already mapped to this flight")
        if self.repo.booked_count(flight_id) >= flight.seat_capacity:
            raise BusinessRuleError("Flight is fully booked")
        ref = booking_reference()
        while self.repo.booking_ref_exists(ref):
            ref = booking_reference()
        booking = PassengerFlight(passenger_id=passenger_id, flight_id=flight_id, booking_reference=ref,
                                  travel_class=travel_class)
        self.db.add(booking)
        self.db.flush()
        if commit:
            self.db.commit()
        return booking

    def update_booking_status(self, passenger_id: int, flight_id: int, status: BookingStatus, user: User):
        booking = self.repo.get_booking(passenger_id, flight_id)
        if not booking:
            raise NotFoundError("Booking")
        if status == BookingStatus.CHECKED_IN or status == BookingStatus.BOARDED:
            raise BusinessRuleError("Use the check-in / boarding endpoints to set this status")
        booking.status = status
        self.db.commit()
        return booking

    def bookings(self, passenger_id: int) -> list[PassengerFlight]:
        self.repo.get_or_404(passenger_id)
        return self.repo.bookings_for_passenger(passenger_id)

    def history(self, passenger_id: int) -> dict:
        passenger = self.repo.get_or_404(passenger_id)
        items = []
        for b in self.repo.bookings_for_passenger(passenger_id):
            ci = self.checkins.get_for_passenger_flight(passenger_id, b.flight_id)
            bp = ci.boarding_pass if ci else None
            bags = self.db.scalar(select(func.count(Baggage.id)).where(
                Baggage.passenger_id == passenger_id, Baggage.flight_id == b.flight_id)) or 0
            items.append({
                "booking": b, "flight_number": b.flight.flight_number,
                "scheduled_departure": b.flight.scheduled_departure, "flight_status": b.flight.status.value,
                "checkin_id": ci.id if ci else None, "seat_number": ci.seat_number if ci else None,
                "boarding_pass_reference": bp.reference if bp else None, "baggage_count": bags,
            })
        return {"passenger": passenger, "history": items}
