from __future__ import annotations

import logging
from datetime import date, timedelta

from django.utils.dateparse import parse_date
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import User
from apps.mealplans.models import MealPlan
from apps.mealplans.serializers import (
    MealPlanDayDetailSerializer,
    MealPlanSerializer,
    RegeneratePlanSerializer,
    RegenerateSlotSerializer,
)
from apps.mealplans.services.engine import NoSuitableRecipeError
from apps.mealplans.services.plan_service import (
    get_or_generate_plan,
    regenerate_plan,
    regenerate_slot,
)
from core.error_codes import NO_SUITABLE_RECIPE, VALIDATION_ERROR
from core.exceptions import AppValidationError
from core.responses import success_response

log = logging.getLogger(__name__)


def _parse_plan_date(raw: str) -> date:
    """Parse ISO date string; raises AppValidationError on bad format."""
    parsed = parse_date(raw)
    if parsed is None:
        raise AppValidationError(
            message=f"Invalid date format '{raw}'. Expected YYYY-MM-DD.",
            code=VALIDATION_ERROR,
        )
    return parsed


def _fetch_plan_with_related(pk: int) -> MealPlan:
    """Re-fetch MealPlan with all slot FK relations loaded."""
    return MealPlan.objects.select_related("breakfast", "lunch", "dinner").get(pk=pk)


class TodayMealPlanView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request: Request) -> Response:
        assert isinstance(request.user, User)
        try:
            plan = get_or_generate_plan(request.user, date.today())
        except NoSuitableRecipeError as exc:
            return Response(
                {
                    "status": "error",
                    "message": str(exc),
                    "error": {"code": NO_SUITABLE_RECIPE, "details": {}},
                },
                status=422,
            )
        serializer = MealPlanDayDetailSerializer(plan)
        return success_response(serializer.data, "Today's meal plan.")


class DayMealPlanView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request: Request, plan_date: str) -> Response:
        assert isinstance(request.user, User)
        parsed = _parse_plan_date(plan_date)
        try:
            plan = get_or_generate_plan(request.user, parsed)
        except NoSuitableRecipeError as exc:
            return Response(
                {
                    "status": "error",
                    "message": str(exc),
                    "error": {"code": NO_SUITABLE_RECIPE, "details": {}},
                },
                status=422,
            )
        serializer = MealPlanDayDetailSerializer(plan)
        return success_response(serializer.data, f"Meal plan for {parsed}.")


class WeekMealPlanView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request: Request) -> Response:
        assert isinstance(request.user, User)
        from_param = request.query_params.get("from")
        if from_param:
            from_date = _parse_plan_date(from_param)
        else:
            today = date.today()
            from_date = today - timedelta(days=today.weekday())  # Monday

        to_date = from_date + timedelta(days=6)

        plans = (
            MealPlan.objects.filter(
                user=request.user,
                plan_date__range=(from_date, to_date),
            )
            .select_related("breakfast", "lunch", "dinner")
            .order_by("plan_date")
        )
        serializer = MealPlanSerializer(plans, many=True)
        return success_response(serializer.data, "Meal plans for the week.")


class RegenerateSlotView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request: Request) -> Response:
        assert isinstance(request.user, User)
        serializer = RegenerateSlotSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        plan_date: date = serializer.validated_data["date"]
        slot: str = serializer.validated_data["slot"]

        try:
            plan = regenerate_slot(request.user, plan_date, slot)
        except NoSuitableRecipeError as exc:
            return Response(
                {
                    "status": "error",
                    "message": str(exc),
                    "error": {"code": NO_SUITABLE_RECIPE, "details": {}},
                },
                status=422,
            )

        # Re-fetch with all related objects so serializer doesn't trigger extra queries
        plan = _fetch_plan_with_related(plan.pk)
        out = MealPlanDayDetailSerializer(plan)
        return success_response(out.data, f"Slot '{slot}' regenerated.")


class RegeneratePlanView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request: Request) -> Response:
        assert isinstance(request.user, User)
        serializer = RegeneratePlanSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        plan_date: date = serializer.validated_data["date"]

        try:
            plan = regenerate_plan(request.user, plan_date)
        except NoSuitableRecipeError as exc:
            return Response(
                {
                    "status": "error",
                    "message": str(exc),
                    "error": {"code": NO_SUITABLE_RECIPE, "details": {}},
                },
                status=422,
            )

        plan = _fetch_plan_with_related(plan.pk)
        out = MealPlanDayDetailSerializer(plan)
        return success_response(out.data, "Meal plan regenerated.")
