from fastapi import APIRouter, Body, Depends

from app.api.dependencies import DB, CurrentUser, allow
from app.core.constants import TURNAROUND_ACTIVITY_PLAN
from app.core.permissions import Permissions
from app.models.turnaround import Turnaround
from app.models.user import User
from app.repositories.turnaround_repository import TurnaroundRepository
from app.schemas.common import Page
from app.schemas.turnaround import (
    ActivityAssign,
    ActivityComplete,
    ActivityOut,
    ActivityStart,
    ParkingAssign,
    TurnaroundCreate,
    TurnaroundOut,
)
from app.services.turnaround_service import TurnaroundService
from app.utils.enums import TurnaroundStatus
from app.utils.filters import DateRangeParams
from app.utils.pagination import PageParams, page_params, paginate

router = APIRouter(prefix="/turnarounds", tags=["Aircraft Turnaround"])


@router.get("/workflow", summary="Turnaround activity plan with planned durations and prerequisites")
def workflow(_: CurrentUser):
    return [{"sequence": i, "activity": a.value, "planned_minutes": m, "prerequisites": [p.value for p in pre]}
            for i, (a, m, pre) in enumerate(TURNAROUND_ACTIVITY_PLAN, start=1)]


@router.post("", response_model=TurnaroundOut, status_code=201,
             summary="Create turnaround (auto-creates the 9 workflow activities)")
def create_turnaround(data: TurnaroundCreate, db: DB, user: User = allow(Permissions.TURNAROUND_MANAGE)):
    return TurnaroundService(db).create(data, user)


@router.get("", response_model=Page[TurnaroundOut])
def list_turnarounds(db: DB, _: CurrentUser, flight_id: int | None = None, status: TurnaroundStatus | None = None,
                     dates: DateRangeParams = Depends(), params: PageParams = Depends(page_params)):
    start, end = dates.bounds
    stmt = TurnaroundRepository(db).search(flight_id, status, start, end).order_by(Turnaround.id.desc())
    return paginate(db, stmt, params)


@router.get("/flight/{flight_id}", response_model=TurnaroundOut)
def get_for_flight(flight_id: int, db: DB, _: CurrentUser):
    return TurnaroundService(db).get_for_flight(flight_id)


@router.get("/{turnaround_id}", response_model=TurnaroundOut)
def get_turnaround(turnaround_id: int, db: DB, _: CurrentUser):
    return TurnaroundService(db).get(turnaround_id)


@router.patch("/{turnaround_id}/parking", response_model=TurnaroundOut, summary="Aircraft parking assignment")
def assign_parking(turnaround_id: int, data: ParkingAssign, db: DB, user: User = allow(Permissions.TURNAROUND_MANAGE)):
    return TurnaroundService(db).assign_parking(turnaround_id, data.parking_stand, user)


@router.patch("/{turnaround_id}/activities/{activity_id}/assign", response_model=ActivityOut)
def assign_activity(turnaround_id: int, activity_id: int, data: ActivityAssign, db: DB,
                    user: User = allow(Permissions.TURNAROUND_MANAGE)):
    return TurnaroundService(db).assign_activity(turnaround_id, activity_id, data, user)


@router.post("/{turnaround_id}/activities/{activity_id}/start", response_model=ActivityOut)
def start_activity(turnaround_id: int, activity_id: int, data: ActivityStart, db: DB,
                   user: User = allow(Permissions.TASK_EXECUTE)):
    return TurnaroundService(db).start_activity(turnaround_id, activity_id, data, user)


@router.post("/{turnaround_id}/activities/{activity_id}/complete", response_model=ActivityOut,
             summary="Complete activity (delay_reason required if it overran)")
def complete_activity(turnaround_id: int, activity_id: int, data: ActivityComplete, db: DB,
                      user: User = allow(Permissions.TASK_EXECUTE)):
    return TurnaroundService(db).complete_activity(turnaround_id, activity_id, data, user)


@router.post("/{turnaround_id}/activities/{activity_id}/skip", response_model=ActivityOut)
def skip_activity(turnaround_id: int, activity_id: int, db: DB, remarks: str = Body(..., embed=True),
                  user: User = allow(Permissions.TURNAROUND_MANAGE)):
    return TurnaroundService(db).skip_activity(turnaround_id, activity_id, remarks, user)


@router.post("/{turnaround_id}/cancel", response_model=TurnaroundOut)
def cancel_turnaround(turnaround_id: int, db: DB, user: User = allow(Permissions.TURNAROUND_MANAGE)):
    return TurnaroundService(db).cancel(turnaround_id, user)
