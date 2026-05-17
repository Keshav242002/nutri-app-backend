from typing import Any

from firebase_admin import auth as firebase_auth
from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.request import Request

from apps.accounts.models import User
from apps.accounts.services.accounts import register_or_get_user
from core.error_codes import INVALID_AUTH_HEADER, INVALID_TOKEN, TOKEN_EXPIRED


class FirebaseAuthentication(BaseAuthentication):
    """Verifies Firebase ID tokens from the Authorization: Bearer header."""

    def authenticate(self, request: Request) -> tuple[User, dict[str, Any]] | None:
        auth_header = request.headers.get("Authorization", "")
        if not auth_header:
            return None

        parts = auth_header.split()
        if len(parts) != 2 or parts[0].lower() != "bearer":
            raise AuthenticationFailed(
                {"code": INVALID_AUTH_HEADER, "message": "Malformed Authorization header."}
            )

        token = parts[1]
        try:
            decoded = firebase_auth.verify_id_token(token)
        except firebase_auth.ExpiredIdTokenError as exc:
            raise AuthenticationFailed(
                {"code": TOKEN_EXPIRED, "message": "Firebase token has expired."}
            ) from exc
        except Exception as exc:
            raise AuthenticationFailed(
                {"code": INVALID_TOKEN, "message": "Firebase token is invalid."}
            ) from exc

        user, created = register_or_get_user(
            firebase_uid=decoded["uid"],
            email=decoded.get("email", ""),
            display_name=decoded.get("name", ""),
        )
        decoded["_created"] = created
        return user, decoded
