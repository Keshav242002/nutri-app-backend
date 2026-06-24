"""Task tests for apps/notifications — called directly, no broker."""

from __future__ import annotations

from datetime import date, timedelta
from unittest.mock import patch

import pytest
from django.utils import timezone
from freezegun import freeze_time

from apps.accounts.tests.factories import UserFactory
from apps.notifications.models import CATEGORY_STREAK, Notification
from apps.notifications.tasks import prune_old_notifications, send_push
from apps.tracker.models import STATUS_ATE_PLANNED
from apps.tracker.tasks import recompute_yesterday_summaries
from apps.tracker.tests.factories import MealLogFactory

from .factories import DeviceTokenFactory, NotificationFactory

pytestmark = pytest.mark.django_db


def test_send_push_calls_fcm_service() -> None:
    user = UserFactory()
    DeviceTokenFactory(user=user)
    notification = NotificationFactory(user=user)

    with patch("apps.notifications.services.fcm_service.send_to_user") as mock_send:
        send_push(notification.pk)

    mock_send.assert_called_once()


def test_send_push_missing_notification_is_noop() -> None:
    with patch("apps.notifications.services.fcm_service.send_to_user") as mock_send:
        send_push(999999)
    mock_send.assert_not_called()


def test_prune_deletes_only_old_notifications() -> None:
    user = UserFactory()
    fresh = NotificationFactory(user=user)
    old = NotificationFactory(user=user)
    # Force the old row's created_at well past the retention window.
    Notification.objects.filter(pk=old.pk).update(created_at=timezone.now() - timedelta(days=31))

    prune_old_notifications()

    remaining = set(Notification.objects.values_list("pk", flat=True))
    assert remaining == {fresh.pk}


def test_nightly_task_fires_streak_notification() -> None:
    """recompute_yesterday_summaries evaluates the streak and dispatches at a milestone."""
    user = UserFactory()
    # 7 consecutive fully-logged days ending on 2026-06-20 (the task's "yesterday").
    end = date(2026, 6, 20)
    for offset in range(7):
        day = end - timedelta(days=offset)
        for slot in ("breakfast", "lunch", "dinner"):
            MealLogFactory(user=user, log_date=day, slot=slot, status=STATUS_ATE_PLANNED)

    with patch("apps.notifications.tasks.send_push"):
        with freeze_time("2026-06-21 02:00:00"):
            recompute_yesterday_summaries()

    assert Notification.objects.filter(user=user, category=CATEGORY_STREAK).count() == 1
