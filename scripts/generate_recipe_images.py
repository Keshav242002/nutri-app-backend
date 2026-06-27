#!/usr/bin/env python3
"""Generate images for all recipes in the database using Pollinations.AI (FLUX).

Pollinations is free (Seed tier). Auth is a Bearer token read from
POLLINATIONS_AI_API_KEY in the .env file. Anonymous (no key) also works but is
slower (1 req/15s) and may watermark output.

Usage:
    # one recipe (preview)
    python scripts/generate_recipe_images.py --slugs ai-dal-khichdi

    # full run
    python scripts/generate_recipe_images.py --output-dir ./recipe_images
"""

from __future__ import annotations

import argparse
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

# ── Make the repo root importable (script lives in scripts/) ─────────────────
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

# ── Load .env before anything else ───────────────────────────────────────────
from dotenv import load_dotenv  # noqa: E402

load_dotenv(REPO_ROOT / ".env")

# ── Django setup ─────────────────────────────────────────────────────────────
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "nutriplan.settings.development")

import django  # noqa: E402

django.setup()

from apps.recipes.models import Recipe  # noqa: E402

# Pollinations image endpoint. The prompt is URL-encoded into the path.
POLLINATIONS_BASE = "https://gen.pollinations.ai/image/"
DEFAULT_MODEL = "flux"  # only genuinely-free model on the Seed tier (gptimage costs pollen)
DEFAULT_QUALITY = "hd"  # only honored/charged by gptimage* models; ignored by flux
IMAGE_W = 1024
IMAGE_H = 1024
REQUEST_TIMEOUT = 180  # gptimage takes ~20s
MAX_RETRIES = 4  # for 429 (rate limit) and 5xx


def build_prompt(recipe: Recipe) -> str:
    """Build a food-photography prompt from a Recipe instance."""
    diet_info = ""
    if recipe.diet_tags:
        diet_info = f" ({', '.join(recipe.diet_tags)})"

    cuisine_display = recipe.get_cuisine_display()
    meal_display = recipe.get_meal_type_display()

    return (
        f"Professional food photography of {recipe.name}, "
        f"a {cuisine_display} {meal_display} dish{diet_info}. "
        f"Beautifully plated on a rustic ceramic plate, "
        f"natural warm lighting, shallow depth of field, "
        f"top-down overhead angle, garnished authentically, "
        f"vibrant colors, appetizing, high resolution, "
        f"clean background with subtle texture."
    )


def build_url(recipe: Recipe, model: str, quality: str) -> str:
    """Build the Pollinations image URL for a recipe."""
    prompt = urllib.parse.quote(build_prompt(recipe), safe="")
    params = {
        "model": model,
        "width": IMAGE_W,
        "height": IMAGE_H,
        "nologo": "true",
        "seed": recipe.id,  # stable seed → reproducible (honored by flux/seedream; ignored by gptimage)
    }
    if model.startswith("gptimage") or model == "gpt-image-2":
        params["quality"] = quality
    return f"{POLLINATIONS_BASE}{prompt}?{urllib.parse.urlencode(params)}"


