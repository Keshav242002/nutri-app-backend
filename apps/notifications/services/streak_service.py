"""Logging-streak evaluation.

A day *qualifies* only when all three meal slots (breakfast, lunch, dinner) were logged
as eaten (`ate_planned` / `ate_substituted` / `ate_custom`). `skipped` and `planned` do
not count. The current streak is the run of consecutive qualifying days ending on a given
date. Crossing a milestone (3, 7, 30) dispatches a streak notification.
"""

from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import TYPE_CHECKING

from apps.notifications.models import CATEGORY_STREAK
from apps.notifications.services.notification_service import dispatch
from apps.tracker.models import EATING_STATUSES, MealLog

if TYPE_CHECKING:
    from apps.accounts.models import User

logger = logging.getLogger(__name__)

MILESTONES = frozenset({3, 7, 30})
_REQUIRED_SLOTS = {"breakfast", "lunch", "dinner"}
# Safety bound on the backward walk so a long history can't run unbounded.
_MAX_LOOKBACK_DAYS = 400


def _day_qualifies(user: User, day: date) -> bool:
    """True if all three slots for `day` were logged as eaten."""
    eaten_slots = set(
        MealLog.objects.filter(user=user, log_date=day, status__in=EATING_STATUSES).values_list(
            "slot", flat=True
        )
    )
    return _REQUIRED_SLOTS.issubset(eaten_slots)


def current_streak(user: User, day: date) -> int:
    """Count consecutive qualifying days ending on `day` (0 if `day` itself fails)."""
    streak = 0
    cursor = day
    for _ in range(_MAX_LOOKBACK_DAYS):
        if not _day_qualifies(user, cursor):
            break
        streak += 1
        cursor = cursor - timedelta(days=1)
    return streak


def evaluate_streak(user: User, day: date) -> int:
    """Compute the streak ending on `day` and dispatch a milestone notification if hit."""
    streak = current_streak(user, day)
    if streak in MILESTONES:
        dispatch(
            user,
            CATEGORY_STREAK,
            dedup_key=f"streak-{streak}:{user.pk}:{day.isoformat()}",
            context={"streak_days": streak},
        )
    return streak
