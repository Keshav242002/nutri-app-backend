"""Tests for apps.mealplans.tasks."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from django.db import OperationalError
from freezegun import freeze_time

from apps.accounts.tests.factories import UserFactory
from apps.mealplans.tasks import generate_plan_for_user, generate_plans_for_all_users
from apps.profiles.tests.factories import DietaryProfileFactory


@pytest.mark.django_db
class TestGeneratePlanForUser:
    def test_creates_plan(self) -> None:
        """Task calls get_or_generate_plan with the correct user and date."""
        user = UserFactory()
        DietaryProfileFactory(user=user)

        with patch("apps.mealplans.tasks.get_or_generate_plan") as mock_gen:
            generate_plan_for_user(user.pk, "2026-05-31")

        mock_gen.assert_called_once()
        args = mock_gen.call_args[0]
        assert args[0] == user
        assert str(args[1]) == "2026-05-31"

    def test_idempotent(self) -> None:
        """Calling the task twice invokes the service twice (idempotency is in the service)."""
        user = UserFactory()
        DietaryProfileFactory(user=user)

        with patch("apps.mealplans.tasks.get_or_generate_plan") as mock_gen:
            generate_plan_for_user(user.pk, "2026-05-31")
            generate_plan_for_user(user.pk, "2026-05-31")

        assert mock_gen.call_count == 2

    def test_retries_on_transient_error(self) -> None:
        """Task calls self.retry with the OperationalError on a transient DB failure."""
        user = UserFactory()
        transient = OperationalError("transient db error")

        with patch("apps.mealplans.tasks.get_or_generate_plan", side_effect=transient):
            # patch.object replaces task.retry; return_value=transient means
            # `raise self.retry(exc=exc)` raises the OperationalError
            with patch.object(
                generate_plan_for_user, "retry", return_value=transient
            ) as mock_retry:
                with pytest.raises(OperationalError):
                    generate_plan_for_user(user.pk, "2026-05-31")

        mock_retry.assert_called_once_with(exc=transient)

    def test_silently_handles_missing_user(self) -> None:
        """Task does not raise when the given user_id does not exist."""
        with patch("apps.mealplans.tasks.get_or_generate_plan") as mock_gen:
            generate_plan_for_user(999999, "2026-05-31")

        mock_gen.assert_not_called()


@pytest.mark.django_db
class TestGeneratePlansForAllUsers:
    def test_skips_users_outside_4am_window(self) -> None:
        """Users whose local time is not 4 AM are not dispatched."""
        user = UserFactory()
        DietaryProfileFactory(user=user, timezone="UTC")

        with freeze_time("2026-05-31 10:00:00"):
            with patch("apps.mealplans.tasks.generate_plan_for_user") as mock_task:
                generate_plans_for_all_users("today")

        mock_task.delay.assert_not_called()

    def test_dispatches_for_users_at_4am(self) -> None:
        """Users whose local time is within the 4 AM hour get a plan dispatch."""
        user = UserFactory()
        DietaryProfileFactory(user=user, timezone="UTC")

        with freeze_time("2026-05-31 04:30:00"):
            with patch("apps.mealplans.tasks.generate_plan_for_user") as mock_task:
                generate_plans_for_all_users("today")

        mock_task.delay.assert_called_once_with(user.pk, "2026-05-31")

    def test_target_today_uses_local_date(self) -> None:
        """target='today' dispatches for the current local date."""
        user = UserFactory()
        DietaryProfileFactory(user=user, timezone="UTC")

        with freeze_time("2026-05-31 04:00:00"):
            with patch("apps.mealplans.tasks.generate_plan_for_user") as mock_task:
                generate_plans_for_all_users("today")

        mock_task.delay.assert_called_once_with(user.pk, "2026-05-31")

    def test_target_tomorrow_uses_next_local_date(self) -> None:
        """target='tomorrow' dispatches for local_date + 1 day."""
        user = UserFactory()
        DietaryProfileFactory(user=user, timezone="UTC")

        with freeze_time("2026-05-31 04:00:00"):
            with patch("apps.mealplans.tasks.generate_plan_for_user") as mock_task:
                generate_plans_for_all_users("tomorrow")

        mock_task.delay.assert_called_once_with(user.pk, "2026-06-01")
