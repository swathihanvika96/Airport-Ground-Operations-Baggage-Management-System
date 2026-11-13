from sqlalchemy.orm import Session

from app.core.exceptions import ConflictError
from app.models.airport import Airport
from app.models.user import User
from app.repositories.airport_repository import AirportRepository
from app.schemas.airport import AirportCreate, AirportUpdate
from app.services.audit_service import AuditService, snapshot
from app.utils.enums import AirportStatus, AuditAction


class AirportService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = AirportRepository(db)
        self.audit = AuditService(db)

    def create(self, data: AirportCreate, user: User) -> Airport:
        code = data.code.upper()
        if self.repo.get_by_code(code):
            raise ConflictError(f"Airport code {code} already exists")
        icao = data.icao_code.upper() if data.icao_code else None
        if icao and self.repo.exists(icao_code=icao):
            raise ConflictError(f"ICAO code {icao} already exists")
        airport = self.repo.create(**data.model_dump(exclude={"code", "icao_code"}), code=code, icao_code=icao)
        self.audit.log(AuditAction.AIRPORT_CREATED, "airport", airport.id, None, snapshot(airport), user.id)
        self.db.commit()
        return airport

    def get(self, airport_id: int) -> Airport:
        return self.repo.get_or_404(airport_id)

    def get_by_code(self, code: str) -> Airport:
        airport = self.repo.get_by_code(code)
        if not airport:
            from app.core.exceptions import NotFoundError
            raise NotFoundError("Airport", code)
        return airport

    def update(self, airport_id: int, data: AirportUpdate, user: User) -> Airport:
        airport = self.repo.get_or_404(airport_id)
        changes = data.model_dump(exclude_unset=True)
        prev = snapshot(airport, list(changes))
        self.repo.update(airport, changes)
        self.audit.log(AuditAction.AIRPORT_UPDATED, "airport", airport.id, prev, snapshot(airport, list(changes)), user.id)
        self.db.commit()
        return airport

    def set_status(self, airport_id: int, status: AirportStatus, user: User) -> Airport:
        airport = self.repo.get_or_404(airport_id)
        prev = {"operational_status": airport.operational_status}
        airport.operational_status = status
        self.audit.log(AuditAction.AIRPORT_UPDATED, "airport", airport.id, prev, {"operational_status": status}, user.id)
        self.db.commit()
        return airport

    def delete(self, airport_id: int, user: User) -> None:
        from app.models.flight import Flight
        from sqlalchemy import or_, select
        airport = self.repo.get_or_404(airport_id)
        if self.db.scalar(select(Flight.id).where(or_(Flight.departure_airport_id == airport_id,
                                                      Flight.arrival_airport_id == airport_id)).limit(1)):
            raise ConflictError("Airport has flights and cannot be deleted; set it CLOSED instead")
        self.audit.log(AuditAction.AIRPORT_UPDATED, "airport", airport.id, snapshot(airport), {"deleted": True}, user.id)
        self.repo.delete(airport)
        self.db.commit()
