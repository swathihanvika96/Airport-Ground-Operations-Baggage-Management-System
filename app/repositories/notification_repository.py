from sqlalchemy import func, select, update

from app.models.notification import Notification
from app.repositories.base import BaseRepository
from app.utils.datetime_utils import utcnow


class NotificationRepository(BaseRepository[Notification]):
    model = Notification
    entity_name = "Notification"

    def for_user(self, user_id, is_read=None, notification_type=None):
        stmt = select(Notification).where(Notification.user_id == user_id)
        if is_read is not None:
            stmt = stmt.where(Notification.is_read.is_(is_read))
        if notification_type:
            stmt = stmt.where(Notification.notification_type == notification_type)
        return stmt.order_by(Notification.created_at.desc(), Notification.id.desc())

    def unread_count(self, user_id) -> int:
        return self.db.scalar(select(func.count(Notification.id)).where(
            Notification.user_id == user_id, Notification.is_read.is_(False))) or 0

    def mark_all_read(self, user_id) -> int:
        result = self.db.execute(update(Notification)
                                 .where(Notification.user_id == user_id, Notification.is_read.is_(False))
                                 .values(is_read=True, read_at=utcnow()))
        return result.rowcount or 0
