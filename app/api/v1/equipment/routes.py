from fastapi import APIRouter, Depends, Query

from app.api.dependencies import DB, CurrentUser, allow
from app.core.permissions import Permissions
from app.models.equipment import Equipment
from app.models.user import User
from app.repositories.equipment_repository import EquipmentRepository
from app.schemas.common import Page, UTCDateTime
from app.schemas.equipment import (
    EquipmentAssignmentOut,
    EquipmentCreate,
    EquipmentOut,
    EquipmentStatusUpdate,
    EquipmentUpdate,
)
from app.services.equipment_service import EquipmentService
from app.utils.enums import EquipmentStatus, EquipmentType
from app.utils.pagination import PageParams, page_params, paginate

router = APIRouter(prefix="/equipment", tags=["Ground Equipment"])


@router.post("", response_model=EquipmentOut, status_code=201)
def register_equipment(data: EquipmentCreate, db: DB, user: User = allow(Permissions.EQUIPMENT_MANAGE)):
    return EquipmentService(db).create(data, user)


@router.get("", response_model=Page[EquipmentOut])
def list_equipment(db: DB, _: CurrentUser, q: str | None = None, equipment_type: EquipmentType | None = None,
                   status: EquipmentStatus | None = None, terminal_id: int | None = None,
                   airport_id: int | None = None, params: PageParams = Depends(page_params)):
    stmt = EquipmentRepository(db).search(q, equipment_type, status, terminal_id, airport_id).order_by(Equipment.equipment_code)
    return paginate(db, stmt, params)


@router.get("/available", response_model=list[EquipmentOut], summary="Equipment availability for a time window")
def available(db: DB, _: CurrentUser, start_time: UTCDateTime = Query(...), end_time: UTCDateTime = Query(...),
              equipment_type: EquipmentType | None = None, terminal_id: int | None = None):
    return EquipmentService(db).available(start_time, end_time, equipment_type, terminal_id)


@router.get("/{equipment_id}", response_model=EquipmentOut)
def get_equipment(equipment_id: int, db: DB, _: CurrentUser):
    return EquipmentService(db).get(equipment_id)


@router.patch("/{equipment_id}", response_model=EquipmentOut)
def update_equipment(equipment_id: int, data: EquipmentUpdate, db: DB, user: User = allow(Permissions.EQUIPMENT_MANAGE)):
    return EquipmentService(db).update(equipment_id, data, user)


@router.patch("/{equipment_id}/status", response_model=EquipmentOut)
def update_status(equipment_id: int, data: EquipmentStatusUpdate, db: DB,
                  user: User = allow(Permissions.EQUIPMENT_MANAGE)):
    return EquipmentService(db).set_status(equipment_id, data.status, user, data.remarks)


@router.get("/{equipment_id}/usage-history", response_model=Page[EquipmentAssignmentOut])
def usage_history(equipment_id: int, db: DB, _: CurrentUser, params: PageParams = Depends(page_params)):
    EquipmentService(db).get(equipment_id)
    return paginate(db, EquipmentRepository(db).assignments(equipment_id=equipment_id), params)
