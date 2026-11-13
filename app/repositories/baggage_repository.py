from sqlalchemy import select

from app.models.baggage import Baggage
from app.repositories.base import BaseRepository


class BaggageRepository(BaseRepository[Baggage]):
    model = Baggage
    entity_name = "Baggage"

    def get_by_tag(self, tag: str) -> Baggage | None:
        return self.db.scalar(select(Baggage).where(Baggage.tag_number == tag.upper()))

    def search(self, flight_id=None, passenger_id=None, status=None, category=None, tag=None, on_hold=None,
               start=None, end=None):
        stmt = select(Baggage)
        if flight_id:
            stmt = stmt.where(Baggage.flight_id == flight_id)
        if passenger_id:
            stmt = stmt.where(Baggage.passenger_id == passenger_id)
        if status:
            stmt = stmt.where(Baggage.status == status)
        if category:
            stmt = stmt.where(Baggage.category == category)
        if tag:
            stmt = stmt.where(Baggage.tag_number.ilike(f"%{tag}%"))
        if on_hold is not None:
            stmt = stmt.where(Baggage.is_on_hold.is_(on_hold))
        if start:
            stmt = stmt.where(Baggage.created_at >= start)
        if end:
            stmt = stmt.where(Baggage.created_at < end)
        return stmt
