from __future__ import annotations

import logging
from datetime import date, timedelta

from celery import shared_task

log = logging.getLogger(__name__)


@shared_task  # type: ignore[untyped-decorator]
def recompute_yesterday_summaries() -> None:
    """Safety-net: recompute all DailyNutritionSummary rows for yesterday (UTC)."""
    from apps.accounts.models import User
    from apps.tracker.models import MealLog
    from apps.tracker.services.nutrition_service import recompute_daily_summary

    yesterday = date.today() - timedelta(days=1)
    user_ids = (
        MealLog.objects.filter(log_date=yesterday).values_list("user_id", flat=True).distinct()
    )
    recomputed = 0
    for user_id in user_ids:
        try:
            user = User.objects.get(pk=user_id)
            recompute_daily_summary(user, yesterday)
            recomputed += 1
        except Exception as exc:
            log.error(
                "event=task_recompute_summary_error user_id=%s error=%s",
                user_id,
                exc,
            )
    log.info(
        "event=recompute_yesterday_summaries_done date=%s count=%d",
        yesterday,
        recomputed,
    )
