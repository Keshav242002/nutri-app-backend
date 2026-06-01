import logging
import time
from collections.abc import Callable
from functools import wraps
from typing import Any, TypeVar

F = TypeVar("F", bound=Callable[..., Any])

_audit_logger = logging.getLogger("nutriplan.audit")


def _extract_user_id(args: tuple[Any, ...], kwargs: dict[str, Any]) -> int | None:
    """Find user PK from function arguments: kwarg 'user' first, then args[0]."""
    user = kwargs.get("user")
    if user is None and args:
        user = args[0]
    if user is not None:
        pk = getattr(user, "pk", None)
        if isinstance(pk, int):
            return pk
    return None


def audit_log(action: str) -> Callable[[F], F]:
    """Emit a structured audit entry around a service call.

    Logs action, user_id, status (success/failure), and duration_ms.
    Always re-raises exceptions — never swallows them.
    """

    def decorator(func: F) -> F:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            user_id = _extract_user_id(args, kwargs)
            start = time.monotonic()
            try:
                result = func(*args, **kwargs)
                duration_ms = int((time.monotonic() - start) * 1000)
                _audit_logger.info(
                    action,
                    extra={
                        "event": action,
                        "action": action,
                        "user_id": user_id,
                        "status": "success",
                        "duration_ms": duration_ms,
                    },
                )
                return result
            except Exception:
                duration_ms = int((time.monotonic() - start) * 1000)
                _audit_logger.info(
                    action,
                    extra={
                        "event": action,
                        "action": action,
                        "user_id": user_id,
                        "status": "failure",
                        "duration_ms": duration_ms,
                    },
                )
                raise

        return wrapper  # type: ignore[return-value]

    return decorator
