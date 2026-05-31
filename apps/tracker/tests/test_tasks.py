"""Tests for apps.tracker.tasks."""

from __future__ import annotations

from datetime import date
from unittest.mock import patch

import pytest
from freezegun import freeze_time

from apps.accounts.tests.factories import UserFactory
from apps.tracker.tasks import recompute_yesterday_summaries
from apps.tracker.tests.factories import MealLogFactory

# Patch at the source so the deferred `from ... import` inside the task gets the mock
_RECOMPUTE_PATH = "apps.tracker.services.nutrition_service.recompute_daily_summary"


@pytest.mark.django_db
class TestRecomputeYesterdaySummaries:
    @freeze_time("2026-05-31")
    def test_recomputes_for_users_with_logs(self) -> None:
        """Calls recompute_daily_summary for each user with MealLog rows for yesterday."""
        user = UserFactory()
        MealLogFactory(user=user, log_date=date(2026, 5, 30))

        with patch(_RECOMPUTE_PATH) as mock_recompute:
            recompute_yesterday_summaries()

        mock_recompute.assert_called_once()
        call_user, call_date = mock_recompute.call_args[0]
        assert call_user == user
        assert call_date == date(2026, 5, 30)

    @freeze_time("2026-05-31")
    def test_skips_users_without_logs_for_yesterday(self) -> None:
        """Does not call recompute for users whose logs are not for yesterday."""
        user = UserFactory()
        # Log for today, not yesterday
        MealLogFactory(user=user, log_date=date(2026, 5, 31))

        with patch(_RECOMPUTE_PATH) as mock_recompute:
            recompute_yesterday_summaries()

        mock_recompute.assert_not_called()
