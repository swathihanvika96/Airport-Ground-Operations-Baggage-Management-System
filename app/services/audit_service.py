"""Audit trail: who changed what, when, with previous and new values."""
import json
from datetime import date, datetime
from enum import Enum
from typing import Any

from sqlalchemy import inspect
from sqlalchemy.orm import Session

from app.middleware.request_id import client_ip_ctx, request_id_ctx
from app.models.audit_log import AuditLog
from app.repositories.audit_repository import AuditRepository
from app.utils.enums import AuditAction


def _default(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return str(value)


def snapshot(obj: Any, fields: list[str] | None = None) -> dict[str, Any] | None:
    """Serialisable dict of an ORM object's column values (optionally a subset)."""
    if obj is None:
        return None
    cols = [c.key for c in inspect(obj).mapper.column_attrs]
    if fields:
        cols = [c for c in cols if c in fields]
    return {c: getattr(obj, c) for c in cols if c not in ("hashed_password",)}


def _dump(value: Any) -> str | None:
    if value is None:
        return None
    return json.dumps(value, default=_default)


class AuditService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = AuditRepository(db)

    def log(self, action: AuditAction | str, entity_type: str, entity_id: int | None = None,
            previous: Any = None, new: Any = None, user_id: int | None = None) -> AuditLog:
        entry = AuditLog(
            user_id=user_id,
            action=action.value if isinstance(action, Enum) else action,
            entity_type=entity_type,
            entity_id=entity_id,
            previous_value=_dump(previous),
            new_value=_dump(new),
            ip_address=client_ip_ctx.get(),
            request_id=request_id_ctx.get(),
        )
        self.db.add(entry)
        return entry

    @staticmethod
    def to_out(entry: AuditLog) -> dict[str, Any]:
        def load(v):
            if v is None:
                return None
            try:
                return json.loads(v)
            except ValueError:
                return v
        return {
            "id": entry.id, "user_id": entry.user_id, "action": entry.action, "entity_type": entry.entity_type,
            "entity_id": entry.entity_id, "previous_value": load(entry.previous_value),
            "new_value": load(entry.new_value), "ip_address": entry.ip_address,
            "request_id": entry.request_id, "timestamp": entry.timestamp,
        }
