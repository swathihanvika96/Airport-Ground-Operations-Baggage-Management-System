from fastapi import APIRouter, Depends

from app.api.dependencies import DB, CurrentUser, allow
from app.core.permissions import Permissions
from app.models.baggage import Baggage
from app.models.user import User
from app.repositories.baggage_repository import BaggageRepository
from app.schemas.baggage import BaggageCreate, BaggageOut, BaggageUpdate
from app.schemas.common import Page
from app.services.baggage_service import BaggageService
from app.utils.enums import BaggageCategory, BaggageStatus
from app.utils.filters import DateRangeParams, SortParams, apply_sorting
from app.utils.pagination import PageParams, page_params, paginate

router = APIRouter(prefix="/baggage", tags=["Baggage"])


@router.post("", response_model=BaggageOut, status_code=201,
             summary="Register baggage (unique tag, weight limits per category)")
def register_baggage(data: BaggageCreate, db: DB, user: User = allow(Permissions.BAGGAGE_REGISTER)):
    return BaggageService(db).register(data, user)


@router.get("", response_model=Page[BaggageOut])
def list_baggage(db: DB, _: CurrentUser, flight_id: int | None = None, passenger_id: int | None = None,
                 status: BaggageStatus | None = None, category: BaggageCategory | None = None,
                 tag: str | None = None, on_hold: bool | None = None, dates: DateRangeParams = Depends(),
                 params: PageParams = Depends(page_params), sort: SortParams = Depends()):
    start, end = dates.bounds
    stmt = BaggageRepository(db).search(flight_id, passenger_id, status, category, tag, on_hold, start, end)
    stmt = apply_sorting(stmt, Baggage, sort, default="created_at",
                         allowed={"created_at", "updated_at", "weight_kg", "tag_number", "status", "id"})
    return paginate(db, stmt, params)


@router.get("/tag/{tag_number}", response_model=BaggageOut)
def get_by_tag(tag_number: str, db: DB, _: CurrentUser):
    return BaggageService(db).get_by_tag(tag_number)


@router.get("/{baggage_id}", response_model=BaggageOut)
def get_baggage(baggage_id: int, db: DB, _: CurrentUser):
    return BaggageService(db).get(baggage_id)


@router.patch("/{baggage_id}", response_model=BaggageOut)
def update_baggage(baggage_id: int, data: BaggageUpdate, db: DB, user: User = allow(Permissions.BAGGAGE_REGISTER)):
    return BaggageService(db).update(baggage_id, data, user)
