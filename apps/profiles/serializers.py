"""
DietaryProfile serializer.

Key design decisions:
  - disclaimer_acknowledged: write_only=True, validated to be True, NOT a model field.
    The service pops it before assigning to the profile.
  - age: SerializerMethodField — derived from date_of_birth at read time.
    Age is NEVER stored; stored age creates year-staleness bugs.
  - target_* fields: read_only=True (silently ignored on write per DRF default).
  - daily/weekly_food_budget_inr: required=False because budget derivation
    happens in the service layer (at least one must be present, checked there).
"""

from typing import Any

from rest_framework import serializers

from apps.profiles.models import DietaryProfile
from core.utils.nutrition_math import compute_age


class DietaryProfileSerializer(serializers.ModelSerializer[DietaryProfile]):

    # Write-only disclaimer — validated here, popped in the service before save
    disclaimer_acknowledged = serializers.BooleanField(write_only=True)

    # Read-only derived field — never stored
    age = serializers.SerializerMethodField()

    class Meta:
        model = DietaryProfile
        fields = [
            # Step 1
            "date_of_birth",
            "sex",
            "height_cm",
            "weight_kg",
            # Step 2
            "activity_level",
            "goal",
            # Step 3
            "primary_cuisine_region",
            "secondary_cuisine_preferences",
            "spice_tolerance",
            # Step 4
            "diet_pattern",
            "no_onion_garlic",
            "allergies",
            "dislikes",
            # Step 5
            "daily_food_budget_inr",
            "weekly_food_budget_inr",
            "household_size",
            "cooking_frequency",
            # Step 6
            "max_prep_time_min",
            "skill_level",
            "disclaimer_acknowledged",
            # Computed (read-only)
            "target_calories",
            "target_protein_g",
            "target_carbs_g",
            "target_fat_g",
            "target_fiber_g",
            # Derived read-only
            "age",
            # Timestamps
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "target_calories",
            "target_protein_g",
            "target_carbs_g",
            "target_fat_g",
            "target_fiber_g",
            "created_at",
            "updated_at",
        ]
        extra_kwargs = {
            "daily_food_budget_inr": {"required": False},
            "weekly_food_budget_inr": {"required": False},
            "secondary_cuisine_preferences": {"required": False, "default": list},
            "allergies": {"required": False, "default": list},
            "dislikes": {"required": False, "default": list},
            "no_onion_garlic": {"required": False},
        }

    def get_age(self, obj: DietaryProfile) -> int:
        return compute_age(obj.date_of_birth)

    def validate_date_of_birth(self, value: object) -> object:
        import datetime

        if not isinstance(value, datetime.date):
            return value
        age = compute_age(value)
        if age < 13:
            raise serializers.ValidationError("Minimum age is 13 years. Date of birth too recent.")
        if age > 100:
            raise serializers.ValidationError("Maximum age is 100 years. Date of birth too old.")
        return value

    def validate_disclaimer_acknowledged(self, value: bool) -> bool:
        if value is not True:
            raise serializers.ValidationError(
                "Disclaimer must be acknowledged (set to true) to submit a profile."
            )
        return value


class ProfileUpdateSerializer(DietaryProfileSerializer):
    """Serializer for PATCH /profiles/me. Excludes disclaimer_acknowledged."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.fields.pop("disclaimer_acknowledged", None)
