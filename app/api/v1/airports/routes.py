from fastapi import APIRouter, Depends

from app.api.dependencies import DB, CurrentUser, allow
from app.core.permissions import Permissions
from app.models.airport import Airport
from app.models.user import User
from app.repositories.airport_repository import AirportRepository
from app.schemas.airport import AirportCreate, AirportOut, AirportStatusUpdate, AirportUpdate
from app.schemas.common import Page
from app.schemas.terminal import TerminalOut
from app.services.airport_service import AirportService
from app.utils.enums import AirportStatus
from app.utils.filters import SortParams, apply_sorting
from app.utils.pagination import PageParams, page_params, paginate

router = APIRouter(prefix="/airports", tags=["Airports"])


@router.post("", response_model=AirportOut, status_code=201)
def create_airport(data: AirportCreate, db: DB, user: User = allow(Permissions.AIRPORT_MANAGE)):
    return AirportService(db).create(data, user)


@router.get("", response_model=Page[AirportOut])
def search_airports(db: DB, _: CurrentUser, q: str | None = None, country: str | None = None,
                    city: str | None = None, status: AirportStatus | None = None,
                    params: PageParams = Depends(page_params), sort: SortParams = Depends()):
    """Search by name/code/city/ICAO (q) and filter by country, city, operational status."""
    stmt = apply_sorting(AirportRepository(db).search(q, country, city, status), Airport, sort, default="code",
                         allowed={"code", "name", "city", "country", "created_at", "id"})
    return paginate(db, stmt, params)


@router.get("/code/{code}", response_model=AirportOut)
def get_by_code(code: str, db: DB, _: CurrentUser):
    return AirportService(db).get_by_code(code)


@router.get("/{airport_id}", response_model=AirportOut)
def get_airport(airport_id: int, db: DB, _: CurrentUser):
    return AirportService(db).get(airport_id)


@router.get("/{airport_id}/terminals", response_model=list[TerminalOut])
def airport_terminals(airport_id: int, db: DB, _: CurrentUser):
    return AirportService(db).get(airport_id).terminals


@router.patch("/{airport_id}", response_model=AirportOut)
def update_airport(airport_id: int, data: AirportUpdate, db: DB, user: User = allow(Permissions.AIRPORT_MANAGE)):
    return AirportService(db).update(airport_id, data, user)


@router.patch("/{airport_id}/status", response_model=AirportOut)
def update_status(airport_id: int, data: AirportStatusUpdate, db: DB, user: User = allow(Permissions.AIRPORT_MANAGE)):
    return AirportService(db).set_status(airport_id, data.operational_status, user)


@router.delete("/{airport_id}", status_code=204)
def delete_airport(airport_id: int, db: DB, user: User = allow(Permissions.AIRPORT_MANAGE)):
    AirportService(db).delete(airport_id, user)
