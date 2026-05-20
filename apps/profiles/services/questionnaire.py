"""
Static questionnaire metadata for the 6-step onboarding flow.

Field names map 1:1 to DietaryProfile model fields — no question_id indirection.
"""

from typing import Any

QUESTIONNAIRE_V1: dict[str, Any] = {
    "version": "1.0.0",
    "steps": [
        {
            "step": 1,
            "title": "Basic Information",
            "fields": [
                {
                    "name": "date_of_birth",
                    "label": "Date of Birth",
                    "type": "date",
                    "required": True,
                    "constraints": {"min_age": 13, "max_age": 100},
                },
                {
                    "name": "sex",
                    "label": "Sex",
                    "type": "single_select",
                    "required": True,
                    "options": [
                        {"value": "male", "label": "Male"},
                        {"value": "female", "label": "Female"},
                        {"value": "other", "label": "Other"},
                        {"value": "prefer_not_to_say", "label": "Prefer not to say"},
                    ],
                },
                {
                    "name": "height_cm",
                    "label": "Height (cm)",
                    "type": "number",
                    "required": True,
                    "constraints": {"min": 100, "max": 250},
                },
                {
                    "name": "weight_kg",
                    "label": "Weight (kg)",
                    "type": "number",
                    "required": True,
                    "constraints": {"min": 30.0, "max": 300.0},
                },
            ],
        },
        {
            "step": 2,
            "title": "Activity & Goal",
            "fields": [
                {
                    "name": "activity_level",
                    "label": "Activity Level",
                    "type": "single_select",
                    "required": True,
                    "options": [
                        {"value": "sedentary", "label": "Sedentary"},
                        {"value": "light", "label": "Light"},
                        {"value": "moderate", "label": "Moderate"},
                        {"value": "very", "label": "Very Active"},
                        {"value": "athlete", "label": "Athlete"},
                    ],
                },
                {
                    "name": "goal",
                    "label": "Goal",
                    "type": "single_select",
                    "required": True,
                    "options": [
                        {"value": "lose_weight", "label": "Lose Weight"},
                        {"value": "maintain", "label": "Maintain"},
                        {"value": "gain_muscle", "label": "Gain Muscle"},
                        {"value": "gain_weight_healthy", "label": "Gain Weight (Healthy)"},
                        {"value": "eat_healthier", "label": "Eat Healthier"},
                    ],
                },
            ],
        },
        {
            "step": 3,
            "title": "Cuisine & Region",
            "fields": [
                {
                    "name": "primary_cuisine_region",
                    "label": "Primary Cuisine Region",
                    "type": "single_select",
                    "required": True,
                    "options": [
                        {"value": "north_indian", "label": "North Indian"},
                        {"value": "south_indian", "label": "South Indian"},
                        {"value": "east_indian", "label": "East Indian"},
                        {"value": "west_indian", "label": "West Indian"},
                    ],
                },
                {
                    "name": "secondary_cuisine_preferences",
                    "label": "Secondary Cuisine Preferences",
                    "type": "multi_select",
                    "required": False,
                    "options": [
                        {"value": "punjabi", "label": "Punjabi"},
                        {"value": "gujarati", "label": "Gujarati"},
                        {"value": "maharashtrian", "label": "Maharashtrian"},
                        {"value": "bengali", "label": "Bengali"},
                        {"value": "tamil", "label": "Tamil"},
                        {"value": "kerala", "label": "Kerala"},
                        {"value": "andhra", "label": "Andhra"},
                        {"value": "rajasthani", "label": "Rajasthani"},
                        {"value": "goan", "label": "Goan"},
                        {"value": "sindhi", "label": "Sindhi"},
                        {"value": "continental", "label": "Continental"},
                        {"value": "chinese_indo", "label": "Indo-Chinese"},
                        {"value": "pan_asian", "label": "Pan Asian"},
                    ],
                },
                {
                    "name": "spice_tolerance",
                    "label": "Spice Tolerance",
                    "type": "single_select",
                    "required": True,
                    "options": [
                        {"value": "mild", "label": "Mild"},
                        {"value": "medium", "label": "Medium"},
                        {"value": "hot", "label": "Hot"},
                        {"value": "very_hot", "label": "Very Hot"},
                    ],
                },
            ],
        },
        {
            "step": 4,
            "title": "Dietary Pattern",
            "fields": [
                {
                    "name": "diet_pattern",
                    "label": "Diet Pattern",
                    "type": "single_select",
                    "required": True,
                    "options": [
                        {"value": "vegetarian", "label": "Vegetarian"},
                        {"value": "eggetarian", "label": "Eggetarian"},
                        {"value": "non_vegetarian", "label": "Non-Vegetarian"},
                        {"value": "pescatarian", "label": "Pescatarian"},
                        {"value": "vegan", "label": "Vegan"},
                        {"value": "jain", "label": "Jain"},
                    ],
                },
                {
                    "name": "no_onion_garlic",
                    "label": "No Onion / Garlic",
                    "type": "boolean",
                    "required": False,
                    "hint": "Automatically enabled for Jain diet pattern.",
                },
                {
                    "name": "allergies",
                    "label": "Allergies",
                    "type": "multi_select",
                    "required": False,
                    "options": [
                        {"value": "dairy", "label": "Dairy"},
                        {"value": "eggs", "label": "Eggs"},
                        {"value": "gluten", "label": "Gluten"},
                        {"value": "peanuts", "label": "Peanuts"},
                        {"value": "tree_nuts", "label": "Tree Nuts"},
                        {"value": "soy", "label": "Soy"},
                        {"value": "shellfish", "label": "Shellfish"},
                        {"value": "fish", "label": "Fish"},
                        {"value": "sesame", "label": "Sesame"},
                        {"value": "mustard", "label": "Mustard"},
                    ],
                },
                {
                    "name": "dislikes",
                    "label": "Food Dislikes",
                    "type": "free_text_array",
                    "required": False,
                    "constraints": {"max_items": 30},
                },
            ],
        },
        {
            "step": 5,
            "title": "Budget & Household",
            "fields": [
                {
                    "name": "daily_food_budget_inr",
                    "label": "Daily Food Budget (₹)",
                    "type": "number",
                    "required": False,
                    "constraints": {"min": 100, "max": 3000},
                    "group": "budget",
                    "group_constraint": "at_least_one_required",
                },
                {
                    "name": "weekly_food_budget_inr",
                    "label": "Weekly Food Budget (₹)",
                    "type": "number",
                    "required": False,
                    "constraints": {"min": 700, "max": 20000},
                    "group": "budget",
                    "group_constraint": "at_least_one_required",
                },
                {
                    "name": "household_size",
                    "label": "Household Size",
                    "type": "number",
                    "required": False,
                    "constraints": {"min": 1, "max": 12},
                },
                {
                    "name": "cooking_frequency",
                    "label": "Cooking Frequency",
                    "type": "single_select",
                    "required": True,
                    "options": [
                        {"value": "daily", "label": "Daily"},
                        {"value": "weekends_only", "label": "Weekends Only"},
                        {"value": "rarely", "label": "Rarely"},
                    ],
                },
            ],
        },
        {
            "step": 6,
            "title": "Cooking Constraints",
            "fields": [
                {
                    "name": "max_prep_time_min",
                    "label": "Max Prep Time (minutes)",
                    "type": "slider_range",
                    "required": False,
                    "constraints": {"min": 10, "max": 90},
                },
                {
                    "name": "skill_level",
                    "label": "Cooking Skill Level",
                    "type": "single_select",
                    "required": True,
                    "options": [
                        {"value": "beginner", "label": "Beginner"},
                        {"value": "intermediate", "label": "Intermediate"},
                        {"value": "advanced", "label": "Advanced"},
                    ],
                },
                {
                    "name": "disclaimer_acknowledged",
                    "label": (
                        "I acknowledge that this app is not a substitute for "
                        "professional medical advice."
                    ),
                    "type": "disclaimer_checkbox",
                    "required": True,
                },
            ],
        },
    ],
}
