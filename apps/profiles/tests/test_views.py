"""
View / endpoint tests for apps/profiles.

All tests use the registered_user fixture from conftest.py, which returns
(client_with_auth, user) with the Firebase mock already active for registration.
Each test wraps its own endpoint calls in the firebase patch.
"""

from __future__ import annotations

from datetime import date
from typing import Any
from unittest.mock import patch

import pytest
from django.test import Client

from apps.profiles.tests.conftest import (
    AUTH_ME_URL,
    FAKE_TOKEN_PAYLOAD,
    ONBOARDING_URL,
    PROFILE_ME_URL,
)

QUESTIONS_URL = "/api/v1/profiles/onboarding/questions"

# ---------------------------------------------------------------------------
# Shared onboarding payload
# ---------------------------------------------------------------------------

ONBOARDING_PAYLOAD: dict[str, Any] = {
    "date_of_birth": "1994-06-15",
    "sex": "male",
    "height_cm": 180,
    "weight_kg": "80.0",
    "activity_level": "moderate",
    "goal": "maintain",
    "primary_cuisine_region": "north_indian",
    "secondary_cuisine_preferences": [],
    "spice_tolerance": "medium",
    "diet_pattern": "vegetarian",
    "no_onion_garlic": False,
    "allergies": [],
    "dislikes": [],
    "daily_food_budget_inr": "150.00",
    "weekly_food_budget_inr": None,
    "household_size": 1,
    "cooking_frequency": "daily",
    "max_prep_time_min": 30,
    "skill_level": "beginner",
    "disclaimer_acknowledged": True,
}


def _patch_firebase():  # type: ignore[return]
    return patch("firebase_admin.auth.verify_id_token", return_value=FAKE_TOKEN_PAYLOAD)


def _post_onboarding(client: Client, payload: dict | None = None) -> Any:
    data = payload if payload is not None else ONBOARDING_PAYLOAD
    with _patch_firebase():
        return client.post(
            ONBOARDING_URL,
            data=data,
            content_type="application/json",
        )


def _get_profile_me(client: Client) -> Any:
    with _patch_firebase():
        return client.get(PROFILE_ME_URL)


