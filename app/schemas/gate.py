from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.common import ORMModel
from app.utils.enums import GateStatus, GateType


class GateCreate(BaseModel):
    terminal_id: int
    gate_number: str = Field(min_length=1, max_length=10)
    gate_type: GateType = GateType.DOMESTIC


class GateUpdate(BaseModel):
    gate_type: GateType | None = None
    status: GateStatus | None = None
    is_active: bool | None = None


class GateOut(ORMModel):
    id: int
    terminal_id: int
    gate_number: str
    gate_type: GateType
    status: GateStatus
    is_active: bool
    created_at: datetime
