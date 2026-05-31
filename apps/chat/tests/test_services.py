"""
Tests for apps/chat/services/. All external calls (LLM, USDA) are mocked.
"""

from __future__ import annotations

from datetime import timedelta
from unittest.mock import MagicMock, patch

import pytest
from django.utils import timezone

from apps.chat.models import ChatMessage
from apps.chat.services import chat_service
from apps.chat.services.ai_recipe_validator import validate_and_persist_ai_recipe
from apps.chat.services.llm_config import Provider, ProviderConfig
from apps.profiles.tests.factories import DietaryProfileFactory
from apps.recipes.tests.factories import IngredientFactory
from core.exceptions import AppValidationError, ExternalServiceError, RateLimitError

from .factories import ChatMessageFactory, ChatSessionFactory

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_provider_cfg() -> ProviderConfig:
    return ProviderConfig(
        provider=Provider.OPENROUTER,
        api_key="test-key",
        model="openrouter/free",
        base_url="https://openrouter.ai/api/v1",
        timeout_seconds=30,
        supports_strict_schema=False,
    )


# ---------------------------------------------------------------------------
# chat_service.create_session
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestCreateSession:
    def test_creates_session_with_title(self):
        profile = DietaryProfileFactory()
        session = chat_service.create_session(profile.user, title="My Chat")
        assert session.pk is not None
        assert session.title == "My Chat"
        assert session.user == profile.user

    def test_creates_session_with_blank_title(self):
        profile = DietaryProfileFactory()
        session = chat_service.create_session(profile.user)
        assert session.title == ""


# ---------------------------------------------------------------------------
# chat_service.list_sessions
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestListSessions:
    def test_returns_only_own_sessions(self):
        profile1 = DietaryProfileFactory()
        profile2 = DietaryProfileFactory()
        ChatSessionFactory(user=profile1.user)
        ChatSessionFactory(user=profile2.user)
        sessions = list(chat_service.list_sessions(profile1.user))
        assert len(sessions) == 1
        assert sessions[0].user == profile1.user


# ---------------------------------------------------------------------------
# chat_service.get_session_messages
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestGetSessionMessages:
    def test_returns_messages_for_own_session(self):
        session = ChatSessionFactory()
        ChatMessageFactory(session=session, content="hello")
        msgs = list(chat_service.get_session_messages(session.pk, session.user))
        assert len(msgs) == 1

    def test_raises_not_found_for_wrong_user(self):
        session = ChatSessionFactory()
        other_profile = DietaryProfileFactory()
        from core.exceptions import NotFoundError

        with pytest.raises(NotFoundError):
            chat_service.get_session_messages(session.pk, other_profile.user)


# ---------------------------------------------------------------------------
# chat_service.check_rate_limit
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestCheckRateLimit:
    def test_allows_under_limit(self):
        session = ChatSessionFactory()
        for _ in range(5):
            ChatMessageFactory(session=session, role=ChatMessage.Role.USER)
        with patch.object(chat_service, "_get_chat_rate_limit", return_value=30):
            chat_service.check_rate_limit(session.user)

    def test_raises_at_limit(self):
        session = ChatSessionFactory()
        for _ in range(3):
            ChatMessageFactory(session=session, role=ChatMessage.Role.USER)
        with patch.object(chat_service, "_get_chat_rate_limit", return_value=3):
            with pytest.raises(RateLimitError):
                chat_service.check_rate_limit(session.user)

    def test_old_messages_dont_count(self):
        session = ChatSessionFactory()
        old_msg = ChatMessageFactory(session=session, role=ChatMessage.Role.USER)
        ChatMessage.objects.filter(pk=old_msg.pk).update(
            created_at=timezone.now() - timedelta(hours=2)
        )
        with patch.object(chat_service, "_get_chat_rate_limit", return_value=1):
            chat_service.check_rate_limit(session.user)  # should not raise


# ---------------------------------------------------------------------------
# chat_service.send_message_chat
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestSendMessageChat:
    def test_saves_user_and_assistant_messages(self):
        session = ChatSessionFactory()
        cfg = _make_provider_cfg()
        with (
            patch("apps.chat.services.chat_service.check_rate_limit"),
            patch("apps.chat.services.chat_service._load_context", return_value=(None, None)),
            patch("apps.chat.services.chat_service.chat_completion", return_value="AI reply"),
            patch("apps.chat.services.chat_service.get_provider_config", return_value=cfg),
        ):
            msg = chat_service.send_message_chat(session, "Hello", session.user)

        assert msg.role == ChatMessage.Role.ASSISTANT
        assert msg.content == "AI reply"
        assert session.messages.count() == 2

    def test_llm_failure_propagates(self):
        session = ChatSessionFactory()
        cfg = _make_provider_cfg()
        with (
            patch("apps.chat.services.chat_service.check_rate_limit"),
            patch("apps.chat.services.chat_service._load_context", return_value=(None, None)),
            patch(
                "apps.chat.services.chat_service.chat_completion",
                side_effect=ExternalServiceError(code="LLM_FAILURE", message="fail"),
            ),
            patch("apps.chat.services.chat_service.get_provider_config", return_value=cfg),
        ):
            with pytest.raises(ExternalServiceError):
                chat_service.send_message_chat(session, "Hello", session.user)


