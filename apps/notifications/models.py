from django.conf import settings
from django.db import models

from core.mixins import TimestampedModel

# ---------------------------------------------------------------------------
# Choice constants
# ---------------------------------------------------------------------------

CATEGORY_DAILY_TARGET = "daily_target"
CATEGORY_GOAL_UPDATED = "goal_updated"
CATEGORY_PLAN_READY = "plan_ready"
CATEGORY_STREAK = "streak"

CATEGORY_CHOICES = [
    (CATEGORY_DAILY_TARGET, "Daily Target Met"),
    (CATEGORY_GOAL_UPDATED, "Goal Updated"),
    (CATEGORY_PLAN_READY, "Meal Plan Ready"),
    (CATEGORY_STREAK, "Streak Milestone"),
]

PLATFORM_IOS = "ios"
PLATFORM_ANDROID = "android"
PLATFORM_WEB = "web"

PLATFORM_CHOICES = [
    (PLATFORM_IOS, "iOS"),
    (PLATFORM_ANDROID, "Android"),
    (PLATFORM_WEB, "Web"),
]


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


class Notification(TimestampedModel):
    """One notification for one user — the source of truth for the in-app feed."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notifications",
        db_index=True,
    )
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES)
    title = models.CharField(max_length=120)
    body = models.CharField(max_length=300)

    # Deep-link route + ids for the client, e.g. {"route": "tracker/today"}
    data = models.JSONField(default=dict, blank=True)

    read_at = models.DateTimeField(null=True, blank=True)

    # Idempotency key — unique per user so repeated dispatch (e.g. the idempotent
    # nightly recompute) cannot create duplicate rows.
    dedup_key = models.CharField(max_length=120, db_index=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user", "dedup_key"],
                name="notification_user_dedup_unique",
            ),
        ]
        indexes = [
            models.Index(fields=["user", "-created_at"], name="notification_user_created_idx"),
        ]

    def __str__(self) -> str:
        return f"Notification({self.user_id}, {self.category}, read={self.read_at is not None})"


class DeviceToken(TimestampedModel):
    """An FCM registration token for one of a user's devices."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="device_tokens",
        db_index=True,
    )
    fcm_token = models.CharField(max_length=255, unique=True)
    platform = models.CharField(max_length=10, choices=PLATFORM_CHOICES)
    last_seen_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return f"DeviceToken({self.user_id}, {self.platform})"
