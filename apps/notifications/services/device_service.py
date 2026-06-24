"""Device token registration for FCM push delivery."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from apps.notifications.models import DeviceToken

if TYPE_CHECKING:
    from apps.accounts.models import User

logger = logging.getLogger(__name__)


def register_device(user: User, fcm_token: str, platform: str) -> DeviceToken:
    """Register (or re-point) an FCM token to this user. Idempotent by token."""
    device, created = DeviceToken.objects.update_or_create(
        fcm_token=fcm_token,
        defaults={"user": user, "platform": platform},
    )
    logger.info(
        "device_registered" if created else "device_reregistered",
        extra={"event": "device_registered", "user_id": user.pk},
    )
    return device


def unregister_device(user: User, fcm_token: str) -> int:
    """Delete a user's device token. Returns the number of rows removed (0 or 1)."""
    deleted, _ = DeviceToken.objects.filter(user=user, fcm_token=fcm_token).delete()
    logger.info(
        "device_unregistered",
        extra={"event": "device_unregistered", "user_id": user.pk},
    )
    return deleted
