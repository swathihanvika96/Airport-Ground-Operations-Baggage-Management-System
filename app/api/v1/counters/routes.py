from fastapi import APIRouter, Depends, Query

from app.api.dependencies import DB, CurrentUser, allow
from app.core.permissions import Permissions
from app.models.counter import CheckInCounter
from app.models.user import User
from app.repositories.counter_repository import CounterRepository
from app.schemas.assignment import CounterAssignmentOut, CounterAssignRequest
from app.schemas.common import Page, UTCDateTime
from app.schemas.counter import CounterCreate, CounterOut, CounterUpdate
from app.services.counter_service import CounterService
from app.utils.enums import AssignmentStatus, CounterStatus
from app.utils.pagination import PageParams, page_params, paginate

router = APIRouter(prefix="/counters", tags=["Check-in Counters"])


@router.post("", response_model=CounterOut, status_code=201)
def register_counter(data: CounterCreate, db: DB, user: User = allow(Permissions.COUNTER_MANAGE)):
    return CounterService(db).create(data, user)


@router.get("", response_model=Page[CounterOut])
def list_counters(db: DB, _: CurrentUser, terminal_id: int | None = None, airport_id: int | None = None,
                  status: CounterStatus | None = None, is_active: bool | None = None,
                  params: PageParams = Depends(page_params)):
    stmt = CounterRepository(db).search(terminal_id, airport_id, status, is_active).order_by(CheckInCounter.counter_number)
    return paginate(db, stmt, params)


@router.get("/available", response_model=list[CounterOut], summary="Counter availability for a time window")
def available_counters(db: DB, _: CurrentUser, start_time: UTCDateTime = Query(...),
                       end_time: UTCDateTime = Query(...), terminal_id: int | None = None,
                       airport_id: int | None = None):
    return CounterService(db).available(start_time, end_time, terminal_id, airport_id)


@router.get("/assignments", response_model=Page[CounterAssignmentOut], summary="Counter assignment history")
def assignment_history(db: DB, _: CurrentUser, counter_id: int | None = None, flight_id: int | None = None,
                       status: AssignmentStatus | None = None, params: PageParams = Depends(page_params)):
    return paginate(db, CounterRepository(db).assignments(counter_id, flight_id, status), params)


@router.get("/{counter_id}", response_model=CounterOut)
def get_counter(counter_id: int, db: DB, _: CurrentUser):
    return CounterService(db).get(counter_id)


@router.patch("/{counter_id}", response_model=CounterOut)
def update_counter(counter_id: int, data: CounterUpdate, db: DB, user: User = allow(Permissions.COUNTER_MANAGE)):
    return CounterService(db).update(counter_id, data, user)


@router.post("/{counter_id}/assign", response_model=CounterAssignmentOut, status_code=201)
def assign_counter(counter_id: int, data: CounterAssignRequest, db: DB,
                   user: User = allow(Permissions.COUNTER_ASSIGN)):
    return CounterService(db).assign(counter_id, data.flight_id, user, data.start_time, data.end_time, data.remarks)


@router.post("/assignments/{assignment_id}/release", response_model=CounterAssignmentOut)
def release_counter(assignment_id: int, db: DB, user: User = allow(Permissions.COUNTER_ASSIGN)):
    return CounterService(db).release(assignment_id, user)
