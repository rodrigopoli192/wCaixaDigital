"""
Django settings for local development.
"""

from decouple import config

from .base import *  # noqa: F401, F403

DEBUG = True

ALLOWED_HOSTS = ["localhost", "127.0.0.1", "0.0.0.0"]

# Debug Toolbar
# INSTALLED_APPS += ["debug_toolbar", "django_extensions"]  # noqa: F405
# MIDDLEWARE.insert(0, "debug_toolbar.middleware.DebugToolbarMiddleware")  # noqa: F405

INTERNAL_IPS = ["127.0.0.1"]

# Email - Console backend for development
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

# Disable caching in development (no Redis required)
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.dummy.DummyCache",
    }
}

# Simplified logging for development
LOGGING["handlers"]["console"]["level"] = "DEBUG"  # noqa: F405
LOGGING["loggers"]["caixa_nfse"]["level"] = "DEBUG"  # noqa: F405

# Fix: Use FileHandler instead of RotatingFileHandler on Windows to avoid PermissionError
LOGGING["handlers"]["file"] = {
    "class": "logging.FileHandler",
    "filename": BASE_DIR / "logs" / "django_local.log",  # noqa: F405
    "formatter": "verbose",
}

# Use SQLite for quick testing without PostgreSQL
# To use PostgreSQL, set USE_POSTGRES=True in .env
USE_POSTGRES = config("USE_POSTGRES", default=False, cast=bool)

if not USE_POSTGRES:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",  # noqa: F405
        }
    }

# Disable Celery for local dev (tasks run synchronously)
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True

# Disable security features for local development
SECURE_SSL_REDIRECT = False
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False
