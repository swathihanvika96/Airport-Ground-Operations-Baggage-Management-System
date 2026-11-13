from datetime import date

from fastapi import APIRouter, Depends

from app.api.dependencies import DB, allow
from app.core.permissions import Permissions
from app.models.user import User
from app.schemas.dashboard import BaggageMetrics, DashboardOverview, FlightMetrics, OperationsMetrics, ResourceMetrics
from app.services.dashboard_service import DashboardService
from app.utils.filters import DateRangeParams

router = APIRouter(prefix="/dashboard", tags=["Operations Dashboard"])


def _overview(db, dates: DateRangeParams, airport_id):
    return DashboardService(db).overview(dates.date_from, dates.date_to, airport_id)


@router.get("/overview", response_model=DashboardOverview, summary="All dashboard metrics")
def overview(db: DB, _: User = allow(Permissions.DASHBOARD_VIEW), dates: DateRangeParams = Depends(),
             airport_id: int | None = None):
    return _overview(db, dates, airport_id)


@router.get("/today", response_model=DashboardOverview, summary="Metrics for flights scheduled today (UTC)")
def today(db: DB, _: User = allow(Permissions.DASHBOARD_VIEW), airport_id: int | None = None):
    d = date.today()
    return DashboardService(db).overview(d, d, airport_id)


@router.get("/flights", response_model=FlightMetrics)
def flights(db: DB, _: User = allow(Permissions.DASHBOARD_VIEW), dates: DateRangeParams = Depends(),
            airport_id: int | None = None):
    return _overview(db, dates, airport_id)["flights"]


@router.get("/resources", response_model=ResourceMetrics)
def resources(db: DB, _: User = allow(Permissions.DASHBOARD_VIEW), airport_id: int | None = None):
    return DashboardService(db).overview(None, None, airport_id)["resources"]


@router.get("/baggage", response_model=BaggageMetrics)
def baggage(db: DB, _: User = allow(Permissions.DASHBOARD_VIEW), dates: DateRangeParams = Depends(),
            airport_id: int | None = None):
    return _overview(db, dates, airport_id)["baggage"]


@router.get("/operations", response_model=OperationsMetrics)
def operations(db: DB, _: User = allow(Permissions.DASHBOARD_VIEW), dates: DateRangeParams = Depends(),
               airport_id: int | None = None):
    return _overview(db, dates, airport_id)["operations"]
