"""
Prompt construction for the chat and ingredient-to-recipe LLM calls.

All functions return lists of OpenAI-style message dicts (role/content).
The JSON schema for structured completions is ALWAYS embedded in the prompt text
so it works identically across providers that don't support strict schema enforcement.
"""

from __future__ import annotations

import json

from apps.mealplans.models import MealPlan
from apps.profiles.models import DietaryProfile

_RECIPE_SCHEMA = {
    "type": "object",
    "required": ["recipes"],
    "properties": {
        "recipes": {
            "type": "array",
            "items": {
                "type": "object",
                "required": [
                    "name",
                    "meal_type",
                    "servings",
                    "diet_tags",
                    "allergen_tags",
                    "ingredients",
                    "steps",
                ],
                "properties": {
                    "name": {"type": "string"},
                    "meal_type": {"type": "string", "enum": ["breakfast", "lunch", "dinner"]},
                    "servings": {"type": "integer", "minimum": 1, "maximum": 12},
                    "diet_tags": {"type": "array", "items": {"type": "string"}},
                    "allergen_tags": {"type": "array", "items": {"type": "string"}},
                    "ingredients": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "required": ["ingredient_name", "quantity_grams"],
                            "properties": {
                                "ingredient_name": {"type": "string"},
                                "quantity_grams": {"type": "number", "exclusiveMinimum": 0},
                            },
                        },
                    },
                    "steps": {"type": "array", "items": {"type": "string"}},
                },
            },
        }
    },
}


def build_system_prompt(
    profile: DietaryProfile,
    today_plan: MealPlan | None,
) -> str:
    """Build the system prompt for free-chat mode.

    Embeds the user's nutrition targets, diet pattern, allergens (with explicit
    'never recommend' instruction), and today's meal plan for context.
    """
    lines: list[str] = [
        "You are a personalised nutrition assistant for NutriPlan, "
        "an Indian-first meal planning app.",
        "Always give practical, evidence-based advice tailored to the user's profile below.",
        "",
        "## User Profile",
        f"Diet pattern: {profile.diet_pattern}",
        f"Goal: {profile.goal}",
        f"Primary cuisine: {profile.primary_cuisine_region}",
        f"Spice tolerance: {profile.spice_tolerance}",
    ]

    if profile.no_onion_garlic:
        lines.append("No onion/garlic (jain or preference).")

    if profile.target_calories:
        lines.append(f"Daily calorie target: {profile.target_calories} kcal")
    if profile.target_protein_g:
        lines.append(f"Protein target: {profile.target_protein_g} g")
    if profile.target_carbs_g:
        lines.append(f"Carbs target: {profile.target_carbs_g} g")
    if profile.target_fat_g:
        lines.append(f"Fat target: {profile.target_fat_g} g")

    if profile.allergies:
        allergen_list = ", ".join(profile.allergies)
        lines.append(
            f"\n## CRITICAL — Allergens\n"
            f"NEVER recommend any food containing: {allergen_list}. "
            f"This is a hard safety rule — no exceptions."
        )

    if profile.dislikes:
        lines.append(f"Foods the user dislikes (avoid if possible): {', '.join(profile.dislikes)}")

    if today_plan is not None:
        lines.append("\n## Today's Meal Plan")
        if today_plan.breakfast:
            lines.append(f"Breakfast: {today_plan.breakfast.name}")
        if today_plan.lunch:
            lines.append(f"Lunch: {today_plan.lunch.name}")
        if today_plan.dinner:
            lines.append(f"Dinner: {today_plan.dinner.name}")

    lines += [
        "",
        "Keep responses concise and actionable. "
        "Use metric units. Prioritise Indian foods and ingredients.",
    ]

    return "\n".join(lines)


def build_ingredient_prompt(
    ingredients: list[str],
    profile: DietaryProfile,
    available_ingredient_names: list[str],
    count: int = 3,
) -> list[dict[str, str]]:
    """Build messages for ingredient-to-recipe structured completion.

    Embeds the full JSON schema in the system message so the constraint applies
    to all providers including those that don't support strict schema enforcement.
    The model is also given the full list of valid ingredient names from the DB
    so it is constrained to use existing ingredients only.
    """
    schema_str = json.dumps(_RECIPE_SCHEMA, indent=2)
    available_str = ", ".join(available_ingredient_names[:200])  # cap prompt size

    system_content = (
        f"You are a recipe generation engine for NutriPlan, an Indian-first nutrition app.\n"
        f"Generate exactly {count} recipe(s) using the ingredients the user provides.\n"
        f"\n"
        f"User profile:\n"
        f"  Diet pattern: {profile.diet_pattern}\n"
        f"  Goal: {profile.goal}\n"
        f"  Allergens (NEVER use): {', '.join(profile.allergies) or 'none'}\n"
        f"  No onion/garlic: {profile.no_onion_garlic}\n"
        f"\n"
        f"INGREDIENT NAMING RULES (CRITICAL — failure causes recipe rejection):\n"
        f"1. The user's listed ingredients are casual, everyday names "
        f"(e.g. 'rice', 'oil', 'dal', 'chicken'). For each one, map it to the closest "
        f"SPECIFIC ingredient from the approved list below. For example, if the user says "
        f"'rice', choose a specific rice such as 'Basmati rice (raw)' from the list.\n"
        f"2. You MUST use ingredient names EXACTLY as they appear in the approved list — "
        f"character for character, including any parenthetical suffix like '(raw)'. "
        f"Do not simplify, abbreviate, translate, or rephrase ingredient names. "
        f"If a dish needs an ingredient not in the list, choose a different dish.\n"
        f"3. NEVER output a generic ingredient name — always use the exact specific name "
        f"from the approved list, character for character including '(raw)'.\n"
        f"4. If the user's ingredient has multiple matches in the list, pick the most "
        f"common one for the dish you're making.\n"
        f"\n"
        f"Approved ingredient list (use ONLY these names, character for character):\n"
        f"{available_str}\n"
        f"\n"
        f"OTHER RULES:\n"
        f"5. Return ONLY valid JSON matching the schema below. "
        f"No markdown, no prose, no code fences.\n"
        f"6. quantity_grams must be between 1 and 5000.\n"
        f"7. Servings must be between 1 and 12.\n"
        f"\n"
        f"JSON Schema (return EXACTLY this shape):\n"
        f"{schema_str}"
    )

    user_content = (
        f"I have these ingredients: {', '.join(ingredients)}.\n"
        f"Please generate {count} recipe(s) I can make with them."
    )

    return [
        {"role": "system", "content": system_content},
        {"role": "user", "content": user_content},
    ]
