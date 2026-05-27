from __future__ import annotations

import logging
from datetime import date, timedelta

from django.utils.dateparse import parse_date
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import User
from apps.mealplans.models import GroceryList, MealPlan
from apps.mealplans.serializers import (
    GroceryListSerializer,
    MealPlanDayDetailSerializer,
    MealPlanSerializer,
    RegeneratePlanSerializer,
    RegenerateSlotSerializer,
    WeeklyPlanGenerateSerializer,
)
from apps.mealplans.services.engine import NoSuitableRecipeError
from apps.mealplans.services.grocery_service import get_or_compute_grocery_list
from apps.mealplans.services.plan_service import (
    get_or_generate_plan,
    regenerate_plan,
    regenerate_slot,
)
from apps.mealplans.services.weekly_service import generate_weekly_plan
from core.error_codes import MEAL_PLAN_NOT_FOUND, NO_SUITABLE_RECIPE, VALIDATION_ERROR
from core.exceptions import AppValidationError, NotFoundError
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


def _resolve_week_monday(plan_date: date) -> date:
    """Return Monday of the ISO week containing plan_date."""
    return plan_date - timedelta(days=plan_date.weekday())


class WeeklyPlanGenerateView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request: Request) -> Response:
        assert isinstance(request.user, User)
        ser = WeeklyPlanGenerateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)

        ref_date: date | None = ser.validated_data.get("date")

        # Compute week range to derive days_existing before generating.
        today = ref_date or date.today()
        has_any = MealPlan.objects.filter(user=request.user).exists()
        if not has_any:
            start_date = today
            end_date = today + timedelta(days=(6 - today.weekday()))
        else:
            start_date = today - timedelta(days=today.weekday())
            end_date = start_date + timedelta(days=6)

        days_existing = MealPlan.objects.filter(
            user=request.user, plan_date__range=(start_date, end_date)
        ).count()

        try:
            plans = generate_weekly_plan(request.user, ref_date)
        except NoSuitableRecipeError as exc:
            return Response(
                {
                    "status": "error",
                    "message": str(exc),
                    "error": {"code": NO_SUITABLE_RECIPE, "details": {}},
                },
                status=422,
            )
        except NotFoundError as exc:
            return Response(
                {
                    "status": "error",
                    "message": exc.message,
                    "error": {"code": exc.code, "details": {}},
                },
                status=404,
            )

        days_generated = len(plans) - days_existing
        week_start = plans[0].plan_date if plans else start_date
        week_end = plans[-1].plan_date if plans else end_date
        out = MealPlanSerializer(plans, many=True)
        return success_response(
            {
                "week_start": str(week_start),
                "week_end": str(week_end),
                "days_generated": days_generated,
                "days_existing": days_existing,
                "plans": out.data,
            },
            f"Weekly meal plan generated (Mon {week_start} to Sun {week_end}).",
        )


class GroceryListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request: Request, plan_date: str) -> Response:
        assert isinstance(request.user, User)
        parsed = _parse_plan_date(plan_date)
        week_monday = _resolve_week_monday(parsed)
        week_end = week_monday + timedelta(days=6)

        if not MealPlan.objects.filter(
            user=request.user, plan_date__range=(week_monday, week_end)
        ).exists():
            return Response(
                {
                    "status": "error",
                    "message": f"No meal plans found for week of {week_monday}.",
                    "error": {"code": MEAL_PLAN_NOT_FOUND, "details": {}},
                },
                status=404,
            )

        try:
            gl = get_or_compute_grocery_list(request.user, week_monday)
        except NotFoundError as exc:
            return Response(
                {
                    "status": "error",
                    "message": exc.message,
                    "error": {"code": exc.code, "details": {}},
                },
                status=404,
            )

        out = GroceryListSerializer(gl)
        return success_response(out.data, f"Grocery list for week of {week_monday}.")


class GroceryListRegenerateView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request: Request, plan_date: str) -> Response:
        assert isinstance(request.user, User)
        parsed = _parse_plan_date(plan_date)
        week_monday = _resolve_week_monday(parsed)
        week_end = week_monday + timedelta(days=6)

        if not MealPlan.objects.filter(
            user=request.user, plan_date__range=(week_monday, week_end)
        ).exists():
            return Response(
                {
                    "status": "error",
                    "message": f"No meal plans found for week of {week_monday}.",
                    "error": {"code": MEAL_PLAN_NOT_FOUND, "details": {}},
                },
                status=404,
            )

        GroceryList.objects.filter(user=request.user, week_start_date=week_monday).delete()

        try:
            gl = get_or_compute_grocery_list(request.user, week_monday)
        except NotFoundError as exc:
            return Response(
                {
                    "status": "error",
                    "message": exc.message,
                    "error": {"code": exc.code, "details": {}},
                },
                status=404,
            )

        out = GroceryListSerializer(gl)
        return success_response(out.data, f"Grocery list recomputed for week of {week_monday}.")