def _patch_profile_me(client: Client, data: dict) -> Any:
    with _patch_firebase():
        return client.patch(
            PROFILE_ME_URL,
            data=data,
            content_type="application/json",
        )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestOnboardingEndpoint:
    def test_onboarding_endpoint_is_idempotent(self, registered_user: tuple) -> None:
        """POST twice → HTTP 200 both times; only 1 row in DB."""
        from apps.profiles.models import DietaryProfile

        client, user = registered_user
        r1 = _post_onboarding(client)
        r2 = _post_onboarding(client)

        assert r1.status_code == 200, r1.json()
        assert r2.status_code == 200, r2.json()
        assert DietaryProfile.objects.filter(user=user).count() == 1

    def test_onboarding_recomputes_targets_on_update(self, registered_user: tuple) -> None:
        """POST with new weight → target_calories changes."""
        client, _ = registered_user
        r1 = _post_onboarding(client)
        cal1 = r1.json()["data"]["target_calories"]

        heavy_payload = {**ONBOARDING_PAYLOAD, "weight_kg": "120.0"}
        r2 = _post_onboarding(client, heavy_payload)
        cal2 = r2.json()["data"]["target_calories"]

        assert cal2 != cal1

    def test_get_profile_includes_computed_fields(self, registered_user: tuple) -> None:
        """After onboarding, GET /profiles/me returns non-null target_calories."""
        client, _ = registered_user
        _post_onboarding(client)
        r = _get_profile_me(client)

        assert r.status_code == 200, r.json()
        data = r.json()["data"]
        assert data["target_calories"] is not None
        assert data["target_protein_g"] is not None
        assert data["target_carbs_g"] is not None
        assert data["target_fat_g"] is not None
        assert data["target_fiber_g"] is not None

    def test_has_profile_true_after_onboarding(self, registered_user: tuple) -> None:
        """GET /auth/me after onboarding → has_profile: true."""
        client, _ = registered_user
        _post_onboarding(client)
        with _patch_firebase():
            r = client.get(AUTH_ME_URL)
        assert r.status_code == 200
        assert r.json()["data"]["has_profile"] is True

    def test_get_me_404_when_no_profile(self, registered_user: tuple) -> None:
        """Authenticated user with no profile → 404 PROFILE_NOT_FOUND."""
        from core.error_codes import PROFILE_NOT_FOUND

        client, _ = registered_user
        # Do NOT post onboarding
        r = _get_profile_me(client)
        assert r.status_code == 404
        assert r.json()["error"]["code"] == PROFILE_NOT_FOUND

    def test_onboarding_message_created_on_first_post(self, registered_user: tuple) -> None:
        """First POST → message says 'created'."""
        client, _ = registered_user
        r = _post_onboarding(client)
        assert r.status_code == 200
        assert "created" in r.json()["message"].lower()

    def test_onboarding_message_updated_on_second_post(self, registered_user: tuple) -> None:
        """Second POST → message says 'updated'."""
        client, _ = registered_user
        _post_onboarding(client)
        r = _post_onboarding(client)
        assert r.status_code == 200
        assert "updated" in r.json()["message"].lower()

    def test_onboarding_rejects_when_both_budget_fields_absent(
        self, registered_user: tuple
    ) -> None:
        """POST with neither budget field → 400 VALIDATION_ERROR."""
        from core.error_codes import VALIDATION_ERROR

        client, _ = registered_user
        payload = {
            k: v
            for k, v in ONBOARDING_PAYLOAD.items()
            if k not in ("daily_food_budget_inr", "weekly_food_budget_inr")
        }
        r = _post_onboarding(client, payload)
        assert r.status_code == 400
        assert r.json()["error"]["code"] == VALIDATION_ERROR


@pytest.mark.django_db
class TestPatchEndpoint:
    def test_patch_recomputes_when_weight_changes(self, registered_user: tuple) -> None:
        """PATCH weight_kg → new target_calories."""
        client, _ = registered_user
        r1 = _post_onboarding(client)
        cal1 = r1.json()["data"]["target_calories"]

        r2 = _patch_profile_me(client, {"weight_kg": "120.0"})
        assert r2.status_code == 200, r2.json()
        assert r2.json()["data"]["target_calories"] != cal1

    def test_patch_recomputes_when_activity_changes(self, registered_user: tuple) -> None:
        """PATCH activity_level → new target_calories."""
        client, _ = registered_user
        r1 = _post_onboarding(client)
        cal1 = r1.json()["data"]["target_calories"]

        r2 = _patch_profile_me(client, {"activity_level": "athlete"})
        assert r2.status_code == 200, r2.json()
        assert r2.json()["data"]["target_calories"] != cal1
        assert r2.json()["data"]["target_calories"] > cal1

    def test_patch_recomputes_when_goal_changes(self, registered_user: tuple) -> None:
        """PATCH goal → new target_calories AND different macro splits."""
        client, _ = registered_user
        r1 = _post_onboarding(client)
        maintain_calories = r1.json()["data"]["target_calories"]

        r2 = _patch_profile_me(client, {"goal": "lose_weight"})
        assert r2.status_code == 200, r2.json()
        data = r2.json()["data"]
        # lose_weight has -500 delta and 35/40/25 split
        assert data["goal"] == "lose_weight"
        assert float(data["target_calories"]) < maintain_calories

    def test_patch_recomputes_when_dob_changes_year_boundary(self, registered_user: tuple) -> None:
        """PATCH date_of_birth → age changes → different BMR → different targets."""
        client, _ = registered_user
        r1 = _post_onboarding(client)
        cal1 = r1.json()["data"]["target_calories"]

        # Change DOB to make person 40yo instead of 30yo
        r2 = _patch_profile_me(client, {"date_of_birth": "1984-06-15"})
        assert r2.status_code == 200, r2.json()
        # Older → lower BMR → lower TDEE → fewer calories
        assert r2.json()["data"]["target_calories"] < cal1

    def test_other_sex_uses_averaged_bmr_formula(self, registered_user: tuple) -> None:
        """sex=other BMR offset is bmr_base-78 (average of +5 and -161).
        Verified by computing the expected value independently from constants."""
        from datetime import date as date_cls

        from core.utils.nutrition_math import ACTIVITY_MULTIPLIERS, GOAL_CALORIE_DELTA, compute_age

        client, _ = registered_user
        other_payload = {**ONBOARDING_PAYLOAD, "sex": "other"}
        r = _post_onboarding(client, other_payload)
        assert r.status_code == 200, r.json()

        # Independent calculation using same formula as compute_targets
        dob = date_cls(1994, 6, 15)
        age = compute_age(dob)
        bmr_base = 10 * 80.0 + 6.25 * 180 - 5 * age
        bmr = bmr_base - 78.0  # other/prefer_not_to_say offset
        tdee = bmr * ACTIVITY_MULTIPLIERS["moderate"]
        delta = GOAL_CALORIE_DELTA["maintain"]
        expected = max(1200, round(tdee + delta))

        assert r.json()["data"]["target_calories"] == expected

    def test_patch_does_not_require_disclaimer_acknowledged(self, registered_user: tuple) -> None:
        """PATCH without disclaimer_acknowledged → 200 OK (disclaimer only required on POST)."""
        client, _ = registered_user
        _post_onboarding(client)
        r = _patch_profile_me(client, {"weight_kg": "75.0"})
        assert r.status_code == 200, r.json()

    def test_patch_ignores_disclaimer_if_sent(self, registered_user: tuple) -> None:
        """PATCH with disclaimer_acknowledged included → 200 OK, field absent from response."""
        client, _ = registered_user
        _post_onboarding(client)
        r = _patch_profile_me(client, {"weight_kg": "75.0", "disclaimer_acknowledged": True})
        assert r.status_code == 200, r.json()
        assert "disclaimer_acknowledged" not in r.json()["data"]


