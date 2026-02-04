"""
Caixa app configuration.
"""

from django.apps import AppConfig


class CaixaConfig(AppConfig):
    """Configuration for caixa app."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "caixa_nfse.caixa"
    verbose_name = "Caixa"

    def ready(self):
        """Import signals when app is ready."""
        try:
            import caixa_nfse.caixa.signals  # noqa: F401
        except ImportError:
            pass
