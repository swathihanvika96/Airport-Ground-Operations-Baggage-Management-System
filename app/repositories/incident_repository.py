from sqlalchemy import or_, select

from app.models.incident import Incident
from app.repositories.base import BaseRepository


class IncidentRepository(BaseRepository[Incident]):
    model = Incident
    entity_name = "Incident"

    def search(self, q=None, status=None, severity=None, category=None, flight_id=None, terminal_id=None,
               start=None, end=None):
        stmt = select(Incident)
        if q:
            like = f"%{q}%"
            stmt = stmt.where(or_(Incident.title.ilike(like), Incident.reference.ilike(like)))
        if status:
            stmt = stmt.where(Incident.status == status)
        if severity:
            stmt = stmt.where(Incident.severity == severity)
        if category:
            stmt = stmt.where(Incident.category == category)
        if flight_id:
            stmt = stmt.where(Incident.flight_id == flight_id)
        if terminal_id:
            stmt = stmt.where(Incident.terminal_id == terminal_id)
        if start:
            stmt = stmt.where(Incident.reported_at >= start)
        if end:
            stmt = stmt.where(Incident.reported_at < end)
        return stmt
