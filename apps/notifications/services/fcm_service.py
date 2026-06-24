"""FCM push delivery via the Firebase Admin SDK.

Reuses the Firebase app initialized at startup (`apps.accounts.firebase.init_firebase`) —
no separate credentials. Called only from the `send_push` Celery task, never the request
path. Failures are logged, not raised: the persisted Notification is the source of truth,
so a dropped push is non-fatal.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from apps.notifications.models import DeviceToken

if TYPE_CHECKING:
    from apps.accounts.models import User
    from apps.notifications.models import Notification

logger = logging.getLogger(__name__)


def send_to_user(user: User, notification: Notification) -> int:
    """Send a push for `notification` to all of the user's devices.

    Returns the count of successful sends. Prunes tokens FCM reports as stale.
    """
    # Lazy import so the package is only required when a push actually fires.
    from firebase_admin import messaging

    tokens = list(DeviceToken.objects.filter(user=user).values_list("fcm_token", flat=True))
    if not tokens:
        return 0

    message = messaging.MulticastMessage(
        tokens=tokens,
        notification=messaging.Notification(
            title=notification.title,
            body=notification.body,
        ),
        data={k: str(v) for k, v in notification.data.items()},
    )

    batch = messaging.send_each_for_multicast(message)

    stale: list[str] = []
    for token, resp in zip(tokens, batch.responses, strict=True):
        if resp.success:
            continue
        exc = resp.exception
        if isinstance(exc, (messaging.UnregisteredError, messaging.SenderIdMismatchError)):
            stale.append(token)

    if stale:
        DeviceToken.objects.filter(fcm_token__in=stale).delete()

    logger.info(
        "fcm_push_sent",
        extra={
            "event": "fcm_push_sent",
            "user_id": user.pk,
            "success_count": batch.success_count,
            "pruned": len(stale),
        },
    )
    return int(batch.success_count)
