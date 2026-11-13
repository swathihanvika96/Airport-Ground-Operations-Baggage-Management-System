from sqlalchemy import select

from app.models.baggage_screening import BaggageScreening
from app.repositories.base import BaseRepository


class ScreeningRepository(BaseRepository[BaggageScreening]):
    model = BaggageScreening
    entity_name = "Screening record"

    def latest_for_baggage(self, baggage_id) -> BaggageScreening | None:
        return self.db.scalar(select(BaggageScreening).where(BaggageScreening.baggage_id == baggage_id)
                              .order_by(BaggageScreening.screened_at.desc(), BaggageScreening.id.desc()).limit(1))

    def search(self, baggage_id=None, status=None):
        stmt = select(BaggageScreening)
        if baggage_id:
            stmt = stmt.where(BaggageScreening.baggage_id == baggage_id)
        if status:
            stmt = stmt.where(BaggageScreening.status == status)
        return stmt
