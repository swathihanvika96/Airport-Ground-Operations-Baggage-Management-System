from fastapi import APIRouter, Depends

from app.api.dependencies import DB, CurrentUser, allow
from app.core.permissions import Permissions
from app.models.flight_delay import FlightDelay
from app.models.user import User
from app.repositories.delay_repository import DelayRepository
from app.schemas.common import Page
from app.schemas.flight_delay import DelayCreate, DelayOut, DelayUpdate, FlightDelaySummary
from app.services.delay_service import DelayService
from app.utils.enums import DelayCategory, Department
from app.utils.filters import DateRangeParams, SortParams, apply_sorting
from app.utils.pagination import PageParams, page_params, paginate

router = APIRouter(prefix="/delays", tags=["Flight Delays"])


@router.post("", response_model=DelayOut, status_code=201,
             summary="Record a delay (give delay_minutes or updated_departure; flight -> DELAYED)")
def record_delay(data: DelayCreate, db: DB, user: User = allow(Permissions.DELAY_MANAGE)):
    return DelayService(db).record(data, user)


@router.get("", response_model=Page[DelayOut])
def list_delays(db: DB, _: CurrentUser, flight_id: int | None = None, category: DelayCategory | None = None,
                department: Department | None = None, dates: DateRangeParams = Depends(),
                params: PageParams = Depends(page_params), sort: SortParams = Depends()):
    start, end = dates.bounds
    stmt = DelayRepository(db).search(flight_id, category, department, start, end)
    stmt = apply_sorting(stmt, FlightDelay, sort, default="recorded_at",
                         allowed={"recorded_at", "delay_minutes", "id"})
    return paginate(db, stmt, params)


@router.get("/flight/{flight_id}", response_model=FlightDelaySummary, summary="Delay history & total for a flight")
def flight_delays(flight_id: int, db: DB, _: CurrentUser):
    return DelayService(db).summary(flight_id)


@router.get("/{delay_id}", response_model=DelayOut)
def get_delay(delay_id: int, db: DB, _: CurrentUser):
    return DelayService(db).get(delay_id)


@router.patch("/{delay_id}", response_model=DelayOut)
def update_delay(delay_id: int, data: DelayUpdate, db: DB, user: User = allow(Permissions.DELAY_MANAGE)):
    return DelayService(db).update(delay_id, data, user)
