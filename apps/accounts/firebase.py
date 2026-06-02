import json

import firebase_admin
from django.conf import settings
from firebase_admin import credentials


def init_firebase() -> None:
    """Initialize Firebase Admin SDK once at startup. Safe to call multiple times."""
    if firebase_admin._apps:
        return
    if not settings.FIREBASE_CREDENTIALS_JSON and not settings.FIREBASE_CREDENTIALS_PATH:
        # No credentials configured — skip init (e.g. mypy type-check in CI).
        return
    if settings.FIREBASE_CREDENTIALS_JSON:
        cred = credentials.Certificate(json.loads(settings.FIREBASE_CREDENTIALS_JSON))
    else:
        cred = credentials.Certificate(settings.FIREBASE_CREDENTIALS_PATH)
    firebase_admin.initialize_app(cred)
