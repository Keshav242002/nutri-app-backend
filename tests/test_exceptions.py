from rest_framework import status
from rest_framework.exceptions import NotAuthenticated
from rest_framework.exceptions import ValidationError as DRFValidationError

from core.exceptions import (
    AppValidationError,
    ConflictError,
    ExternalServiceError,
    NotFoundError,
    RateLimitError,
    app_exception_handler,
)


def _ctx() -> dict:  # type: ignore[type-arg]
    return {}


def test_app_exception_handler_formats_envelope() -> None:
    exc = AppValidationError(message="Bad input", details={"field": "name"})
    response = app_exception_handler(exc, _ctx())
    assert response is not None
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.data["error"]["code"] == "VALIDATION_ERROR"
    assert response.data["message"] == "Bad input"
    assert response.data["error"]["details"] == {"field": "name"}


def test_not_found_error_returns_404() -> None:
    exc = NotFoundError()
    response = app_exception_handler(exc, _ctx())
    assert response is not None
    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert response.data["error"]["code"] == "NOT_FOUND"


def test_conflict_error_returns_409() -> None:
    exc = ConflictError()
    response = app_exception_handler(exc, _ctx())
    assert response is not None
    assert response.status_code == status.HTTP_409_CONFLICT


def test_rate_limit_error_returns_429() -> None:
    exc = RateLimitError()
    response = app_exception_handler(exc, _ctx())
    assert response is not None
    assert response.status_code == status.HTTP_429_TOO_MANY_REQUESTS


def test_external_service_error_returns_502() -> None:
    exc = ExternalServiceError(code="OPENAI_FAILURE", message="OpenAI timed out")
    response = app_exception_handler(exc, _ctx())
    assert response is not None
    assert response.status_code == status.HTTP_502_BAD_GATEWAY
    assert response.data["error"]["code"] == "OPENAI_FAILURE"


def test_drf_not_authenticated_returns_401() -> None:
    exc = NotAuthenticated()
    response = app_exception_handler(exc, _ctx())
    assert response is not None
    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert response.data["error"]["code"] == "NOT_AUTHENTICATED"


def test_drf_validation_error_returns_400_with_fields() -> None:
    exc = DRFValidationError(detail={"email": ["Enter a valid email address."]})
    response = app_exception_handler(exc, _ctx())
    assert response is not None
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.data["error"]["code"] == "VALIDATION_ERROR"
    assert "fields" in response.data["error"]["details"]
