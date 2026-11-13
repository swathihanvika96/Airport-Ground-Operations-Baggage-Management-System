from fastapi import APIRouter, Depends

from app.api.dependencies import DB, CurrentUser, allow
from app.core.permissions import Permissions
from app.models.user import User
from app.schemas.common import Message, Page
from app.schemas.notification import BroadcastRequest, NotificationOut, UnreadCount
from app.services.notification_service import NotificationService
from app.utils.enums import NotificationType
from app.utils.pagination import PageParams, page_params, paginate

router = APIRouter(prefix="/notifications", tags=["Notifications"])


@router.get("", response_model=Page[NotificationOut], summary="My in-app notifications")
def my_notifications(db: DB, user: CurrentUser, is_read: bool | None = None,
                     notification_type: NotificationType | None = None, params: PageParams = Depends(page_params)):
    return paginate(db, NotificationService(db).list_for_user(user.id, is_read, notification_type), params)


@router.get("/unread-count", response_model=UnreadCount)
def unread_count(db: DB, user: CurrentUser):
    return {"unread": NotificationService(db).unread_count(user.id)}


@router.patch("/{notification_id}/read", response_model=NotificationOut)
def mark_read(notification_id: int, db: DB, user: CurrentUser):
    return NotificationService(db).mark_read(user.id, notification_id, True)


@router.patch("/{notification_id}/unread", response_model=NotificationOut)
def mark_unread(notification_id: int, db: DB, user: CurrentUser):
    return NotificationService(db).mark_read(user.id, notification_id, False)


@router.post("/read-all", response_model=Message)
def read_all(db: DB, user: CurrentUser):
    count = NotificationService(db).mark_all_read(user.id)
    return {"message": f"{count} notifications marked as read"}


@router.delete("/{notification_id}", status_code=204)
def delete(notification_id: int, db: DB, user: CurrentUser):
    NotificationService(db).delete(user.id, notification_id)


@router.post("/broadcast", response_model=Message, summary="Send an announcement to roles (or everyone)")
def broadcast(data: BroadcastRequest, db: DB, user: User = allow(Permissions.NOTIFICATION_BROADCAST)):
    svc = NotificationService(db)
    count = svc.notify_roles(data.roles or None, data.notification_type, data.title, data.message,
                             priority=data.priority)
    db.commit()
    return {"message": f"Notification sent to {count} users"}
