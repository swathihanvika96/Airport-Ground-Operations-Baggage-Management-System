from fastapi import APIRouter, Depends

from app.api.dependencies import DB, CurrentUser, allow
from app.core.permissions import Permissions
from app.models.incident import Incident
from app.models.user import User
from app.repositories.incident_repository import IncidentRepository
from app.schemas.common import Page
from app.schemas.incident import (
    IncidentAssign,
    IncidentCreate,
    IncidentDetail,
    IncidentHistoryOut,
    IncidentOut,
    IncidentStatusUpdate,
    IncidentUpdate,
)
from app.services.incident_service import IncidentService
from app.utils.enums import IncidentCategory, IncidentStatus, Severity
from app.utils.filters import DateRangeParams, SortParams, apply_sorting
from app.utils.pagination import PageParams, page_params, paginate

router = APIRouter(prefix="/incidents", tags=["Operational Incidents"])


@router.post("", response_model=IncidentOut, status_code=201)
def create_incident(data: IncidentCreate, db: DB, user: User = allow(Permissions.INCIDENT_REPORT)):
    return IncidentService(db).create(data, user)


@router.get("", response_model=Page[IncidentOut])
def list_incidents(db: DB, _: CurrentUser, q: str | None = None, status: IncidentStatus | None = None,
                   severity: Severity | None = None, category: IncidentCategory | None = None,
                   flight_id: int | None = None, terminal_id: int | None = None, dates: DateRangeParams = Depends(),
                   params: PageParams = Depends(page_params), sort: SortParams = Depends()):
    start, end = dates.bounds
    stmt = IncidentRepository(db).search(q, status, severity, category, flight_id, terminal_id, start, end)
    stmt = apply_sorting(stmt, Incident, sort, default="reported_at",
                         allowed={"reported_at", "severity", "status", "id"})
    return paginate(db, stmt, params)


@router.get("/{incident_id}", response_model=IncidentDetail)
def get_incident(incident_id: int, db: DB, _: CurrentUser):
    return IncidentService(db).get(incident_id)


@router.get("/{incident_id}/history", response_model=list[IncidentHistoryOut])
def incident_history(incident_id: int, db: DB, _: CurrentUser):
    return IncidentService(db).get(incident_id).history


@router.patch("/{incident_id}", response_model=IncidentOut)
def update_incident(incident_id: int, data: IncidentUpdate, db: DB, user: User = allow(Permissions.INCIDENT_MANAGE)):
    return IncidentService(db).update(incident_id, data, user)


@router.post("/{incident_id}/assign", response_model=IncidentOut)
def assign_incident(incident_id: int, data: IncidentAssign, db: DB, user: User = allow(Permissions.INCIDENT_MANAGE)):
    return IncidentService(db).assign(incident_id, data, user)


@router.patch("/{incident_id}/status", response_model=IncidentOut, summary="Change status / resolve / close")
def change_status(incident_id: int, data: IncidentStatusUpdate, db: DB,
                  user: User = allow(Permissions.INCIDENT_MANAGE)):
    return IncidentService(db).change_status(incident_id, data, user)
