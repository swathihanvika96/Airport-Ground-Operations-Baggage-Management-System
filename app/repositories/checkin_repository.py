from sqlalchemy import func, select

from app.models.boarding_pass import BoardingPass
from app.models.checkin import CheckIn
from app.repositories.base import BaseRepository
from app.utils.enums import CheckInStatus


class CheckInRepository(BaseRepository[CheckIn]):
    model = CheckIn
    entity_name = "Check-in"

    def get_for_passenger_flight(self, passenger_id, flight_id) -> CheckIn | None:
        return self.db.scalar(select(CheckIn).where(CheckIn.passenger_id == passenger_id,
                                                    CheckIn.flight_id == flight_id))

    def taken_seats(self, flight_id) -> set[str]:
        return set(self.db.scalars(select(CheckIn.seat_number).where(
            CheckIn.flight_id == flight_id, CheckIn.status != CheckInStatus.CANCELLED)).all())

    def search(self, flight_id=None, passenger_id=None, status=None, counter_id=None):
        stmt = select(CheckIn)
        if flight_id:
            stmt = stmt.where(CheckIn.flight_id == flight_id)
        if passenger_id:
            stmt = stmt.where(CheckIn.passenger_id == passenger_id)
        if status:
            stmt = stmt.where(CheckIn.status == status)
        if counter_id:
            stmt = stmt.where(CheckIn.counter_id == counter_id)
        return stmt

    # --- boarding passes ---
    def boarding_pass_by_ref(self, ref) -> BoardingPass | None:
        return self.db.scalar(select(BoardingPass).where(BoardingPass.reference == ref))

    def boarding_pass_for_checkin(self, checkin_id) -> BoardingPass | None:
        return self.db.scalar(select(BoardingPass).where(BoardingPass.checkin_id == checkin_id))

    def next_boarding_sequence(self, flight_id) -> int:
        return (self.db.scalar(select(func.max(BoardingPass.sequence_number))
                               .where(BoardingPass.flight_id == flight_id)) or 0) + 1

    def boarding_ref_exists(self, ref) -> bool:
        return self.boarding_pass_by_ref(ref) is not None
