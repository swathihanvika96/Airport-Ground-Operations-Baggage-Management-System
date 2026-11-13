from sqlalchemy import select

from app.models.audit_log import AuditLog
from app.repositories.base import BaseRepository


class AuditRepository(BaseRepository[AuditLog]):
    model = AuditLog
    entity_name = "Audit log"

    def search(self, user_id=None, action=None, entity_type=None, entity_id=None, start=None, end=None):
        stmt = select(AuditLog)
        if user_id:
            stmt = stmt.where(AuditLog.user_id == user_id)
        if action:
            stmt = stmt.where(AuditLog.action == action)
        if entity_type:
            stmt = stmt.where(AuditLog.entity_type == entity_type)
        if entity_id:
            stmt = stmt.where(AuditLog.entity_id == entity_id)
        if start:
            stmt = stmt.where(AuditLog.timestamp >= start)
        if end:
            stmt = stmt.where(AuditLog.timestamp < end)
        return stmt
