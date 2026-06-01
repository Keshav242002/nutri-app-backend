import sys
from pathlib import Path

import environ

BASE_DIR = Path(__file__).resolve().parent.parent.parent

env = environ.Env(
    DJANGO_DEBUG=(bool, False),
    DJANGO_ALLOWED_HOSTS=(list, ["localhost", "127.0.0.1"]),
    CORS_ALLOWED_ORIGINS=(list, []),
    REGENERATE_RATE_LIMIT=(str, "3/d"),
    CHAT_RATE_LIMIT=(str, "30/h"),
    OPENAI_MODEL=(str, "gpt-4o"),
    LLM_TIMEOUT_SECONDS=(int, 30),
    USDA_BASE_URL=(str, "https://api.nal.usda.gov/fdc/v1"),
    AI_PROVIDER=(str, "openrouter"),
    OPENROUTER_MODEL=(str, "openrouter/free"),
    GEMINI_MODEL=(str, "gemini-2.5-flash"),
)

environ.Env.read_env(BASE_DIR / ".env")

SECRET_KEY = env("DJANGO_SECRET_KEY")
DEBUG = env("DJANGO_DEBUG")
ALLOWED_HOSTS = env("DJANGO_ALLOWED_HOSTS")

DJANGO_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.postgres",
]

THIRD_PARTY_APPS = [
    "rest_framework",
    "corsheaders",
    "django_filters",
    "drf_spectacular",
    "django_celery_beat",
]

LOCAL_APPS: list[str] = [
    "apps.accounts",
    "apps.profiles",
    "apps.recipes",
    "apps.mealplans",
    "apps.tracker",
    "apps.chat",
]

AUTH_USER_MODEL = "accounts.User"

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "nutriplan.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "nutriplan.wsgi.application"
ASGI_APPLICATION = "nutriplan.asgi.application"

DATABASES = {
    "default": env.db("DATABASE_URL"),
}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "apps.accounts.authentication.FirebaseAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_PAGINATION_CLASS": "core.pagination.StandardCursorPagination",
    "PAGE_SIZE": 20,
    "EXCEPTION_HANDLER": "core.exceptions.app_exception_handler",
}

SPECTACULAR_SETTINGS = {
    "TITLE": "NutriPlan API",
    "DESCRIPTION": "Personalized nutrition backend — meal planning, tracking, and AI chatbot.",
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
    # Resolve duplicate enum names arising from the same choices appearing on multiple models.
    "ENUM_NAME_OVERRIDES": {
        "MealTypeEnum": "apps.recipes.models.MEAL_TYPE_CHOICES",
        "EstimatedDifficultyEnum": "apps.recipes.models.DIFFICULTY_CHOICES",
        "SpiceLevelEnum": "apps.recipes.models.SPICE_LEVEL_CHOICES",
    },
}

CORS_ALLOWED_ORIGINS = env("CORS_ALLOWED_ORIGINS")
CORS_ALLOW_ALL_ORIGINS = DEBUG

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": env("REDIS_URL", default="redis://localhost:6379/0"),
    }
}

CELERY_TIMEZONE = "UTC"
CELERY_TASK_TRACK_STARTED = True
CELERY_TASK_TIME_LIMIT = 30 * 60
CELERY_BEAT_SCHEDULER = "django_celery_beat.schedulers:DatabaseScheduler"
CELERY_BROKER_URL: str = env("CELERY_BROKER_URL", default="redis://localhost:6379/1")
CELERY_RESULT_BACKEND: str = env("CELERY_RESULT_BACKEND", default="redis://localhost:6379/2")

# Firebase — populated in M1
FIREBASE_CREDENTIALS_PATH: str = env("FIREBASE_CREDENTIALS_PATH", default="")
FIREBASE_CREDENTIALS_JSON: str = env("FIREBASE_CREDENTIALS_JSON", default="")

# ── LLM Provider (M7) ─────────────────────────────────────────────────────────
# Switch providers by changing AI_PROVIDER env var only. No code changes needed.
AI_PROVIDER: str = env("AI_PROVIDER")
LLM_TIMEOUT_SECONDS: int = env("LLM_TIMEOUT_SECONDS")

# OpenRouter (default — free models available at openrouter.ai/keys)
OPENROUTER_API_KEY: str = env("OPENROUTER_API_KEY", default="")
OPENROUTER_MODEL: str = env("OPENROUTER_MODEL")

# OpenAI native (only needed if AI_PROVIDER=openai)
OPENAI_API_KEY: str = env("OPENAI_API_KEY", default="")
OPENAI_MODEL: str = env("OPENAI_MODEL")

# Gemini (used for both gemini_openai and gemini_native; key from aistudio.google.com)
GEMINI_API_KEY: str = env("GEMINI_API_KEY", default="")
GEMINI_MODEL: str = env("GEMINI_MODEL")

# USDA — populated in M7
USDA_API_KEY: str = env("USDA_API_KEY", default="")
USDA_BASE_URL: str = env("USDA_BASE_URL")

REGENERATE_RATE_LIMIT: str = env("REGENERATE_RATE_LIMIT")
CHAT_RATE_LIMIT: str = env("CHAT_RATE_LIMIT")

# ── Dev-only auth bypass (M2 manual testing) ──────────────────────────────────
# Allows requests with a known token to skip Firebase verification entirely.
# All three conditions must be true: DEBUG=True, DEV_AUTH_BYPASS_ENABLED=True,
# and the Authorization header must carry exactly DEV_AUTH_BYPASS_TOKEN.
DEV_AUTH_BYPASS_ENABLED: bool = env.bool("DEV_AUTH_BYPASS_ENABLED", default=False)
DEV_AUTH_BYPASS_TOKEN: str = env("DEV_AUTH_BYPASS_TOKEN", default="dev-bypass-token-do-not-ship")

if DEBUG and DEV_AUTH_BYPASS_ENABLED:
    sys.stderr.write(
        "\n*** WARNING: DEV_AUTH_BYPASS_ENABLED is True. "
        "This must NEVER be true in production. ***\n\n"
    )