# ---------------------------------------------------------------------------
# chat_service.send_message_ingredient
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestSendMessageIngredient:
    def test_persists_validated_recipe(self):
        profile = DietaryProfileFactory()
        session = ChatSessionFactory(user=profile.user)
        IngredientFactory(name="Rice", is_active=True)
        cfg = _make_provider_cfg()

        fake_json = {
            "recipes": [
                {
                    "name": "AI Rice Bowl",
                    "meal_type": "lunch",
                    "servings": 2,
                    "diet_tags": ["vegetarian"],
                    "allergen_tags": [],
                    "ingredients": [{"ingredient_name": "Rice", "quantity_grams": 200}],
                    "steps": ["Cook rice."],
                }
            ]
        }

        mock_recipe = MagicMock()
        mock_recipe.pk = 99
        mock_recipe.name = "AI Rice Bowl"
        mock_recipe.meal_type = "lunch"
        mock_recipe.cached_calories_per_serving = 350
        mock_recipe.servings = 2

        with (
            patch("apps.chat.services.chat_service.check_rate_limit"),
            patch("apps.chat.services.chat_service._load_context", return_value=(profile, None)),
            patch(
                "apps.chat.services.chat_service.structured_completion",
                return_value=fake_json,
            ),
            patch("apps.chat.services.chat_service.get_provider_config", return_value=cfg),
            patch(
                "apps.chat.services.chat_service.validate_and_persist_ai_recipe",
                return_value=mock_recipe,
            ),
        ):
            msg = chat_service.send_message_ingredient(
                session=session,
                content="Make me a recipe with Rice",
                ingredients=["Rice"],
                user=profile.user,
            )

        assert msg.role == ChatMessage.Role.ASSISTANT
        assert msg.metadata is not None
        assert len(msg.metadata["recipes"]) == 1
        assert msg.metadata["recipes"][0]["name"] == "AI Rice Bowl"

    def test_failed_validation_logged_not_aborted(self):
        profile = DietaryProfileFactory()
        session = ChatSessionFactory(user=profile.user)
        cfg = _make_provider_cfg()

        fake_json = {"recipes": [{"name": "Bad Recipe"}]}

        with (
            patch("apps.chat.services.chat_service.check_rate_limit"),
            patch("apps.chat.services.chat_service._load_context", return_value=(profile, None)),
            patch(
                "apps.chat.services.chat_service.structured_completion",
                return_value=fake_json,
            ),
            patch("apps.chat.services.chat_service.get_provider_config", return_value=cfg),
            patch(
                "apps.chat.services.chat_service.validate_and_persist_ai_recipe",
                side_effect=AppValidationError(code="VALIDATION_ERROR", message="invalid"),
            ),
        ):
            msg = chat_service.send_message_ingredient(
                session=session,
                content="Make me something",
                ingredients=["Nonexistent"],
                user=profile.user,
            )

        assert msg.role == ChatMessage.Role.ASSISTANT
        assert msg.metadata["recipes"] == []

    def test_partial_batch_when_one_recipe_rejected(self):
        """3 recipes generated; 1 fails ingredient validation → 2 returned, 1 logged."""
        profile = DietaryProfileFactory()
        session = ChatSessionFactory(user=profile.user)
        cfg = _make_provider_cfg()

        fake_json = {
            "recipes": [
                {"name": "Recipe A"},
                {"name": "Recipe B"},
                {"name": "Recipe C"},
            ]
        }

        mock_a = MagicMock()
        mock_a.pk = 1
        mock_a.name = "Recipe A"
        mock_a.meal_type = "lunch"
        mock_a.cached_calories_per_serving = 350
        mock_a.servings = 2

        mock_c = MagicMock()
        mock_c.pk = 3
        mock_c.name = "Recipe C"
        mock_c.meal_type = "dinner"
        mock_c.cached_calories_per_serving = 420
        mock_c.servings = 2

        side_effects = [
            mock_a,
            AppValidationError(code="VALIDATION_ERROR", message="bad ingredient"),
            mock_c,
        ]

        with (
            patch("apps.chat.services.chat_service.check_rate_limit"),
            patch("apps.chat.services.chat_service._load_context", return_value=(profile, None)),
            patch(
                "apps.chat.services.chat_service.structured_completion",
                return_value=fake_json,
            ),
            patch("apps.chat.services.chat_service.get_provider_config", return_value=cfg),
            patch(
                "apps.chat.services.chat_service.validate_and_persist_ai_recipe",
                side_effect=side_effects,
            ),
        ):
            msg = chat_service.send_message_ingredient(
                session=session,
                content="Make me recipes",
                ingredients=["rice", "dal"],
                user=profile.user,
            )

        assert msg.role == ChatMessage.Role.ASSISTANT
        assert msg.metadata is not None
        assert len(msg.metadata["recipes"]) == 2
        names = [r["name"] for r in msg.metadata["recipes"]]
        assert "Recipe A" in names
        assert "Recipe C" in names
        assert "Recipe B" not in names


