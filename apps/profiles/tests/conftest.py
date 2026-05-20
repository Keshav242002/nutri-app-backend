"""
Shared test fixtures for apps/profiles/tests/.

Provides:
  - FAKE_TOKEN_PAYLOAD: standard Firebase payload for a test user
  - firebase_mock (autouse=False): context manager / patch for firebase_admin.auth.verify_id_token
  - auth_client: a Django test Client with a valid (mocked) Firebase auth header pre-loaded
  - registered_user: a User created via the /auth/register endpoint using the mock token

Usage in tests that need an authenticated client + registered user:
    def test_something(self, auth_client, registered_user): ...
"""

from typing import Any
from unittest.mock import patch

import pytest
from django.test import Client

REGISTER_URL = "/api/v1/auth/register"
ONBOARDING_URL = "/api/v1/profiles/onboarding"
PROFILE_ME_URL = "/api/v1/profiles/me"
AUTH_ME_URL = "/api/v1/auth/me"

FAKE_TOKEN_PAYLOAD: dict[str, Any] = {
    "uid": "test-firebase-uid-profiles",
    "email": "profiletest@example.com",
    "name": "Profile Test User",
}


def _auth_header() -> dict[str, str]:
    return {"HTTP_AUTHORIZATION": "Bearer fake-firebase-token"}


@pytest.fixture()
def auth_client(client: Client):  # type: ignore[type-arg]
    """
    Returns a Django test Client pre-configured so that every request
    carries the Firebase auth header. The firebase mock is NOT active here —
    individual tests that hit endpoints must wrap with firebase_mock themselves
    or use the registered_user fixture which does so.
    """
    client.defaults.update(_auth_header())
    return client


@pytest.fixture()
def registered_user(client: Client):  # type: ignore[type-arg]
    """
    Creates (registers) a User via the /auth/register endpoint using the
    mocked Firebase token. Returns (client_with_auth, user_instance).
    """
    client.defaults.update(_auth_header())
    with patch("firebase_admin.auth.verify_id_token", return_value=FAKE_TOKEN_PAYLOAD):
        client.post(REGISTER_URL)
    # Fetch the created user from DB
    from apps.accounts.models import User

    user = User.objects.get(firebase_uid=FAKE_TOKEN_PAYLOAD["uid"])
    return client, user
