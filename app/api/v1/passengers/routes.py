from fastapi import APIRouter, Depends

from app.api.dependencies import DB, CurrentUser, allow
from app.core.permissions import Permissions
from app.models.passenger import Passenger
from app.models.user import User
from app.repositories.passenger_repository import PassengerRepository
from app.schemas.common import Page
from app.schemas.passenger import (
    BookingCreate,
    BookingOut,
    BookingStatusUpdate,
    PassengerCreate,
    PassengerHistory,
    PassengerOut,
    PassengerUpdate,
)
from app.services.passenger_service import PassengerService
from app.utils.enums import BookingStatus, PassengerStatus
from app.utils.filters import SortParams, apply_sorting
from app.utils.pagination import PageParams, page_params, paginate

router = APIRouter(prefix="/passengers", tags=["Passengers"])


@router.post("", response_model=PassengerOut, status_code=201,
             summary="Register passenger (synthetic data); optionally map to a flight")
def register_passenger(data: PassengerCreate, db: DB, user: User = allow(Permissions.PASSENGER_MANAGE)):
    return PassengerService(db).create(data, user)


@router.get("", response_model=Page[PassengerOut], summary="Search passengers")
def search_passengers(db: DB, _: User = allow(Permissions.PASSENGER_MANAGE), q: str | None = None,
                      flight_id: int | None = None, booking_status: BookingStatus | None = None,
                      status: PassengerStatus | None = None, nationality: str | None = None,
                      params: PageParams = Depends(page_params), sort: SortParams = Depends()):
    """`q` matches name, email, phone, ID reference or booking reference."""
    stmt = PassengerRepository(db).search(q, flight_id, booking_status, status, nationality)
    stmt = apply_sorting(stmt, Passenger, sort, default="id", allowed={"id", "last_name", "first_name", "created_at"})
    return paginate(db, stmt, params)


@router.get("/{passenger_id}", response_model=PassengerOut)
def get_passenger(passenger_id: int, db: DB, _: User = allow(Permissions.PASSENGER_MANAGE)):
    return PassengerService(db).get(passenger_id)


@router.patch("/{passenger_id}", response_model=PassengerOut)
def update_passenger(passenger_id: int, data: PassengerUpdate, db: DB,
                     user: User = allow(Permissions.PASSENGER_MANAGE)):
    return PassengerService(db).update(passenger_id, data, user)


@router.get("/{passenger_id}/history", response_model=PassengerHistory, summary="Passenger travel history")
def passenger_history(passenger_id: int, db: DB, _: User = allow(Permissions.PASSENGER_MANAGE)):
    return PassengerService(db).history(passenger_id)


@router.get("/{passenger_id}/flights", response_model=list[BookingOut])
def passenger_bookings(passenger_id: int, db: DB, _: CurrentUser):
    return PassengerService(db).bookings(passenger_id)


@router.post("/{passenger_id}/flights", response_model=BookingOut, status_code=201, summary="Map passenger to flight")
def add_booking(passenger_id: int, data: BookingCreate, db: DB, user: User = allow(Permissions.PASSENGER_MANAGE)):
    return PassengerService(db).add_booking(passenger_id, data.flight_id, data.travel_class, user)


@router.patch("/{passenger_id}/flights/{flight_id}/status", response_model=BookingOut)
def update_booking_status(passenger_id: int, flight_id: int, data: BookingStatusUpdate, db: DB,
                          user: User = allow(Permissions.PASSENGER_MANAGE)):
    return PassengerService(db).update_booking_status(passenger_id, flight_id, data.status, user)