# ---------------------------------------------------------------------------
# ai_recipe_validator
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestAiRecipeValidator:
    def _valid_recipe_json(self, ingredient_name: str) -> dict:
        return {
            "name": "Test AI Dish",
            "meal_type": "lunch",
            "servings": 2,
            "diet_tags": ["vegetarian"],
            "allergen_tags": [],
            "ingredients": [{"ingredient_name": ingredient_name, "quantity_grams": 200}],
            "steps": ["Cook it."],
        }

    def test_valid_recipe_is_persisted(self):
        profile = DietaryProfileFactory()
        IngredientFactory(name="Lentils", is_active=True)
        recipe_json = self._valid_recipe_json("Lentils")

        mock_nutrition = {"calories": 350}
        with patch(
            "apps.chat.services.ai_recipe_validator.compute_recipe_nutrition",
            return_value=mock_nutrition,
        ):
            recipe = validate_and_persist_ai_recipe(recipe_json, profile.user)

        assert recipe.pk is not None
        assert recipe.source == "ai_generated"
        assert recipe.name == "Test AI Dish"

    def test_unknown_ingredient_raises(self):
        profile = DietaryProfileFactory()
        recipe_json = self._valid_recipe_json("NonExistentIngredient")
        with pytest.raises(AppValidationError, match="does not exist"):
            validate_and_persist_ai_recipe(recipe_json, profile.user)

    def test_invalid_meal_type_raises(self):
        profile = DietaryProfileFactory()
        IngredientFactory(name="Wheat", is_active=True)
        recipe_json = self._valid_recipe_json("Wheat")
        recipe_json["meal_type"] = "brunch"
        with pytest.raises(AppValidationError, match="meal_type"):
            validate_and_persist_ai_recipe(recipe_json, profile.user)

    def test_calories_out_of_range_deletes_recipe(self):
        from apps.recipes.models import Recipe

        profile = DietaryProfileFactory()
        IngredientFactory(name="Sugar", is_active=True)
        recipe_json = self._valid_recipe_json("Sugar")

        mock_nutrition = {"calories": 5000}
        with patch(
            "apps.chat.services.ai_recipe_validator.compute_recipe_nutrition",
            return_value=mock_nutrition,
        ):
            with pytest.raises(AppValidationError, match="calories"):
                validate_and_persist_ai_recipe(recipe_json, profile.user)
            assert Recipe.objects.filter(name="Test AI Dish").count() == 0

    def test_quantity_out_of_range_raises(self):
        profile = DietaryProfileFactory()
        IngredientFactory(name="Ghee", is_active=True)
        recipe_json = self._valid_recipe_json("Ghee")
        recipe_json["ingredients"][0]["quantity_grams"] = 9999
        with pytest.raises(AppValidationError, match="quantity_grams"):
            validate_and_persist_ai_recipe(recipe_json, profile.user)

    def test_servings_out_of_range_raises(self):
        profile = DietaryProfileFactory()
        IngredientFactory(name="Milk", is_active=True)
        recipe_json = self._valid_recipe_json("Milk")
        recipe_json["servings"] = 50
        with pytest.raises(AppValidationError, match="servings"):
            validate_and_persist_ai_recipe(recipe_json, profile.user)

    def test_strip_parenthetical_match(self):
        """Tier 2: AI outputs 'basmati rice'; DB has 'Basmati rice (raw)' → resolved."""
        from apps.recipes.models import Recipe

        profile = DietaryProfileFactory()
        IngredientFactory(name="Basmati rice (raw)", is_active=True)
        recipe_json = self._valid_recipe_json("basmati rice")

        mock_nutrition = {"calories": 350}
        with patch(
            "apps.chat.services.ai_recipe_validator.compute_recipe_nutrition",
            return_value=mock_nutrition,
        ):
            recipe = validate_and_persist_ai_recipe(recipe_json, profile.user)

        assert recipe.pk is not None
        assert Recipe.objects.filter(pk=recipe.pk).exists()

    def test_alias_map_resolves_known_drift(self):
        """Tier 4: AI outputs 'arhar dal'; alias map resolves to 'Toor dal (raw)'."""
        from apps.recipes.models import Recipe

        profile = DietaryProfileFactory()
        IngredientFactory(name="Toor dal (raw)", is_active=True)
        recipe_json = self._valid_recipe_json("arhar dal")

        mock_nutrition = {"calories": 350}
        with patch(
            "apps.chat.services.ai_recipe_validator.compute_recipe_nutrition",
            return_value=mock_nutrition,
        ):
            recipe = validate_and_persist_ai_recipe(recipe_json, profile.user)

        assert recipe.pk is not None
        assert Recipe.objects.filter(pk=recipe.pk).exists()

    def test_zero_prep_cook_time_is_valid(self):
        """AI recipes with no prep/cook time default to 0 — model must accept it."""
        profile = DietaryProfileFactory()
        IngredientFactory(name="Paneer", is_active=True)
        recipe_json = self._valid_recipe_json("Paneer")
        # No prep_time_min / cook_time_min keys in the JSON — validator never reads them,
        # Recipe model defaults both to 0.

        mock_nutrition = {"calories": 280}
        with patch(
            "apps.chat.services.ai_recipe_validator.compute_recipe_nutrition",
            return_value=mock_nutrition,
        ):
            recipe = validate_and_persist_ai_recipe(recipe_json, profile.user)

        assert recipe.prep_time_min == 0
        assert recipe.cook_time_min == 0

    def test_calorie_check_failure_leaves_no_orphan_recipe(self):
        """When computed calories fall outside the valid range, the Recipe row is deleted."""
        from apps.recipes.models import Recipe

        profile = DietaryProfileFactory()
        IngredientFactory(name="Salt", is_active=True)
        recipe_json = self._valid_recipe_json("Salt")

        # Return calories below the minimum (50) so the guard fires.
        mock_nutrition = {"calories": 5}
        with patch(
            "apps.chat.services.ai_recipe_validator.compute_recipe_nutrition",
            return_value=mock_nutrition,
        ):
            before = Recipe.objects.count()
            with pytest.raises(AppValidationError, match="calories"):
                validate_and_persist_ai_recipe(recipe_json, profile.user)
            assert Recipe.objects.count() == before

    def test_duplicate_resolved_ingredient_raises_validation_error(self):
        """Two AI names resolving to the same DB Ingredient must be rejected before any DB write."""
        from apps.recipes.models import Recipe

        profile = DietaryProfileFactory()
        IngredientFactory(name="Basmati rice (raw)", is_active=True)
        # "Basmati rice (raw)" matches tier 1; "basmati rice" matches tier 2 — same DB row.
        recipe_json = {
            "name": "Duplicate Ingredient Dish",
            "meal_type": "lunch",
            "servings": 2,
            "diet_tags": [],
            "allergen_tags": [],
            "ingredients": [
                {"ingredient_name": "Basmati rice (raw)", "quantity_grams": 200},
                {"ingredient_name": "basmati rice", "quantity_grams": 50},
            ],
            "steps": ["Cook."],
        }
        before = Recipe.objects.count()
        with pytest.raises(AppValidationError, match="appears more than once"):
            validate_and_persist_ai_recipe(recipe_json, profile.user)
        assert Recipe.objects.count() == before

    def test_unknown_ingredient_rejects_whole_recipe_not_partial(self):
        """Unknown ingredient rejects the recipe immediately; no Recipe row is created."""
        from apps.recipes.models import Recipe

        profile = DietaryProfileFactory()
        IngredientFactory(name="Rice", is_active=True)
        # Two ingredients: one known, one unknown.
        recipe_json = {
            "name": "Partial Dish",
            "meal_type": "lunch",
            "servings": 2,
            "diet_tags": [],
            "allergen_tags": [],
            "ingredients": [
                {"ingredient_name": "Rice", "quantity_grams": 200},
                {"ingredient_name": "GhostIngredientXYZ", "quantity_grams": 50},
            ],
            "steps": ["Cook."],
        }
        with pytest.raises(AppValidationError, match="does not exist"):
            validate_and_persist_ai_recipe(recipe_json, profile.user)

        # Verify no Recipe was persisted (partial persist is forbidden)
        assert Recipe.objects.filter(name="Partial Dish").count() == 0


