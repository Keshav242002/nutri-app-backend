from typing import Any
from unittest.mock import patch

import pytest
from django.test import Client

REGISTER_URL = "/api/v1/auth/register"
RECIPE_LIST_URL = "/api/v1/recipes/"

FAKE_TOKEN_PAYLOAD: dict[str, Any] = {
    "uid": "test-firebase-uid-recipes",
    "email": "recipetest@example.com",
    "name": "Recipe Test User",
}


def _auth_header() -> dict[str, str]:
    return {"HTTP_AUTHORIZATION": "Bearer fake-firebase-token"}


@pytest.fixture()
def registered_user(client: Client):  # type: ignore[type-arg]
    """Register a user via the auth endpoint and return (client_with_auth, user)."""
    client.defaults.update(_auth_header())
    with patch("firebase_admin.auth.verify_id_token", return_value=FAKE_TOKEN_PAYLOAD):
        client.post(REGISTER_URL)
    from apps.accounts.models import User

    user = User.objects.get(firebase_uid=FAKE_TOKEN_PAYLOAD["uid"])
    return client, user
