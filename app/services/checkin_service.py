import re

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.constants import CHECKIN_ALLOWED_STATUSES, SEAT_LETTERS, SEAT_PATTERN, SEAT_ROWS
from app.core.exceptions import BusinessRuleError, ConflictError
from app.models.checkin import CheckIn
from app.models.flight import Flight
from app.models.user import User
from app.repositories.checkin_repository import CheckInRepository
from app.repositories.counter_repository import CounterRepository
from app.repositories.flight_repository import FlightRepository
from app.repositories.passenger_repository import PassengerRepository
from app.schemas.checkin import CheckInCreate
from app.services.audit_service import AuditService, snapshot
from app.services.boarding_pass_service import BoardingPassService
from app.utils.datetime_utils import utcnow
from app.utils.enums import AuditAction, BookingStatus, CheckInChannel, CheckInStatus, FlightStatus, PassengerStatus


def next_free_seat(taken: set[str], capacity: int) -> str | None:
    rows = min(SEAT_ROWS, max(1, -(-capacity // len(SEAT_LETTERS))))
    for row in range(1, rows + 1):
        for letter in SEAT_LETTERS:
            seat = f"{row}{letter}"
            if seat not in taken:
                return seat
    return None


def validate_seat(seat: str, capacity: int) -> str:
    seat = seat.upper()
    m = re.match(SEAT_PATTERN, seat)
    if not m:
        raise BusinessRuleError(f"Invalid seat number '{seat}'")
    rows = max(1, -(-capacity // len(SEAT_LETTERS)))
    if int(m.group(1)) > rows or m.group(2) not in SEAT_LETTERS:
        raise BusinessRuleError(f"Seat {seat} does not exist on this aircraft (rows 1-{rows}, seats {SEAT_LETTERS})")
    return seat


class CheckInService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = CheckInRepository(db)
        self.flights = FlightRepository(db)
        self.passengers = PassengerRepository(db)
        self.counters = CounterRepository(db)
        self.boarding = BoardingPassService(db)
        self.audit = AuditService(db)

    def _validate_flight(self, flight: Flight) -> None:
        if flight.status not in CHECKIN_ALLOWED_STATUSES:
            raise BusinessRuleError(
                f"Check-in is not open for flight {flight.flight_number} (status {flight.status.value})",
                code="CHECKIN_NOT_OPEN")

    def check_in(self, data: CheckInCreate, user: User) -> tuple[CheckIn, object]:
        flight = self.flights.get_or_404(data.flight_id, lock=True)  # lock serialises seat allocation
        passenger = self.passengers.get_or_404(data.passenger_id)
        if passenger.status != PassengerStatus.ACTIVE:
            raise BusinessRuleError("Passenger is not active")
        self._validate_flight(flight)
        booking = self.passengers.get_booking(passenger.id, flight.id)
        if not booking:
            raise BusinessRuleError("Passenger is not booked on this flight", code="NOT_BOOKED")
        if booking.status in (BookingStatus.CANCELLED, BookingStatus.NO_SHOW):
            raise BusinessRuleError(f"Booking is {booking.status.value}")

        existing = self.repo.get_for_passenger_flight(passenger.id, flight.id)
        if existing and existing.status != CheckInStatus.CANCELLED:
            raise ConflictError("Passenger is already checked in for this flight", code="DUPLICATE_CHECKIN",
                                details={"checkin_id": existing.id})

        # counter validation: must hold an active assignment for this flight
        counter_id = data.counter_id
        if counter_id:
            self.counters.get_or_404(counter_id)
            if not self.counters.active_assignment(counter_id, flight.id):
                raise BusinessRuleError("Counter is not assigned to this flight")
        elif data.channel == CheckInChannel.COUNTER:
            active = self.counters.active_assignments_for_flight(flight.id)
            counter_id = active[0].counter_id if active else None

        taken = self.repo.taken_seats(flight.id)
        if data.seat_number:
            seat = validate_seat(data.seat_number, flight.seat_capacity)
            if seat in taken:
                raise ConflictError(f"Seat {seat} is already taken", code="SEAT_TAKEN")
        else:
            seat = next_free_seat(taken, flight.seat_capacity)
            if not seat:
                raise BusinessRuleError("No seats available")

        now = utcnow()
        if existing:  # re-check-in after a cancellation
            checkin = existing
            checkin.seat_number, checkin.counter_id, checkin.channel = seat, counter_id, data.channel
            checkin.checkin_time, checkin.status, checkin.checked_in_by_id = now, CheckInStatus.CHECKED_IN, user.id
        else:
            checkin = CheckIn(passenger_id=passenger.id, flight_id=flight.id, booking_id=booking.id,
                              counter_id=counter_id, seat_number=seat, checkin_time=now, channel=data.channel,
                              checked_in_by_id=user.id)
            self.db.add(checkin)
        try:
            self.db.flush()
        except IntegrityError as exc:  # race on the (passenger, flight) unique key
            self.db.rollback()
            raise ConflictError("Passenger is already checked in for this flight", code="DUPLICATE_CHECKIN") from exc
        booking.status = BookingStatus.CHECKED_IN
        bp = self.boarding.generate(checkin, flight, booking)
        self.audit.log(AuditAction.CHECKIN_CREATED, "checkin", checkin.id, None,
                       {**snapshot(checkin), "boarding_pass": bp.reference}, user.id)
        self.db.commit()
        return checkin, bp

    def get(self, checkin_id: int) -> CheckIn:
        return self.repo.get_or_404(checkin_id)

    def change_seat(self, checkin_id: int, seat_number: str, user: User) -> CheckIn:
        checkin = self.repo.get_or_404(checkin_id)
        if checkin.status != CheckInStatus.CHECKED_IN:
            raise BusinessRuleError("Seat can only be changed for an active check-in")
        flight = self.flights.get_or_404(checkin.flight_id, lock=True)
        seat = validate_seat(seat_number, flight.seat_capacity)
        if seat in self.repo.taken_seats(flight.id) - {checkin.seat_number}:
            raise ConflictError(f"Seat {seat} is already taken", code="SEAT_TAKEN")
        prev = {"seat_number": checkin.seat_number}
        checkin.seat_number = seat
        if checkin.boarding_pass:
            checkin.boarding_pass.seat_number = seat
        self.audit.log(AuditAction.CHECKIN_UPDATED, "checkin", checkin.id, prev, {"seat_number": seat}, user.id)
        self.db.commit()
        return checkin

    def cancel(self, checkin_id: int, user: User) -> CheckIn:
        checkin = self.repo.get_or_404(checkin_id)
        if checkin.status != CheckInStatus.CHECKED_IN:
            raise BusinessRuleError(f"Cannot cancel a check-in that is {checkin.status.value}")
        checkin.status = CheckInStatus.CANCELLED
        booking = self.passengers.get_booking_by_id(checkin.booking_id)
        if booking:
            booking.status = BookingStatus.BOOKED
        if checkin.boarding_pass:
            checkin.boarding_pass.is_valid = False
        self.audit.log(AuditAction.CHECKIN_CANCELLED, "checkin", checkin.id, {"status": "CHECKED_IN"},
                       {"status": "CANCELLED"}, user.id)
        self.db.commit()
        return checkin

    def board(self, checkin_id: int, user: User) -> CheckIn:
        checkin = self.repo.get_or_404(checkin_id)
        flight = self.flights.get_or_404(checkin.flight_id)
        if flight.status != FlightStatus.BOARDING:
            raise BusinessRuleError("Flight is not boarding")
        if checkin.status != CheckInStatus.CHECKED_IN:
            raise BusinessRuleError(f"Check-in is {checkin.status.value}")
        checkin.status = CheckInStatus.BOARDED
        checkin.boarded_at = utcnow()
        booking = self.passengers.get_booking_by_id(checkin.booking_id)
        if booking:
            booking.status = BookingStatus.BOARDED
        self.audit.log(AuditAction.CHECKIN_UPDATED, "checkin", checkin.id, {"status": "CHECKED_IN"},
                       {"status": "BOARDED"}, user.id)
        self.db.commit()
        return checkin