# ---------------------------------------------------------------------------
# llm_config
# ---------------------------------------------------------------------------


class TestLlmConfig:
    def test_get_provider_config_openrouter(self):
        from apps.chat.services.llm_config import Provider, get_provider_config

        with patch("apps.chat.services.llm_config.settings") as mock_settings:
            mock_settings.AI_PROVIDER = "openrouter"
            mock_settings.OPENROUTER_API_KEY = "test-key"
            mock_settings.OPENROUTER_MODEL = "openrouter/free"
            mock_settings.LLM_TIMEOUT_SECONDS = 30
            cfg = get_provider_config()
        assert cfg.provider == Provider.OPENROUTER
        assert cfg.api_key == "test-key"

    def test_invalid_provider_raises(self):
        from apps.chat.services.llm_config import get_provider_config

        with patch("apps.chat.services.llm_config.settings") as mock_settings:
            mock_settings.AI_PROVIDER = "invalid_provider"
            with pytest.raises(ValueError, match="Invalid AI_PROVIDER"):
                get_provider_config()

    def test_get_provider_config_openai(self):
        from apps.chat.services.llm_config import Provider, get_provider_config

        with patch("apps.chat.services.llm_config.settings") as mock_settings:
            mock_settings.AI_PROVIDER = "openai"
            mock_settings.OPENAI_API_KEY = "sk-test"
            mock_settings.OPENAI_MODEL = "gpt-4o"
            mock_settings.LLM_TIMEOUT_SECONDS = 30
            cfg = get_provider_config()
        assert cfg.provider == Provider.OPENAI
        assert cfg.supports_strict_schema is True

    def test_get_provider_config_gemini_native(self):
        from apps.chat.services.llm_config import Provider, get_provider_config

        with patch("apps.chat.services.llm_config.settings") as mock_settings:
            mock_settings.AI_PROVIDER = "gemini_native"
            mock_settings.GEMINI_API_KEY = "gemini-key"
            mock_settings.GEMINI_MODEL = "gemini-2.5-flash"
            mock_settings.LLM_TIMEOUT_SECONDS = 30
            cfg = get_provider_config()
        assert cfg.provider == Provider.GEMINI_NATIVE
        assert cfg.base_url is None


# ---------------------------------------------------------------------------
# llm_client helpers — _is_transient, _parse_json_strict
# ---------------------------------------------------------------------------


class TestIsTransient:
    def test_timeout_in_name_is_transient(self):
        from apps.chat.services.llm_client import _is_transient

        assert _is_transient(TimeoutError("timed out")) is True

    def test_connection_in_message_is_transient(self):
        from apps.chat.services.llm_client import _is_transient

        assert _is_transient(OSError("connection refused")) is True

    def test_502_in_message_is_transient(self):
        from apps.chat.services.llm_client import _is_transient

        assert _is_transient(RuntimeError("502 Bad Gateway")) is True

    def test_503_in_message_is_transient(self):
        from apps.chat.services.llm_client import _is_transient

        assert _is_transient(RuntimeError("503 service unavailable")) is True

    def test_value_error_not_transient(self):
        from apps.chat.services.llm_client import _is_transient

        assert _is_transient(ValueError("invalid input")) is False


