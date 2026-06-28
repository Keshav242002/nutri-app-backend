from core.logging import get_logging_config

from .base import *  # noqa: F401, F403
from .base import env

DEBUG = False

# Hard-coded False in production — overrides any env var to prevent accidental exposure.
DEV_AUTH_BYPASS_ENABLED = False

# SSL redirect — set SECURE_SSL_REDIRECT=False in .env for IP-only deployments (no domain/TLS)
SECURE_SSL_REDIRECT = env.bool("SECURE_SSL_REDIRECT", default=True)
SECURE_HSTS_SECONDS = 31536000 if SECURE_SSL_REDIRECT else 0
SECURE_HSTS_INCLUDE_SUBDOMAINS = SECURE_SSL_REDIRECT
SECURE_HSTS_PRELOAD = SECURE_SSL_REDIRECT
SESSION_COOKIE_SECURE = SECURE_SSL_REDIRECT
CSRF_COOKIE_SECURE = SECURE_SSL_REDIRECT
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https") if SECURE_SSL_REDIRECT else None

LOGGING = get_logging_config(debug=False)

SECURE_REDIRECT_EXEMPT = [r"^healthz$"]

_sentry_dsn: str = env("SENTRY_DSN", default="")
if _sentry_dsn:
    import sentry_sdk
    from sentry_sdk.integrations.celery import CeleryIntegration
    from sentry_sdk.integrations.django import DjangoIntegration

    sentry_sdk.init(
        dsn=_sentry_dsn,
        integrations=[DjangoIntegration(), CeleryIntegration()],
        traces_sample_rate=0.1,
        send_default_pii=False,
    )
