"""Notification dispatch hook.

In-app notifications are persisted synchronously in the DB. This worker is the extension point for
out-of-band delivery (email/SMS/push). If REDIS_URL is configured, events are published to a Redis
channel so an external consumer (or a websocket gateway) can fan them out; otherwise they are logged.
"""
import json
import logging

from app.core.config import settings

logger = logging.getLogger("workers.notifications")
_redis = None
CHANNEL = "airport:notifications"


def _get_redis():
    global _redis
    if _redis is None and settings.REDIS_URL:
        try:
            import redis  # optional dependency
            _redis = redis.Redis.from_url(settings.REDIS_URL, socket_connect_timeout=1)
        except Exception as exc:  # pragma: no cover - redis optional
            logger.warning("Redis unavailable (%s); falling back to logging", exc)
            _redis = False
    return _redis or None


def enqueue_notification(notification_type: str, title: str, recipients: int) -> None:
    event = {"type": notification_type, "title": title, "recipients": recipients}
    client = _get_redis()
    if client:
        try:
            client.publish(CHANNEL, json.dumps(event))
            return
        except Exception as exc:  # pragma: no cover
            logger.warning("Redis publish failed: %s", exc)
    logger.info("notification: %s", event)