class TestParseJsonStrict:
    def test_plain_json_dict(self):
        from apps.chat.services.llm_client import _parse_json_strict

        cfg = _make_provider_cfg()
        result = _parse_json_strict('{"key": "value"}', cfg)
        assert result == {"key": "value"}

    def test_json_with_markdown_fences(self):
        from apps.chat.services.llm_client import _parse_json_strict

        cfg = _make_provider_cfg()
        raw = '```json\n{"key": "value"}\n```'
        result = _parse_json_strict(raw, cfg)
        assert result == {"key": "value"}

    def test_json_with_plain_fences(self):
        from apps.chat.services.llm_client import _parse_json_strict

        cfg = _make_provider_cfg()
        raw = '```\n{"key": "value"}\n```'
        result = _parse_json_strict(raw, cfg)
        assert result == {"key": "value"}

    def test_invalid_json_raises(self):
        from apps.chat.services.llm_client import _parse_json_strict

        cfg = _make_provider_cfg()
        with pytest.raises(ExternalServiceError, match="non-JSON"):
            _parse_json_strict("not json at all", cfg)

    def test_non_dict_json_raises(self):
        from apps.chat.services.llm_client import _parse_json_strict

        cfg = _make_provider_cfg()
        with pytest.raises(ExternalServiceError, match="not an object"):
            _parse_json_strict("[1, 2, 3]", cfg)


# ---------------------------------------------------------------------------
# llm_client — _get_openai_client
# ---------------------------------------------------------------------------


class TestGetOpenaiClient:
    def test_no_api_key_raises(self):
        from apps.chat.services.llm_client import _get_openai_client

        cfg = ProviderConfig(
            provider=Provider.OPENROUTER,
            api_key="",
            model="test",
            base_url="https://example.com",
            timeout_seconds=30,
            supports_strict_schema=False,
        )
        with pytest.raises(ExternalServiceError, match="No API key"):
            _get_openai_client(cfg)

    def test_returns_client_for_openrouter(self):
        from apps.chat.services.llm_client import _get_openai_client

        cfg = _make_provider_cfg()
        with patch("openai.OpenAI") as mock_cls:
            mock_cls.return_value = MagicMock()
            client = _get_openai_client(cfg)
        assert client is mock_cls.return_value
        mock_cls.assert_called_once()


# ---------------------------------------------------------------------------
# llm_client — _openai_compatible_completion
# ---------------------------------------------------------------------------


class TestOpenaiCompatibleCompletion:
    def test_success(self):
        from apps.chat.services.llm_client import _openai_compatible_completion

        mock_client = MagicMock()
        mock_completion = MagicMock()
        mock_completion.choices[0].message.content = "AI reply"
        mock_client.chat.completions.create.return_value = mock_completion

        cfg = _make_provider_cfg()
        with patch("apps.chat.services.llm_client._get_openai_client", return_value=mock_client):
            result = _openai_compatible_completion(
                cfg, [{"role": "user", "content": "Hi"}], json_mode=False, stream=False
            )
        assert result == "AI reply"

    def test_transient_error_retries_then_succeeds(self):
        from apps.chat.services.llm_client import _openai_compatible_completion

        mock_client = MagicMock()
        mock_completion = MagicMock()
        mock_completion.choices[0].message.content = "Retry success"
        mock_client.chat.completions.create.side_effect = [
            TimeoutError("timeout"),
            mock_completion,
        ]

        cfg = _make_provider_cfg()
        with (
            patch("apps.chat.services.llm_client._get_openai_client", return_value=mock_client),
            patch("apps.chat.services.llm_client.time.sleep"),
        ):
            result = _openai_compatible_completion(
                cfg, [{"role": "user", "content": "Hi"}], json_mode=False, stream=False
            )
        assert result == "Retry success"

    def test_hard_failure_raises_external_service_error(self):
        from apps.chat.services.llm_client import _openai_compatible_completion

        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = RuntimeError("api down")

        cfg = _make_provider_cfg()
        with (
            patch("apps.chat.services.llm_client._get_openai_client", return_value=mock_client),
            patch("apps.chat.services.llm_client.time.sleep"),
        ):
            with pytest.raises(ExternalServiceError, match="LLM call failed"):
                _openai_compatible_completion(
                    cfg, [{"role": "user", "content": "Hi"}], json_mode=False, stream=False
                )

    def test_stream_returns_chunks(self):
        from apps.chat.services.llm_client import _openai_compatible_completion

        chunk1 = MagicMock()
        chunk1.choices = [MagicMock()]
        chunk1.choices[0].delta.content = "Hello"
        chunk2 = MagicMock()
        chunk2.choices = [MagicMock()]
        chunk2.choices[0].delta.content = " world"

        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = iter([chunk1, chunk2])

        cfg = _make_provider_cfg()
        with patch("apps.chat.services.llm_client._get_openai_client", return_value=mock_client):
            result = _openai_compatible_completion(cfg, [], json_mode=False, stream=True)
            chunks = list(result)
        assert chunks == ["Hello", " world"]


# ---------------------------------------------------------------------------
# llm_client — _stream_openai
# ---------------------------------------------------------------------------


class TestStreamOpenai:
    def test_yields_non_empty_chunks(self):
        from apps.chat.services.llm_client import _stream_openai

        cfg = _make_provider_cfg()
        chunk1 = MagicMock()
        chunk1.choices = [MagicMock()]
        chunk1.choices[0].delta.content = "Hi"
        chunk_empty = MagicMock()
        chunk_empty.choices = [MagicMock()]
        chunk_empty.choices[0].delta.content = None

        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = iter([chunk1, chunk_empty])

        result = list(_stream_openai(mock_client, {"model": "test", "messages": []}, cfg))
        assert result == ["Hi"]

    def test_exception_raises_external_service_error(self):
        from apps.chat.services.llm_client import _stream_openai

        cfg = _make_provider_cfg()
        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = RuntimeError("stream broke")

        with pytest.raises(ExternalServiceError):
            list(_stream_openai(mock_client, {}, cfg))


