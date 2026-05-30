"""Shared fixtures for tracker tests."""

from __future__ import annotations

from datetime import date
from typing import Any
from unittest.mock import patch

import pytest
from django.test import Client

from apps.accounts.models import User

REGISTER_URL = "/api/v1/auth/register"
TRACKER_LOG_URL = "/api/v1/tracker/log/"
TRACKER_LIST_URL = "/api/v1/tracker/"
TRACKER_RANGE_URL = "/api/v1/tracker/range/"
NUTRITION_DAILY_URL = "/api/v1/nutrition/daily/"
NUTRITION_WEEKLY_URL = "/api/v1/nutrition/weekly/"

LOG_DATE = "2026-05-30"
LOG_DATE_OBJ = date(2026, 5, 30)

FAKE_TOKEN_PAYLOAD: dict[str, Any] = {
    "uid": "test-firebase-uid-tracker",
    "email": "trackertest@example.com",
    "name": "Tracker Test User",
}


def _auth_header() -> dict[str, str]:
    return {"HTTP_AUTHORIZATION": "Bearer fake-tracker-token"}


@pytest.fixture()
def tracker_client(client: Client) -> tuple[Client, User]:
    """Authenticated client with registered user (no profile)."""
    client.defaults.update(_auth_header())
    with patch("firebase_admin.auth.verify_id_token", return_value=FAKE_TOKEN_PAYLOAD):
        client.post(REGISTER_URL)
    user = User.objects.get(firebase_uid=FAKE_TOKEN_PAYLOAD["uid"])
    return client, user


@pytest.fixture()
def tracker_client_with_profile(client: Client) -> tuple[Client, User, Any]:
    """Authenticated client + registered user + DietaryProfile."""
    from apps.profiles.tests.factories import DietaryProfileFactory

    client.defaults.update(_auth_header())
    with patch("firebase_admin.auth.verify_id_token", return_value=FAKE_TOKEN_PAYLOAD):
        client.post(REGISTER_URL)
    user = User.objects.get(firebase_uid=FAKE_TOKEN_PAYLOAD["uid"])
    profile = DietaryProfileFactory(
        user=user,
        daily_food_budget_inr=None,
        weekly_food_budget_inr=None,
        max_prep_time_min=60,
        diet_pattern="vegetarian",
    )
    return client, user, profile


def _auth_post(client: Client, url: str, data: dict[str, Any]) -> Any:
    with patch("firebase_admin.auth.verify_id_token", return_value=FAKE_TOKEN_PAYLOAD):
        return client.post(url, data=data, content_type="application/json")


def _auth_get(client: Client, url: str) -> Any:
    with patch("firebase_admin.auth.verify_id_token", return_value=FAKE_TOKEN_PAYLOAD):
        return client.get(url)
