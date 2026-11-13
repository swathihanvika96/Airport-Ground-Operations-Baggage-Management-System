from sqlalchemy import select

from app.models.baggage_tracking import BaggageTrackingEvent
from app.repositories.base import BaseRepository


class TrackingRepository(BaseRepository[BaggageTrackingEvent]):
    model = BaggageTrackingEvent
    entity_name = "Tracking event"

    def history(self, baggage_id) -> list[BaggageTrackingEvent]:
        return list(self.db.scalars(select(BaggageTrackingEvent)
                                    .where(BaggageTrackingEvent.baggage_id == baggage_id)
                                    .order_by(BaggageTrackingEvent.timestamp, BaggageTrackingEvent.id)).all())
