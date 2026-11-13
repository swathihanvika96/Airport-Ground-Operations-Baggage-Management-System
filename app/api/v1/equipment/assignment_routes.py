from fastapi import APIRouter, Depends

from app.api.dependencies import DB, CurrentUser, allow
from app.core.permissions import Permissions
from app.models.user import User
from app.repositories.equipment_repository import EquipmentRepository
from app.schemas.common import Page
from app.schemas.equipment import EquipmentAssignmentOut, EquipmentAssignRequest
from app.services.equipment_service import EquipmentService
from app.utils.enums import AssignmentStatus
from app.utils.pagination import PageParams, page_params, paginate

router = APIRouter(prefix="/equipment-assignments", tags=["Equipment Assignment"])


@router.post("", response_model=EquipmentAssignmentOut, status_code=201,
             summary="Assign equipment to a flight (availability + conflict validated)")
def assign(data: EquipmentAssignRequest, db: DB, user: User = allow(Permissions.EQUIPMENT_ASSIGN)):
    return EquipmentService(db).assign(data.equipment_id, data.flight_id, user, data.start_time, data.end_time,
                                       data.remarks)


@router.get("", response_model=Page[EquipmentAssignmentOut])
def list_assignments(db: DB, _: CurrentUser, equipment_id: int | None = None, flight_id: int | None = None,
                     status: AssignmentStatus | None = None, params: PageParams = Depends(page_params)):
    return paginate(db, EquipmentRepository(db).assignments(equipment_id, flight_id, status), params)


@router.post("/{assignment_id}/release", response_model=EquipmentAssignmentOut)
def release(assignment_id: int, db: DB, user: User = allow(Permissions.EQUIPMENT_ASSIGN)):
    return EquipmentService(db).release(assignment_id, user)
