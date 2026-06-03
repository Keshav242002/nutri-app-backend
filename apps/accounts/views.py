from django.utils.decorators import method_decorator
from django_ratelimit.decorators import ratelimit
from drf_spectacular.utils import extend_schema
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import User
from apps.accounts.serializers import (
    RegisterResponseSerializer,
    UpdateDisplayNameSerializer,
    UserSerializer,
)
from apps.accounts.services.accounts import update_display_name
from core.exceptions import RateLimitError
from core.responses import success_response
from core.schema import envelope_response, error_response


class RegisterView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Register / upsert user",
        description=(
            "Idempotent. Verifies the Firebase Bearer token and upserts the Django User record. "
            "Returns `created=true` on first registration."
        ),
        request=None,
        responses={
            200: envelope_response(
                RegisterResponseSerializer, "User registered or already exists."
            ),
            401: error_response("INVALID_TOKEN", "Invalid or missing Firebase token."),
            429: error_response("RATE_LIMITED", "Too many registration attempts (10/min per IP)."),
        },
    )
    @method_decorator(ratelimit(key="ip", rate="10/m", method="POST", block=False))
    def post(self, request: Request) -> Response:
        """Idempotent registration: upserts the Django User from the verified Firebase token."""
        if getattr(request, "limited", False):
            raise RateLimitError(message="Too many registration attempts. Please try again later.")
        user = request.user
        assert isinstance(user, User)
        decoded: dict[str, object] = request.auth  # type: ignore[assignment]
        created: bool = bool(decoded.get("_created", False))
        serializer = RegisterResponseSerializer(
            user, context={"created": created, "request": request}
        )
        message = "User registered successfully." if created else "User already registered."
        return success_response(serializer.data, message)


class MeView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Get current user",
        description="Return the authenticated user's profile stub (email, display_name, has_profile).",
        responses={
            200: envelope_response(UserSerializer, "User retrieved."),
            401: error_response("NOT_AUTHENTICATED", "No valid token."),
        },
    )
    def get(self, request: Request) -> Response:
        """Return the authenticated user's details."""
        user = request.user
        assert isinstance(user, User)
        serializer = UserSerializer(user, context={"request": request})
        return success_response(serializer.data, "User retrieved.")

    @extend_schema(
        summary="Update display name",
        description=(
            "Set the user's display_name. Required for email/OTP sign-ups where Firebase "
            "does not supply a name claim. Idempotent — safe to call on returning users "
            "(no-op if name is unchanged)."
        ),
        request=UpdateDisplayNameSerializer,
        responses={
            200: envelope_response(UserSerializer, "Display name updated."),
            400: error_response("VALIDATION_ERROR", "display_name is blank or too long."),
            401: error_response("NOT_AUTHENTICATED", "No valid token."),
        },
    )
    def patch(self, request: Request) -> Response:
        """Update display_name for the authenticated user."""
        user = request.user
        assert isinstance(user, User)
        serializer = UpdateDisplayNameSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = update_display_name(user, str(serializer.validated_data["display_name"]))
        return success_response(
            UserSerializer(user, context={"request": request}).data, "Display name updated."
        )
