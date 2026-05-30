from __future__ import annotations

import logging
from datetime import date

from django.utils.dateparse import parse_date
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import User
from apps.profiles.services.profiles import get_profile
from apps.tracker.models import DailyNutritionSummary, MealLog
from apps.tracker.serializers import (
    DailyNutritionSerializer,
    MealLogResponseSerializer,
    MealLogSerializer,
    WeeklyNutritionSerializer,
)
from apps.tracker.services.tracker_service import upsert_meal_log
from core.error_codes import VALIDATION_ERROR
from core.exceptions import AppValidationError
from core.responses import success_response

log = logging.getLogger(__name__)

_MAX_RANGE_DAYS = 90


def _parse_date_param(raw: str | None, param_name: str) -> date:
    """Parse a required ISO date query param; raises AppValidationError on bad format or missing."""
    if not raw:
        raise AppValidationError(
            message=f"Query parameter '{param_name}' is required (format: YYYY-MM-DD).",
            code=VALIDATION_ERROR,
        )
    parsed = parse_date(raw)
    if parsed is None:
        raise AppValidationError(
            message=f"Invalid date format for '{param_name}'. Expected YYYY-MM-DD.",
            code=VALIDATION_ERROR,
        )
    return parsed


class MealLogView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request: Request) -> Response:
        assert isinstance(request.user, User)
        ser = MealLogSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        vd = ser.validated_data

        meal_log = upsert_meal_log(
            user=request.user,
            log_date=vd["log_date"],
            slot=vd["slot"],
            status=vd["status"],
            planned_recipe_id=vd.get("planned_recipe_id"),
            actual_recipe_id=vd.get("actual_recipe_id"),
            servings_eaten=vd.get("servings_eaten"),
            custom_description=vd.get("custom_description"),
            custom_calories=vd.get("custom_calories"),
            custom_protein_g=vd.get("custom_protein_g"),
            custom_carbs_g=vd.get("custom_carbs_g"),
            custom_fat_g=vd.get("custom_fat_g"),
            notes=vd.get("notes", ""),
        )

        # Re-fetch with related for response
        meal_log = MealLog.objects.select_related("planned_recipe", "actual_recipe").get(
            pk=meal_log.pk
        )
        out = MealLogResponseSerializer(meal_log)
        return success_response(out.data, "Meal logged successfully.")


class TrackerListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request: Request) -> Response:
        assert isinstance(request.user, User)
        log_date = _parse_date_param(request.query_params.get("date"), "date")

        logs = (
            MealLog.objects.filter(user=request.user, log_date=log_date)
            .select_related("planned_recipe", "actual_recipe")
            .order_by("slot")
        )
        out = MealLogResponseSerializer(logs, many=True)
        return success_response(out.data, f"Meal logs for {log_date}.")


class TrackerRangeView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request: Request) -> Response:
        assert isinstance(request.user, User)
        from_date = _parse_date_param(request.query_params.get("from"), "from")
        to_date = _parse_date_param(request.query_params.get("to"), "to")

        if to_date < from_date:
            raise AppValidationError(
                message="'to' must be on or after 'from'.",
                code=VALIDATION_ERROR,
            )
        if (to_date - from_date).days > _MAX_RANGE_DAYS:
            raise AppValidationError(
                message=f"Date range may not exceed {_MAX_RANGE_DAYS} days.",
                code=VALIDATION_ERROR,
            )

        logs = (
            MealLog.objects.filter(user=request.user, log_date__range=(from_date, to_date))
            .select_related("planned_recipe", "actual_recipe")
            .order_by("log_date", "slot")
        )
        out = MealLogResponseSerializer(logs, many=True)
        return success_response(out.data, f"Meal logs from {from_date} to {to_date}.")


class DailyNutritionView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request: Request) -> Response:
        assert isinstance(request.user, User)
        summary_date = _parse_date_param(request.query_params.get("date"), "date")

        # Profile for targets (raises NotFoundError → 404 via exception handler)
        profile = get_profile(request.user)

        summary, _ = DailyNutritionSummary.objects.get_or_create(
            user=request.user,
            summary_date=summary_date,
        )
        out = DailyNutritionSerializer(summary, context={"profile": profile})
        return success_response(out.data, f"Daily nutrition for {summary_date}.")


class WeeklyNutritionView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request: Request) -> Response:
        assert isinstance(request.user, User)
        from_date = _parse_date_param(request.query_params.get("from"), "from")
        to_date = _parse_date_param(request.query_params.get("to"), "to")

        if to_date < from_date:
            raise AppValidationError(
                message="'to' must be on or after 'from'.",
                code=VALIDATION_ERROR,
            )

        profile = get_profile(request.user)

        summaries = list(
            DailyNutritionSummary.objects.filter(
                user=request.user, summary_date__range=(from_date, to_date)
            ).order_by("summary_date")
        )

        out = WeeklyNutritionSerializer(summaries, profile=profile)
        return success_response(out.data, f"Weekly nutrition from {from_date} to {to_date}.")
