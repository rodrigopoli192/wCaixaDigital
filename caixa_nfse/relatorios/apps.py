"""
Relatorios app configuration.
"""

from django.apps import AppConfig


class RelatoriosConfig(AppConfig):
    """Configuration for the relatorios app."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "caixa_nfse.relatorios"
    verbose_name = "Relatórios"
