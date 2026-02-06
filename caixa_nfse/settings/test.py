"""
Django settings for testing.
"""

from .base import *  # noqa: F401, F403

DEBUG = False
SECRET_KEY = "test-secret-key-not-for-production"

# Use SQLite for faster tests
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}

# Remove WhiteNoise middleware and storage for tests
if "whitenoise.middleware.WhiteNoiseMiddleware" in MIDDLEWARE:
    MIDDLEWARE.remove("whitenoise.middleware.WhiteNoiseMiddleware")

STATICFILES_STORAGE = "django.contrib.staticfiles.storage.StaticFilesStorage"

# Disable caching
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.dummy.DummyCache",
    }
}

# Celery - run tasks synchronously in tests
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True

# Password hashers - faster for tests
PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.MD5PasswordHasher",
]

# Email
EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"

# Disable encryption for tests
FIELD_ENCRYPTION_KEY = "dGVzdC1lbmNyeXB0aW9uLWtleS0zMi1ieXRlcyE="  # base64 encoded test key

# Logging - disable file logging during tests to avoid lock issues
LOGGING = {
    "version": 1,
    "disable_existing_loggers": True,
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
        },
    },
    "root": {
        "handlers": ["console"],
        "level": "CRITICAL",  # Only critical errors
    },
}
