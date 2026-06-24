"""Model tests for apps/notifications."""

from __future__ import annotations

import pytest
from django.db import IntegrityError

from apps.accounts.tests.factories import UserFactory
from apps.notifications.models import DeviceToken
from apps.notifications.services import device_service

from .factories import DeviceTokenFactory, NotificationFactory

pytestmark = pytest.mark.django_db


def test_dedup_key_unique_per_user() -> None:
    user = UserFactory()
    NotificationFactory(user=user, dedup_key="streak-7:1:2026-06-20")
    with pytest.raises(IntegrityError):
        NotificationFactory(user=user, dedup_key="streak-7:1:2026-06-20")


def test_same_dedup_key_allowed_for_different_users() -> None:
    NotificationFactory(user=UserFactory(), dedup_key="shared-key")
    # Different user, same key — must not raise.
    NotificationFactory(user=UserFactory(), dedup_key="shared-key")


def test_device_token_upsert_repoints_to_new_user() -> None:
    user_a = UserFactory()
    user_b = UserFactory()
    DeviceTokenFactory(user=user_a, fcm_token="shared-token")

    device_service.register_device(user_b, "shared-token", "ios")

    token = DeviceToken.objects.get(fcm_token="shared-token")
    assert token.user_id == user_b.pk
    assert token.platform == "ios"
    assert DeviceToken.objects.filter(fcm_token="shared-token").count() == 1
