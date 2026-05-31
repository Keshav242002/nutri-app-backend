from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from celery import shared_task
from django.db import OperationalError

from apps.accounts.models import User
from apps.mealplans.services.plan_service import get_or_generate_plan
from apps.profiles.models import DietaryProfile

log = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)  # type: ignore[untyped-decorator]
def generate_plan_for_user(self: Any, user_id: int, plan_date_iso: str) -> None:
    """Generate (or return existing) meal plan for one user on the given date."""
    try:
        user = User.objects.get(pk=user_id)
        plan_date = date.fromisoformat(plan_date_iso)
        get_or_generate_plan(user, plan_date)
        log.info(
            "event=task_generate_plan_success user_id=%s plan_date=%s",
            user_id,
            plan_date_iso,
        )
    except User.DoesNotExist:
        log.error("event=task_generate_plan_user_not_found user_id=%s", user_id)
    except OperationalError as exc:
        log.warning(
            "event=task_generate_plan_transient_error user_id=%s error=%s",
            user_id,
            exc,
        )
        raise self.retry(exc=exc) from exc
    except Exception as exc:
        log.error("event=task_generate_plan_failed user_id=%s error=%s", user_id, exc)


@shared_task  # type: ignore[untyped-decorator]
def generate_plans_for_all_users(target: str = "today") -> None:
    """Dispatch generate_plan_for_user for active users whose local hour is 4."""
    profiles = DietaryProfile.objects.select_related("user").filter(user__is_active=True)
    dispatched = 0
    for profile in profiles:
        try:
            tz = ZoneInfo(profile.timezone)
            local_now = datetime.now(tz=tz)
            if local_now.hour != 4:
                continue
            local_date = local_now.date()
            if target == "tomorrow":
                local_date = local_date + timedelta(days=1)
            generate_plan_for_user.delay(profile.user_id, local_date.isoformat())
            dispatched += 1
        except Exception as exc:
            log.error(
                "event=task_dispatch_plan_error user_id=%s error=%s",
                profile.user_id,
                exc,
            )
    log.info("event=generate_plans_dispatched target=%s count=%d", target, dispatched)