def generate_image(
    recipe: Recipe,
    output_dir: Path,
    api_key: str | None,
    model: str = DEFAULT_MODEL,
    quality: str = DEFAULT_QUALITY,
) -> Path | None:
    """Generate an image for a single recipe and save it. Returns path or None on failure."""
    slug = recipe.slug
    output_path = output_dir / f"{slug}.jpg"

    if output_path.exists():
        print(f"  ⏩  Skipping {slug} (already exists)")
        return output_path

    url = build_url(recipe, model, quality)
    headers = {"User-Agent": "nutriplan-recipe-imager/1.0"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    for attempt in range(1, MAX_RETRIES + 1):
        req = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
                content_type = resp.headers.get("Content-Type", "")
                data = resp.read()
            if not content_type.startswith("image/"):
                print(f"  ⚠️  {slug} — non-image response ({content_type}): {data[:200]!r}")
                return None
            output_path.write_bytes(data)
            print(f"  ✅  {slug} → {output_path} ({len(data) // 1024} KB)")
            return output_path
        except urllib.error.HTTPError as e:
            body = e.read()[:300]
            # 429 = rate limited, 5xx = transient server error → back off and retry
            if e.code == 429 or 500 <= e.code < 600:
                backoff = min(60, 5 * 2 ** (attempt - 1))
                print(f"  ⏳  {slug} — HTTP {e.code} (attempt {attempt}/{MAX_RETRIES}), retry in {backoff}s")
                time.sleep(backoff)
                continue
            print(f"  ❌  {slug} — HTTP {e.code}: {body!r}")
            return None
        except Exception as e:  # noqa: BLE001
            backoff = min(60, 5 * 2 ** (attempt - 1))
            print(f"  ⏳  {slug} — error: {e} (attempt {attempt}/{MAX_RETRIES}), retry in {backoff}s")
            time.sleep(backoff)
            continue
    print(f"  ❌  {slug} — gave up after {MAX_RETRIES} attempts")
    return None


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate recipe images via Pollinations.AI")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("./recipe_images"),
        help="Directory to save generated images (default: ./recipe_images)",
    )
    parser.add_argument(
        "--model",
        default=DEFAULT_MODEL,
        help=f"Pollinations model (default: {DEFAULT_MODEL}; free on Seed tier: gptimage, flux)",
    )
    parser.add_argument(
        "--quality",
        default=DEFAULT_QUALITY,
        choices=["low", "medium", "high", "hd"],
        help=f"Quality for gptimage models only (default: {DEFAULT_QUALITY})",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=3.0,
        help="Seconds to wait between API calls (default: 3.0; gptimage gen time already exceeds the 5s window)",
    )
    parser.add_argument(
        "--slugs",
        nargs="*",
        help="Only generate images for these specific recipe slugs",
    )
    args = parser.parse_args()

    # ── API key (optional — anonymous works but is slower/watermarked) ────────
    api_key = os.environ.get("POLLINATIONS_AI_API_KEY") or None
    if api_key:
        print("🔑  Using POLLINATIONS_AI_API_KEY (Bearer auth)")
    else:
        print("⚠️   No POLLINATIONS_AI_API_KEY found — falling back to anonymous access")

    # ── Set up output directory ──────────────────────────────────────────────
    output_dir: Path = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    print(f"📁  Output directory: {output_dir.resolve()}")

    # ── Fetch recipes ────────────────────────────────────────────────────────
    qs = Recipe.objects.filter(is_active=True).order_by("slug")
    if args.slugs:
        qs = qs.filter(slug__in=args.slugs)

    recipes = list(qs)
    total = len(recipes)
    print(f"🍽️   Found {total} recipes to process")
    print(f"🤖  Model: {args.model}\n")

    if total == 0:
        print("Nothing to do.")
        return

    success_count = 0
    skip_count = 0
    fail_count = 0

    for i, recipe in enumerate(recipes, start=1):
        print(f"[{i}/{total}] {recipe.name}")

        output_path = output_dir / f"{recipe.slug}.jpg"
        already_exists = output_path.exists()

        result = generate_image(
            recipe, output_dir, api_key, model=args.model, quality=args.quality
        )

        if result and already_exists:
            skip_count += 1
        elif result:
            success_count += 1
        else:
            fail_count += 1

        if i < total:
            time.sleep(args.delay)

    print(f"\n{'=' * 50}")
    print("📊  Done!")
    print(f"    ✅  Generated: {success_count}")
    print(f"    ⏩  Skipped:   {skip_count}")
    print(f"    ❌  Failed:    {fail_count}")
    print(f"    📁  Output:    {output_dir.resolve()}")
    print(f"{'=' * 50}")


if __name__ == "__main__":
    main()
