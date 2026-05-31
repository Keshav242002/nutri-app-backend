"""
USDA FoodData Central API client with Redis caching.

All responses cached in Redis for 30 days (USDA data is effectively static).
Prioritises foundationFoods, falls back to srLegacy.
"""

from __future__ import annotations

import hashlib
import json
import logging
from typing import Any

from django.conf import settings
from django.core.cache import cache

from core.error_codes import USDA_FAILURE
from core.exceptions import ExternalServiceError

logger = logging.getLogger(__name__)

_CACHE_TTL = 60 * 60 * 24 * 30  # 30 days in seconds
_PAGE_SIZE = 5
_PREFERRED_DATA_TYPES = ["Foundation", "SR Legacy"]


def _cache_key(prefix: str, value: str) -> str:
    digest = hashlib.md5(value.encode(), usedforsecurity=False).hexdigest()
    return f"usda:{prefix}:{digest}"


def _get(url: str, params: dict[str, Any]) -> dict[str, Any]:
    """Make a GET request to USDA. Raises ExternalServiceError on failure."""
    import httpx

    api_key = getattr(settings, "USDA_API_KEY", "")
    base_url = getattr(settings, "USDA_BASE_URL", "https://api.nal.usda.gov/fdc/v1")

    try:
        with httpx.Client(timeout=15) as client:
            response = client.get(
                f"{base_url}{url}",
                params={**params, "api_key": api_key},
            )
            response.raise_for_status()
            result: dict[str, Any] = response.json()
            return result
    except Exception as exc:  # noqa: BLE001
        logger.error(
            "usda_request_failure",
            extra={"event": "usda_request_failure", "url": url, "error": str(exc)},
        )
        raise ExternalServiceError(
            code=USDA_FAILURE, message=f"USDA request failed: {exc}"
        ) from exc


def search_food(query: str) -> list[dict[str, Any]]:
    """Search USDA for foods matching query. Returns up to 5 results. Cached 30 days."""
    key = _cache_key("search", query)
    cached = cache.get(key)
    if cached is not None:
        return cached  # type: ignore[no-any-return]

    data = _get("/foods/search", {"query": query, "pageSize": _PAGE_SIZE})
    foods: list[dict[str, Any]] = data.get("foods", [])
    cache.set(key, foods, _CACHE_TTL)
    return foods


def get_food_nutrients(fdc_id: int) -> dict[str, Any]:
    """Fetch nutrient details for a USDA FDC ID. Cached 30 days."""
    key = _cache_key("food", str(fdc_id))
    cached = cache.get(key)
    if cached is not None:
        return cached  # type: ignore[no-any-return]

    data = _get(f"/food/{fdc_id}", {})
    cache.set(key, data, _CACHE_TTL)
    return data


def macros_per_100g(query: str) -> dict[str, float] | None:
    """Search → pick best match → extract macros per 100g. Returns None if no match."""
    foods = search_food(query)
    if not foods:
        return None

    # Prefer foundationFoods / srLegacy; fall back to first result.
    best = next(
        (f for f in foods if f.get("dataType") in _PREFERRED_DATA_TYPES),
        foods[0],
    )

    fdc_id = best.get("fdcId")
    if not fdc_id:
        return None

    detail = get_food_nutrients(fdc_id)
    nutrients = detail.get("foodNutrients", [])

    # USDA nutrient IDs: 1003=Protein, 1005=Carbs, 1004=Fat, 1008=Energy(kcal)
    id_map = {1003: "protein_g", 1005: "carbs_g", 1004: "fat_g", 1008: "calories"}
    result: dict[str, float] = {}
    for n in nutrients:
        nid = n.get("nutrient", {}).get("id") or n.get("nutrientId")
        amount = n.get("amount") or n.get("value")
        if nid in id_map and amount is not None:
            result[id_map[nid]] = float(amount)

    return result if result else None


def _serialize_for_cache(obj: Any) -> str:
    return json.dumps(obj)
