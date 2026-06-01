"""
OpenAPI schema helpers for drf-spectacular.

Our success response envelope is {status, message, data: <serializer>}.
drf-spectacular introspects raw serializers and does NOT see the envelope wrapper applied by
success_response(). These helpers produce explicit OpenApiResponse objects that document the
true envelope shape.

Serializer classes created by inline_serializer() are cached by name to prevent duplicate-name
warnings when the same envelope is referenced by multiple endpoints.
"""

from typing import Any

from drf_spectacular.extensions import OpenApiAuthenticationExtension
from drf_spectacular.openapi import AutoSchema
from drf_spectacular.utils import OpenApiResponse, inline_serializer
from rest_framework import serializers

# ---------------------------------------------------------------------------
# Firebase auth extension — tells drf-spectacular how to describe Firebase tokens
# ---------------------------------------------------------------------------


class FirebaseAuthenticationScheme(OpenApiAuthenticationExtension):  # type: ignore[no-untyped-call]
    target_class = "apps.accounts.authentication.FirebaseAuthentication"
    name = "FirebaseBearerAuth"

    def get_security_definition(self, _auto_schema: AutoSchema) -> dict[str, Any]:
        return {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT",
            "description": "Firebase ID token from the Firebase Auth SDK.",
        }


# ---------------------------------------------------------------------------
# Singleton inline serializer cache
# Calling inline_serializer() with the same name more than once creates distinct classes
# with identical __name__, causing drf-spectacular duplicate-name warnings.
# Caching by name ensures one class per envelope type across all endpoints.
# ---------------------------------------------------------------------------

_inline_cache: dict[str, type[serializers.Serializer[Any]]] = {}


def _cached_inline(name: str, fields: dict[str, Any]) -> type[serializers.Serializer[Any]]:
    """Return a cached inline serializer class; create on first call."""
    if name not in _inline_cache:
        _inline_cache[name] = type(inline_serializer(name=name, fields=fields))
    return _inline_cache[name]


# ---------------------------------------------------------------------------
# Reusable error envelope
# ---------------------------------------------------------------------------


class ErrorEnvelopeSerializer(serializers.Serializer[None]):
    """Canonical error response: {status, message, error: {code, details}}."""

    status = serializers.CharField(default="error")
    message = serializers.CharField(help_text="Human-readable error description.")
    error = inline_serializer(
        name="ErrorDetail",
        fields={
            "code": serializers.CharField(help_text="Machine-readable error code."),
            "details": serializers.DictField(required=False),
        },
    )


def error_response(code: str, description: str = "") -> OpenApiResponse:
    """Document a specific error code response using the shared error envelope."""
    return OpenApiResponse(
        response=ErrorEnvelopeSerializer,
        description=f"{description} (code: `{code}`)" if description else code,
    )


# ---------------------------------------------------------------------------
# Success envelope helpers
# ---------------------------------------------------------------------------


def envelope_response(
    serializer_class: type[serializers.BaseSerializer[Any]],
    description: str = "",
) -> OpenApiResponse:
    """Wrap a serializer class in the {status, message, data} success envelope."""
    name = f"{serializer_class.__name__}Envelope"
    envelope_class = _cached_inline(
        name,
        {
            "status": serializers.CharField(default="success"),
            "message": serializers.CharField(),
            "data": serializer_class(),
        },
    )
    return OpenApiResponse(response=envelope_class, description=description)


def envelope_list_response(
    serializer_class: type[serializers.BaseSerializer[Any]],
    description: str = "",
) -> OpenApiResponse:
    """Wrap a cursor-paginated list serializer in the {status, message, data} envelope."""
    page_name = f"{serializer_class.__name__}Page"
    page_class = _cached_inline(
        page_name,
        {
            "next": serializers.CharField(allow_null=True),
            "previous": serializers.CharField(allow_null=True),
            "results": serializer_class(many=True),
        },
    )
    name = f"{serializer_class.__name__}ListEnvelope"
    envelope_class = _cached_inline(
        name,
        {
            "status": serializers.CharField(default="success"),
            "message": serializers.CharField(),
            "data": page_class(),
        },
    )
    return OpenApiResponse(response=envelope_class, description=description)


__all__ = [
    "AutoSchema",
    "ErrorEnvelopeSerializer",
    "FirebaseAuthenticationScheme",
    "envelope_response",
    "envelope_list_response",
    "error_response",
]