# ---------------------------------------------------------------------------
# llm_client — _gemini_native_completion
# ---------------------------------------------------------------------------


class TestGeminiNativeCompletion:
    def _gemini_cfg(self) -> ProviderConfig:
        return ProviderConfig(
            provider=Provider.GEMINI_NATIVE,
            api_key="gemini-key",
            model="gemini-2.5-flash",
            base_url=None,
            timeout_seconds=30,
            supports_strict_schema=True,
        )

    def _empty_cfg(self) -> ProviderConfig:
        return ProviderConfig(
            provider=Provider.GEMINI_NATIVE,
            api_key="",
            model="gemini-2.5-flash",
            base_url=None,
            timeout_seconds=30,
            supports_strict_schema=True,
        )

    def test_no_api_key_raises(self):
        from apps.chat.services.llm_client import _gemini_native_completion

        cfg = self._empty_cfg()
        with pytest.raises(ExternalServiceError, match="GEMINI_API_KEY"):
            _gemini_native_completion(cfg, [], json_mode=False, stream=False)

    def test_success_returns_text(self):
        from apps.chat.services.llm_client import _gemini_native_completion

        cfg = self._gemini_cfg()
        mock_response = MagicMock()
        mock_response.text = "Gemini answer"

        mock_client = MagicMock()
        mock_client.models.generate_content.return_value = mock_response

        with (
            patch("google.genai.Client", return_value=mock_client),
            patch("google.genai.types.GenerateContentConfig"),
        ):
            result = _gemini_native_completion(
                cfg, [{"role": "user", "content": "Hello"}], json_mode=False, stream=False
            )
        assert result == "Gemini answer"

    def test_api_error_raises_external_service_error(self):
        from apps.chat.services.llm_client import _gemini_native_completion

        cfg = self._gemini_cfg()
        mock_client = MagicMock()
        mock_client.models.generate_content.side_effect = RuntimeError("Gemini API error")

        with (
            patch("google.genai.Client", return_value=mock_client),
            patch("google.genai.types.GenerateContentConfig"),
        ):
            with pytest.raises(ExternalServiceError, match="Gemini native"):
                _gemini_native_completion(cfg, [], json_mode=False, stream=False)

    def test_stream_returns_chunks(self):
        from apps.chat.services.llm_client import _gemini_native_completion

        cfg = self._gemini_cfg()
        chunk1 = MagicMock()
        chunk1.text = "chunk A"
        chunk2 = MagicMock()
        chunk2.text = "chunk B"

        mock_client = MagicMock()
        mock_client.models.generate_content_stream.return_value = iter([chunk1, chunk2])

        with (
            patch("google.genai.Client", return_value=mock_client),
            patch("google.genai.types.GenerateContentConfig"),
        ):
            result = _gemini_native_completion(cfg, [], json_mode=False, stream=True)
            chunks = list(result)
        assert chunks == ["chunk A", "chunk B"]


# ---------------------------------------------------------------------------
# llm_client — chat_completion + structured_completion routing
# ---------------------------------------------------------------------------


class TestChatCompletion:
    def test_routes_to_openai_compatible_for_openrouter(self):
        from apps.chat.services.llm_client import chat_completion

        cfg = _make_provider_cfg()
        with (
            patch("apps.chat.services.llm_client.get_provider_config", return_value=cfg),
            patch(
                "apps.chat.services.llm_client._openai_compatible_completion",
                return_value="openai-reply",
            ) as mock_fn,
        ):
            result = chat_completion([{"role": "user", "content": "hi"}])
        assert result == "openai-reply"
        mock_fn.assert_called_once()

    def test_routes_to_gemini_native(self):
        from apps.chat.services.llm_client import chat_completion

        cfg = ProviderConfig(
            provider=Provider.GEMINI_NATIVE,
            api_key="key",
            model="gemini-2.5-flash",
            base_url=None,
            timeout_seconds=30,
            supports_strict_schema=True,
        )
        with (
            patch("apps.chat.services.llm_client.get_provider_config", return_value=cfg),
            patch(
                "apps.chat.services.llm_client._gemini_native_completion",
                return_value="gemini-reply",
            ) as mock_fn,
        ):
            result = chat_completion([])
        assert result == "gemini-reply"
        mock_fn.assert_called_once()


class TestStructuredCompletion:
    def test_parses_json_reply(self):
        from apps.chat.services.llm_client import structured_completion

        cfg = _make_provider_cfg()
        with (
            patch("apps.chat.services.llm_client.get_provider_config", return_value=cfg),
            patch(
                "apps.chat.services.llm_client.chat_completion",
                return_value='{"recipes": []}',
            ),
        ):
            result = structured_completion([], schema={})
        assert result == {"recipes": []}

    def test_retries_on_parse_failure_succeeds_on_second(self):
        from apps.chat.services.llm_client import structured_completion

        cfg = _make_provider_cfg()
        # First call returns unparseable garbage; second returns valid JSON.
        with (
            patch("apps.chat.services.llm_client.get_provider_config", return_value=cfg),
            patch(
                "apps.chat.services.llm_client.chat_completion",
                side_effect=["not valid json at all", '{"recipes": []}'],
            ),
        ):
            result = structured_completion([], schema={})
        assert result == {"recipes": []}

    def test_raises_after_two_parse_failures(self):
        from apps.chat.services.llm_client import structured_completion

        cfg = _make_provider_cfg()
        with (
            patch("apps.chat.services.llm_client.get_provider_config", return_value=cfg),
            patch(
                "apps.chat.services.llm_client.chat_completion",
                side_effect=["not json", "also not json"],
            ),
        ):
            with pytest.raises(ExternalServiceError):
                structured_completion([], schema={})


