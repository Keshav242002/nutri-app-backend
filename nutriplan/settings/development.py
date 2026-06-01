from core.logging import get_logging_config

from .base import *  # noqa: F401, F403

DEBUG = True

ALLOWED_HOSTS = ["*"]

CORS_ALLOW_ALL_ORIGINS = True

EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

LOGGING = get_logging_config(debug=True)

# Disable django-ratelimit in local dev/tests so Redis state doesn't bleed between test runs.
RATELIMIT_ENABLE = False
