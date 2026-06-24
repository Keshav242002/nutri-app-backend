"""View / endpoint tests for apps/notifications."""

from __future__ import annotations

from typing import Any
from unittest.mock import patch

import pytest
from django.test import Client

from apps.accounts.models import User
from apps.notifications.models import DeviceToken, Notification

from .factories import NotificationFactory

pytestmark = pytest.mark.django_db

REGISTER_URL = "/api/v1/auth/register"
LIST_URL = "/api/v1/notifications/"
UNREAD_COUNT_URL = "/api/v1/notifications/unread-count/"
MARK_ALL_URL = "/api/v1/notifications/mark-all-read/"
DEVICES_URL = "/api/v1/notifications/devices/"

FAKE_TOKEN: dict[str, Any] = {
    "uid": "notif-test-uid",
    "email": "notiftest@example.com",
    "name": "Notif Tester",
}


def _header() -> dict[str, str]:
    return {"HTTP_AUTHORIZATION": "Bearer fake-notif-token"}


@pytest.fixture()
def auth_client(client: Client) -> tuple[Client, User]:
    client.defaults.update(_header())
    with patch("firebase_admin.auth.verify_id_token", return_value=FAKE_TOKEN):
        client.post(REGISTER_URL)
    user = User.objects.get(firebase_uid=FAKE_TOKEN["uid"])
    return client, user


def _get(client: Client, url: str) -> Any:
    with patch("firebase_admin.auth.verify_id_token", return_value=FAKE_TOKEN):
        return client.get(url)


def _post(client: Client, url: str, data: dict[str, Any] | None = None) -> Any:
    with patch("firebase_admin.auth.verify_id_token", return_value=FAKE_TOKEN):
        return client.post(url, data=data or {}, content_type="application/json")


def _delete(client: Client, url: str) -> Any:
    with patch("firebase_admin.auth.verify_id_token", return_value=FAKE_TOKEN):
        return client.delete(url)


# ---------------------------------------------------------------------------
# List + unread filter
# ---------------------------------------------------------------------------


def test_list_returns_paginated_envelope(auth_client: tuple[Client, User]) -> None:
    client, user = auth_client
    NotificationFactory.create_batch(3, user=user)

    r = _get(client, LIST_URL)
    assert r.status_code == 200
    body = r.json()
    assert "results" in body
    assert len(body["results"]) == 3


def test_list_unread_filter(auth_client: tuple[Client, User]) -> None:
    client, user = auth_client
    NotificationFactory(user=user)
    read = NotificationFactory(user=user)
    Notification.objects.filter(pk=read.pk).update(read_at="2026-06-20T00:00:00Z")

    r = _get(client, LIST_URL + "?unread=true")
    assert r.status_code == 200
    assert len(r.json()["results"]) == 1


def test_list_scoped_to_request_user(auth_client: tuple[Client, User]) -> None:
    client, user = auth_client
    NotificationFactory(user=user)
    NotificationFactory()  # different user

    r = _get(client, LIST_URL)
    assert len(r.json()["results"]) == 1


# ---------------------------------------------------------------------------
# Unread count + mark read
# ---------------------------------------------------------------------------


def test_unread_count(auth_client: tuple[Client, User]) -> None:
    client, user = auth_client
    NotificationFactory.create_batch(2, user=user)
    r = _get(client, UNREAD_COUNT_URL)
    assert r.status_code == 200
    assert r.json()["data"]["unread_count"] == 2


def test_mark_read(auth_client: tuple[Client, User]) -> None:
    client, user = auth_client
    n = NotificationFactory(user=user)
    r = _post(client, f"{LIST_URL}{n.pk}/read/")
    assert r.status_code == 200
    assert r.json()["data"]["read_at"] is not None
    n.refresh_from_db()
    assert n.read_at is not None


def test_mark_read_other_users_notification_404(auth_client: tuple[Client, User]) -> None:
    client, _ = auth_client
    other = NotificationFactory()  # belongs to another user
    r = _post(client, f"{LIST_URL}{other.pk}/read/")
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "NOT_FOUND"


def test_mark_all_read(auth_client: tuple[Client, User]) -> None:
    client, user = auth_client
    NotificationFactory.create_batch(3, user=user)
    r = _post(client, MARK_ALL_URL)
    assert r.status_code == 200
    assert r.json()["data"]["updated"] == 3
    assert Notification.objects.filter(user=user, read_at__isnull=True).count() == 0


# ---------------------------------------------------------------------------
# Device register / unregister
# ---------------------------------------------------------------------------


def test_register_device(auth_client: tuple[Client, User]) -> None:
    client, user = auth_client
    r = _post(client, DEVICES_URL, {"fcm_token": "abc123", "platform": "android"})
    assert r.status_code == 201
    assert DeviceToken.objects.filter(user=user, fcm_token="abc123").exists()


def test_register_device_invalid_platform_400(auth_client: tuple[Client, User]) -> None:
    client, _ = auth_client
    r = _post(client, DEVICES_URL, {"fcm_token": "abc123", "platform": "blackberry"})
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "VALIDATION_ERROR"


def test_unregister_device(auth_client: tuple[Client, User]) -> None:
    client, user = auth_client
    _post(client, DEVICES_URL, {"fcm_token": "abc123", "platform": "android"})
    r = _delete(client, f"{DEVICES_URL}abc123/")
    assert r.status_code == 200
    assert r.json()["data"]["deleted"] == 1
    assert not DeviceToken.objects.filter(fcm_token="abc123").exists()


def test_list_requires_auth(client: Client) -> None:
    r = client.get(LIST_URL)
    assert r.status_code == 401
