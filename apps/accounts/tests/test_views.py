from typing import Any
from unittest.mock import patch

import pytest
from django.test import Client

REGISTER_URL = "/api/v1/auth/register"
ME_URL = "/api/v1/auth/me"

FAKE_TOKEN_PAYLOAD: dict[str, Any] = {
    "uid": "test-firebase-uid-123",
    "email": "testuser@example.com",
    "name": "Test User",
}


def _auth_header() -> dict[str, str]:
    return {"HTTP_AUTHORIZATION": "Bearer fake-firebase-token"}


@pytest.mark.django_db
class TestFirebaseAuthentication:
    def test_authentication_creates_user_on_first_token(self, client: Client) -> None:
        with patch("firebase_admin.auth.verify_id_token", return_value=FAKE_TOKEN_PAYLOAD):
            response = client.post(REGISTER_URL, **_auth_header())
        assert response.status_code == 200
        data = response.json()
        assert data["firebase_uid"] == FAKE_TOKEN_PAYLOAD["uid"]
        assert data["email"] == FAKE_TOKEN_PAYLOAD["email"]
        assert data["created"] is True

    def test_authentication_rejects_expired_token(self, client: Client) -> None:
        import firebase_admin.auth

        with patch(
            "firebase_admin.auth.verify_id_token",
            side_effect=firebase_admin.auth.ExpiredIdTokenError("expired", "expired"),
        ):
            response = client.get(ME_URL, **_auth_header())
        assert response.status_code == 401
        assert response.json()["error"]["code"] == "TOKEN_EXPIRED"

    def test_authentication_rejects_malformed_header(self, client: Client) -> None:
        response = client.get(ME_URL, HTTP_AUTHORIZATION="Token not-bearer-format")
        assert response.status_code == 401
        assert response.json()["error"]["code"] == "INVALID_AUTH_HEADER"

    def test_me_endpoint_requires_auth(self, client: Client) -> None:
        response = client.get(ME_URL)
        assert response.status_code == 401


@pytest.mark.django_db
class TestRegisterEndpoint:
    def test_register_endpoint_idempotent(self, client: Client) -> None:
        with patch("firebase_admin.auth.verify_id_token", return_value=FAKE_TOKEN_PAYLOAD):
            r1 = client.post(REGISTER_URL, **_auth_header())
            r2 = client.post(REGISTER_URL, **_auth_header())
        assert r1.status_code == 200
        assert r2.status_code == 200
        assert r1.json()["created"] is True
        assert r2.json()["created"] is False
        assert r1.json()["firebase_uid"] == r2.json()["firebase_uid"]


@pytest.mark.django_db
class TestMeEndpoint:
    def test_me_returns_correct_user(self, client: Client) -> None:
        with patch("firebase_admin.auth.verify_id_token", return_value=FAKE_TOKEN_PAYLOAD):
            client.post(REGISTER_URL, **_auth_header())
            response = client.get(ME_URL, **_auth_header())
        assert response.status_code == 200
        data = response.json()
        assert data["firebase_uid"] == FAKE_TOKEN_PAYLOAD["uid"]
        assert data["email"] == FAKE_TOKEN_PAYLOAD["email"]

    def test_me_returns_has_profile_false_when_no_profile(self, client: Client) -> None:
        with patch("firebase_admin.auth.verify_id_token", return_value=FAKE_TOKEN_PAYLOAD):
            client.post(REGISTER_URL, **_auth_header())
            response = client.get(ME_URL, **_auth_header())
        assert response.status_code == 200
        assert response.json()["has_profile"] is False
