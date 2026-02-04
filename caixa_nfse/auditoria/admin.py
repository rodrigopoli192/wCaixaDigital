"""
Auditoria admin configuration.
"""

from django.contrib import admin
from django.utils.html import format_html

from .models import RegistroAuditoria


@admin.register(RegistroAuditoria)
class RegistroAuditoriaAdmin(admin.ModelAdmin):
    """Admin for RegistroAuditoria - read-only."""

    list_display = [
        "created_at",
        "usuario",
        "tabela",
        "registro_id",
        "acao_badge",
        "ip_address",
        "hash_curto",
    ]
    list_filter = ["acao", "tabela", "created_at"]
    search_fields = ["registro_id", "usuario__email", "tabela"]
    readonly_fields = [
        "id",
        "created_at",
        "tenant",
        "tabela",
        "registro_id",
        "acao",
        "usuario",
        "ip_address",
        "user_agent",
        "session_id",
        "dados_antes",
        "dados_depois",
        "campos_alterados",
        "justificativa",
        "hash_registro",
        "hash_anterior",
    ]
    date_hierarchy = "created_at"
    ordering = ["-created_at"]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def acao_badge(self, obj):
        colors = {
            "CREATE": "success",
            "UPDATE": "primary",
            "DELETE": "danger",
            "VIEW": "info",
            "EXPORT": "warning",
        }
        return format_html(
            '<span class="badge bg-{}">{}</span>',
            colors.get(obj.acao, "secondary"),
            obj.get_acao_display(),
        )

    acao_badge.short_description = "Ação"

    def hash_curto(self, obj):
        return obj.hash_registro[:16] + "..."

    hash_curto.short_description = "Hash"
