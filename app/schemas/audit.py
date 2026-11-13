from datetime import datetime
from typing import Any

from app.schemas.common import ORMModel


class AuditLogOut(ORMModel):
    id: int
    user_id: int | None
    action: str
    entity_type: str
    entity_id: int | None
    previous_value: Any | None
    new_value: Any | None
    ip_address: str | None
    request_id: str | None
    timestamp: datetime