# ---------------------------------------------------------------------------
# chat_service — _get_chat_rate_limit + send_message_chat_stream
# ---------------------------------------------------------------------------


class TestGetChatRateLimit:
    def test_parses_rate_limit_setting(self):
        from apps.chat.services.chat_service import _get_chat_rate_limit

        with patch("apps.chat.services.chat_service.settings") as mock_settings:
            mock_settings.CHAT_RATE_LIMIT = "50/h"
            result = _get_chat_rate_limit()
        assert result == 50


@pytest.mark.django_db
class TestSendMessageChatStream:
    def test_yields_chunks_and_saves_messages(self):
        session = ChatSessionFactory()
        cfg = _make_provider_cfg()

        with (
            patch("apps.chat.services.chat_service.check_rate_limit"),
            patch("apps.chat.services.chat_service._load_context", return_value=(None, None)),
            patch(
                "apps.chat.services.chat_service.chat_completion",
                return_value=iter(["Hello", " world"]),
            ),
            patch("apps.chat.services.chat_service.get_provider_config", return_value=cfg),
        ):
            chunks = list(chat_service.send_message_chat_stream(session, "Hi", session.user))

        assert chunks == ["Hello", " world"]
        assert session.messages.count() == 2
        assistant_msg = session.messages.filter(role=ChatMessage.Role.ASSISTANT).first()
        assert assistant_msg is not None
        assert assistant_msg.content == "Hello world"


# ---------------------------------------------------------------------------
# usda_client — search_food, get_food_nutrients, macros_per_100g, _get
# ---------------------------------------------------------------------------


class TestSearchFood:
    def test_cache_hit_returns_without_fetching(self):
        from apps.chat.services.usda_client import search_food

        cached = [{"fdcId": 123, "description": "Rice"}]
        with patch("apps.chat.services.usda_client.cache") as mock_cache:
            mock_cache.get.return_value = cached
            result = search_food("rice")
        assert result == cached
        mock_cache.set.assert_not_called()

    def test_cache_miss_fetches_and_caches(self):
        from apps.chat.services.usda_client import search_food

        foods = [{"fdcId": 123, "description": "Rice"}]
        with (
            patch("apps.chat.services.usda_client.cache") as mock_cache,
            patch("apps.chat.services.usda_client._get", return_value={"foods": foods}),
        ):
            mock_cache.get.return_value = None
            result = search_food("rice")
        assert result == foods
        mock_cache.set.assert_called_once()


class TestGetFoodNutrients:
    def test_cache_hit(self):
        from apps.chat.services.usda_client import get_food_nutrients

        cached = {"fdcId": 123, "foodNutrients": []}
        with patch("apps.chat.services.usda_client.cache") as mock_cache:
            mock_cache.get.return_value = cached
            result = get_food_nutrients(123)
        assert result == cached

    def test_cache_miss_fetches_and_caches(self):
        from apps.chat.services.usda_client import get_food_nutrients

        data = {"fdcId": 123, "foodNutrients": []}
        with (
            patch("apps.chat.services.usda_client.cache") as mock_cache,
            patch("apps.chat.services.usda_client._get", return_value=data),
        ):
            mock_cache.get.return_value = None
            result = get_food_nutrients(123)
        assert result == data
        mock_cache.set.assert_called_once()


class TestMacrosPer100g:
    def test_no_foods_returns_none(self):
        from apps.chat.services.usda_client import macros_per_100g

        with patch("apps.chat.services.usda_client.search_food", return_value=[]):
            result = macros_per_100g("unknownfood")
        assert result is None

    def test_no_fdc_id_returns_none(self):
        from apps.chat.services.usda_client import macros_per_100g

        with patch(
            "apps.chat.services.usda_client.search_food",
            return_value=[{"description": "Rice"}],
        ):
            result = macros_per_100g("rice")
        assert result is None

    def test_extracts_macros_from_nutrients(self):
        from apps.chat.services.usda_client import macros_per_100g

        foods = [{"fdcId": 123, "description": "Brown Rice", "dataType": "Foundation"}]
        nutrients = [
            {"nutrient": {"id": 1003}, "amount": 7.5},
            {"nutrient": {"id": 1005}, "amount": 77.2},
            {"nutrient": {"id": 1004}, "amount": 2.9},
            {"nutrient": {"id": 1008}, "amount": 362.0},
        ]
        food_detail = {"fdcId": 123, "foodNutrients": nutrients}
        with (
            patch("apps.chat.services.usda_client.search_food", return_value=foods),
            patch("apps.chat.services.usda_client.get_food_nutrients", return_value=food_detail),
        ):
            result = macros_per_100g("rice")
        assert result is not None
        assert result["protein_g"] == 7.5
        assert result["calories"] == 362.0

    def test_prefers_foundation_data_type(self):
        from apps.chat.services.usda_client import macros_per_100g

        foods = [
            {"fdcId": 999, "description": "Unknown source"},
            {"fdcId": 123, "description": "Foundation Rice", "dataType": "Foundation"},
        ]
        food_detail = {
            "fdcId": 123,
            "foodNutrients": [{"nutrient": {"id": 1008}, "amount": 362.0}],
        }
        with (
            patch("apps.chat.services.usda_client.search_food", return_value=foods),
            patch(
                "apps.chat.services.usda_client.get_food_nutrients", return_value=food_detail
            ) as mock_get,
        ):
            macros_per_100g("rice")
        mock_get.assert_called_once_with(123)

    def test_empty_nutrients_returns_none(self):
        from apps.chat.services.usda_client import macros_per_100g

        foods = [{"fdcId": 123, "description": "Mystery food"}]
        food_detail = {"fdcId": 123, "foodNutrients": []}
        with (
            patch("apps.chat.services.usda_client.search_food", return_value=foods),
            patch("apps.chat.services.usda_client.get_food_nutrients", return_value=food_detail),
        ):
            result = macros_per_100g("mystery")
        assert result is None