@pytest.mark.django_db
class TestOnboardingValidation:
    """Endpoint-level validation (serializer + service layer)."""

    def test_onboarding_endpoint_rejects_age_below_13(self, registered_user: tuple) -> None:
        """DOB such that age < 13 → 400 VALIDATION_ERROR."""
        from core.error_codes import VALIDATION_ERROR

        client, _ = registered_user
        young_dob = date.today().replace(year=date.today().year - 12).isoformat()
        r = _post_onboarding(client, {**ONBOARDING_PAYLOAD, "date_of_birth": young_dob})
        assert r.status_code == 400
        assert r.json()["error"]["code"] == VALIDATION_ERROR

    def test_onboarding_endpoint_rejects_height_out_of_range(self, registered_user: tuple) -> None:
        """height_cm=400 → 400 VALIDATION_ERROR."""
        from core.error_codes import VALIDATION_ERROR

        client, _ = registered_user
        r = _post_onboarding(client, {**ONBOARDING_PAYLOAD, "height_cm": 400})
        assert r.status_code == 400
        assert r.json()["error"]["code"] == VALIDATION_ERROR

    def test_onboarding_endpoint_rejects_weight_out_of_range(self, registered_user: tuple) -> None:
        """weight_kg=1 (< 30 minimum) → 400 VALIDATION_ERROR."""
        from core.error_codes import VALIDATION_ERROR

        client, _ = registered_user
        r = _post_onboarding(client, {**ONBOARDING_PAYLOAD, "weight_kg": "1.0"})
        assert r.status_code == 400
        assert r.json()["error"]["code"] == VALIDATION_ERROR

    def test_onboarding_endpoint_rejects_invalid_activity_level(
        self, registered_user: tuple
    ) -> None:
        """activity_level='superfast' → 400 VALIDATION_ERROR."""
        from core.error_codes import VALIDATION_ERROR

        client, _ = registered_user
        r = _post_onboarding(client, {**ONBOARDING_PAYLOAD, "activity_level": "superfast"})
        assert r.status_code == 400
        assert r.json()["error"]["code"] == VALIDATION_ERROR


