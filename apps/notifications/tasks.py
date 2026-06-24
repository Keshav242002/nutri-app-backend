from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from celery import shared_task
from django.utils import timezone

log = logging.getLogger(__name__)

# Notifications older than this are pruned by the nightly task.
RETENTION_DAYS = 30


@shared_task(bind=True, max_retries=3, default_retry_delay=60)  # type: ignore[untyped-decorator]
def send_push(self: Any, notification_id: int) -> None:
    """Deliver a persisted notification to the user's devices via FCM."""
    from apps.notifications.models import Notification
    from apps.notifications.services.fcm_service import send_to_user

    try:
        notification = Notification.objects.select_related("user").get(pk=notification_id)
    except Notification.DoesNotExist:
        log.error("event=send_push_notification_not_found notification_id=%s", notification_id)
        return

    try:
        send_to_user(notification.user, notification)
    except Exception as exc:
        log.warning(
            "event=send_push_failed notification_id=%s error=%s",
            notification_id,
            exc,
        )
        raise self.retry(exc=exc) from exc


@shared_task  # type: ignore[untyped-decorator]
def prune_old_notifications() -> None:
    """Delete notifications older than RETENTION_DAYS (read or unread)."""
    from apps.notifications.models import Notification

    cutoff = timezone.now() - timedelta(days=RETENTION_DAYS)
    deleted, _ = Notification.objects.filter(created_at__lt=cutoff).delete()
    log.info("event=prune_old_notifications_done deleted=%d cutoff=%s", deleted, cutoff)
