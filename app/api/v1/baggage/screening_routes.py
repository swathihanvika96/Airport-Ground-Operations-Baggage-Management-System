from fastapi import APIRouter, Depends

from app.api.dependencies import DB, CurrentUser, allow
from app.core.permissions import Permissions
from app.models.baggage_screening import BaggageScreening
from app.models.user import User
from app.repositories.screening_repository import ScreeningRepository
from app.schemas.baggage_screening import ScreeningCreate, ScreeningOut, ScreeningRelease
from app.schemas.common import Page
from app.services.baggage_screening_service import BaggageScreeningService
from app.utils.enums import ScreeningStatus
from app.utils.pagination import PageParams, page_params, paginate

router = APIRouter(prefix="/baggage", tags=["Baggage Screening"])


@router.post("/{baggage_id}/screenings", response_model=ScreeningOut, status_code=201,
             summary="Record screening result (CLEARED / HOLD / REJECTED)")
def screen(baggage_id: int, data: ScreeningCreate, db: DB, user: User = allow(Permissions.BAGGAGE_SCREEN)):
    return BaggageScreeningService(db).screen(baggage_id, data, user)


@router.get("/{baggage_id}/screenings", response_model=list[ScreeningOut])
def baggage_screenings(baggage_id: int, db: DB, _: CurrentUser):
    repo = ScreeningRepository(db)
    return repo.list(repo.search(baggage_id=baggage_id).order_by(BaggageScreening.screened_at))


@router.get("/screenings/all", response_model=Page[ScreeningOut], summary="All screening records")
def list_screenings(db: DB, _: User = allow(Permissions.BAGGAGE_SCREEN), status: ScreeningStatus | None = None,
                    params: PageParams = Depends(page_params)):
    stmt = ScreeningRepository(db).search(status=status).order_by(BaggageScreening.screened_at.desc())
    return paginate(db, stmt, params)


@router.post("/screenings/{screening_id}/release", response_model=ScreeningOut, summary="Release a security hold")
def release(screening_id: int, data: ScreeningRelease, db: DB, user: User = allow(Permissions.BAGGAGE_SCREEN)):
    return BaggageScreeningService(db).release(screening_id, data.remarks, user)
