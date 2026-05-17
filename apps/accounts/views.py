from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import User
from apps.accounts.serializers import RegisterResponseSerializer, UserSerializer


class RegisterView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request: Request) -> Response:
        """Idempotent registration: upserts the Django User from the verified Firebase token."""
        user = request.user
        assert isinstance(user, User)
        decoded: dict[str, object] = request.auth  # type: ignore[assignment]
        created: bool = bool(decoded.get("_created", False))
        serializer = RegisterResponseSerializer(
            user, context={"created": created, "request": request}
        )
        return Response(serializer.data)


class MeView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request: Request) -> Response:
        """Return the authenticated user's details."""
        user = request.user
        assert isinstance(user, User)
        serializer = UserSerializer(user, context={"request": request})
        return Response(serializer.data)