class TestUsdaGetFunction:
    def test_success_returns_dict(self):
        from apps.chat.services.usda_client import _get

        mock_response = MagicMock()
        mock_response.json.return_value = {"foods": []}
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.Client") as mock_cls:
            mock_http = MagicMock()
            mock_http.__enter__ = MagicMock(return_value=mock_http)
            mock_http.__exit__ = MagicMock(return_value=False)
            mock_http.get.return_value = mock_response
            mock_cls.return_value = mock_http
            result = _get("/foods/search", {"query": "rice"})
        assert result == {"foods": []}

    def test_exception_raises_external_service_error(self):
        from apps.chat.services.usda_client import _get

        with patch("httpx.Client") as mock_cls:
            mock_http = MagicMock()
            mock_http.__enter__ = MagicMock(return_value=mock_http)
            mock_http.__exit__ = MagicMock(return_value=False)
            mock_http.get.side_effect = RuntimeError("network error")
            mock_cls.return_value = mock_http
            with pytest.raises(ExternalServiceError, match="USDA request failed"):
                _get("/foods/search", {})


# ---------------------------------------------------------------------------
# prompt_builder — build_system_prompt + build_ingredient_prompt
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestBuildSystemPrompt:
    def test_basic_profile_no_plan_no_allergens(self):
        from apps.chat.services.prompt_builder import build_system_prompt

        profile = DietaryProfileFactory()
        result = build_system_prompt(profile, today_plan=None)
        assert "personalised nutrition assistant" in result
        assert profile.diet_pattern in result
        assert profile.goal in result

    def test_with_allergens_includes_critical_block(self):
        from apps.chat.services.prompt_builder import build_system_prompt

        profile = DietaryProfileFactory(allergies=["peanuts", "dairy"])
        result = build_system_prompt(profile, today_plan=None)
        assert "CRITICAL" in result
        assert "peanuts" in result
        assert "dairy" in result

    def test_with_dislikes_includes_dislike_line(self):
        from apps.chat.services.prompt_builder import build_system_prompt

        profile = DietaryProfileFactory(dislikes=["broccoli", "karela"])
        result = build_system_prompt(profile, today_plan=None)
        assert "broccoli" in result

    def test_with_no_onion_garlic_includes_note(self):
        from apps.chat.services.prompt_builder import build_system_prompt

        profile = DietaryProfileFactory(no_onion_garlic=True)
        result = build_system_prompt(profile, today_plan=None)
        assert "onion/garlic" in result

    def test_with_nutrition_targets(self):
        from apps.chat.services.prompt_builder import build_system_prompt

        profile = DietaryProfileFactory()
        # save() recomputes targets from biometrics — check that the computed value appears
        result = build_system_prompt(profile, today_plan=None)
        assert "kcal" in result
        assert "Protein target:" in result

    def test_with_today_plan_includes_meals(self):
        from apps.chat.services.prompt_builder import build_system_prompt

        profile = DietaryProfileFactory()
        mock_plan = MagicMock()
        mock_plan.breakfast.name = "Oats Porridge"
        mock_plan.lunch.name = "Dal Rice"
        mock_plan.dinner.name = "Roti Sabzi"
        result = build_system_prompt(profile, today_plan=mock_plan)
        assert "Today's Meal Plan" in result
        assert "Oats Porridge" in result
        assert "Dal Rice" in result

    def test_with_no_plan_excludes_meal_section(self):
        from apps.chat.services.prompt_builder import build_system_prompt

        profile = DietaryProfileFactory()
        result = build_system_prompt(profile, today_plan=None)
        assert "Today's Meal Plan" not in result


@pytest.mark.django_db
class TestBuildIngredientPrompt:
    def test_returns_system_and_user_messages(self):
        from apps.chat.services.prompt_builder import build_ingredient_prompt

        profile = DietaryProfileFactory()
        messages = build_ingredient_prompt(
            ingredients=["Rice", "Lentils"],
            profile=profile,
            available_ingredient_names=["Rice", "Lentils", "Tomato"],
            count=2,
        )
        assert len(messages) == 2
        assert messages[0]["role"] == "system"
        assert messages[1]["role"] == "user"
        assert "Rice" in messages[1]["content"]
        assert "Lentils" in messages[1]["content"]

    def test_schema_embedded_in_system_message(self):
        from apps.chat.services.prompt_builder import build_ingredient_prompt

        profile = DietaryProfileFactory()
        messages = build_ingredient_prompt(
            ingredients=["Rice"],
            profile=profile,
            available_ingredient_names=["Rice"],
            count=1,
        )
        assert "JSON Schema" in messages[0]["content"]
        assert "ingredient_name" in messages[0]["content"]
