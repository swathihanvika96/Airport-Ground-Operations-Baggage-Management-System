from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.common import ORMModel
from app.utils.enums import NotificationType, Severity, UserRole


class NotificationOut(ORMModel):
    id: int
    user_id: int
    notification_type: NotificationType
    priority: Severity
    title: str
    message: str
    entity_type: str | None
    entity_id: int | None
    is_read: bool
    read_at: datetime | None
    created_at: datetime


class BroadcastRequest(BaseModel):
    title: str = Field(min_length=3, max_length=200)
    message: str = Field(min_length=3)
    roles: list[UserRole] = Field(default_factory=list, description="Empty = all active users")
    notification_type: NotificationType = NotificationType.SYSTEM
    priority: Severity = Severity.MEDIUM


class UnreadCount(BaseModel):
    unread: int
