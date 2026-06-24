"""Service tests for apps/notifications."""

from __future__ import annotations

from datetime import date, timedelta
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from apps.accounts.tests.factories import UserFactory
from apps.notifications.models import (
    CATEGORY_DAILY_TARGET,
    CATEGORY_STREAK,
    DeviceToken,
    Notification,
)
from apps.notifications.services import notification_service, streak_service
from apps.notifications.services.fcm_service import send_to_user
from apps.tracker.models import (
    STATUS_ATE_PLANNED,
    STATUS_SKIPPED,
)
from apps.tracker.tests.factories import MealLogFactory

from .factories import DeviceTokenFactory, NotificationFactory

pytestmark = pytest.mark.django_db


# ---------------------------------------------------------------------------
# dispatch
# ---------------------------------------------------------------------------


def test_dispatch_creates_row_and_enqueues_push() -> None:
    user = UserFactory()
    with patch("apps.notifications.tasks.send_push") as mock_task:
        result = notification_service.dispatch(
            user, CATEGORY_DAILY_TARGET, dedup_key="daily-target:1:2026-06-20"
        )

    assert result is not None
    assert Notification.objects.filter(user=user).count() == 1
    mock_task.delay.assert_called_once_with(result.pk)


def test_dispatch_is_idempotent_on_dedup_key() -> None:
    user = UserFactory()
    with patch("apps.notifications.tasks.send_push") as mock_task:
        first = notification_service.dispatch(user, CATEGORY_DAILY_TARGET, dedup_key="k")
        second = notification_service.dispatch(user, CATEGORY_DAILY_TARGET, dedup_key="k")

    assert first is not None
    assert second is None
    assert Notification.objects.filter(user=user).count() == 1
    mock_task.delay.assert_called_once()  # only the first dispatch enqueues


def test_dispatch_renders_template_with_context() -> None:
    user = UserFactory()
    with patch("apps.notifications.tasks.send_push"):
        n = notification_service.dispatch(
            user, CATEGORY_STREAK, dedup_key="s", context={"streak_days": 7}
        )
    assert n is not None
    assert "7-day streak" in n.title
    assert n.data["route"] == "tracker/today"


# ---------------------------------------------------------------------------
# read / list operations
# ---------------------------------------------------------------------------


def test_unread_count_and_mark_read() -> None:
    user = UserFactory()
    n1 = NotificationFactory(user=user)
    NotificationFactory(user=user)
    assert notification_service.unread_count(user) == 2

    notification_service.mark_read(user, n1.pk)
    assert notification_service.unread_count(user) == 1


def test_mark_all_read() -> None:
    user = UserFactory()
    NotificationFactory(user=user)
    NotificationFactory(user=user)
    updated = notification_service.mark_all_read(user)
    assert updated == 2
    assert notification_service.unread_count(user) == 0


def test_list_unread_only_filters() -> None:
    user = UserFactory()
    NotificationFactory(user=user)
    read = NotificationFactory(user=user)
    notification_service.mark_read(user, read.pk)

    assert notification_service.list_notifications(user).count() == 2
    assert notification_service.list_notifications(user, unread_only=True).count() == 1


# ---------------------------------------------------------------------------
# streak evaluation (rule: all 3 slots logged as eaten)
# ---------------------------------------------------------------------------


def _log_full_day(user: object, day: date) -> None:
    for slot in ("breakfast", "lunch", "dinner"):
        MealLogFactory(user=user, log_date=day, slot=slot, status=STATUS_ATE_PLANNED)


def test_day_qualifies_only_when_all_three_slots_eaten() -> None:
    user = UserFactory()
    day = date(2026, 6, 20)
    MealLogFactory(user=user, log_date=day, slot="breakfast", status=STATUS_ATE_PLANNED)
    MealLogFactory(user=user, log_date=day, slot="lunch", status=STATUS_ATE_PLANNED)
    # dinner missing → does not qualify
    assert streak_service.current_streak(user, day) == 0


