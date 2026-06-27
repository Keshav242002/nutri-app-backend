#!/usr/bin/env python3
"""Upload recipe images to Firebase Storage.

Usage:
    pip install firebase-admin
    python scripts/upload_images_to_firebase.py

Reads images from apps/recipes/seed_data/images/ and uploads them to
the Firebase Storage bucket under recipes/images/<filename>.

Requires FIREBASE_CREDENTIALS_PATH or FIREBASE_CREDENTIALS_JSON env var
(same ones the backend uses).

Idempotent: re-running overwrites existing blobs without error.
"""

import json
import os
import sys
from pathlib import Path

import firebase_admin
from firebase_admin import credentials, storage

# ── Config ───────────────────────────────────────────────────────────
IMAGE_DIR = Path(__file__).resolve().parent.parent / "apps" / "recipes" / "seed_data" / "images"
BUCKET_NAME = "nutri-app-28ff6.firebasestorage.app"
STORAGE_PREFIX = "recipes/images"


def init_firebase() -> None:
    """Initialize Firebase Admin SDK (skip if already initialized)."""
    if firebase_admin._apps:
        return

    cred_path = os.environ.get("FIREBASE_CREDENTIALS_PATH", "")
    cred_json = os.environ.get("FIREBASE_CREDENTIALS_JSON", "")

    if cred_path and Path(cred_path).exists():
        cred = credentials.Certificate(cred_path)
    elif cred_json:
        cred = credentials.Certificate(json.loads(cred_json))
    else:
        print(
            "ERROR: Set FIREBASE_CREDENTIALS_PATH or FIREBASE_CREDENTIALS_JSON",
            file=sys.stderr,
        )
        sys.exit(1)

    firebase_admin.initialize_app(cred, {"storageBucket": BUCKET_NAME})


def upload_images() -> None:
    """Upload all images from IMAGE_DIR to Firebase Storage."""
    if not IMAGE_DIR.exists():
        print(f"ERROR: Image directory not found: {IMAGE_DIR}", file=sys.stderr)
        sys.exit(1)

    image_files = sorted(IMAGE_DIR.glob("*.png"))
    if not image_files:
        print(f"No .png files found in {IMAGE_DIR}")
        return

    bucket = storage.bucket()
    print(f"Uploading {len(image_files)} images to gs://{BUCKET_NAME}/{STORAGE_PREFIX}/\n")

    uploaded = 0
    failed = 0

    for img_path in image_files:
        blob_name = f"{STORAGE_PREFIX}/{img_path.name}"
        blob = bucket.blob(blob_name)

        try:
            blob.upload_from_filename(str(img_path), content_type="image/png")
            blob.make_public()
            uploaded += 1
            print(f"  ✓ {img_path.name}")
        except Exception as exc:
            failed += 1
            print(f"  ✗ {img_path.name}: {exc}", file=sys.stderr)

    print(f"\nDone: {uploaded} uploaded, {failed} failed out of {len(image_files)} total.")

    if uploaded > 0:
        # Print sample URL for verification
        sample = image_files[0].name
        print(
            f"\nSample URL:\n"
            f"  https://firebasestorage.googleapis.com/v0/b/{BUCKET_NAME}"
            f"/o/recipes%2Fimages%2F{sample}?alt=media"
        )


if __name__ == "__main__":
    init_firebase()
    upload_images()
