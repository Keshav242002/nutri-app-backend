"""Notification dispatch — the single entry point for creating notifications.

Two layers: a `Notification` row is the source of truth (created synchronously here),
and an FCM push is enqueued as a fire-and-forget Celery task. Dispatch is idempotent via
`(user, dedup_key)`: a repeated call with the same key creates no new row and sends no
push.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from django.db.models import QuerySet
from django.utils import timezone

from apps.notifications.models import Notification
from apps.notifications.services.templates import render
from core.error_codes import NOT_FOUND
from core.exceptions import NotFoundError

if TYPE_CHECKING:
    from apps.accounts.models import User

logger = logging.getLogger(__name__)


def dispatch(
    user: User,
    category: str,
    *,
    dedup_key: str,
    context: dict[str, Any] | None = None,
) -> Notification | None:
    """Create a notification (idempotent by dedup_key) and enqueue its push.

    Returns the new Notification, or None if one already existed for this dedup_key.
    """
    context = context or {}
    title, body, route = render(category, context)
    data = {"route": route, **context}

    notification, created = Notification.objects.get_or_create(
        user=user,
        dedup_key=dedup_key,
        defaults={
            "category": category,
            "title": title,
            "body": body,
            "data": data,
        },
    )

    if not created:
        return None

    # Enqueue the FCM push (external call) on the worker — never in the request path.
    from apps.notifications.tasks import send_push

    send_push.delay(notification.pk)

    logger.info(
        "notification_dispatched",
        extra={
            "event": "notification_dispatched",
            "user_id": user.pk,
            "category": category,
        },
    )
    return notification


def list_notifications(user: User, unread_only: bool = False) -> QuerySet[Notification]:
    """Return the user's notifications, newest first; optionally unread only."""
    qs = Notification.objects.filter(user=user)
    if unread_only:
        qs = qs.filter(read_at__isnull=True)
    return qs.order_by("-created_at")


def unread_count(user: User) -> int:
    """Return the number of unread notifications for the user."""
    return Notification.objects.filter(user=user, read_at__isnull=True).count()


def mark_read(user: User, notification_id: int) -> Notification:
    """Mark one notification read. Raises NotFoundError if it isn't the user's."""
    try:
        notification = Notification.objects.get(pk=notification_id, user=user)
    except Notification.DoesNotExist:
        raise NotFoundError(message="Notification not found.", code=NOT_FOUND) from None
    if notification.read_at is None:
        notification.read_at = timezone.now()
        notification.save(update_fields=["read_at", "updated_at"])
    return notification


def mark_all_read(user: User) -> int:
    """Mark all of the user's unread notifications read. Returns the count updated."""
    return Notification.objects.filter(user=user, read_at__isnull=True).update(
        read_at=timezone.now()
    )
