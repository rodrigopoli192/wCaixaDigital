"""
Auditoria app configuration.
"""

from django.apps import AppConfig


class AuditoriaConfig(AppConfig):
    """Configuration for auditoria app."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "caixa_nfse.auditoria"
    verbose_name = "Auditoria"

    def ready(self):
        """Import signals when app is ready."""
        try:
            import caixa_nfse.auditoria.signals  # noqa: F401
        except ImportError:
            pass