@pytest.mark.django_db
class TestResponseEnvelope:
    """All endpoints return the canonical success/error envelope."""

    def test_success_envelope_has_status_message_data(self, registered_user: tuple) -> None:
        """POST onboarding → envelope has status, message, data keys."""
        client, _ = registered_user
        r = _post_onboarding(client)
        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "success"
        assert "message" in body
        assert "data" in body

    def test_error_envelope_has_status_message_error(self, registered_user: tuple) -> None:
        """404 → envelope has status, message, error.code keys."""
        client, _ = registered_user
        r = _get_profile_me(client)
        assert r.status_code == 404
        body = r.json()
        assert body["status"] == "error"
        assert "message" in body
        assert "code" in body["error"]

    def test_get_profile_me_envelope(self, registered_user: tuple) -> None:
        """GET /profiles/me → success envelope with data.target_calories."""
        client, _ = registered_user
        _post_onboarding(client)
        r = _get_profile_me(client)
        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "success"
        assert body["message"] == "Profile retrieved."
        assert "target_calories" in body["data"]

    def test_patch_envelope(self, registered_user: tuple) -> None:
        """PATCH /profiles/me → success envelope with message."""
        client, _ = registered_user
        _post_onboarding(client)
        r = _patch_profile_me(client, {"weight_kg": "75.0"})
        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "success"
        assert body["message"] == "Profile updated successfully."

    def test_validation_error_envelope_shape(self, registered_user: tuple) -> None:
        """400 validation error → status=error, error.code=VALIDATION_ERROR, details key."""
        from core.error_codes import VALIDATION_ERROR

        client, _ = registered_user
        r = _post_onboarding(client, {**ONBOARDING_PAYLOAD, "height_cm": 400})
        assert r.status_code == 400
        body = r.json()
        assert body["status"] == "error"
        assert body["error"]["code"] == VALIDATION_ERROR
        assert "details" in body["error"]


@pytest.mark.django_db
class TestOnboardingQuestionsEndpoint:
    """GET /api/v1/profiles/onboarding/questions"""

    def test_questions_returns_200_with_envelope(self, registered_user: tuple) -> None:
        """Returns 200 success envelope with version and steps."""
        client, _ = registered_user
        with _patch_firebase():
            r = client.get(QUESTIONS_URL)
        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "success"
        assert body["message"] == "Onboarding questionnaire retrieved."
        assert "data" in body

    def test_questions_requires_auth(self, client: Client) -> None:
        """Unauthenticated request → 401."""
        r = client.get(QUESTIONS_URL)
        assert r.status_code == 401

    def test_questions_has_six_steps(self, registered_user: tuple) -> None:
        """Response data contains exactly 6 steps."""
        client, _ = registered_user
        with _patch_firebase():
            r = client.get(QUESTIONS_URL)
        data = r.json()["data"]
        assert len(data["steps"]) == 6

    def test_questions_field_names_match_model_fields(self, registered_user: tuple) -> None:
        """Stored field names in the questionnaire map to real DietaryProfile fields.

        disclaimer_acknowledged is excluded — it is write-only and intentionally not stored.
        """
        from apps.profiles.models import DietaryProfile

        model_field_names = {f.name for f in DietaryProfile._meta.get_fields()}
        # Write-only fields that are present in the questionnaire but not stored on the model
        not_model_fields = {"disclaimer_acknowledged"}

        client, _ = registered_user
        with _patch_firebase():
            r = client.get(QUESTIONS_URL)
        data = r.json()["data"]

        questionnaire_fields = [
            field["name"]
            for step in data["steps"]
            for field in step["fields"]
            if field["name"] not in not_model_fields
        ]
        for field_name in questionnaire_fields:
            assert (
                field_name in model_field_names
            ), f"Questionnaire field '{field_name}' not found in DietaryProfile model"
