from fastapi import APIRouter, Depends

from app.api.dependencies import DB, CurrentUser, allow
from app.core.constants import FLIGHT_STATUS_TRANSITIONS
from app.core.permissions import Permissions
from app.models.flight import Flight
from app.models.user import User
from app.repositories.counter_repository import CounterRepository
from app.repositories.flight_repository import FlightRepository
from app.repositories.gate_repository import GateRepository
from app.schemas.assignment import CounterAssignmentOut, GateAssignmentOut
from app.schemas.common import Page
from app.schemas.flight import FlightCreate, FlightOut, FlightStatusUpdate, FlightUpdate
from app.services.flight_service import FlightService
from app.utils.enums import FlightStatus
from app.utils.filters import DateRangeParams, SortParams, apply_sorting
from app.utils.pagination import PageParams, page_params, paginate

router = APIRouter(prefix="/flights", tags=["Flights"])


@router.post("", response_model=FlightOut, status_code=201)
def create_flight(data: FlightCreate, db: DB, user: User = allow(Permissions.FLIGHT_MANAGE)):
    return FlightService(db).create(data, user)


@router.get("", response_model=Page[FlightOut])
def list_flights(db: DB, _: CurrentUser, q: str | None = None, status: FlightStatus | None = None,
                 airline_code: str | None = None, departure_airport_id: int | None = None,
                 arrival_airport_id: int | None = None, airport_id: int | None = None,
                 dates: DateRangeParams = Depends(), params: PageParams = Depends(page_params),
                 sort: SortParams = Depends()):
    start, end = dates.bounds
    stmt = FlightRepository(db).search(q, status, airline_code, departure_airport_id, arrival_airport_id, start, end,
                                       airport_id)
    stmt = apply_sorting(stmt, Flight, sort, default="scheduled_departure",
                         allowed={"scheduled_departure", "scheduled_arrival", "flight_number", "status", "id"})
    return paginate(db, stmt, params)


@router.get("/status-transitions", summary="Valid flight status transitions")
def transitions(_: CurrentUser):
    return {k.value: sorted(v.value for v in vs) for k, vs in FLIGHT_STATUS_TRANSITIONS.items()}


@router.get("/{flight_id}", response_model=FlightOut)
def get_flight(flight_id: int, db: DB, _: CurrentUser):
    return FlightService(db).get(flight_id)


@router.patch("/{flight_id}", response_model=FlightOut, summary="Update flight / schedule (audited)")
def update_flight(flight_id: int, data: FlightUpdate, db: DB, user: User = allow(Permissions.FLIGHT_MANAGE)):
    return FlightService(db).update(flight_id, data, user)


@router.patch("/{flight_id}/status", response_model=FlightOut)
def update_flight_status(flight_id: int, data: FlightStatusUpdate, db: DB,
                         user: User = allow(Permissions.FLIGHT_STATUS_UPDATE)):
    return FlightService(db).update_status(flight_id, data.status, user, data.actual_time, data.remarks)


@router.delete("/{flight_id}", status_code=204)
def delete_flight(flight_id: int, db: DB, user: User = allow(Permissions.FLIGHT_MANAGE)):
    FlightService(db).delete(flight_id, user)


@router.get("/{flight_id}/gate-assignments", response_model=list[GateAssignmentOut])
def flight_gate_history(flight_id: int, db: DB, _: CurrentUser):
    FlightService(db).get(flight_id)
    repo = GateRepository(db)
    return repo.list(repo.assignments(flight_id=flight_id))


@router.get("/{flight_id}/counter-assignments", response_model=list[CounterAssignmentOut])
def flight_counter_history(flight_id: int, db: DB, _: CurrentUser):
    FlightService(db).get(flight_id)
    repo = CounterRepository(db)
    return repo.list(repo.assignments(flight_id=flight_id))
