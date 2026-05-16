from typing import Any

from rest_framework.authentication import BaseAuthentication
from rest_framework.request import Request


class PlaceholderAuthentication(BaseAuthentication):
    """No-op auth used in M0. Replaced by FirebaseAuthentication in M1."""

    def authenticate(self, request: Request) -> tuple[Any, Any] | None:
        return None
