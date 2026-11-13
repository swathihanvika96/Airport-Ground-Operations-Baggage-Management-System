from fastapi import APIRouter, Depends

from app.api.dependencies import DB, CurrentUser, allow
from app.core.permissions import Permissions
from app.models.terminal import Terminal
from app.models.user import User
from app.repositories.terminal_repository import TerminalRepository
from app.schemas.common import Page
from app.schemas.terminal import TerminalCreate, TerminalOut, TerminalUpdate
from app.services.terminal_service import TerminalService
from app.utils.enums import TerminalStatus
from app.utils.pagination import PageParams, page_params, paginate

router = APIRouter(prefix="/terminals", tags=["Terminals"])


@router.post("", response_model=TerminalOut, status_code=201)
def create_terminal(data: TerminalCreate, db: DB, user: User = allow(Permissions.TERMINAL_MANAGE)):
    return TerminalService(db).create(data, user)


@router.get("", response_model=Page[TerminalOut])
def list_terminals(db: DB, _: CurrentUser, airport_id: int | None = None, status: TerminalStatus | None = None,
                   params: PageParams = Depends(page_params)):
    return paginate(db, TerminalRepository(db).search(airport_id, status).order_by(Terminal.id), params)


@router.get("/{terminal_id}", response_model=TerminalOut)
def get_terminal(terminal_id: int, db: DB, _: CurrentUser):
    return TerminalService(db).get(terminal_id)


@router.get("/{terminal_id}/map", summary="Terminal mapping: gates and counters")
def terminal_map(terminal_id: int, db: DB, _: CurrentUser):
    return TerminalService(db).map(terminal_id)


@router.patch("/{terminal_id}", response_model=TerminalOut)
def update_terminal(terminal_id: int, data: TerminalUpdate, db: DB, user: User = allow(Permissions.TERMINAL_MANAGE)):
    return TerminalService(db).update(terminal_id, data, user)
