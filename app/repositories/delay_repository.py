from sqlalchemy import select

from app.models.flight_delay import FlightDelay
from app.repositories.base import BaseRepository


class DelayRepository(BaseRepository[FlightDelay]):
    model = FlightDelay
    entity_name = "Flight delay"

    def history(self, flight_id) -> list[FlightDelay]:
        return list(self.db.scalars(select(FlightDelay).where(FlightDelay.flight_id == flight_id)
                                    .order_by(FlightDelay.recorded_at, FlightDelay.id)).all())

    def search(self, flight_id=None, category=None, department=None, start=None, end=None):
        stmt = select(FlightDelay)
        if flight_id:
            stmt = stmt.where(FlightDelay.flight_id == flight_id)
        if category:
            stmt = stmt.where(FlightDelay.delay_category == category)
        if department:
            stmt = stmt.where(FlightDelay.responsible_department == department)
        if start:
            stmt = stmt.where(FlightDelay.recorded_at >= start)
        if end:
            stmt = stmt.where(FlightDelay.recorded_at < end)
        return stmt
