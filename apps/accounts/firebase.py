import json

import firebase_admin
from django.conf import settings
from firebase_admin import credentials


def init_firebase() -> None:
    """Initialize Firebase Admin SDK once at startup. Safe to call multiple times."""
    if firebase_admin._apps:
        return
    if settings.FIREBASE_CREDENTIALS_JSON:
        cred = credentials.Certificate(json.loads(settings.FIREBASE_CREDENTIALS_JSON))
    else:
        cred = credentials.Certificate(settings.FIREBASE_CREDENTIALS_PATH)
    firebase_admin.initialize_app(cred)
