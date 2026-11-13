from fastapi import APIRouter, Depends, Query

from app.api.dependencies import DB, CurrentUser, allow
from app.core.permissions import Permissions
from app.models.gate import Gate
from app.models.user import User
from app.repositories.gate_repository import GateRepository
from app.schemas.assignment import GateAssignmentOut, GateAssignRequest
from app.schemas.common import Page, UTCDateTime
from app.schemas.gate import GateCreate, GateOut, GateUpdate
from app.services.gate_service import GateService
from app.utils.enums import AssignmentStatus, GateStatus
from app.utils.pagination import PageParams, page_params, paginate

router = APIRouter(prefix="/gates", tags=["Gates"])


@router.post("", response_model=GateOut, status_code=201)
def register_gate(data: GateCreate, db: DB, user: User = allow(Permissions.GATE_MANAGE)):
    return GateService(db).create(data, user)


@router.get("", response_model=Page[GateOut])
def list_gates(db: DB, _: CurrentUser, terminal_id: int | None = None, airport_id: int | None = None,
               status: GateStatus | None = None, is_active: bool | None = None,
               params: PageParams = Depends(page_params)):
    stmt = GateRepository(db).search(terminal_id, airport_id, status, is_active).order_by(Gate.gate_number)
    return paginate(db, stmt, params)


@router.get("/available", response_model=list[GateOut], summary="Gate availability for a time window")
def available_gates(db: DB, _: CurrentUser, start_time: UTCDateTime = Query(...), end_time: UTCDateTime = Query(...),
                    terminal_id: int | None = None, airport_id: int | None = None):
    return GateService(db).available(start_time, end_time, terminal_id, airport_id)


@router.get("/assignments", response_model=Page[GateAssignmentOut], summary="Gate assignment history")
def assignment_history(db: DB, _: CurrentUser, gate_id: int | None = None, flight_id: int | None = None,
                       status: AssignmentStatus | None = None, params: PageParams = Depends(page_params)):
    return paginate(db, GateRepository(db).assignments(gate_id, flight_id, status), params)


@router.get("/{gate_id}", response_model=GateOut)
def get_gate(gate_id: int, db: DB, _: CurrentUser):
    return GateService(db).get(gate_id)


@router.patch("/{gate_id}", response_model=GateOut)
def update_gate(gate_id: int, data: GateUpdate, db: DB, user: User = allow(Permissions.GATE_MANAGE)):
    return GateService(db).update(gate_id, data, user)


@router.post("/{gate_id}/assign", response_model=GateAssignmentOut, status_code=201,
             summary="Assign gate to flight (conflict-checked; re-assign = gate change)")
def assign_gate(gate_id: int, data: GateAssignRequest, db: DB, user: User = allow(Permissions.GATE_ASSIGN)):
    return GateService(db).assign(gate_id, data.flight_id, user, data.start_time, data.end_time, data.remarks)


@router.post("/assignments/{assignment_id}/release", response_model=GateAssignmentOut)
def release_gate(assignment_id: int, db: DB, user: User = allow(Permissions.GATE_ASSIGN)):
    return GateService(db).release(assignment_id, user)
