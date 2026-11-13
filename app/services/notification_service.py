"""In-app notifications. Role-targeted messages are fanned out to one row per user (own read/unread state)."""
from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError
from app.models.notification import Notification
from app.repositories.notification_repository import NotificationRepository
from app.repositories.user_repository import UserRepository
from app.utils.datetime_utils import utcnow
from app.utils.enums import NotificationType, Severity, UserRole
from app.workers.notification_worker import enqueue_notification


class NotificationService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = NotificationRepository(db)
        self.users = UserRepository(db)

    def notify_users(self, user_ids: list[int], ntype: NotificationType, title: str, message: str,
                     entity_type: str | None = None, entity_id: int | None = None,
                     priority: Severity = Severity.MEDIUM) -> int:
        created = 0
        for uid in dict.fromkeys(user_ids):  # de-duplicate, keep order
            n = Notification(user_id=uid, notification_type=ntype, title=title, message=message,
                             entity_type=entity_type, entity_id=entity_id, priority=priority)
            self.db.add(n)
            created += 1
        if created:
            enqueue_notification(ntype.value, title, len(user_ids))
        return created

    def notify_roles(self, roles: list[UserRole] | None, ntype: NotificationType, title: str, message: str,
                     entity_type: str | None = None, entity_id: int | None = None,
                     priority: Severity = Severity.MEDIUM, extra_user_ids: list[int] | None = None) -> int:
        ids = self.users.active_ids_by_roles(roles)
        if extra_user_ids:
            ids += [i for i in extra_user_ids if i]
        return self.notify_users(ids, ntype, title, message, entity_type, entity_id, priority)

    # --- user facing ---
    def list_for_user(self, user_id, is_read=None, notification_type=None):
        return self.repo.for_user(user_id, is_read, notification_type)

    def _own(self, user_id, notification_id) -> Notification:
        n = self.repo.get(notification_id)
        if not n or n.user_id != user_id:
            raise NotFoundError("Notification", notification_id)
        return n

    def mark_read(self, user_id, notification_id, read: bool = True) -> Notification:
        n = self._own(user_id, notification_id)
        n.is_read = read
        n.read_at = utcnow() if read else None
        self.db.commit()
        return n

    def mark_all_read(self, user_id) -> int:
        count = self.repo.mark_all_read(user_id)
        self.db.commit()
        return count

    def delete(self, user_id, notification_id) -> None:
        n = self._own(user_id, notification_id)
        self.db.delete(n)
        self.db.commit()

    def unread_count(self, user_id) -> int:
        return self.repo.unread_count(user_id)
