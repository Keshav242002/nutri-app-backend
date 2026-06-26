"""View / endpoint tests for apps/chat."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from django.test import Client

from apps.accounts.models import User
from apps.profiles.tests.factories import DietaryProfileFactory
from apps.recipes.tests.factories import IngredientFactory

from .factories import ChatMessageFactory, ChatSessionFactory

pytestmark = pytest.mark.django_db

REGISTER_URL = "/api/v1/auth/register"
SESSIONS_URL = "/api/v1/chat/sessions/"
MESSAGES_URL = "/api/v1/chat/sessions/{}/messages/"

FAKE_TOKEN: dict[str, Any] = {
    "uid": "chat-test-uid",
    "email": "chattest@example.com",
    "name": "Chat Tester",
}


def _header() -> dict[str, str]:
    return {"HTTP_AUTHORIZATION": "Bearer fake-chat-token"}


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


def _post(client: Client, url: str, data: dict[str, Any]) -> Any:
    with patch("firebase_admin.auth.verify_id_token", return_value=FAKE_TOKEN):
        return client.post(url, data=data, content_type="application/json")


# ---------------------------------------------------------------------------
# Session create / list
# ---------------------------------------------------------------------------


def test_create_session_201(auth_client: tuple[Client, User]) -> None:
    client, user = auth_client
    r = _post(client, SESSIONS_URL, {"title": "My Session"})
    assert r.status_code == 201
    body = r.json()
    assert body["status"] == "success"
    assert body["data"]["title"] == "My Session"


def test_create_session_blank_title(auth_client: tuple[Client, User]) -> None:
    client, user = auth_client
    r = _post(client, SESSIONS_URL, {})
    assert r.status_code == 201
    assert r.json()["data"]["title"] == ""


def test_list_sessions_200(auth_client: tuple[Client, User]) -> None:
    client, user = auth_client
    ChatSessionFactory(user=user)
    ChatSessionFactory(user=user)
    r = _get(client, SESSIONS_URL)
    assert r.status_code == 200
    body = r.json()
    assert "results" in body


def test_list_sessions_excludes_other_users(auth_client: tuple[Client, User]) -> None:
    client, user = auth_client
    other = DietaryProfileFactory()
    ChatSessionFactory(user=other.user)
    ChatSessionFactory(user=user)
    r = _get(client, SESSIONS_URL)
    results = r.json()["results"]
    assert len(results) == 1


# ---------------------------------------------------------------------------
# Message list / send
# ---------------------------------------------------------------------------


def test_list_messages_200(auth_client: tuple[Client, User]) -> None:
    client, user = auth_client
    session = ChatSessionFactory(user=user)
    ChatMessageFactory(session=session, content="hi")
    r = _get(client, MESSAGES_URL.format(session.pk))
    assert r.status_code == 200
    assert "results" in r.json()


def test_list_messages_wrong_user_404(auth_client: tuple[Client, User]) -> None:
    client, user = auth_client
    other_session = ChatSessionFactory()
    r = _get(client, MESSAGES_URL.format(other_session.pk))
    assert r.status_code == 404


def test_send_chat_message_201(auth_client: tuple[Client, User]) -> None:
    client, user = auth_client
    session = ChatSessionFactory(user=user)
    cfg = MagicMock()
    cfg.provider.value = "openrouter"
    cfg.model = "openrouter/free"
    with (
        patch("apps.chat.services.chat_service.check_rate_limit"),
        patch("apps.chat.services.chat_service._load_context", return_value=(None, None, None, [])),
        patch("apps.chat.services.chat_service.chat_completion", return_value="Hello!"),
        patch("apps.chat.services.chat_service.get_provider_config", return_value=cfg),
    ):
        r = _post(client, MESSAGES_URL.format(session.pk), {"content": "Hi", "mode": "chat"})
    assert r.status_code == 201
    body = r.json()
    assert body["status"] == "success"
    assert body["data"]["role"] == "assistant"
    assert body["data"]["content"] == "Hello!"


def test_send_message_wrong_session_404(auth_client: tuple[Client, User]) -> None:
    client, user = auth_client
    other_session = ChatSessionFactory()
    r = _post(client, MESSAGES_URL.format(other_session.pk), {"content": "Hi", "mode": "chat"})
    assert r.status_code == 404


def test_send_ingredient_message_201(auth_client: tuple[Client, User]) -> None:
    client, user = auth_client
    session = ChatSessionFactory(user=user)
    profile = DietaryProfileFactory(user=user)
    # "Rice" is in the DB → grounded path (persist + loggable card with slug).
    IngredientFactory(name="Rice", is_active=True)
    cfg = MagicMock()
    cfg.provider.value = "openrouter"
    cfg.model = "openrouter/free"

    mock_recipe = MagicMock()
    mock_recipe.pk = 42
    mock_recipe.name = "Rice Bowl"
    mock_recipe.slug = "rice-bowl"
    mock_recipe.meal_type = "lunch"
    mock_recipe.cached_calories_per_serving = 400
    mock_recipe.servings = 2

    with (
        patch("apps.chat.services.chat_service.check_rate_limit"),
        patch(
            "apps.chat.services.chat_service._load_context", return_value=(profile, None, None, [])
        ),
        patch(
            "apps.chat.services.chat_service.structured_completion",
            return_value={"recipes": [{"name": "Rice Bowl"}]},
        ),
        patch("apps.chat.services.chat_service.get_provider_config", return_value=cfg),
        patch(
            "apps.chat.services.chat_service.validate_and_persist_ai_recipe",
            return_value=mock_recipe,
        ),
    ):
        r = _post(
            client,
            MESSAGES_URL.format(session.pk),
            {"content": "Make a recipe with rice", "mode": "ingredient", "ingredients": ["Rice"]},
        )
    assert r.status_code == 201
    body = r.json()
    assert body["status"] == "success"
    recipes = body["data"]["metadata"]["recipes"]
    assert len(recipes) == 1
    assert recipes[0]["slug"] == "rice-bowl"
    assert "description" in recipes[0]


def test_ingredient_mode_requires_ingredients(auth_client: tuple[Client, User]) -> None:
    client, user = auth_client
    session = ChatSessionFactory(user=user)
    r = _post(
        client,
        MESSAGES_URL.format(session.pk),
        {"content": "Make something", "mode": "ingredient", "ingredients": []},
    )
    assert r.status_code == 400


def test_invalid_mode_returns_400(auth_client: tuple[Client, User]) -> None:
    client, user = auth_client
    session = ChatSessionFactory(user=user)
    r = _post(
        client,
        MESSAGES_URL.format(session.pk),
        {"content": "Hi", "mode": "invalid_mode"},
    )
    assert r.status_code == 400


def test_unauthenticated_request_returns_401(client: Client) -> None:
    r = client.get(SESSIONS_URL)
    assert r.status_code == 401
