"""
Model-level tests for DietaryProfile.

These test the model's DB behaviour (field constraints, save() hook) rather
than the math itself (which lives in test_services.py).
"""

import pytest

from apps.profiles.tests.factories import DietaryProfileFactory


@pytest.mark.django_db
class TestDietaryProfileModel:
    def test_profile_creates_with_computed_targets(self) -> None:
        """Profile created via factory has non-null computed targets after save()."""
        profile = DietaryProfileFactory()
        assert profile.target_calories is not None
        assert profile.target_calories > 0
        assert profile.target_protein_g is not None
        assert profile.target_carbs_g is not None
        assert profile.target_fat_g is not None
        assert profile.target_fiber_g is not None

    def test_profile_str_repr(self) -> None:
        profile = DietaryProfileFactory()
        result = str(profile)
        assert "DietaryProfile" in result
        assert "maintain" in result

    def test_profile_has_timestamps(self) -> None:
        profile = DietaryProfileFactory()
        assert profile.created_at is not None
        assert profile.updated_at is not None

    def test_profile_one_to_one_with_user(self) -> None:
        """user.profile reverse relation resolves correctly."""
        profile = DietaryProfileFactory()
        assert profile.user.profile == profile  # type: ignore[attr-defined]

    def test_save_recomputes_targets_on_update(self) -> None:
        """Changing weight and calling save() updates target_calories."""
        profile = DietaryProfileFactory(weight_kg="80.0", goal="maintain")
        original_calories = profile.target_calories

        profile.weight_kg = "120.0"  # type: ignore[assignment]
        profile.save()

        assert profile.target_calories != original_calories
        assert profile.target_calories is not None

    def test_timezone_field_default(self) -> None:
        """New profiles default to Asia/Kolkata timezone."""
        profile = DietaryProfileFactory()
        assert profile.timezone == "Asia/Kolkata"  # type: ignore[union-attr]

    def test_timezone_field_accepts_valid_tz(self) -> None:
        """A valid IANA timezone passes full_clean()."""
        profile = DietaryProfileFactory()
        profile.timezone = "America/New_York"  # type: ignore[union-attr]
        profile.full_clean()  # type: ignore[union-attr]

    def test_timezone_field_rejects_invalid(self) -> None:
        """An invalid timezone raises ValidationError on full_clean()."""
        from django.core.exceptions import ValidationError

        profile = DietaryProfileFactory()
        profile.timezone = "Not/A/Timezone"  # type: ignore[union-attr]
        with pytest.raises(ValidationError):
            profile.full_clean()  # type: ignore[union-attr]
