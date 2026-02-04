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
        """Register signals."""
        from . import signals  # noqa
        from . import auth_signals  # noqa
