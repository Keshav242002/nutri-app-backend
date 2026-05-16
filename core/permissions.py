from rest_framework.permissions import BasePermission
from rest_framework.request import Request
from rest_framework.views import APIView


class IsFirebaseAuthenticated(BasePermission):
    """Requires a valid Firebase-authenticated user. Implemented fully in M1."""

    def has_permission(self, request: Request, view: APIView) -> bool:
        return bool(request.user and request.user.is_authenticated)
