from typing import Any


def get_logging_config(*, debug: bool) -> dict[str, Any]:
    """Return the LOGGING dict for Django settings."""
    level = "DEBUG" if debug else "WARNING"

    if debug:
        formatter = "console"
        formatters: dict[str, Any] = {
            "console": {
                "format": "[%(asctime)s] %(levelname)s %(name)s %(message)s",
            }
        }
    else:
        formatter = "json"
        formatters = {
            "json": {
                "()": "pythonjsonlogger.jsonlogger.JsonFormatter",
                "fmt": "%(asctime)s %(levelname)s %(name)s %(message)s",
            }
        }

    return {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": formatters,
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "formatter": formatter,
            }
        },
        "root": {
            "handlers": ["console"],
            "level": level,
        },
        "loggers": {
            "django": {"handlers": ["console"], "level": level, "propagate": False},
            "nutriplan": {"handlers": ["console"], "level": "DEBUG", "propagate": False},
            "nutriplan.audit": {"handlers": ["console"], "level": "INFO", "propagate": False},
            "apps": {"handlers": ["console"], "level": "DEBUG", "propagate": False},
            "core": {"handlers": ["console"], "level": "DEBUG", "propagate": False},
        },
    }