def test_skipped_slot_does_not_qualify() -> None:
    user = UserFactory()
    day = date(2026, 6, 20)
    MealLogFactory(user=user, log_date=day, slot="breakfast", status=STATUS_ATE_PLANNED)
    MealLogFactory(user=user, log_date=day, slot="lunch", status=STATUS_ATE_PLANNED)
    MealLogFactory(user=user, log_date=day, slot="dinner", status=STATUS_SKIPPED)
    assert streak_service.current_streak(user, day) == 0


def test_current_streak_counts_consecutive_qualifying_days() -> None:
    user = UserFactory()
    end = date(2026, 6, 20)
    for offset in range(3):
        _log_full_day(user, end - timedelta(days=offset))
    assert streak_service.current_streak(user, end) == 3


def test_evaluate_streak_fires_one_notification_at_milestone() -> None:
    user = UserFactory()
    end = date(2026, 6, 20)
    for offset in range(7):
        _log_full_day(user, end - timedelta(days=offset))

    with patch("apps.notifications.tasks.send_push"):
        streak = streak_service.evaluate_streak(user, end)

    assert streak == 7
    streak_notifs = Notification.objects.filter(user=user, category=CATEGORY_STREAK)
    assert streak_notifs.count() == 1
    # Idempotent — a second evaluation creates no duplicate.
    with patch("apps.notifications.tasks.send_push"):
        streak_service.evaluate_streak(user, end)
    assert streak_notifs.count() == 1


def test_evaluate_streak_no_notification_off_milestone() -> None:
    user = UserFactory()
    end = date(2026, 6, 20)
    for offset in range(4):  # 4 is not a milestone
        _log_full_day(user, end - timedelta(days=offset))

    with patch("apps.notifications.tasks.send_push"):
        streak = streak_service.evaluate_streak(user, end)

    assert streak == 4
    assert Notification.objects.filter(user=user, category=CATEGORY_STREAK).count() == 0


# ---------------------------------------------------------------------------
# fcm_service — mocked firebase_admin.messaging, never hits FCM
# ---------------------------------------------------------------------------


class _UnregisteredError(Exception):
    pass


class _SenderIdMismatchError(Exception):
    pass


def _fake_messaging(stale_tokens: set[str]) -> SimpleNamespace:
    """Fake messaging that marks any token in `stale_tokens` as Unregistered."""

    def send_each(msg: dict[str, object]) -> SimpleNamespace:
        tokens: list[str] = msg["tokens"]  # type: ignore[assignment]
        responses = []
        success = 0
        for tok in tokens:
            if tok in stale_tokens:
                responses.append(SimpleNamespace(success=False, exception=_UnregisteredError()))
            else:
                responses.append(SimpleNamespace(success=True, exception=None))
                success += 1
        return SimpleNamespace(responses=responses, success_count=success)

    return SimpleNamespace(
        MulticastMessage=lambda **kw: kw,
        Notification=lambda **kw: kw,
        UnregisteredError=_UnregisteredError,
        SenderIdMismatchError=_SenderIdMismatchError,
        send_each_for_multicast=send_each,
    )


def test_send_to_user_no_devices_returns_zero() -> None:
    user = UserFactory()
    assert send_to_user(user, NotificationFactory(user=user)) == 0


def test_send_to_user_prunes_stale_tokens() -> None:
    user = UserFactory()
    DeviceTokenFactory(user=user, fcm_token="good")
    DeviceTokenFactory(user=user, fcm_token="stale")
    notification = NotificationFactory(user=user)

    with patch("firebase_admin.messaging", new=_fake_messaging(stale_tokens={"stale"})):
        sent = send_to_user(user, notification)

    assert sent == 1
    remaining = set(DeviceToken.objects.filter(user=user).values_list("fcm_token", flat=True))
    assert remaining == {"good"}
