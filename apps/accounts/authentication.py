import logging
from typing import Any

from firebase_admin import auth as firebase_auth
from firebase_admin import exceptions as firebase_exceptions
from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.request import Request

from apps.accounts.models import User
from apps.accounts.services.accounts import register_or_get_user
from core.error_codes import (
    EXTERNAL_SERVICE_ERROR,
    INVALID_AUTH_HEADER,
    INVALID_TOKEN,
    TOKEN_EXPIRED,
    TOKEN_REVOKED,
)

logger = logging.getLogger(__name__)


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
            logger.error(
                "auth_failed",
                extra={"event": "auth_failed", "error_code": TOKEN_EXPIRED},
            )
            raise AuthenticationFailed(
                {"code": TOKEN_EXPIRED, "message": "Firebase token has expired."}
            ) from exc
        except firebase_auth.RevokedIdTokenError as exc:
            logger.error(
                "auth_failed",
                extra={"event": "auth_failed", "error_code": TOKEN_REVOKED},
            )
            raise AuthenticationFailed(
                {"code": TOKEN_REVOKED, "message": "Firebase token has been revoked."}
            ) from exc
        except firebase_auth.InvalidIdTokenError as exc:
            logger.error(
                "auth_failed",
                extra={"event": "auth_failed", "error_code": INVALID_TOKEN},
            )
            raise AuthenticationFailed(
                {"code": INVALID_TOKEN, "message": "Firebase token is invalid."}
            ) from exc
        except firebase_exceptions.FirebaseError as exc:
            logger.error(
                "auth_failed",
                extra={"event": "auth_failed", "error_code": EXTERNAL_SERVICE_ERROR},
            )
            raise AuthenticationFailed(
                {"code": EXTERNAL_SERVICE_ERROR, "message": "Firebase service error."}
            ) from exc
        # Genuinely unexpected exceptions are NOT caught — they propagate up as 500.

        firebase_uid: str = str(decoded["uid"])
        user, created = register_or_get_user(
            firebase_uid=firebase_uid,
            email=str(decoded.get("email", "")),
            display_name=str(decoded.get("name", "")),
        )
        decoded["_created"] = created
        logger.info(
            "token_verified",
            extra={"event": "token_verified", "user_id": user.pk, "firebase_uid": firebase_uid},
        )
        return user, decoded
