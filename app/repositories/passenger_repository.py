from sqlalchemy import or_, select

from app.models.passenger import Passenger, PassengerFlight
from app.repositories.base import BaseRepository


class PassengerRepository(BaseRepository[Passenger]):
    model = Passenger
    entity_name = "Passenger"

    def search(self, q=None, flight_id=None, booking_status=None, status=None, nationality=None):
        stmt = select(Passenger)
        if flight_id or booking_status:
            stmt = stmt.join(PassengerFlight, PassengerFlight.passenger_id == Passenger.id)
            if flight_id:
                stmt = stmt.where(PassengerFlight.flight_id == flight_id)
            if booking_status:
                stmt = stmt.where(PassengerFlight.status == booking_status)
        if q:
            like = f"%{q}%"
            conds = [Passenger.first_name.ilike(like), Passenger.last_name.ilike(like), Passenger.email.ilike(like),
                     Passenger.id_reference.ilike(like), Passenger.phone.ilike(like)]
            booked = select(PassengerFlight.passenger_id).where(PassengerFlight.booking_reference.ilike(like))
            conds.append(Passenger.id.in_(booked))
            stmt = stmt.where(or_(*conds))
        if status:
            stmt = stmt.where(Passenger.status == status)
        if nationality:
            stmt = stmt.where(Passenger.nationality.ilike(nationality))
        return stmt.distinct()

    def get_booking(self, passenger_id, flight_id) -> PassengerFlight | None:
        return self.db.scalar(select(PassengerFlight).where(
            PassengerFlight.passenger_id == passenger_id, PassengerFlight.flight_id == flight_id))

    def get_booking_by_id(self, booking_id) -> PassengerFlight | None:
        return self.db.get(PassengerFlight, booking_id)

    def booking_ref_exists(self, ref) -> bool:
        return self.db.scalar(select(PassengerFlight.id).where(PassengerFlight.booking_reference == ref)) is not None

    def bookings_for_passenger(self, passenger_id) -> list[PassengerFlight]:
        return list(self.db.scalars(select(PassengerFlight).where(PassengerFlight.passenger_id == passenger_id)
                                    .order_by(PassengerFlight.created_at.desc())).all())

    def booked_count(self, flight_id) -> int:
        from app.utils.enums import BookingStatus
        return self.count(select(PassengerFlight).where(PassengerFlight.flight_id == flight_id,
                                                        PassengerFlight.status != BookingStatus.CANCELLED))
