from fastapi import APIRouter, Depends

from app.api.dependencies import DB, CurrentUser, allow
from app.core.permissions import Permissions
from app.models.checkin import CheckIn
from app.models.user import User
from app.repositories.checkin_repository import CheckInRepository
from app.schemas.boarding_pass import BoardingPassOut
from app.schemas.checkin import CheckInCreate, CheckInOut, CheckInResult, SeatChangeRequest
from app.schemas.common import Page
from app.services.boarding_pass_service import BoardingPassService
from app.services.checkin_service import CheckInService
from app.utils.enums import CheckInStatus
from app.utils.pagination import PageParams, page_params, paginate

router = APIRouter(prefix="/checkin", tags=["Check-in & Boarding Pass"])


@router.post("", response_model=CheckInResult, status_code=201,
             summary="Check in passenger (validates flight, seat, counter; prevents duplicates; issues boarding pass)")
def check_in(data: CheckInCreate, db: DB, user: User = allow(Permissions.CHECKIN)):
    checkin, bp = CheckInService(db).check_in(data, user)
    return {"checkin": checkin, "boarding_pass": bp}


@router.get("", response_model=Page[CheckInOut])
def list_checkins(db: DB, _: CurrentUser, flight_id: int | None = None, passenger_id: int | None = None,
                  status: CheckInStatus | None = None, counter_id: int | None = None,
                  params: PageParams = Depends(page_params)):
    stmt = CheckInRepository(db).search(flight_id, passenger_id, status, counter_id).order_by(CheckIn.checkin_time.desc())
    return paginate(db, stmt, params)


@router.get("/boarding-pass/{reference}", response_model=BoardingPassOut)
def boarding_pass_by_reference(reference: str, db: DB, _: CurrentUser):
    return BoardingPassService(db).get_by_reference(reference)


@router.get("/{checkin_id}", response_model=CheckInOut)
def get_checkin(checkin_id: int, db: DB, _: CurrentUser):
    return CheckInService(db).get(checkin_id)


@router.get("/{checkin_id}/boarding-pass", response_model=BoardingPassOut)
def get_boarding_pass(checkin_id: int, db: DB, _: CurrentUser):
    return BoardingPassService(db).get_for_checkin(checkin_id)


@router.patch("/{checkin_id}/seat", response_model=CheckInOut)
def change_seat(checkin_id: int, data: SeatChangeRequest, db: DB, user: User = allow(Permissions.CHECKIN)):
    return CheckInService(db).change_seat(checkin_id, data.seat_number, user)


@router.post("/{checkin_id}/cancel", response_model=CheckInOut)
def cancel_checkin(checkin_id: int, db: DB, user: User = allow(Permissions.CHECKIN)):
    return CheckInService(db).cancel(checkin_id, user)


@router.post("/{checkin_id}/board", response_model=CheckInOut, summary="Mark passenger boarded (flight must be BOARDING)")
def board(checkin_id: int, db: DB, user: User = allow(Permissions.BOARDING)):
    return CheckInService(db).board(checkin_id, user)
