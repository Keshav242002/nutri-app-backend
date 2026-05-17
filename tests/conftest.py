from typing import Any

import pytest
from django.test import Client


@pytest.fixture
def client() -> Client:
    """Django test client."""
    return Client()


@pytest.fixture
def firebase_decoded_token() -> dict[str, Any]:
    """Fake decoded Firebase token payload returned by mocked verify_id_token."""
    return {
        "uid": "test-firebase-uid-123",
        "email": "testuser@example.com",
        "name": "Test User",
    }
