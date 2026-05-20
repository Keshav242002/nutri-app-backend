from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import User
from apps.profiles.serializers import DietaryProfileSerializer, ProfileUpdateSerializer
from apps.profiles.services.profiles import get_profile, update_profile, upsert_profile
from apps.profiles.services.questionnaire import QUESTIONNAIRE_V1
from core.responses import success_response


class OnboardingQuestionsView(APIView):
    """GET /api/v1/profiles/onboarding/questions — static questionnaire metadata."""

    permission_classes = [IsAuthenticated]

    def get(self, _request: Request) -> Response:
        return success_response(QUESTIONNAIRE_V1, "Onboarding questionnaire retrieved.")


class OnboardingView(APIView):
    """
    POST /api/v1/profiles/onboarding

    Idempotent — creates or updates the authenticated user's DietaryProfile.
    Returns the full profile with computed macro targets.
    """

    permission_classes = [IsAuthenticated]

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

    def get(self, request: Request) -> Response:
        user = request.user
        assert isinstance(user, User)

        profile = get_profile(user)  # raises NotFoundError on miss
        serializer = DietaryProfileSerializer(profile)
        return success_response(serializer.data, "Profile retrieved.")

    def patch(self, request: Request) -> Response:
        user = request.user
        assert isinstance(user, User)

        serializer = ProfileUpdateSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)

        profile = update_profile(user, dict(serializer.validated_data))
        out = DietaryProfileSerializer(profile)
        return success_response(out.data, "Profile updated successfully.")
