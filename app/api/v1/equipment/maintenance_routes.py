from fastapi import APIRouter, Depends

from app.api.dependencies import DB, CurrentUser, allow
from app.core.permissions import Permissions
from app.models.equipment import Equipment
from app.models.user import User
from app.repositories.equipment_repository import EquipmentRepository
from app.schemas.common import Page
from app.schemas.equipment import EquipmentOut, MaintenanceComplete, MaintenanceCreate, MaintenanceOut
from app.services.equipment_service import EquipmentService
from app.utils.datetime_utils import utcnow
from app.utils.enums import MaintenanceStatus
from app.utils.pagination import PageParams, page_params, paginate

router = APIRouter(prefix="/equipment-maintenance", tags=["Equipment Maintenance"])


@router.post("", response_model=MaintenanceOut, status_code=201)
def schedule(data: MaintenanceCreate, db: DB, user: User = allow(Permissions.MAINTENANCE)):
    return EquipmentService(db).schedule_maintenance(data, user)


@router.get("", response_model=Page[MaintenanceOut])
def list_maintenance(db: DB, _: CurrentUser, equipment_id: int | None = None,
                     status: MaintenanceStatus | None = None, params: PageParams = Depends(page_params)):
    return paginate(db, EquipmentRepository(db).maintenance(equipment_id, status), params)


@router.get("/due", response_model=list[EquipmentOut], summary="Equipment due/overdue for maintenance")
def due(db: DB, _: CurrentUser, within_days: int = 7):
    from datetime import timedelta
    limit = utcnow().date() + timedelta(days=within_days)
    repo = EquipmentRepository(db)
    return repo.list(repo.query().where(Equipment.next_maintenance_date.is_not(None),
                                        Equipment.next_maintenance_date <= limit))


@router.post("/{maintenance_id}/start", response_model=MaintenanceOut)
def start(maintenance_id: int, db: DB, user: User = allow(Permissions.MAINTENANCE)):
    return EquipmentService(db).start_maintenance(maintenance_id, user)


@router.post("/{maintenance_id}/complete", response_model=MaintenanceOut)
def complete(maintenance_id: int, data: MaintenanceComplete, db: DB, user: User = allow(Permissions.MAINTENANCE)):
    return EquipmentService(db).complete_maintenance(maintenance_id, user, data.remarks, data.next_maintenance_date)


@router.post("/{maintenance_id}/cancel", response_model=MaintenanceOut)
def cancel(maintenance_id: int, db: DB, user: User = allow(Permissions.MAINTENANCE)):
    return EquipmentService(db).cancel_maintenance(maintenance_id, user)
