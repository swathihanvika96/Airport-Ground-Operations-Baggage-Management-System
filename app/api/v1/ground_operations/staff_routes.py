from fastapi import APIRouter, Depends

from app.api.dependencies import DB, CurrentUser, allow
from app.core.permissions import Permissions
from app.models.ground_staff import GroundStaff
from app.models.user import User
from app.repositories.staff_repository import StaffRepository
from app.schemas.common import Page
from app.schemas.ground_staff import AvailabilityUpdate, StaffCreate, StaffOut, StaffUpdate
from app.services.staff_service import StaffService
from app.utils.enums import Department, Shift, StaffAvailability
from app.utils.pagination import PageParams, page_params, paginate

router = APIRouter(prefix="/ground-staff", tags=["Ground Staff"])


@router.post("", response_model=StaffOut, status_code=201)
def register_staff(data: StaffCreate, db: DB, user: User = allow(Permissions.STAFF_MANAGE)):
    return StaffService(db).create(data, user)


@router.get("", response_model=Page[StaffOut])
def list_staff(db: DB, _: CurrentUser, q: str | None = None, department: Department | None = None,
               shift: Shift | None = None, availability: StaffAvailability | None = None, skill: str | None = None,
               supervisor_id: int | None = None, is_active: bool | None = None,
               params: PageParams = Depends(page_params)):
    stmt = StaffRepository(db).search(q, department, shift, availability, skill.lower() if skill else None,
                                      supervisor_id, is_active).order_by(GroundStaff.full_name)
    return paginate(db, stmt, params)


@router.get("/{staff_id}", response_model=StaffOut)
def get_staff(staff_id: int, db: DB, _: CurrentUser):
    return StaffService(db).get(staff_id)


@router.patch("/{staff_id}", response_model=StaffOut)
def update_staff(staff_id: int, data: StaffUpdate, db: DB, user: User = allow(Permissions.STAFF_MANAGE)):
    return StaffService(db).update(staff_id, data, user)


@router.patch("/{staff_id}/availability", response_model=StaffOut)
def set_availability(staff_id: int, data: AvailabilityUpdate, db: DB, user: User = allow(Permissions.STAFF_MANAGE)):
    return StaffService(db).set_availability(staff_id, data.availability_status, user)


@router.get("/{staff_id}/team", response_model=list[StaffOut], summary="Staff reporting to this supervisor")
def team(staff_id: int, db: DB, _: CurrentUser):
    return StaffService(db).team(staff_id)
