import logging
from typing import Any

from django.http import Http404
from rest_framework import status
from rest_framework.exceptions import (
    AuthenticationFailed,
    NotAuthenticated,
)
from rest_framework.exceptions import (
    ValidationError as DRFValidationError,
)
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler

from core.error_codes import (  # noqa: F401  # re-exported for backwards compatibility
    CONFLICT,
    EXTERNAL_SERVICE_ERROR,
    INTERNAL_ERROR,
    INVALID_AUTH_HEADER,
    INVALID_FILTER_VALUE,
    INVALID_TOKEN,
    MEAL_PLAN_NOT_FOUND,
    NO_SUITABLE_RECIPE,
    NOT_AUTHENTICATED,
    NOT_FOUND,
    OPENAI_FAILURE,
    PROFILE_NOT_FOUND,
    RATE_LIMITED,
    REGENERATE_LIMIT,
    TOKEN_EXPIRED,
    TOKEN_REVOKED,
    USDA_FAILURE,
    VALIDATION_ERROR,
)

_logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Exception hierarchy
# ---------------------------------------------------------------------------


class AppException(Exception):  # noqa: N818
    """Base for all application-level exceptions."""

    status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR
    default_code: str = INTERNAL_ERROR
    default_message: str = "An unexpected error occurred."

    def __init__(
        self,
        message: str | None = None,
        code: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        self.message = message or self.default_message
        self.code = code or self.default_code
        self.details = details or {}
        super().__init__(self.message)


class AppValidationError(AppException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_code = VALIDATION_ERROR
    default_message = "Validation failed."


class NotFoundError(AppException):
    status_code = status.HTTP_404_NOT_FOUND
    default_code = NOT_FOUND
    default_message = "Resource not found."


class ConflictError(AppException):
    status_code = status.HTTP_409_CONFLICT
    default_code = CONFLICT
    default_message = "Resource already exists."


class RateLimitError(AppException):
    status_code = status.HTTP_429_TOO_MANY_REQUESTS
    default_code = RATE_LIMITED
    default_message = "Rate limit exceeded."


class ExternalServiceError(AppException):
    status_code = status.HTTP_502_BAD_GATEWAY
    default_code = INTERNAL_ERROR
    default_message = "External service error."


# ---------------------------------------------------------------------------
# DRF exception handler
# ---------------------------------------------------------------------------


def _error_envelope(
    code: str, message: str, details: dict[str, Any] | None = None
) -> dict[str, Any]:
    return {
        "status": "error",
        "message": message,
        "error": {"code": code, "details": details or {}},
    }


def app_exception_handler(exc: Exception, context: dict[str, Any]) -> Response | None:
    """Converts all exceptions to the canonical error envelope."""

    if isinstance(exc, AppException):
        return Response(
            _error_envelope(exc.code, exc.message, exc.details),
            status=exc.status_code,
        )

    if isinstance(exc, Http404):
        return Response(
            _error_envelope(NOT_FOUND, "Resource not found."),
            status=status.HTTP_404_NOT_FOUND,
        )

    if isinstance(exc, NotAuthenticated):
        return Response(
            _error_envelope(NOT_AUTHENTICATED, "Authentication credentials were not provided."),
            status=status.HTTP_401_UNAUTHORIZED,
        )

    if isinstance(exc, AuthenticationFailed):
        detail = getattr(exc, "detail", {})
        code = str(detail.get("code", INVALID_TOKEN)) if isinstance(detail, dict) else INVALID_TOKEN
        return Response(
            _error_envelope(code, str(exc.detail)),
            status=status.HTTP_401_UNAUTHORIZED,
        )

    if isinstance(exc, DRFValidationError):
        return Response(
            _error_envelope(VALIDATION_ERROR, "Validation failed.", {"fields": exc.detail}),
            status=status.HTTP_400_BAD_REQUEST,
        )

    # Fall back to DRF's default for anything else (e.g. MethodNotAllowed)
    response = drf_exception_handler(exc, context)
    if response is not None:
        data = response.data
        message = (
            str(data.get("detail", "An error occurred.")) if isinstance(data, dict) else str(data)
        )
        response.data = _error_envelope(INTERNAL_ERROR, message)
        return response

    # DRF returned None -> a genuinely unexpected exception (not an APIException
    # subclass), e.g. ZoneInfoNotFoundError, KeyError, etc. Without this branch
    # Django emits its default HTML 500 page, which breaks JSON-only clients
    # (their response decoder throws on the HTML body). Always return the
    # canonical JSON envelope instead. The full traceback is logged here so the
    # actual defect is still recoverable from the server logs; the client never
    # sees a stack trace.
    _logger.exception(
        "unhandled_exception",
        extra={"event": "unhandled_exception", "error_code": INTERNAL_ERROR},
    )
    return Response(
        _error_envelope(INTERNAL_ERROR, "An unexpected error occurred. Please try again."),
        status=status.HTTP_500_INTERNAL_SERVER_ERROR,
    )
