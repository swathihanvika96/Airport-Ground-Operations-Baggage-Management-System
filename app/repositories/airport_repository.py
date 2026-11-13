from sqlalchemy import func, or_, select

from app.models.airport import Airport
from app.repositories.base import BaseRepository


class AirportRepository(BaseRepository[Airport]):
    model = Airport
    entity_name = "Airport"

    def get_by_code(self, code: str) -> Airport | None:
        return self.db.scalar(select(Airport).where(func.upper(Airport.code) == code.upper()))

    def search(self, q=None, country=None, city=None, status=None):
        stmt = select(Airport)
        if q:
            like = f"%{q}%"
            stmt = stmt.where(or_(Airport.name.ilike(like), Airport.code.ilike(like), Airport.city.ilike(like),
                                  Airport.icao_code.ilike(like)))
        if country:
            stmt = stmt.where(Airport.country.ilike(country))
        if city:
            stmt = stmt.where(Airport.city.ilike(city))
        if status:
            stmt = stmt.where(Airport.operational_status == status)
        return stmt
