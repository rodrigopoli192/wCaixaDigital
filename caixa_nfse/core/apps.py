"""
Core app configuration.
"""

from django.apps import AppConfig


class CoreConfig(AppConfig):
    """Configuration for core app."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "caixa_nfse.core"
    verbose_name = "Core"

    def ready(self):
        """Import signals when app is ready."""
        try:
            import caixa_nfse.core.signals  # noqa: F401
        except ImportError:
            pass
