from sqlalchemy import select

from app.models.turnaround import Turnaround
from app.models.turnaround_activity import TurnaroundActivity
from app.repositories.base import BaseRepository


class TurnaroundRepository(BaseRepository[Turnaround]):
    model = Turnaround
    entity_name = "Turnaround"

    def get_activity(self, activity_id) -> TurnaroundActivity | None:
        return self.db.get(TurnaroundActivity, activity_id)

    def search(self, flight_id=None, status=None, start=None, end=None):
        stmt = select(Turnaround)
        if flight_id:
            stmt = stmt.where(Turnaround.flight_id == flight_id)
        if status:
            stmt = stmt.where(Turnaround.status == status)
        if start:
            stmt = stmt.where(Turnaround.created_at >= start)
        if end:
            stmt = stmt.where(Turnaround.created_at < end)
        return stmt
