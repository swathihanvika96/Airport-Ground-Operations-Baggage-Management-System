from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.common import ORMModel
from app.utils.enums import TerminalStatus


class TerminalCreate(BaseModel):
    airport_id: int
    code: str = Field(min_length=1, max_length=10)
    name: str = Field(min_length=1, max_length=100)
    capacity: int = Field(0, ge=0, description="Passengers per hour")
    is_international: bool = False
    status: TerminalStatus = TerminalStatus.ACTIVE


class TerminalUpdate(BaseModel):
    name: str | None = None
    capacity: int | None = Field(None, ge=0)
    is_international: bool | None = None
    status: TerminalStatus | None = None


class TerminalOut(ORMModel):
    id: int
    airport_id: int
    code: str
    name: str
    capacity: int
    is_international: bool
    status: TerminalStatus
    created_at: datetime


class TerminalMapOut(TerminalOut):
    gates: list[dict] = []
    counters: list[dict] = []
