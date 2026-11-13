from fastapi import APIRouter, Depends

from app.api.dependencies import DB, allow
from app.core.permissions import Permissions
from app.models.audit_log import AuditLog
from app.models.user import User
from app.repositories.audit_repository import AuditRepository
from app.schemas.audit import AuditLogOut
from app.schemas.common import Page
from app.services.audit_service import AuditService
from app.utils.enums import AuditAction
from app.utils.filters import DateRangeParams
from app.utils.pagination import PageParams, page_params, paginate

router = APIRouter(prefix="/audit-logs", tags=["Audit Logs"])


@router.get("", response_model=Page[AuditLogOut])
def list_audit_logs(db: DB, _: User = allow(Permissions.AUDIT_VIEW), user_id: int | None = None,
                    action: AuditAction | None = None, entity_type: str | None = None, entity_id: int | None = None,
                    dates: DateRangeParams = Depends(), params: PageParams = Depends(page_params)):
    start, end = dates.bounds
    stmt = AuditRepository(db).search(user_id, action.value if action else None, entity_type, entity_id, start, end)
    page = paginate(db, stmt.order_by(AuditLog.timestamp.desc(), AuditLog.id.desc()), params)
    page["items"] = [AuditService.to_out(e) for e in page["items"]]
    return page


@router.get("/entity/{entity_type}/{entity_id}", response_model=list[AuditLogOut], summary="Full trail for an entity")
def entity_trail(entity_type: str, entity_id: int, db: DB, _: User = allow(Permissions.AUDIT_VIEW)):
    repo = AuditRepository(db)
    rows = repo.list(repo.search(entity_type=entity_type, entity_id=entity_id).order_by(AuditLog.timestamp, AuditLog.id))
    return [AuditService.to_out(e) for e in rows]


@router.get("/actions", summary="List of audited action types")
def actions(_: User = allow(Permissions.AUDIT_VIEW)):
    return [a.value for a in AuditAction]
