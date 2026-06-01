from django.utils.decorators import method_decorator
from django_ratelimit.decorators import ratelimit
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import User
from apps.accounts.serializers import RegisterResponseSerializer, UserSerializer
from core.exceptions import RateLimitError
from core.responses import success_response


class RegisterView(APIView):
    permission_classes = [IsAuthenticated]

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

    def get(self, request: Request) -> Response:
        """Return the authenticated user's details."""
        user = request.user
        assert isinstance(user, User)
        serializer = UserSerializer(user, context={"request": request})
        return success_response(serializer.data, "User retrieved.")
