from __future__ import annotations

from typing import Any

from rest_framework import status as http_status
from rest_framework.response import Response


def success_response(
    data: Any,
    message: str,
    status_code: int = http_status.HTTP_200_OK,
) -> Response:
    """Wrap a successful DRF response in the standard success envelope."""
    return Response(
        {"status": "success", "message": message, "data": data},
        status=status_code,
    )
