from sqlalchemy import or_, select

from app.models.flight import Flight
from app.repositories.base import BaseRepository


class FlightRepository(BaseRepository[Flight]):
    model = Flight
    entity_name = "Flight"

    def search(self, q=None, status=None, airline_code=None, departure_airport_id=None, arrival_airport_id=None,
               start=None, end=None, airport_id=None):
        stmt = select(Flight)
        if q:
            like = f"%{q}%"
            stmt = stmt.where(or_(Flight.flight_number.ilike(like), Flight.airline_name.ilike(like),
                                  Flight.aircraft_registration.ilike(like)))
        if status:
            stmt = stmt.where(Flight.status == status)
        if airline_code:
            stmt = stmt.where(Flight.airline_code == airline_code.upper())
        if departure_airport_id:
            stmt = stmt.where(Flight.departure_airport_id == departure_airport_id)
        if arrival_airport_id:
            stmt = stmt.where(Flight.arrival_airport_id == arrival_airport_id)
        if airport_id:
            stmt = stmt.where(or_(Flight.departure_airport_id == airport_id, Flight.arrival_airport_id == airport_id))
        if start:
            stmt = stmt.where(Flight.scheduled_departure >= start)
        if end:
            stmt = stmt.where(Flight.scheduled_departure < end)
        return stmt
