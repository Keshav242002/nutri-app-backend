"""Tests for core.audit — structured audit logging decorator."""

from unittest.mock import MagicMock, patch

import pytest

from core.audit import audit_log

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class _FakeUser:
    pk = 42


def _audited_ok(_user: _FakeUser, value: int) -> int:
    return value * 2


def _audited_raises(_user: _FakeUser) -> None:
    raise ValueError("boom")


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestAuditLog:
    def test_returns_value_unchanged(self) -> None:
        decorated = audit_log("test.action")(_audited_ok)
        result = decorated(_FakeUser(), 7)
        assert result == 14

    def test_reraises_exception(self) -> None:
        decorated = audit_log("test.action")(_audited_raises)
        with pytest.raises(ValueError, match="boom"):
            decorated(_FakeUser())

    def test_emits_structured_fields_on_success(self) -> None:
        mock_logger = MagicMock()
        with patch("core.audit._audit_logger", mock_logger):
            decorated = audit_log("profile.create")(_audited_ok)
            decorated(_FakeUser(), 3)
        mock_logger.info.assert_called_once()
        extra = mock_logger.info.call_args[1]["extra"]
        assert extra["action"] == "profile.create"
        assert extra["user_id"] == 42
        assert extra["status"] == "success"
        assert isinstance(extra["duration_ms"], int)

    def test_emits_failure_status_on_exception(self) -> None:
        mock_logger = MagicMock()
        with patch("core.audit._audit_logger", mock_logger):
            decorated = audit_log("profile.create")(_audited_raises)
            with pytest.raises(ValueError):
                decorated(_FakeUser())
        mock_logger.info.assert_called_once()
        extra = mock_logger.info.call_args[1]["extra"]
        assert extra["status"] == "failure"
        assert extra["user_id"] == 42

    def test_extracts_user_from_kwarg(self) -> None:
        def _fn(*, user: _FakeUser) -> str:  # noqa: ARG001
            return "ok"

        mock_logger = MagicMock()
        with patch("core.audit._audit_logger", mock_logger):
            decorated = audit_log("chat.message")(_fn)
            decorated(user=_FakeUser())
        extra = mock_logger.info.call_args[1]["extra"]
        assert extra["user_id"] == 42

    def test_caches_backend_is_not_locmemcache(self) -> None:
        """CACHES default backend must not be LocMemCache (broken across multiple workers)."""
        from django.conf import settings

        backend = settings.CACHES["default"]["BACKEND"]
        assert "LocMem" not in backend, (
            f"CACHES backend is {backend!r} — must be Redis so rate limits "
            "are shared across workers."
        )
