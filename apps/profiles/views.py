from drf_spectacular.utils import OpenApiExample, extend_schema
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import User
from apps.profiles.serializers import DietaryProfileSerializer, ProfileUpdateSerializer
from apps.profiles.services.profiles import get_profile, update_profile, upsert_profile
from apps.profiles.services.questionnaire import QUESTIONNAIRE_V1
from core.responses import success_response
from core.schema import envelope_response, error_response


class OnboardingQuestionsView(APIView):
    """GET /api/v1/profiles/onboarding/questions — static questionnaire metadata."""

    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Get onboarding questionnaire",
        description="Returns the 6-step onboarding questionnaire metadata (choices, labels, defaults). No DB queries.",
        responses={200: {"type": "object", "description": "Questionnaire step definitions."}},
    )
    def get(self, _request: Request) -> Response:
        return success_response(QUESTIONNAIRE_V1, "Onboarding questionnaire retrieved.")


class OnboardingView(APIView):
    """
    POST /api/v1/profiles/onboarding

    Idempotent — creates or updates the authenticated user's DietaryProfile.
    Returns the full profile with computed macro targets.
    """

    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Create / update dietary profile",
        description=(
            "Idempotent. Creates or updates the user's DietaryProfile with all onboarding fields. "
            "Returns the profile with computed calorie/macro targets. "
            "`disclaimer_acknowledged` is write-only and not stored."
        ),
        request=DietaryProfileSerializer,
        responses={
            200: envelope_response(
                DietaryProfileSerializer, "Profile created or updated with computed targets."
            ),
            400: error_response("VALIDATION_ERROR", "Validation failed."),
            401: error_response("NOT_AUTHENTICATED", "No valid token."),
        },
        examples=[
            OpenApiExample(
                "Successful onboarding",
                value={
                    "status": "success",
                    "message": "Profile created successfully.",
                    "data": {"goal": "lose_weight"},
                },
                response_only=True,
                status_codes=["200"],
            )
        ],
    )
    def post(self, request: Request) -> Response:
        user = request.user
        assert isinstance(user, User)

        serializer = DietaryProfileSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        profile, created = upsert_profile(user, dict(serializer.validated_data))
        out = DietaryProfileSerializer(profile)
        message = "Profile created successfully." if created else "Profile updated successfully."
        return success_response(out.data, message)


class ProfileMeView(APIView):
    """
    GET  /api/v1/profiles/me  — retrieve profile or 404 PROFILE_NOT_FOUND
    PATCH /api/v1/profiles/me — partial update; recomputes targets
    """

    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Get my profile",
        description="Return the authenticated user's full dietary profile including computed macro targets.",
        responses={
            200: envelope_response(DietaryProfileSerializer, "Profile retrieved."),
            401: error_response("NOT_AUTHENTICATED", "No valid token."),
            404: error_response(
                "PROFILE_NOT_FOUND", "No profile exists yet. Complete onboarding first."
            ),
        },
    )
    def get(self, request: Request) -> Response:
        user = request.user
        assert isinstance(user, User)

        profile = get_profile(user)  # raises NotFoundError on miss
        serializer = DietaryProfileSerializer(profile)
        return success_response(serializer.data, "Profile retrieved.")

    @extend_schema(
        summary="Update my profile",
        description=(
            "Partial update — only fields present in the request body are changed. "
            "Re-applies all normalisation rules and recomputes macro targets on save. "
            "No disclaimer required for PATCH."
        ),
        request=ProfileUpdateSerializer,
        responses={
            200: envelope_response(
                DietaryProfileSerializer, "Profile updated with recomputed targets."
            ),
            400: error_response("VALIDATION_ERROR", "Validation failed."),
            401: error_response("NOT_AUTHENTICATED", "No valid token."),
            404: error_response("PROFILE_NOT_FOUND", "Profile not found."),
        },
    )
    def patch(self, request: Request) -> Response:
        user = request.user
        assert isinstance(user, User)

        serializer = ProfileUpdateSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)

        profile = update_profile(user, dict(serializer.validated_data))
        out = DietaryProfileSerializer(profile)
        return success_response(out.data, "Profile updated successfully.")
