from datetime import timedelta

from sqlalchemy.orm import Session

from app.core.constants import BOARDING_GROUPS, BOARDING_STARTS_BEFORE_DEPARTURE
from app.core.exceptions import NotFoundError
from app.models.boarding_pass import BoardingPass
from app.models.checkin import CheckIn
from app.models.flight import Flight
from app.models.passenger import PassengerFlight
from app.repositories.checkin_repository import CheckInRepository
from app.utils.reference_generator import boarding_pass_reference


class BoardingPassService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = CheckInRepository(db)

    def generate(self, checkin: CheckIn, flight: Flight, booking: PassengerFlight) -> BoardingPass:
        existing = self.repo.boarding_pass_for_checkin(checkin.id)
        ref = boarding_pass_reference(flight.flight_number, flight.scheduled_departure)
        while self.repo.boarding_ref_exists(ref):
            ref = boarding_pass_reference(flight.flight_number, flight.scheduled_departure)
        boarding_time = flight.current_departure - timedelta(minutes=BOARDING_STARTS_BEFORE_DEPARTURE)
        if existing:  # re-issue (e.g. after re-check-in or seat change)
            existing.reference = ref
            existing.seat_number = checkin.seat_number
            existing.gate_number = flight.gate_number
            existing.boarding_time = boarding_time
            existing.is_valid = True
            self.db.flush()
            return existing
        bp = BoardingPass(
            checkin_id=checkin.id, reference=ref, flight_id=flight.id, passenger_id=checkin.passenger_id,
            seat_number=checkin.seat_number, gate_number=flight.gate_number, boarding_time=boarding_time,
            boarding_group=BOARDING_GROUPS.get(booking.travel_class, "3"),
            sequence_number=self.repo.next_boarding_sequence(flight.id),
        )
        self.db.add(bp)
        self.db.flush()
        return bp

    def get_by_reference(self, ref: str) -> BoardingPass:
        bp = self.repo.boarding_pass_by_ref(ref)
        if not bp:
            raise NotFoundError("Boarding pass", ref)
        return bp

    def get_for_checkin(self, checkin_id: int) -> BoardingPass:
        bp = self.repo.boarding_pass_for_checkin(checkin_id)
        if not bp:
            raise NotFoundError("Boarding pass for check-in", checkin_id)
        return bp
